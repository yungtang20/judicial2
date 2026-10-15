import hashlib
import json

import pytest

from app.legal_provider_fixtures import (
    FixtureContractError,
    JudicialOpenDataFixtureAdapter,
    ProviderContractNotAvailable,
    SourceRemovalRequired,
    TaiwanLegalDbFixtureAdapter,
    TlrAnchorFixtureAdapter,
    psue_discovery_adapter,
    taiwan_law_mcp_discovery_adapter,
)
from app.legal_retrieval import build_deidentified_query
from app.legal_retrieval_cache import normalize_adapter_response


JID = "KSDM,100,簡,5635,20111130,1"


def query():
    return build_deidentified_query(
        ["theft_320_1_movable", "embezzlement_335_general"],
        {"prior_lawful_custody": "UNKNOWN"},
    )


def test_mcp_taiwan_legal_db_fixture_uses_documented_search_shape():
    fixture = {
        "success": True,
        "results": [{
            "jid": JID,
            "case_id": "100年度簡字第5635號",
            "court": "臺灣高雄地方法院",
            "date": "100-11-30",
            "cause": "測試 fixture",
            "summary": "此欄位不得進入標準 hit 或快取",
            "url": "https://judgment.judicial.gov.tw/FJUD/data.aspx",
        }],
    }
    result = TaiwanLegalDbFixtureAdapter(fixture).search(query())
    assert result["external_network"] is False
    assert {hit["source_id"] for hit in result["hits"]} == {"JUDG-KSDM-100-JIAN-5635"}
    serialized = json.dumps(normalize_adapter_response(query(), result), ensure_ascii=False)
    assert "此欄位不得進入" not in serialized


def test_mcp_taiwan_legal_db_fixture_rejects_invalid_jid():
    with pytest.raises(FixtureContractError, match="jid 格式錯誤"):
        TaiwanLegalDbFixtureAdapter({"success": True, "results": [{"jid": "bad"}]}).search(query())


def test_tlr_anchor_only_emits_read_allowed_citations():
    fixture = {
        "allowed_citations": ["CITE-READ"],
        "judgments": [
            {"citation_id": "CITE-READ", "jid": JID, "fulltext_available": True},
            {"citation_id": "CITE-UNREAD", "jid": JID, "fulltext_available": False},
        ],
        "unread_candidates": [
            {"citation_id": "CITE-UNREAD", "reason": "payload_budget"}
        ],
        "verification_instructions": {"rule": "cite allowed_citations only"},
    }
    result = TlrAnchorFixtureAdapter(fixture).search(query())
    assert len(result["hits"]) == 1
    assert result["hits"][0]["source_id"] == "JUDG-KSDM-100-JIAN-5635"


def test_tlr_anchor_never_promotes_unread_candidate_even_if_listed_allowed():
    fixture = {
        "allowed_citations": ["CITE-UNREAD"],
        "judgments": [
            {"citation_id": "CITE-UNREAD", "jid": JID, "fulltext_available": True}
        ],
        "unread_candidates": [
            {"citation_id": "CITE-UNREAD", "reason": "not_read"}
        ],
    }
    assert TlrAnchorFixtureAdapter(fixture).search(query())["hits"] == []


def test_judicial_jdoc_hashes_full_content_but_does_not_return_it():
    content = "本段是無個資的離線測試裁判內容。"
    fixture = {
        "JID": JID,
        "JYEAR": "100",
        "JCASE": "簡",
        "JNO": "5635",
        "JDATE": "20111130",
        "JTITLE": "離線測試",
        "ATTACHMENTS": [],
        "JFULLX": {
            "JFULLTYPE": "text",
            "JFULLCONTENT": content,
            "JFULLPDF": "",
        },
    }
    result = JudicialOpenDataFixtureAdapter(fixture, requested_jid=JID).search(query())
    hit = result["hits"][0]
    assert hit["hash_scope"] == "FULL_PUBLIC_DOCUMENT"
    assert hit["content_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert content not in json.dumps(result, ensure_ascii=False)
    normalized = normalize_adapter_response(query(), result)
    assert normalized["records"][0]["content_stored"] is False


def test_judicial_removal_response_requires_cache_purge():
    fixture = {"error": "查無資料，本裁判可能未公開或已從系統移除"}
    adapter = JudicialOpenDataFixtureAdapter(fixture, requested_jid=JID)
    with pytest.raises(SourceRemovalRequired) as exc:
        adapter.search(query())
    assert exc.value.source_locator == JID


def test_judicial_jdoc_rejects_date_that_does_not_match_jid():
    fixture = {
        "JID": JID,
        "JDATE": "20111129",
        "JFULLX": {
            "JFULLTYPE": "text",
            "JFULLCONTENT": "離線測試內容",
            "JFULLPDF": "",
        },
    }
    adapter = JudicialOpenDataFixtureAdapter(fixture, requested_jid=JID)
    with pytest.raises(FixtureContractError, match="JDATE 與 JID 不一致"):
        adapter.search(query())


@pytest.mark.parametrize(
    "adapter",
    [taiwan_law_mcp_discovery_adapter(), psue_discovery_adapter()],
)
def test_undocumented_provider_contracts_fail_closed(adapter):
    assert adapter.external_network is False
    with pytest.raises(ProviderContractNotAvailable, match="尚無足夠公開"):
        adapter.search(query())

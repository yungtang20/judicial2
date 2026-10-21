from __future__ import annotations

import io
import json

from app import ai as ai_module
from app.ai import analyze_candidates
from app.v3_contracts import canonical_sha256
from tests.helpers import BANK


OFFENSES = [{"id": item["id"], "name": item["name"]} for item in BANK["offenses"]]


def _fake_settings(monkeypatch, key="sk-test", model="test-model"):
    monkeypatch.setattr(
        ai_module, "_settings", lambda: (key, "https://mock.local/v1", model)
    )


def test_analyze_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(ai_module, "_settings", lambda: None)
    assert analyze_candidates("摘要", OFFENSES) is None


def test_long_summary_is_split_and_candidates_are_merged(monkeypatch):
    calls = []

    def fake_once(summary, offenses, max_candidates=6, facts=None):
        calls.append(summary)
        return {
            "model": "test-model",
            "candidates": [{
                "id": "fraud" if len(calls) == 1 else "theft",
                "reason": "分段命中",
                "source": "ai",
            }],
        }

    monkeypatch.setattr(ai_module, "_analyze_candidates_once", fake_once)
    result = analyze_candidates("前段。" * 2500, OFFENSES)
    assert result is not None
    assert result["chunk_count"] == 2
    assert len(calls) == 2
    assert [item["id"] for item in result["candidates"]] == ["fraud", "theft"]


def test_external_ai_requires_explicit_enable_flag(monkeypatch):
    monkeypatch.setenv("IAMHC_API_KEY", "sk-test")
    monkeypatch.delenv("ALLOW_EXTERNAL_AI", raising=False)
    assert ai_module.external_ai_enabled() is False
    assert ai_module.ai_configured() is False
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    assert ai_module.external_ai_enabled() is True


def test_analyze_parses_ai_response(monkeypatch):
    _fake_settings(monkeypatch)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            import json

            body = {
                "choices": [{
                    "message": {"content": '{"candidates":[{"id":"fraud","reason":"以詐術使人交付"},{"id":"不存在的id","reason":"應被過濾"}]}'}
                }]
            }
            import io

            return io.BytesIO(json.dumps(body).encode("utf-8")).read()

    def fake_urlopen(req, timeout):
        assert timeout == 70
        return FakeResponse()

    monkeypatch.setattr(ai_module.urlrequest, "urlopen", fake_urlopen)
    result = analyze_candidates("以假客服名義要求匯款", OFFENSES)
    assert result is not None
    assert result["model"] == "test-model"
    assert [item["id"] for item in result["candidates"]] == ["fraud"]
    assert result["candidates"][0]["source"] == "ai"


def test_analyze_falls_back_after_repeated_failure(monkeypatch):
    _fake_settings(monkeypatch)
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        raise ai_module.URLError("network down")

    monkeypatch.setattr(ai_module.urlrequest, "urlopen", fake_urlopen)
    result = analyze_candidates("摘要", OFFENSES)
    assert result is None
    assert len(calls) == ai_module.MAX_ATTEMPTS  # 重試至上限後放棄


def test_prompt_includes_catalog_and_rules():
    messages = ai_module.build_analyze_prompt("測試摘要", [{"id": "theft", "name": "竊盜"}])
    user = messages[1]["content"]
    assert "theft：竊盜" in user
    assert "不得假設" in user

def test_segment_facts_rejects_fabricated_text(monkeypatch):
    _fake_settings(monkeypatch)

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            body = {"choices": [{"message": {"content": json.dumps({"facts": [
                {"text": "被害人於112年10月遭側錄", "kind": "event"},
                {"text": "完全杜撰不存在摘要中的事實", "kind": "event"},
            ]}, ensure_ascii=False)}}]}
            return io.BytesIO(json.dumps(body).encode()).read()

    def fake_urlopen(req, timeout):
        return FakeResponse()
    monkeypatch.setattr(ai_module.urlrequest, "urlopen", fake_urlopen)

    summary = "被害人於112年10月遭側錄私密影像。"
    result = ai_module.segment_facts(summary)
    assert result is not None
    texts = [f["text"] for f in result["facts"]]
    assert "被害人於112年10月遭側錄" in texts
    # 杜撰事實被過濾
    assert "完全杜撰不存在摘要中的事實" not in texts


def test_segment_facts_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(ai_module, "_settings", lambda: None)
    assert ai_module.segment_facts("摘要") is None


def test_segment_facts_rejects_invalid_kind(monkeypatch):
    _fake_settings(monkeypatch)

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            body = {"choices": [{"message": {"content": json.dumps({"facts": [
                {"text": "被害人遭側錄", "kind": "crime_established"},
            ]}, ensure_ascii=False)}}]}
            return io.BytesIO(json.dumps(body).encode()).read()

    monkeypatch.setattr(ai_module.urlrequest, "urlopen", lambda req, timeout: FakeResponse())
    result = ai_module.segment_facts("被害人遭側錄私密影像。")
    assert result is not None
    # 非法 kind 降級為 event，不得通過
    assert result["facts"][0]["kind"] == "event"


def test_analyze_gate1_uses_fallback_without_ai_key():
    from app.rules import analyze_gate1
    intake = {"summary": "被害人遭側錄私密影像，對方以此威脅要求交付金錢。",
              "event_time": "2026-10-10T10:30", "location": "測試"}
    g1 = analyze_gate1(intake, use_ai=True)  # 無 .env 金鑰 → fallback
    assert g1["segmentation_source"] == "rules"
    event_facts = [f for f in g1["facts"] if f["fact_status"] == "當事人陳述"]
    assert len(event_facts) == 1
    assert event_facts[0]["source_excerpt"].startswith("被害人遭側錄")

def test_analyze_prompt_injects_structured_facts():
    facts = [{
        "text": "被害人遭側錄私密影像",
        "subject": "對方", "action": "側錄", "object": "私密影像",
        "time": "", "place": "", "kind": "event",
    }]
    messages = ai_module.build_analyze_prompt("被害人遭側錄私密影像", [{"id": "theft", "name": "竊盜"}], facts=facts)
    user = messages[1]["content"]
    assert "已切分的結構化事實" in user
    assert "被害人遭側錄私密影像" in user
    assert "action=側錄" in user
    # 無 facts 時不注入區塊
    plain = ai_module.build_analyze_prompt("摘要", [{"id": "theft", "name": "竊盜"}])
    assert "已切分的結構化事實" not in plain[1]["content"]


def test_analyze_prompt_includes_prohibited_conclusion_rule():
    messages = ai_module.build_analyze_prompt("摘要", [{"id": "theft", "name": "竊盜"}])
    user = messages[1]["content"]
    assert "不得輸出犯罪成立" in user


def _v3_response_from_messages(messages, *, quote="拿走三千元", offense_id="robbery"):
    user = messages[1]["content"]
    request_text = user.split("【程式產生的 request】\n", 1)[1].split("\n\n【offense_catalog】", 1)[0]
    request_envelope = json.loads(request_text)
    case_text = request_envelope["input_payload"]["case_text"]
    start = case_text.index(quote)
    return {
        key: request_envelope[key]
        for key in (
            "schema_version", "stage", "request_id", "case_revision", "attempt",
            "input_hash", "source_snapshot_hashes",
        )
    } | {
        "response_payload": {
            "candidates": [{
                "offense_id": offense_id,
                "reason": f"案情記載「{quote}」，可能涉及本候選方向。",
                "basis_quote": quote,
                "basis_start": start,
                "basis_end": start + len(quote),
                "missing": ["行為時的具體壓制程度待確認"],
            }],
            "status": {
                "subject_identified": "false",
                "has_victim": "true",
                "is_solved": "false",
            },
        }
    }


def test_v3_candidate_adapter_validates_envelope_and_uses_temperature_zero(monkeypatch):
    _fake_settings(monkeypatch)
    calls = []

    def fake_chat(api_key, base_url, model, messages, max_tokens, *, temperature=0.2):
        calls.append({"temperature": temperature, "messages": messages})
        return json.dumps(_v3_response_from_messages(messages), ensure_ascii=False)

    monkeypatch.setattr(ai_module, "_chat", fake_chat)
    summary = "昨天在巷口被一個男的拿刀抵住脖子，拿走三千元。"
    hashes = {"offense_catalog": canonical_sha256(OFFENSES)}
    result = ai_module.analyze_candidates_v3(
        summary,
        OFFENSES,
        case_revision=4,
        source_snapshot_hashes=hashes,
    )
    assert result is not None
    assert calls[0]["temperature"] == 0
    assert result["candidates"][0]["basis_quote"] == "拿走三千元"
    assert result["status"]["subject_identified"] == "false"
    assert result["contract"]["case_revision"] == 4
    assert result["contract"]["attempt_count"] == 1


def test_v3_candidate_adapter_retries_contract_failure_at_most_twice(monkeypatch):
    _fake_settings(monkeypatch)
    attempts = []

    def fake_chat(api_key, base_url, model, messages, max_tokens, *, temperature=0.2):
        response = _v3_response_from_messages(messages)
        attempts.append(response["attempt"])
        response["response_payload"]["candidates"][0]["basis_start"] = 0
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr(ai_module, "_chat", fake_chat)
    result = ai_module.analyze_candidates_v3(
        "一個男的拿刀抵住脖子，拿走三千元。",
        OFFENSES,
        case_revision=1,
        source_snapshot_hashes={"offense_catalog": canonical_sha256(OFFENSES)},
    )
    assert result is None
    assert attempts == [1, 2, 3]


def test_v3_candidate_adapter_rejects_markdown_wrapped_json_then_recovers(monkeypatch):
    _fake_settings(monkeypatch)
    calls = []

    def fake_chat(api_key, base_url, model, messages, max_tokens, *, temperature=0.2):
        response = json.dumps(_v3_response_from_messages(messages), ensure_ascii=False)
        calls.append(response)
        return f"```json\n{response}\n```" if len(calls) == 1 else response

    monkeypatch.setattr(ai_module, "_chat", fake_chat)
    result = ai_module.analyze_candidates_v3(
        "一個男的拿刀抵住脖子，拿走三千元。",
        OFFENSES,
        case_revision=1,
        source_snapshot_hashes={"offense_catalog": canonical_sha256(OFFENSES)},
    )
    assert result is not None
    assert result["contract"]["attempt_count"] == 2

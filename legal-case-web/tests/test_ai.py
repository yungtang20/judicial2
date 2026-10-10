from __future__ import annotations

from app import ai as ai_module
from app.ai import analyze_candidates
from tests.helpers import BANK


OFFENSES = [{"id": item["id"], "name": item["name"]} for item in BANK["offenses"]]


def _fake_settings(monkeypatch, key="sk-test", model="test-model"):
    monkeypatch.setattr(
        ai_module, "_settings", lambda: (key, "https://mock.local/v1", model)
    )


def test_analyze_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(ai_module, "_settings", lambda: None)
    assert analyze_candidates("摘要", OFFENSES) is None


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

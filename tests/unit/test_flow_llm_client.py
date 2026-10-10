import pytest

from pipeline.flow.llm_client import LocalLLMClient, LocalLLMConfig, LocalLLMError
from tests.fixtures.stub_llm.server import running_stub


def _validator(value):
    assert value["gate"] == "TEST"


def test_t5_non_loopback_endpoint_is_rejected(monkeypatch):
    monkeypatch.setenv("JUDICIAL2_LOCAL_LLM_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("JUDICIAL2_LOCAL_LLM_MODEL", "stub-fixed")
    with pytest.raises(LocalLLMError, match="loopback"):
        LocalLLMConfig.from_env()


def test_t6_missing_endpoint_or_model_stops(monkeypatch):
    monkeypatch.delenv("JUDICIAL2_LOCAL_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("JUDICIAL2_LOCAL_LLM_MODEL", raising=False)
    with pytest.raises(LocalLLMError, match="ENDPOINT"):
        LocalLLMConfig.from_env()


def test_t7_invalid_json_stops_after_three_attempts():
    with running_stub() as (endpoint, server):
        client = LocalLLMClient(LocalLLMConfig(endpoint, "stub-fixed"))
        with pytest.raises(LocalLLMError, match="3 次"):
            client.complete_json(
                system_prompt="synthetic test",
                gate_input={},
                output_schema={},
                validator=_validator,
                stub_fixture="invalid_json",
            )
        assert server.request_count == 3


def test_stub_response_requires_fixed_marker():
    with running_stub() as (endpoint, server):
        client = LocalLLMClient(LocalLLMConfig(endpoint, "stub-fixed"))
        result = client.complete_json(
            system_prompt="synthetic test",
            gate_input={},
            output_schema={},
            validator=_validator,
            stub_fixture="valid_empty",
        )
        assert result["gate"] == "TEST"
        assert server.request_count == 1

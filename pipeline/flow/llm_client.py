"""Loopback-only OpenAI-compatible client used by the v0.3 flow."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
STUB_MODEL = "stub-fixed"


class LocalLLMError(RuntimeError):
    """Raised when configuration, transport, or output validation fails."""


@dataclass(frozen=True)
class LocalLLMConfig:
    endpoint: str
    model: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "LocalLLMConfig":
        endpoint = os.getenv("JUDICIAL2_LOCAL_LLM_ENDPOINT", "").strip()
        model = os.getenv("JUDICIAL2_LOCAL_LLM_MODEL", "").strip()
        if not endpoint:
            raise LocalLLMError("JUDICIAL2_LOCAL_LLM_ENDPOINT 未設定")
        if not model:
            raise LocalLLMError("JUDICIAL2_LOCAL_LLM_MODEL 未設定")
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOOPBACK_HOSTS:
            raise LocalLLMError("本地模型端點必須為 loopback 位址")
        return cls(endpoint=endpoint.rstrip("/"), model=model)

    @property
    def completion_url(self) -> str:
        suffix = "/v1/chat/completions"
        return self.endpoint if self.endpoint.endswith(suffix) else self.endpoint + suffix


Validator = Callable[[dict[str, Any]], None]


class LocalLLMClient:
    def __init__(self, config: LocalLLMConfig | None = None) -> None:
        self.config = config or LocalLLMConfig.from_env()

    def complete_json(
        self,
        *,
        system_prompt: str,
        gate_input: dict[str, Any],
        output_schema: dict[str, Any],
        validator: Validator,
        stub_fixture: str | None = None,
    ) -> dict[str, Any]:
        failures: list[str] = []
        for _attempt in range(3):
            try:
                response = self._request(
                    system_prompt=system_prompt,
                    gate_input=gate_input,
                    output_schema=output_schema,
                    stub_fixture=stub_fixture,
                )
                validator(response)
                return response
            except (LocalLLMError, ValueError, TypeError) as exc:
                failures.append(str(exc))
        raise LocalLLMError("LLM 輸出經 3 次嘗試仍不合格：" + " | ".join(failures))

    def _request(
        self,
        *,
        system_prompt: str,
        gate_input: dict[str, Any],
        output_schema: dict[str, Any],
        stub_fixture: str | None,
    ) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"input": gate_input, "output_schema": output_schema},
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        headers = {"Content-Type": "application/json"}
        if stub_fixture:
            headers["X-Stub-Fixture"] = stub_fixture
        request = Request(
            self.config.completion_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as raw:
                envelope = json.loads(raw.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LocalLLMError(f"本地模型端點不可用：{exc}") from exc

        if self.config.model == STUB_MODEL:
            if envelope.get("_stub") is not True or envelope.get("model") != STUB_MODEL:
                raise LocalLLMError("stub 回應缺少固定識別")
        try:
            content = envelope["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LocalLLMError("LLM 回應不是有效 JSON") from exc
        if not isinstance(result, dict):
            raise LocalLLMError("LLM JSON 最外層必須為物件")
        return result

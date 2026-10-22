"""Provider 端點政策（2026-10-22 新增）。

用途：把「Taiwan Law MCP 只能以自架端點接線」寫成可測試的政策，而不是只
留在審查文件。``HG_LR_02_PRIVACY_SECURITY_REVIEW.md`` 的 P04 指出 hosted
端點會保存完整查詢參數；``docs/HG_LR_01_PROVIDER_REVIEW.md`` 也把 hosted
MCP 列為 ``CONDITIONAL_DISCOVERY_CANDIDATE``。自架端點可讓案件內容留在
本機，因此本模組要求：

- ``mode`` 必須是 ``SELF_HOST_ONLY``，且 ``allow_hosted`` 必須為 false。
- 可選端點必須是 loopback（``127.0.0.1``／``localhost``／``::1``）、
  http、且明確帶 port。
- hosted 端點只能被記錄，不得被選為 ``selectable``。
- 三個 Human Gate 必須被記錄；未核准時 ``runtime_ready`` 一律 false。

本模組不發網路請求、不啟動容器，也不代表任何 Gate 已核准。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "deploy" / "providers" / "taiwan_law_mcp.json"
)
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
REQUIRED_GATES = ("HG-LR-01", "HG-LR-02", "HG-LR-05")


class ProviderEndpointNotAuthorized(RuntimeError):
    """端點政策不允許接線。"""


def load_provider_config(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or DEFAULT_CONFIG_PATH).read_text(encoding="utf-8"))


def _endpoint_errors(
    url: Any, *, allowed_hosts: set[str], allowed_schemes: set[str], require_port: bool
) -> list[str]:
    if not isinstance(url, str) or not url.strip():
        return ["端點必須是非空字串"]
    parts = urlsplit(url)
    errors: list[str] = []
    if parts.scheme not in allowed_schemes:
        errors.append(f"端點 scheme 必須是 {sorted(allowed_schemes)}")
    if parts.username or parts.password:
        errors.append("端點不得含帳密")
    if parts.query or parts.fragment:
        errors.append("端點不得含 query 或 fragment")
    if parts.hostname not in allowed_hosts:
        errors.append(f"端點主機必須是 {sorted(allowed_hosts)}，實際為 {parts.hostname!r}")
    if require_port and parts.port is None:
        errors.append("端點必須明確指定 port")
    return errors


def validate_provider_config(config: dict[str, Any]) -> list[str]:
    """回傳政策錯誤清單；空清單代表可作為自架候選端點。"""

    errors: list[str] = []
    policy = config.get("policy")
    if not isinstance(policy, dict):
        return ["policy 必須是物件"]
    if policy.get("mode") != "SELF_HOST_ONLY":
        errors.append("policy.mode 必須是 SELF_HOST_ONLY")
    if policy.get("allow_hosted") is not False:
        errors.append("policy.allow_hosted 必須是 false")
    if config.get("runtime_enabled") is not False:
        errors.append("runtime_enabled 必須維持 false（接線須 HG-LR-05）")

    allowed_hosts = set(policy.get("allowed_hosts") or [])
    if not allowed_hosts or not allowed_hosts <= LOOPBACK_HOSTS:
        errors.append("policy.allowed_hosts 只能包含 loopback 主機")
    allowed_schemes = set(policy.get("allowed_schemes") or [])
    require_port = policy.get("require_explicit_port") is True

    self_host = config.get("self_host")
    if not isinstance(self_host, dict):
        errors.append("self_host 必須是物件")
    else:
        errors.extend(
            _endpoint_errors(
                self_host.get("url"),
                allowed_hosts=allowed_hosts,
                allowed_schemes=allowed_schemes,
                require_port=require_port,
            )
        )
        if not isinstance(self_host.get("launch"), dict) or not self_host["launch"]:
            errors.append("self_host.launch 必須記錄啟動方式")

    hosted = config.get("hosted_endpoint")
    if not isinstance(hosted, dict):
        errors.append("hosted_endpoint 必須被明確記錄")
    else:
        if hosted.get("selectable") is not False:
            errors.append("hosted_endpoint.selectable 必須是 false")
        if not str(hosted.get("blocked_reason", "")).strip():
            errors.append("hosted_endpoint 必須記錄阻擋原因")

    gates = config.get("human_gate")
    if not isinstance(gates, dict):
        errors.append("human_gate 必須是物件")
    else:
        for gate in REQUIRED_GATES:
            if gates.get(gate) != "PENDING":
                errors.append(f"{gate} 在本輪必須維持 PENDING，不得由程式碼代為核准")
    return errors


def resolve_endpoint(config: dict[str, Any]) -> str:
    """回傳唯一允許接線的自架端點；政策不合格即 fail-closed。"""

    errors = validate_provider_config(config)
    if errors:
        raise ProviderEndpointNotAuthorized("；".join(errors))
    return str(config["self_host"]["url"])


def runtime_ready(config: dict[str, Any]) -> tuple[bool, str]:
    """是否可接入 runtime。本輪必然 False：Gate 未核准且 runtime_enabled=false。"""

    errors = validate_provider_config(config)
    if errors:
        return False, "端點政策不合格：" + "；".join(errors)
    if config.get("runtime_enabled") is not True:
        return False, "runtime_enabled=false；接線屬 HG-LR-05，須人工核准"
    pending = [
        gate
        for gate in REQUIRED_GATES
        if (config.get("human_gate") or {}).get(gate) != "APPROVED"
    ]
    if pending:
        return False, "Human Gate 未核准：" + "、".join(pending)
    return True, "READY"

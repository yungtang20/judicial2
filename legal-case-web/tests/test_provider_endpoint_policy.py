"""Provider 端點政策的鎖定測試（2026-10-22 新增）。

鎖定三件事：
1. Taiwan Law MCP 只能以 loopback 自架端點接線，hosted 端點不可選。
2. 政策不得被改成「先接線再補核准」；runtime_enabled 與 Gate 一律 fail-closed。
3. 設定檔記錄的端點與上游 README 一致，避免文件漂移。
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app import provider_endpoint_policy as policy

CONFIG = policy.load_provider_config()


def test_shipped_config_passes_policy() -> None:
    assert policy.validate_provider_config(CONFIG) == []


def test_resolved_endpoint_is_loopback_self_host() -> None:
    assert policy.resolve_endpoint(CONFIG) == "http://localhost:8787/mcp"


def test_hosted_endpoint_is_recorded_but_not_selectable() -> None:
    hosted = CONFIG["hosted_endpoint"]
    assert hosted["selectable"] is False
    assert hosted["url"] == "https://legaltech.org.tw/mcp"
    assert "P90" not in hosted["blocked_reason"]
    assert "90" in hosted["blocked_reason"]


def test_runtime_is_not_ready_while_gates_are_pending() -> None:
    ready, reason = policy.runtime_ready(CONFIG)
    assert ready is False
    assert "HG-LR-05" in reason
    assert CONFIG["runtime_enabled"] is False


def test_self_host_launch_matches_upstream_readme() -> None:
    launch = CONFIG["self_host"]["launch"]
    assert launch["npx"]["command"] == ["npx", "taiwan-law-mcp"]
    docker = launch["docker"]["command"]
    assert docker[:5] == ["docker", "run", "-d", "-p", "8787:8787"]
    assert "legaltechtw/taiwan-law-mcp" in docker
    assert CONFIG["self_host"]["url"].endswith(":8787/mcp")


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda c: c["policy"].update(allow_hosted=True), "allow_hosted"),
        (lambda c: c["policy"].update(mode="HOSTED_ALLOWED"), "SELF_HOST_ONLY"),
        (
            lambda c: c["self_host"].update(url="https://legaltech.org.tw/mcp"),
            "主機必須是",
        ),
        (
            lambda c: c["self_host"].update(url="http://localhost/mcp"),
            "port",
        ),
        (
            lambda c: c["self_host"].update(url="http://user:pass@localhost:8787/mcp"),
            "帳密",
        ),
        (lambda c: c["hosted_endpoint"].update(selectable=True), "selectable"),
        (lambda c: c.update(runtime_enabled=True), "runtime_enabled"),
        (lambda c: c["human_gate"].update({"HG-LR-01": "APPROVED"}), "HG-LR-01"),
    ],
)
def test_policy_rejects_unsafe_configurations(mutate, expected: str) -> None:
    config = deepcopy(CONFIG)
    mutate(config)
    errors = policy.validate_provider_config(config)
    assert any(expected in error for error in errors), errors
    with pytest.raises(policy.ProviderEndpointNotAuthorized):
        policy.resolve_endpoint(config)


def test_config_file_is_valid_utf8_json() -> None:
    raw = policy.DEFAULT_CONFIG_PATH.read_bytes()
    assert b"\r\n" not in raw
    parsed = json.loads(raw.decode("utf-8"))
    assert parsed["provider_id"] == "taiwan-law-mcp"

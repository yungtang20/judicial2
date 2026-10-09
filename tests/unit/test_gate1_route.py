import pytest

from pipeline.gate1 import run


ROUTE_CASES = [
    {
        "name": "route_a_positive",
        "source": "\n".join(
            [
                "受理性質：受理",
                "案號：TEST-A-001",
                "刑事行為：是",
                "被害人：虛構角色甲",
            ]
        ),
        "expected_route": "A",
    },
    {
        "name": "route_b_positive",
        "source": "\n".join(
            [
                "受理性質：查獲",
                "案號：TEST-B-001",
                "刑事行為：是",
                "被害人：無",
            ]
        ),
        "expected_route": "B",
    },
    {
        "name": "route_c_positive",
        "source": "\n".join(
            [
                "受理性質：備案",
                "案號：TEST-C-001",
                "刑事行為：否",
                "被害人：無",
            ]
        ),
        "expected_route": "C",
    },
    {
        "name": "route_d_positive",
        "source": "\n".join(
            [
                "受理性質：備案",
                "案號：無",
                "刑事行為：否",
                "被害人：無",
            ]
        ),
        "expected_route": "D",
    },
    {
        "name": "route_e_positive",
        "source": "\n".join(
            [
                "受理性質：行政裁處",
                "案號：無",
                "刑事行為：UNKNOWN",
                "被害人：無",
            ]
        ),
        "expected_route": "E",
    },
    {
        "name": "unknown_zero_match",
        "source": "\n".join(
            [
                "受理性質：不明",
                "案號：無",
                "刑事行為：不明",
                "被害人：不明",
            ]
        ),
        "expected_route": "UNKNOWN",
    },
    {
        "name": "unknown_multiple_match",
        "source": "\n".join(
            [
                "受理性質：受理",
                "案號：TEST-MULTI-001",
                "刑事行為：是",
                "被害人：虛構角色乙",
                "行政裁處案件：是",
            ]
        ),
        "expected_route": "UNKNOWN",
    },
]


@pytest.mark.parametrize("case", ROUTE_CASES, ids=lambda case: case["name"])
def test_gate1_route(case: dict[str, str]) -> None:
    result = run(case["source"])
    if result["route"] != case["expected_route"]:
        pytest.fail(f'{case["name"]}: actual_route={result["route"]}', pytrace=False)
    if case["expected_route"] == "UNKNOWN" and "路由無法唯一判定" not in result[
        "warnings"
    ]:
        pytest.fail(f'{case["name"]}: missing_unknown_warning', pytrace=False)

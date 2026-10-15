"""Phase 9-10：固定法律語意測試集與差異測試。"""

from __future__ import annotations

from app.legal_semantic_corpus import (
    CORPUS,
    DIFFERENCE_TESTS,
    run_corpus,
    run_difference_tests,
)


def test_corpus_all_cases_pass_expected_candidate_retention():
    results = run_corpus()
    assert len(results) >= 10, f"測試集應至少 10 案例，目前 {len(results)}"
    failed = [r for r in results if not r["pass"]]
    assert not failed, f"失敗案例：{[r['id'] for r in failed]}"


def test_corpus_covers_all_spec_categories():
    ids = {c["id"] for c in CORPUS}
    assert any(i.startswith("A-") for i in ids), "缺少財產犯罪案例"
    assert any(i.startswith("B-") for i in ids), "缺少網路與性影像案例"
    assert any(i.startswith("C-") for i in ids), "缺少其他區辨案例"


def test_corpus_zero_candidate_cases_are_safe():
    """C-08 預期零候選；系統不得虛構候選。
    （A-05 第六輪起改為侵占/竊盜區辨案例——「遺失/拾獲」關鍵詞修復了
    embezzlement 的合理候選漏列，見 CORPUS 註解與 §337 related_articles。）"""
    results = run_corpus()
    zero_cases = [r for r in results if r["id"] == "C-08"]
    assert len(zero_cases) == 1
    for case in zero_cases:
        assert case["actual"] == [], f"{case['id']} 應回傳零候選，實際：{case['actual']}"


def test_corpus_candidates_carry_distinguishing_questions():
    """spec §7.2：每個候選必須有區分問句參照或需人工提示。"""
    results = run_corpus()
    for r in results:
        if r["actual"]:
            assert r["has_distinguishing_questions"], f"{r['id']} 候選缺區分問句"


def test_difference_tests_single_fact_modifications():
    results = run_difference_tests()
    assert len(results) == len(DIFFERENCE_TESTS)
    for r in results:
        assert r["pass"], f"差異測試 {r['id']} 失敗：預期 {r['expected']}，實際 {r['actual']}"


def test_difference_tests_show_notice_changes_where_expected():
    """spec §12：若關鍵事實修改後輸出完全相同，須調查是否模板化。
    我們以 notice 簽章比對：D-06（虛構事實）應產出不同候選集合。"""
    results = run_difference_tests()
    by_id = {r["id"]: r for r in results}
    # D-06：詐欺正確命中（關鍵詞「虛構」），恐嚇被否定語句正確排除
    assert by_id["D-06-虛構事實要求付款"]["actual"] == ["fraud"]
    # 基準案例（D-01）應含恐嚇與性隱私
    base = by_id["D-01-基準"]["actual"]
    assert "intimidation" in base and "privacy" in base

def test_corpus_candidate_legal_basis_matches_verified_statutes():
    """交叉驗證（spec §5.5）：corpus 每個命中的候選，其法源必為 VERIFIED_CURRENT
    且條文在離線快照中可查。"""
    from app.law_reference import load_cache
    from tests.helpers import BANK
    cache = load_cache()
    results = run_corpus()
    for r in results:
        for oid in r["actual"]:
            offense = [o for o in BANK["offenses"] if o["id"] == oid][0]
            src = offense["source"]
            assert src["status"] == "VERIFIED_CURRENT", f"{oid} 法源未核實"
            key = f"{src['law_name']}:{src['article_no']}"
            assert key in cache, f"{oid} 的法源 {key} 不在快照中"
            # 條文非空且未廢止
            assert cache[key]["article_content"].strip()
            assert not cache[key]["abolished"]


def test_corpus_prohibited_conclusions_enforced_everywhere():
    """所有命中候選必須帶 prohibited_conclusions（不自動定性，spec §5.6）。"""
    from tests.helpers import BANK as bank
    results = run_corpus()
    for r in results:
        for oid in r["actual"]:
            # 重新取候選以驗 prohibited_conclusions
            from app.rules import candidate_offenses
            spec = [c for c in CORPUS if c["id"] == r["id"]][0]
            candidates = candidate_offenses(spec["summary"], bank)
            for c in candidates:
                assert c["prohibited_conclusions"] == ["犯罪成立", "故意成立", "因果關係成立", "競合成立"]

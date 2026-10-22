# -*- coding: utf-8 -*-
"""法源推理流程提取（階段一 4.1）驗收腳本。

檢查 lawbank_reasoning_flow.json 是否符合專案規劃書 4.1 的驗收標準：
  - 每個 statute_id 都有 elements 陣列，且每個 element 有 search_tags
  - 每個 judgment_refs 的 case_ref 若原文有字號則照抄，若無則標 needs_external
  - reasoning_paths 至少一條，且每條能回答「什麼事實特徵→觸發哪些要件→指向哪些候選法條」
  - 輸出為純 JSON，無前言、無結語、無 Markdown 圍欄
另檢查全流程禁語（成立／構成／該當／應論以）。

用法：
    py -3 reasoning-flow/tools/validate_reasoning_flow.py
退出碼：0 = 全部通過；1 = 有失敗項目。
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
DATA_FILE = PKG / "data" / "lawbank_reasoning_flow.json"

FORBIDDEN_WORDS = ["成立", "構成", "該當", "應論以"]
# 允許出現在「免責／說明」語境中的斷定語片段
FORBIDDEN_ALLOWLIST = [
    "不認定犯罪成立",
    "不構成",
    "未構成",
    "構成要件之判準",
    "不作任何成立與否之認定",
    "成立與否",
]

# 判解字號格式：法院名稱 + 年度 + 類別 + 字號 + 號
CASE_REF_RE = re.compile(
    r"^[^0-9]{2,20}?(\d{2,3})年度[^0-9]{0,8}?字第?\s*\d+\s*號"
)

results = []


def check(ok, name, detail=""):
    results.append((bool(ok), name, detail))
    return bool(ok)


def scan_forbidden(text):
    """回傳 (違規詞, 命中片段) 列表。"""
    hits = []
    for word in FORBIDDEN_WORDS:
        for m in re.finditer(re.escape(word), text):
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            snippet = text[start:end]
            if any(allow in snippet for allow in FORBIDDEN_ALLOWLIST):
                continue
            hits.append((word, snippet))
    return hits


def main():
    check(DATA_FILE.exists(), "lawbank_reasoning_flow.json 存在", str(DATA_FILE))
    if not DATA_FILE.exists():
        return report()
    raw = DATA_FILE.read_text(encoding="utf-8")

    # 純 JSON 檢查（不得有 Markdown 圍欄或前言）
    check(not raw.lstrip().startswith("```"), "輸出為純 JSON（無 Markdown 圍欄）")
    check(not raw.lstrip().startswith("以下是"), "輸出為純 JSON（無前言）")
    try:
        data = json.loads(raw)
        check(True, "lawbank_reasoning_flow.json 為合法 JSON")
    except json.JSONDecodeError as exc:
        check(False, "lawbank_reasoning_flow.json 為合法 JSON", str(exc))
        return report()

    for key in (
        "flow_id",
        "source_note",
        "statute_decomposition",
        "element_to_judgment",
        "judgment_to_issue",
        "issue_to_scholarship",
        "reasoning_paths",
        "search_word_recommendations",
        "extraction_gaps",
        "output_flags",
    ):
        check(key in data, f"頂層欄位存在：{key}")

    # --- 每個 statute_id 都有 elements 陣列，且每個 element 有 search_tags ---
    statutes = data.get("statute_decomposition", [])
    check(len(statutes) > 0, "statute_decomposition 非空")
    statute_ids = set()
    for st in statutes:
        sid = st.get("statute_id")
        check(bool(sid), "statute_id 非空")
        if sid in statute_ids:
            check(False, f"statute_id 唯一：{sid}")
        statute_ids.add(sid)
        check("elements" in st, f"{sid}：含 elements 陣列")
        check(isinstance(st.get("elements"), list), f"{sid}：elements 為陣列")
        check(len(st.get("elements", [])) > 0, f"{sid}：elements 非空")
        for el in st.get("elements", []):
            eid = el.get("element_id")
            check(bool(eid), f"{sid}：element_id 非空")
            check(bool(el.get("element_name")), f"{sid}.{eid}：含 element_name")
            check(bool(el.get("definition")), f"{sid}.{eid}：含 definition")
            tags = el.get("search_tags")
            check(isinstance(tags, list) and len(tags) > 0, f"{sid}.{eid}：search_tags 非空陣列")
            # 分析器所需之結構性欄位
            check(
                isinstance(el.get("fact_patterns"), list) and len(el["fact_patterns"]) > 0,
                f"{sid}.{eid}：fact_patterns 非空陣列（事實偵測用）",
            )
            check(
                isinstance(el.get("critical"), bool),
                f"{sid}.{eid}：critical 為布林值（基本要件／非基本要件）",
            )
            check(
                isinstance(el.get("discriminating"), bool),
                f"{sid}.{eid}：discriminating 為布林值（是否為區別性要件）",
            )
            check(
                set(el.get("fact_patterns", [])) != set(tags),
                f"{sid}.{eid}：fact_patterns 與 search_tags 用途不同，未混用",
            )

    # --- element_to_judgment：case_ref 有字號者照抄，無者標 needs_external ---
    e2j = data.get("element_to_judgment", [])
    check(len(e2j) > 0, "element_to_judgment 非空")
    all_element_ids = {el.get("element_id") for st in statutes for el in st.get("elements", [])}
    for grp in e2j:
        eid = grp.get("element_id")
        check(eid in all_element_ids, f"element_to_judgment：{eid} 對應到已定義的 element")
        refs = grp.get("judgment_refs")
        check(isinstance(refs, list), f"element_to_judgment：{eid}.judgment_refs 為陣列")
        if len(refs) == 0:
            # 無判解可對應者，須明確標記為 needs_external 並說明原因
            check(
                grp.get("extraction_status") == "needs_external",
                f"element_to_judgment：{eid} 無判解時須標記 extraction_status=needs_external",
                str(grp.get("extraction_status")),
            )
            check(bool(grp.get("note")), f"element_to_judgment：{eid} 無判解時須附 note 說明原因")
        else:
            check(len(refs) > 0, f"element_to_judgment：{eid} 至少有一筆判解")
        for ref in refs:
            cref = ref.get("case_ref")
            check(bool(cref), f"element_to_judgment：{eid} 之 case_ref 非空")
            if not cref:
                continue
            if CASE_REF_RE.match(cref):
                check(
                    ref.get("status_flag") == "extracted",
                    f"{eid}：{cref} 有字號，狀態標為 extracted",
                    str(ref.get("status_flag")),
                )
            else:
                check(
                    ref.get("status_flag") == "needs_external",
                    f"{eid}：{cref} 無字號，狀態標為 needs_external",
                    str(ref.get("status_flag")),
                )
            check(bool(ref.get("holding_summary")), f"{eid}：{cref} 含 holding_summary")
            yr = ref.get("year")
            if yr is not None:
                check(
                    1900 <= yr <= 2100,
                    f"{eid}：{cref} 之 year 為合理西元年",
                    str(yr),
                )
                check(
                    1 <= int(ref.get("year_roc", 0)) <= 120,
                    f"{eid}：{cref} 之 year_roc 為合理民國年",
                    str(ref.get("year_roc")),
                )

    # --- judgment_to_issue：case_ref 須可回溯到 element_to_judgment ---
    referenced = {
        ref.get("case_ref")
        for grp in e2j
        for ref in grp.get("judgment_refs", [])
        if ref.get("case_ref")
    }
    j2i = data.get("judgment_to_issue", [])
    check(len(j2i) > 0, "judgment_to_issue 非空")
    for item in j2i:
        cref = item.get("case_ref")
        check(bool(cref), "judgment_to_issue：case_ref 非空")
        check(
            cref in referenced,
            f"judgment_to_issue：{cref} 可回溯到 element_to_judgment（避免虛構字號）",
        )
        check(bool(item.get("issue")), f"judgment_to_issue：{cref} 含 issue")
        check(bool(item.get("court_reasoning")), f"judgment_to_issue：{cref} 含 court_reasoning")
        check(
            isinstance(item.get("factors"), list) and len(item["factors"]) > 0,
            f"judgment_to_issue：{cref} 含 factors",
        )

    # --- issue_to_scholarship：每筆 view 有 orientation 與 status ---
    i2s = data.get("issue_to_scholarship", [])
    check(len(i2s) > 0, "issue_to_scholarship 非空")
    issues = {item.get("issue") for item in j2i}
    for item in i2s:
        issue = item.get("issue")
        check(issue in issues, f"issue_to_scholarship：爭點可回溯到 judgment_to_issue")
        views = item.get("scholarship_views")
        check(isinstance(views, list) and len(views) > 0, f"issue_to_scholarship：{issue} 含學說")
        for v in views:
            check(bool(v.get("view")), f"issue_to_scholarship：{issue} 之 view 非空")
            check(bool(v.get("orientation")), f"issue_to_scholarship：{issue} 之 orientation 非空")
            check(
                v.get("status") in ("extracted", "needs_external", "inferred"),
                f"issue_to_scholarship：{issue} 之 status 合法",
                str(v.get("status")),
            )

    # --- reasoning_paths：至少一條，且可回答「事實特徵→要件→候選法條」 ---
    paths = data.get("reasoning_paths", [])
    check(len(paths) >= 1, "reasoning_paths 至少一條")
    for p in paths:
        pid = p.get("path_id")
        check(bool(p.get("fact_pattern")), f"reasoning_paths：{pid} 含 fact_pattern")
        trig = p.get("trigger_elements")
        check(isinstance(trig, list) and len(trig) > 0, f"reasoning_paths：{pid} 含 trigger_elements")
        # 分析器以 required_triggers 判斷該事實型態是否成立
        req = p.get("required_triggers")
        check(
            isinstance(req, list) and len(req) > 0,
            f"reasoning_paths：{pid} 含 required_triggers（型態成立所需事實）",
        )
        for eid in req or []:
            check(
                eid in all_element_ids,
                f"reasoning_paths：{pid} 之 required_trigger {eid} 已定義",
            )
        for eid in trig or []:
            check(eid in all_element_ids, f"reasoning_paths：{pid} 之要件 {eid} 已定義")
        cands = p.get("candidate_statutes")
        check(isinstance(cands, list) and len(cands) > 0, f"reasoning_paths：{pid} 含 candidate_statutes")
        for cs in cands:
            check(cs in statute_ids, f"reasoning_paths：{pid} 之候選法條 {cs} 已於 statute_decomposition 定義")
        for eid in trig or []:
            check(eid in all_element_ids, f"reasoning_paths：{pid} 之要件 {eid} 已定義")
        for eid in p.get("distinguishing_elements") or []:
            check(eid in all_element_ids, f"reasoning_paths：{pid} 之區別要件 {eid} 已定義")
        for cj in p.get("key_judgments") or []:
            check(cj in referenced, f"reasoning_paths：{pid} 之判解 {cj} 可回溯")

    # --- search_word_recommendations ---
    swr = data.get("search_word_recommendations", [])
    check(len(swr) > 0, "search_word_recommendations 非空")
    for s in swr:
        check(bool(s.get("input_term")), "search_word_recommendations：input_term 非空")
        check(
            isinstance(s.get("recommended_terms"), list) and len(s["recommended_terms"]) > 0,
            f"search_word_recommendations：{s.get('input_term')} 含 recommended_terms",
        )
        for eid in s.get("maps_to_elements") or []:
            check(eid in all_element_ids, f"search_word_recommendations：{s.get('input_term')} 對應要件 {eid} 已定義")

    # --- 禁語 ---
    # 引述欄位（法院要旨、條文原文、學說引述）為法源原文，可能含法院原話中的斷定語，
    # 不視為本系統之斷定；故自全檔文字中剔除引述欄位後再檢查其餘（系統自撰部分）。
    quote_values = set()

    def collect(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                collect(v, path + "." + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                collect(v, path + "[" + str(i) + "]")
        elif isinstance(node, str):
            quote_values.add(node)

    collect(data.get("statute_decomposition", []))
    collect(data.get("element_to_judgment", []))
    collect(data.get("judgment_to_issue", []))
    collect(data.get("issue_to_scholarship", []))

    system_text = raw
    for qv in sorted(quote_values, key=len, reverse=True):
        if len(qv) >= 8:
            system_text = system_text.replace(qv, "")

    hits = scan_forbidden(system_text)
    check(
        not hits,
        "系統自撰內容無斷定語（成立／構成／該當／應論以）",
        str(hits[:3]),
    )
    check(
        "quotation_policy" in data,
        "載明引述與自撰之區分政策（quotation_policy）",
    )

    # --- extraction_gaps 結構 ---
    gaps = data.get("extraction_gaps", [])
    check(isinstance(gaps, list), "extraction_gaps 為陣列")
    for g in gaps:
        check(bool(g.get("gap_id")), "extraction_gaps：gap_id 非空")
        check(bool(g.get("description")), f"extraction_gaps：{g.get('gap_id')} 含 description")
        check(
            g.get("status") in ("extracted", "needs_external", "inferred"),
            f"extraction_gaps：{g.get('gap_id')} 之 status 合法",
            str(g.get("status")),
        )

    return report()


def report():
    failed = [r for r in results if not r[0]]
    print("=" * 60)
    print("法源推理流程提取驗收（M2 / 4.1）")
    print("=" * 60)
    for ok, name, detail in results:
        print(("  [OK] " if ok else "  [FAIL] ") + name)
        if not ok and detail:
            print("         " + str(detail).replace("\n", "\n         "))
    print("-" * 60)
    print(f"檢查項目：{len(results)}　通過：{len(results) - len(failed)}　失敗：{len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

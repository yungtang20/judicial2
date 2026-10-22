# -*- coding: utf-8 -*-
"""問句規則提取（階段一 4.3）驗收腳本。

檢查 questions_rules.json 是否符合專案規劃書 4.3 的驗收標準：
  - 每條規則有 check_type 與 check_value，可程式校驗
  - 問句範本為開放式，無是／否問句
  - 每句 maps_to 至少一個缺口或要件

並以同一套規則實際檢驗既有問句庫（questions/*.md 的問句本體），
以證明規則不僅對新造範本有效、亦可套用於既有 44 個罪章檔。

用法：
    py -3 reasoning-flow/tools/validate_questions_rules.py
退出碼：0 = 全部通過；1 = 有失敗項目。
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
ROOT = PKG.parent
DATA_FILE = PKG / "data" / "questions_rules.json"
QUESTIONS_DIR = ROOT / "questions"

results = []


def check(ok, name, detail=""):
    results.append((bool(ok), name, detail))
    return bool(ok)


# ---------------------------------------------------------------- 規則執行器
def _open_markers(rule):
    cv = rule["check_value"]
    if isinstance(cv, dict):
        return cv.get("open_markers", [])
    return [cv]


def _allowed_programmatic(rule):
    cv = rule["check_value"]
    if isinstance(cv, dict):
        return cv.get("allowed_programmatic", [])
    return []


def apply_rule(rule, question, item):
    """依 check_type 檢查單一問句。回傳 (passed, message)。"""
    ctype = rule["check_type"]
    q = question

    if ctype == "required_pattern":
        markers = _open_markers(rule)
        hit = [m for m in markers if m in q]
        if not hit:
            return False, "未含任何開放式標記：" + "、".join(markers[:5])
        if isinstance(rule["check_value"], dict):
            allowed = _allowed_programmatic(rule)
            # 整句是／否命題：含是否/有無 且不含任何 open marker
            if ("是否" in q or "有無" in q) and not hit:
                return False, "整句為是／否命題"
            # 例外句（權益選擇）不計入
            if any(a in q for a in allowed):
                return True, "例外句（權益選擇）"
        return True, "命中：" + "、".join(hit[:3])

    if ctype == "forbidden_word":
        words = rule["check_value"]
        for w in words:
            if w in q:
                return False, "含禁用字：" + w
        return True, ""

    if ctype == "mapping_required":
        cv = rule["check_value"]
        targets = cv if isinstance(cv, list) else [cv]
        maps = item.get("maps_to") or []
        for t in targets:
            if any(t in str(m) for m in maps):
                return True, ""
        return False, "未對應任何 " + "/".join(targets)

    if ctype == "tag_constraint":
        cv = rule["check_value"]
        if not isinstance(cv, dict):
            return True, ""
        if "id_pattern" in cv and item.get("id"):
            if not re.match(cv["id_pattern"], item["id"]):
                return False, "代號格式不符：" + item["id"]
        if "max_question_marks" in cv:
            n = q.count("？") + q.count("?")
            if n > cv["max_question_marks"]:
                return False, f"問號數 {n} > {cv['max_question_marks']}"
        if cv.get("list_marker_required_for_enumeration"):
            # 列舉型（逐項/有哪些/有哪些…）須含 list_marker
            if ("有哪些" in q or "逐項" in q) and cv["list_marker"] not in q and "逐項" in q:
                return False, "列舉型未標示「逐項」"
        return True, ""

    return True, ""


def check_rules_file():
    check(DATA_FILE.exists(), "questions_rules.json 存在", str(DATA_FILE))
    if not DATA_FILE.exists():
        return None
    raw = DATA_FILE.read_text(encoding="utf-8")
    check(not raw.lstrip().startswith("```"), "輸出為純 JSON（無 Markdown 圍欄）")
    data = json.loads(raw)

    for key in ("rules", "question_templates", "target_definitions", "output_format"):
        check(key in data, f"頂層欄位存在：{key}")

    # --- 每條規則有 check_type 與 check_value，可程式校驗 ---
    rules = data.get("rules", [])
    check(len(rules) > 0, "rules 非空")
    valid_types = {"required_pattern", "forbidden_word", "mapping_required", "tag_constraint"}
    for r in rules:
        rid = r.get("rule_id")
        check(bool(rid), "rule_id 非空")
        check(r.get("check_type") in valid_types, f"{rid}：check_type 合法", str(r.get("check_type")))
        check("check_value" in r and r["check_value"] not in (None, "", [], {}), f"{rid}：check_value 非空")
        check(bool(r.get("description")), f"{rid}：含 description")
        check(r.get("severity") in ("error", "warn"), f"{rid}：severity 合法", str(r.get("severity")))

    # --- 問句範本 ---
    templates = data.get("question_templates", [])
    check(len(templates) > 0, "question_templates 非空")
    targets = set(data.get("target_definitions", {}).keys())
    check(len(targets) > 0, "target_definitions 非空")
    ids = set()
    for t in templates:
        tid = t.get("template_id")
        check(tid not in ids, f"template_id 唯一：{tid}")
        ids.add(tid)
        check(t.get("target") in targets, f"{tid}：target 已在 target_definitions 定義", str(t.get("target")))
        check(bool(t.get("template")), f"{tid}：含 template")
        maps = t.get("maps_to")
        check(isinstance(maps, list) and len(maps) > 0, f"{tid}：maps_to 至少一個")
        for m in maps or []:
            check(
                m.startswith("gap_category:") or m.startswith("e_"),
                f"{tid}：maps_to 對應缺口或要件",
                str(m),
            )
        check(bool(t.get("example")), f"{tid}：含 example")
        check(bool(t.get("derived_from")), f"{tid}：標註來源 derived_from")
        check(isinstance(t.get("fact_categories"), list) and len(t["fact_categories"]) > 0, f"{tid}：含 fact_categories")

    # --- 以規則實際檢查範本：開放式、無是／否、無誘導、無定性 ---
    for t in templates:
        q = t["template"]
        for r in rules:
            if "templates" not in (r.get("applies_to") or ["templates"]):
                continue
            if r["check_type"] == "mapping_required":
                continue  # 需 item 結構，另行檢查
            if r.get("severity") != "error":
                continue
            ok, msg = apply_rule(r, q, t)
            check(ok, f"範本 {t['template_id']} 通過規則 {r['rule_id']}", msg)

    # --- 以規則實際檢查「既有問句庫」，證明規則可套用於現有 44 檔 ---
    md_files = sorted(QUESTIONS_DIR.glob("*.md"))
    check(len(md_files) >= 40, "既有問句庫檔案齊備", f"實得 {len(md_files)} 檔")
    existing_total = 0
    existing_open = 0
    existing_violations = []
    open_markers = None
    for r in rules:
        if r["rule_id"] == "open_ended":
            open_markers = r["check_value"]["open_markers"]
    for md in md_files:
        if md.name in ("index.md", "review-checklist.md"):
            continue
        text = md.read_text(encoding="utf-8")
        # 取出「- **B-C-01**（…）：問題」形式的問句本體
        for m in re.finditer(r"^\s*-\s*\*\*[A-Z]{1,3}-(?:C|S|R|D|A|N|W)-\d{2,3}[A-Z]?\*\*\s*（[^）]*）：\s*(.+)$", text, re.M):
            q = m.group(1).strip()
            existing_total += 1
            if open_markers and any(mk in q for mk in open_markers):
                existing_open += 1
            for r in rules:
                if "existing_bank" not in (r.get("applies_to") or []):
                    continue
                if r.get("severity") != "error":
                    continue
                if r["check_type"] in ("forbidden_word", "required_pattern"):
                    ok, msg = apply_rule(r, q, {"id": "", "maps_to": []})
                    if not ok:
                        existing_violations.append((md.name, r["rule_id"], q[:40], msg))
    check(existing_total > 0, "自既有問句庫解析出問句本體", f"共 {existing_total} 句")
    # 硬性違規（暗示答案／法律定性／定性標籤）不得出現於既有問句庫
    check(
        not existing_violations,
        "既有問句庫無硬性違規（暗示答案／法律定性／定性標籤）",
        "; ".join(f"{v[0]}/{v[1]}:{v[2]}" for v in existing_violations[:8]),
    )
    # 開放式比例為量測值，須與 JSON 記載一致（防止資料過期）
    audit = data.get("existing_library_audit", {})
    check(audit.get("available") is True, "existing_library_audit 已產出")
    check(
        audit.get("questions_parsed") == existing_total,
        "existing_library_audit 之問句數與實測一致（防止過期）",
        f"記錄 {audit.get('questions_parsed')} / 實測 {existing_total}",
    )
    measured_ratio = round(existing_open / existing_total, 4) if existing_total else None
    check(
        abs((audit.get("open_ended_ratio") or 0) - (measured_ratio or 0)) < 0.005,
        "existing_library_audit 之開放式比例與實測一致（防止過期）",
        f"記錄 {audit.get('open_ended_ratio')} / 實測 {measured_ratio}",
    )

    # --- output_format ---
    of = data.get("output_format", {})
    for col in ("id", "question", "maps_to", "note"):
        check(col in of.get("columns", []), f"output_format.columns 含 {col}")
    check(of.get("group_by") == "target", "output_format.group_by = target")
    check(
        set(of.get("group_order", [])) == targets,
        "output_format.group_order 涵蓋全部 target",
    )
    check(bool(of.get("footer_note")), "output_format 含 footer_note")

    # --- 禁語：系統自撰部分 ---
    # 僅掃描「內容欄位」。rules[].check_value 為禁用清單本身、
    # rules[].description 為規則說明，兩者必然含禁語字樣，不列入掃描。
    pl = data.get("prohibited_language", {})
    check(len(pl.get("words", [])) > 0, "prohibited_language.words 非空")
    content_parts = []
    for t in templates:
        content_parts.append(t.get("template", ""))
        content_parts.append(t.get("example", ""))
        content_parts.append(t.get("derived_from", ""))
    content_parts.append(of.get("footer_note", ""))
    content_parts.append(data.get("output_format", {}).get("footer_note", ""))
    for t in data.get("target_definitions", {}).values():
        content_parts.append(t.get("definition", ""))
    for g in data.get("extraction_gaps", []):
        content_parts.append(g.get("description", ""))
    content_parts.append(data.get("existing_library_audit", {}).get("audit_scope", ""))
    content_parts.append(pl.get("note", ""))
    scan = "\n".join(content_parts)
    for w in pl.get("words", []):
        hits = []
        for m in re.finditer(re.escape(w), scan):
            seg = scan[max(0, m.start() - 25) : m.end() + 25]
            if any(a in seg for a in pl.get("qualifying_phrases", [])):
                continue
            hits.append(seg.replace("\n", " "))
        check(not hits, f"系統自撰內容無禁語「{w}」", str(hits[:2]))

    # --- extraction_gaps ---
    for g in data.get("extraction_gaps", []):
        check(bool(g.get("gap_id")), "extraction_gaps：gap_id 非空")
        check(bool(g.get("description")), f"extraction_gaps：{g.get('gap_id')} 含 description")
        check(
            g.get("status") in ("extracted", "needs_external", "inferred"),
            f"extraction_gaps：{g.get('gap_id')} 之 status 合法",
        )

    return data


def main():
    data = check_rules_file()
    if data:
        # 目標分佈
        dist = {}
        for t in data.get("question_templates", []):
            dist[t["target"]] = dist.get(t["target"], 0) + 1
        check(len(dist) >= 2, "問句範本涵蓋至少兩種受詢問者角色", str(dist))
    return report()


def report():
    failed = [r for r in results if not r[0]]
    print("=" * 60)
    print("問句規則提取驗收（M3 / 4.3）")
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

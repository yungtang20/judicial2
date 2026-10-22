# -*- coding: utf-8 -*-
"""生成器驗收腳本（專案規劃書 5.2 / M5）。

驗收標準：
  - 每個 gap_id 至少對應一句問句
  - 問句無誘導、無預設答案（須通過 questions_rules.json 全部 error 級規則）
  - 條陳填充未敘明欄位標「（待補）」，主體不明標「（主體待確認）」
  - 案由欄位只填「事實描述＋（候選）」，不填法條罪名
  - 匯出文字末尾有「模擬填充，不構成正式文書」註記

另檢查：匯出文字與 templates.json 之 fixed_text 逐字一致、禁語、
問句分組涵蓋相對人與行為人兩種角色。

用法：
    py -3 reasoning-flow/tools/validate_generator.py
退出碼：0 = 全部通過；1 = 有失敗項目。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
OUT_DIR = PKG / "out"
DATA = PKG / "data"

FORBIDDEN_WORDS = ["成立", "構成", "該當", "應論以"]
ALLOWED = [
    "不作任何罪名成立與否之認定",
    "未作成立與否之判斷",
    "不認定犯罪成立",
    "成立與否",
    "所有罪名均為候選，不認定犯罪成立。",
    "模擬填充，不構成正式文書。",
]
# 案由欄位不得出現之字樣（法條或罪名）
CASE_REASON_FORBIDDEN = [
    "第328條", "第346條", "第320條", "第325條", "第329條", "第330條",
    "刑法第", "強盜罪", "恐嚇取財罪", "竊盜罪", "搶奪罪", "準強盜罪",
]

results = []


def check(ok, name, detail=""):
    results.append((bool(ok), name, detail))
    return bool(ok)


def main():
    # 重新產出
    r = subprocess.run(
        ["node", str(HERE / "generate_output.js"), "--all"],
        cwd=str(PKG), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check(r.returncode == 0, "生成器執行成功", (r.stderr or "")[:300])

    templates = json.loads((DATA / "templates.json").read_text(encoding="utf-8"))
    rules_doc = json.loads((DATA / "questions_rules.json").read_text(encoding="utf-8"))
    flow = json.loads((DATA / "lawbank_reasoning_flow.json").read_text(encoding="utf-8"))
    all_element_ids = {e["element_id"] for s in flow["statute_decomposition"] for e in s["elements"]}
    rule_by_id = {x["rule_id"]: x for x in rules_doc["rules"]}

    cases = sorted((HERE / "test_facts").glob("*.json"))
    check(len(cases) >= 2, "測試案例至少兩則", f"實得 {len(cases)}")

    total_gaps = 0
    total_questions = 0
    targets_seen = set()

    for case in cases:
        base = case.stem
        qf = OUT_DIR / (base + ".questions.json")
        ff = OUT_DIR / (base + ".statement_fill.json")
        ef = OUT_DIR / (base + ".export.txt")
        gf = OUT_DIR / (base + ".gap_list.json")
        for p in (qf, ff, ef, gf):
            check(p.exists(), f"{base}：{p.name} 存在")
        if not (qf.exists() and ff.exists() and ef.exists() and gf.exists()):
            continue

        questions = json.loads(qf.read_text(encoding="utf-8"))
        fill = json.loads(ff.read_text(encoding="utf-8"))
        export_text = ef.read_text(encoding="utf-8").lstrip("\ufeff")
        gap_list = json.loads(gf.read_text(encoding="utf-8"))

        # ---------- 1. 每個 gap_id 至少對應一句問句 ----------
        covered = set()
        for q in questions:
            covered.update(q.get("covers_gaps") or [])
            if q.get("gap_id"):
                covered.add(q["gap_id"])
        gap_ids = {g["gap_id"] for g in gap_list}
        missing = sorted(gap_ids - covered)
        check(not missing, f"{base}：每個 gap_id 至少對應一句問句", "未覆蓋：" + ",".join(missing))
        total_gaps += len(gap_ids)
        total_questions += len(questions)

        # ---------- 2. 問句無誘導、無預設答案（重跑規則校驗） ----------
        for q in questions:
            for r in rules_doc["rules"]:
                if r.get("severity") != "error":
                    continue
                if r["check_type"] == "forbidden_word":
                    for w in r["check_value"]:
                        check(w not in q["question"], f"{base}：問句 {q['id']} 無禁用字「{w}」")
                elif r["check_type"] == "required_pattern":
                    cv = r["check_value"]
                    markers = cv if isinstance(cv, list) else cv.get("open_markers", [])
                    check(
                        any(m in q["question"] for m in markers),
                        f"{base}：問句 {q['id']} 為開放式",
                        q["question"][:50],
                    )
                elif r["check_type"] == "mapping_required":
                    targets = r["check_value"] if isinstance(r["check_value"], list) else [r["check_value"]]
                    maps = q.get("maps_to") or []
                    ok = False
                    for t in targets:
                        if t == "gap_id":
                            ok = ok or bool(q.get("gap_id")) or bool(q.get("covers_gaps")) or any(str(m).startswith("gap_category:") for m in maps)
                        elif t == "element_id":
                            ok = ok or any(str(m).startswith("e_") for m in maps)
                        elif t == "target":
                            ok = ok or bool(q.get("target"))
                        else:
                            ok = ok or any(t in str(m) for m in maps)
                    check(ok, f"{base}：問句 {q['id']} 有對應之缺口或要件")
                elif r["check_type"] == "tag_constraint":
                    cv = r["check_value"]
                    if isinstance(cv, dict):
                        if cv.get("id_pattern"):
                            check(
                                re.match(cv["id_pattern"], q["id"]) is not None,
                                f"{base}：問句代號 {q['id']} 格式正確",
                            )
                        if cv.get("max_question_marks"):
                            n = len(re.findall(r"[？?]", q["question"]))
                            check(n <= cv["max_question_marks"], f"{base}：問句 {q['id']} 問號數符合")
            check(bool(q.get("target")), f"{base}：問句 {q['id']} 有受詢問者角色")
            check(bool(q.get("maps_to")), f"{base}：問句 {q['id']} 有 maps_to")
            for eid in q.get("maps_to", []):
                if str(eid).startswith("e_"):
                    check(eid in all_element_ids, f"{base}：問句 {q['id']} 之要件 {eid} 已定義")
            targets_seen.add(q.get("target"))

        # ---------- 3. 條陳填充標記 ----------
        meta_by_file = OUT_DIR / (base + ".meta.json")
        meta = json.loads(meta_by_file.read_text(encoding="utf-8")) if meta_by_file.exists() else {}
        subject_unknown = meta.get("subject_identified") is False
        for row in fill:
            check(bool(row.get("field_id")), f"{base}：填充列 {row.get('label')} 有 field_id")
            check(bool(row.get("label")), f"{base}：填充列 {row.get('field_id')} 有標籤")
            check(bool(row.get("status")), f"{base}：填充列 {row.get('field_id')} 有狀態")
            if row.get("editable") is not False and row.get("status") not in ("已填", "固定文字", "保留原文佔位", "保留原樣"):
                check(
                    row.get("value") in ("（待補）", "（主體待確認）"),
                    f"{base}：未敘明欄位 {row.get('field_id')} 標為（待補）或（主體待確認）",
                    str(row.get("value")),
                )
            if subject_unknown:
                # 主體不明時，與當事人有關之欄位必須標（主體待確認）
                if row["field_id"] in ("case_reason", "case_summary"):
                    check(
                        row.get("value") == "（主體待確認）",
                        f"{base}：主體不明時欄位 {row.get('field_id')} 標（主體待確認）",
                        str(row.get("value")),
                    )
                else:
                    check(
                        row.get("value") in ("（待補）", "（主體待確認）")
                        or row.get("status") in ("已填", "固定文字", "保留原文佔位", "保留原樣", "固定文字（案號空位保留原樣）"),
                        f"{base}：主體不明時欄位 {row.get('field_id')} 標記合法",
                        str(row.get("value")),
                    )

        # ---------- 4. 案由欄位不填法條罪名 ----------
        case_reason = next((x for x in fill if x["field_id"] == "case_reason"), None)
        check(case_reason is not None, f"{base}：存在 case_reason 欄位")
        if case_reason:
            for w in CASE_REASON_FORBIDDEN:
                check(w not in case_reason["value"], f"{base}：案由欄位不含「{w}」", case_reason["value"][:80])
            if case_reason["status"] == "已填":
                check(
                    case_reason["value"].endswith("（候選）"),
                    f"{base}：案由欄位以（候選）結尾",
                    case_reason["value"][-20:],
                )

        # ---------- 5. 匯出文字 ----------
        check(
            export_text.rstrip().endswith("所有罪名均為候選，不認定犯罪成立。"),
            f"{base}：匯出文字末尾有候選聲明",
            export_text[-60:],
        )
        check(
            "模擬填充，不構成正式文書。" in export_text,
            f"{base}：匯出文字含「模擬填充，不構成正式文書」",
        )
        # 禁語
        scan = export_text
        for a in ALLOWED:
            scan = scan.replace(a, "")
        for w in FORBIDDEN_WORDS:
            hits = [scan[max(0, m.start() - 20): m.end() + 20] for m in re.finditer(re.escape(w), scan)]
            check(not hits, f"{base}：匯出文字無斷定語「{w}」", str(hits[:1]))

        # 匯出文字須與 templates.json 之 fixed_text 逐字一致
        tpl = next((t for t in templates["templates"] if t["template_id"] == fill[0]["template_id"]), None)
        check(tpl is not None, f"{base}：填充表對應之模板存在於 templates.json")
        if tpl:
            exp_lines = []
            if tpl.get("title_text"):
                exp_lines.append(tpl["title_text"])
            for sec in tpl["sections"]:
                for f in sec["fields"]:
                    row = next((x for x in fill if x["field_id"] == f["field_id"]), None)
                    if row is None:
                        continue
                    if f["type"] in ("static", "composite"):
                        exp_lines.append(f["fixed_text"])
                    elif f.get("render") == "below":
                        exp_lines.append(f["fixed_text"] + "\n" + row["value"])
                    elif f.get("variable_position") == "before":
                        exp_lines.append(row["value"] + f["fixed_text"] + f.get("fixed_suffix", ""))
                    else:
                        exp_lines.append(f["fixed_text"] + row["value"] + f.get("fixed_suffix", ""))
            expected = "\n".join(exp_lines)
            check(
                export_text.startswith(expected),
                f"{base}：匯出文字與 templates.json 之 fixed_text 組裝一致",
                f"預期前80字：{expected[:80]} / 實際：{export_text[:80]}",
            )

            # ---------- 條陳順序不可變：對照 條陳.txt 原文 ----------
            # 匯出文字中各固定文字行之出現順序，須與 條陳.txt 該模板區塊完全相同，
            # 且欄位數不得增減。此檢查確保任何階段皆未重排或遺漏條陳格式。
            src_text = (PKG.parent / "條陳.txt").read_text(encoding="utf-8")
            src_lines = src_text.splitlines()
            titles = [t.get("title_text") for t in templates["templates"]]
            try:
                start = src_lines.index(tpl["title_text"])
            except ValueError:
                start = -1
            check(start >= 0, f"{base}：於 條陳.txt 找到模板標題「{tpl.get('title_text')}」")
            if start >= 0:
                # 該模板區塊：自標題行起至下一個標題行（或檔末）前
                end = len(src_lines)
                for i in range(start + 1, len(src_lines)):
                    if src_lines[i] in titles:
                        end = i
                        break
                src_block = [l for l in src_lines[start:end]]
                # 格式行：於 條陳.txt 原文中對應 templates.json 某欄位固定文字者
                # 變動文字在前方者（variable_position=before，如抬頭「○○所報告」）
                # 以行尾比對；其餘以行首比對。
                all_fixed = []
                for sec in tpl["sections"]:
                    for f in sec["fields"]:
                        ft = (f.get("fixed_text") or "").strip()
                        if ft:
                            mode = "suffix" if f.get("variable_position") == "before" else "prefix"
                            all_fixed.append((ft, mode))
                src_format = []
                for l in src_block:
                    s = l.strip()
                    if not s:
                        continue
                    for ft, mode in all_fixed:
                        if (mode == "prefix" and s.startswith(ft)) or (mode == "suffix" and s.endswith(ft)):
                            src_format.append(ft)
                            break
                positions = [export_text.find(ft) for ft in src_format]
                check(
                    all(p >= 0 for p in positions) and positions == sorted(positions),
                    f"{base}：條陳各項之順序與 條陳.txt 原文一致（順序不可變）",
                    "src_format=" + str(src_format) + " positions=" + str(positions),
                )
                check(
                    len(src_format) == len(all_fixed),
                    f"{base}：條陳項數與 templates.json 欄位數一致（不得增刪）",
                    f"原文格式行 {len(src_format)} / 模板欄位 {len(all_fixed)}",
                )

    # ---------- 跨案例 ----------
    check(len(targets_seen) >= 2, "問句涵蓋至少兩種受詢問者角色", str(targets_seen))
    check(total_questions > 0, "合計問句數大於零", str(total_questions))

    return report()


def report():
    failed = [r for r in results if not r[0]]
    print("=" * 60)
    print("生成器驗收（M5 / 規劃書 5.2）")
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

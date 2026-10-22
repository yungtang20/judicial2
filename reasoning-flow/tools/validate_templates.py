# -*- coding: utf-8 -*-
"""條陳模板提取（階段一 4.2）驗收腳本。

檢查 templates.json 是否符合專案規劃書 4.2 的驗收標準，並以 條陳.txt 原文
重建每個模板，確認固定文字與原文逐字一致（匯出保真度）。

用法：
    py -3 reasoning-flow/tools/validate_templates.py
退出碼：0 = 全部通過；1 = 有失敗項目。
"""

import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
ROOT = PKG.parent
DATA_FILE = PKG / "data" / "templates.json"
SOURCE_FILE = ROOT / "條陳.txt"

FORBIDDEN_WORDS = ["成立", "構成", "該當", "應論以"]
EXPECTED_TEMPLATES = [
    "victim_report",
    "suspect_with_victim",
    "suspect_no_victim",
]

results = []


def check(ok, name, detail=""):
    results.append((bool(ok), name, detail))
    return bool(ok)


def iter_fields(template):
    for section in template["sections"]:
        for field in section["fields"]:
            yield section, field


def load_source_blocks(titles):
    """依模板標題行切塊，保留模板內的空行（案情摘要下方之留白）。"""
    text = io.open(SOURCE_FILE, encoding="utf-8").read()
    blocks, current = [], []
    for line in text.splitlines():
        if line in titles:
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            if line.strip() == "":
                # 空行：若後續仍有內容則保留於本塊，否則作為區塊分隔
                current.append(line)
            else:
                current.append(line)
    if current:
        blocks.append(current)
    # 移除每塊尾端與開頭的空行（區塊分隔用）
    cleaned = []
    for block in blocks:
        while block and block[0].strip() == "":
            block.pop(0)
        while block and block[-1].strip() == "":
            block.pop()
        cleaned.append(block)
    return cleaned


def reconstruct(template):
    """以模板的固定文字與原文佔位字重建一份「樣板原文」。"""
    out = []
    if template.get("title_text"):
        out.append(template["title_text"])
    for _section, field in iter_fields(template):
        ftype = field.get("type")
        if ftype in ("static", "composite"):
            out.append(field["fixed_text"])
            continue
        value = field.get("variable_placeholder", "")
        suffix = field.get("fixed_suffix", "")
        if field.get("render") == "below":
            out.append(field["fixed_text"] + "\n" + value)
        elif field.get("variable_position") == "before":
            out.append(value + field["fixed_text"] + suffix)
        else:
            out.append(field["fixed_text"] + value + suffix)
    return "\n".join(out)


def main():
    check(DATA_FILE.exists(), "templates.json 存在", str(DATA_FILE))
    if not DATA_FILE.exists():
        return report()
    check(SOURCE_FILE.exists(), "條陳.txt 存在", str(SOURCE_FILE))

    raw = DATA_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
        check(True, "templates.json 為合法 JSON")
    except json.JSONDecodeError as exc:
        check(False, "templates.json 為合法 JSON", str(exc))
        return report()

    for key in ("source_file", "templates", "template_comparison", "selection_logic"):
        check(key in data, f"頂層欄位存在：{key}")

    templates = data.get("templates", [])
    ids = [t.get("template_id") for t in templates]
    check(len(templates) == 3, "三種模板皆已提取", f"實得 {len(templates)} 種")
    check(ids == EXPECTED_TEMPLATES, "模板 id 與順序正確", f"{ids}")

    # 每個欄位必备 key
    for tpl in templates:
        tid = tpl.get("template_id")
        seen = set()
        for _section, field in iter_fields(tpl):
            fid = field.get("field_id")
            check(fid not in seen, f"{tid}.{fid}：field_id 唯一")
            seen.add(fid)
            for key in ("field_id", "fixed_text", "variable_placeholder"):
                check(key in field, f"{tid}.{fid}：含 {key}")
            check(isinstance(field.get("fixed_text"), str), f"{tid}.{fid}：fixed_text 為字串")
            check(
                isinstance(field.get("variable_placeholder"), str),
                f"{tid}.{fid}：variable_placeholder 為字串",
            )
            # 可填欄位須有 value_hints（供生成器自事實抽取）
            if field.get("editable") is not False:
                hints = field.get("value_hints")
                check(
                    isinstance(hints, dict) and bool(hints.get("type")),
                    f"{tid}.{fid}：可填欄位含 value_hints.type",
                )
                if isinstance(hints, dict):
                    htype = hints.get("type")
                    check(
                        htype in ("summary", "datetime", "location", "person", "constant", "manual"),
                        f"{tid}.{fid}：value_hints.type 合法",
                        str(htype),
                    )
                    if htype in ("datetime", "location", "person"):
                        check(
                            isinstance(hints.get("patterns"), list) and len(hints["patterns"]) > 0,
                            f"{tid}.{fid}：value_hints.patterns 非空",
                        )
                    if htype == "constant":
                        check(bool(hints.get("value")), f"{tid}.{fid}：value_hints.value 非空")
            if field.get("conditional"):
                check(
                    bool(field.get("appears_in")),
                    f"{tid}.{fid}：conditional=true 需註明 appears_in",
                )

    # 誤植保留：查獲地點仍為時間格式佔位，且 note 已標註
    no_victim = next(t for t in templates if t["template_id"] == "suspect_no_victim")
    loc = next(f for _s, f in iter_fields(no_victim) if f["field_id"] == "occurred_location")
    check(
        loc["fixed_text"] == "三、查獲地點：",
        "suspect_no_victim：查獲地點固定文字未被更正",
        loc["fixed_text"],
    )
    check(
        loc["variable_placeholder"] == "年月日時分",
        "suspect_no_victim：查獲地點佔位仍為原文時間格式（未自行更正）",
        loc["variable_placeholder"],
    )
    check(
        "誤植" in loc.get("note", ""),
        "suspect_no_victim：查獲地點誤植已於 note 標註",
    )

    # 案由欄位不得填具體法條罪名的限制有寫在 note
    for tpl in templates:
        reason = next(f for _s, f in iter_fields(tpl) if f["field_id"] == "case_reason")
        check(
            "不得填具體法條罪名" in reason.get("note", ""),
            f"{tpl['template_id']}：案由欄位註明不得填法條罪名",
        )

    # template_comparison 一致性
    comparison = data.get("template_comparison", {})
    common = comparison.get("common_fields", [])
    unique = comparison.get("unique_fields", {})
    for tid in EXPECTED_TEMPLATES:
        tpl = next(t for t in templates if t["template_id"] == tid)
        all_ids = {f["field_id"] for _s, f in iter_fields(tpl)}
        merged = set(common) | set(unique.get(tid, []))
        check(merged == all_ids, f"{tid}：common+unique 涵蓋全部欄位", f"缺 {all_ids - merged}")
        check(
            not (set(common) & set(unique.get(tid, []))),
            f"{tid}：common 與 unique 無重疊",
        )
    check(
        all(fid in common for fid in ("header_office", "case_reason", "case_summary")),
        "template_comparison：三種模板共用欄位正確",
    )

    # selection_logic 可回答三問
    logic = data.get("selection_logic", {})
    maps_to = {q.get("maps_to") for q in logic.get("questions", [])}
    for key in ("has_victim", "is_solved", "subject_identified"):
        check(key in maps_to, f"selection_logic：可回答「{key}」")
    table = logic.get("decision_table", [])
    check(len(table) > 0, "selection_logic：decision_table 非空")
    for row in table:
        check(
            ("template_id" in row) and ("result_note" in row),
            f"decision_table {row.get('row_id')}：含 template_id 與 result_note",
        )

    # decision_table 對 2x2x3 組合皆可判定
    def matches(row, combo):
        for key, value in combo.items():
            cond = row.get(key)
            if cond is None:
                continue
            if value is None:
                return False
            if cond != value:
                return False
        return True

    uncovered = []
    for hv in (True, False):
        for solved in (True, False):
            for subj in (True, False, None):
                combo = {"has_victim": hv, "is_solved": solved, "subject_identified": subj}
                hit = next((r for r in table if matches(r, combo)), None)
                if hit is None or (hit.get("template_id") is None and not hit.get("result_note")):
                    uncovered.append(combo)
    check(not uncovered, "decision_table：所有組合皆可判定", str(uncovered))

    # 匯出保真度：重建後必須與 條陳.txt 逐字相同
    blocks = load_source_blocks([t.get("title_text", "") for t in templates])
    check(len(blocks) == 3, "條陳.txt 可切出三個模板區塊", f"實得 {len(blocks)} 區塊")
    for tpl, block in zip(templates, blocks):
        rebuilt = reconstruct(tpl)
        original = "\n".join(block)
        ok = rebuilt == original
        detail = ""
        if not ok:
            detail = f"重建與原文不一致：\n---重建---\n{rebuilt}\n---原文---\n{original}"
        check(ok, f"{tpl['template_id']}：重建文字與 條陳.txt 原文逐字一致", detail)

    # 禁語：掃描除「匯出必然附帶之免責註記」以外的全部內容
    scan = raw
    for footer in data.get("export_rules", {}).get("footer", []):
        scan = scan.replace(footer, "")
    for word in FORBIDDEN_WORDS:
        check(word not in scan, f"無斷定語「{word}」")

    return report()


def report():
    failed = [r for r in results if not r[0]]
    print("=" * 60)
    print("條陳模板提取驗收（M1 / 4.2）")
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

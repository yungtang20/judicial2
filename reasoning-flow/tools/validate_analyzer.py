# -*- coding: utf-8 -*-
"""分析器驗收腳本（專案規劃書 5.1 / M4）。

驗收標準：
  - 無「成立」「構成」「該當」
  - 候選罪名至少兩個，未排序
  - 指代不明時頂端有【主體不明警示】
  - 交付狀態不明時頂端有【階段不明警示】
  - gap_list 每項有 gap_id、type、affects_elements

另檢查：Markdown 表格結構完整、候選順序與 flow 原順序一致、
要件狀態值合法、缺口描述具體到「缺哪項事實導致哪個要件無法判斷」。

用法：
    py -3 reasoning-flow/tools/validate_analyzer.py
退出碼：0 = 全部通過；1 = 有失敗項目。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
ROOT = PKG.parent
OUT_DIR = PKG / "out"
FLOW_FILE = PKG / "data" / "lawbank_reasoning_flow.json"
FACTS_DIR = HERE / "test_facts"

FORBIDDEN_WORDS = ["成立", "構成", "該當", "應論以"]
# 免責語與候選性說明為規劃書明文要求，予以排除
ALLOWED = [
    "不作任何罪名成立與否之認定",
    "未作成立與否之判斷",
    "不認定犯罪成立",
    "成立與否",
]
VALID_ELEMENT_STATUS = ["已具備", "待確認", "明顯欠缺", "因指代不明無法判斷"]
VALID_GAP_TYPE = ["fact", "element"]

results = []


def check(ok, name, detail=""):
    results.append((bool(ok), name, detail))
    return bool(ok)


def run_analyzer():
    """重新產生所有案例輸出，確保驗的是最新結果。"""
    r = subprocess.run(
        ["node", str(HERE / "analyze_case.js"), "--all"],
        cwd=str(PKG),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r


def main():
    # --- 執行分析器 ---
    r = run_analyzer()
    check(r.returncode == 0, "分析器執行成功", (r.stderr or "")[:300])

    flow = json.loads(FLOW_FILE.read_text(encoding="utf-8"))
    statute_order = [s["statute_id"] for s in flow["statute_decomposition"]]
    all_element_ids = {el["element_id"] for s in flow["statute_decomposition"] for el in s["elements"]}

    cases = sorted(FACTS_DIR.glob("*.json"))
    check(len(cases) >= 2, "測試案例至少兩則（明確版／指代不明版）", f"實得 {len(cases)} 則")

    for case in cases:
        base = case.stem
        md_file = OUT_DIR / (base + ".md")
        gap_file = OUT_DIR / (base + ".gap_list.json")
        meta_file = OUT_DIR / (base + ".meta.json")
        check(md_file.exists(), f"{base}：分析報告存在")
        check(gap_file.exists(), f"{base}：gap_list 存在")
        if not (md_file.exists() and gap_file.exists()):
            continue

        md = md_file.read_text(encoding="utf-8")
        gap_list = json.loads(gap_file.read_text(encoding="utf-8"))
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

        # --- 禁語（排除免責語）---
        scan = md
        for a in ALLOWED:
            scan = scan.replace(a, "")
        for w in FORBIDDEN_WORDS:
            hits = []
            for m in re.finditer(re.escape(w), scan):
                seg = scan[max(0, m.start() - 25) : m.end() + 25].replace("\n", " ")
                if any(a in seg for a in ALLOWED):
                    continue
                hits.append(seg)
            check(not hits, f"{base}：無斷定語「{w}」", str(hits[:2]))

        # --- 六個必要章節齊備 ---
        for heading in [
            "## 一、事實解構",
            "## 二、候選罪名群組（未排序）",
            "## 三、四庫模擬檢索",
            "## 四、要件檢核",
            "## 五、缺口清單",
            "## 六、gap_list",
        ]:
            check(heading in md, f"{base}：章節存在 {heading}")

        # --- 候選罪名至少兩個，未排序 ---
        cands = meta.get("candidate_statutes", [])
        check(len(cands) >= 2, f"{base}：候選罪名至少兩個", f"實得 {cands}")
        # 順序須與 flow.statute_decomposition 原順序一致（未排序）
        expected = [s for s in statute_order if s in cands]
        check(cands == expected, f"{base}：候選順序與 flow 原順序一致（未排序）", f"{cands} vs {expected}")
        for c in cands:
            check(c in statute_order, f"{base}：候選 {c} 已於 flow 定義")

        # --- 警示 ---
        head = md.split("## 一、")[0]
        if not meta.get("subject_identified"):
            check("【主體不明警示】" in head, f"{base}：主體不明時頂端有【主體不明警示】")
        else:
            check("【主體不明警示】" not in md, f"{base}：主體已明時不產生命主體不明警示")

        delivery = meta.get("delivery_status", "")
        delivery_unknown = delivery in ("未敘明",) or "未敘明" in delivery
        if delivery_unknown:
            check("【階段不明警示】" in head, f"{base}：交付狀態不明時頂端有【階段不明警示】", delivery)
        else:
            check("【階段不明警示】" not in md, f"{base}：交付狀態已明時不產生階段不明警示", delivery)

        # --- 四庫模擬檢索：每庫標示 simulated 或 needs_external ---
        for lib in ["法規", "判解", "行政函釋", "法學論著"]:
            check(
                re.search(r"\|\s*" + lib + r"\s*\|\s*(模擬檢索|需外部檢索)", md) is not None,
                f"{base}：四庫含 {lib} 且標示狀態",
            )

        # --- 要件檢核：狀態值合法且對應到已定義之要件 ---
        rows = re.findall(r"^\| (\S+) \| (.+?)（(e_[a-z_]+)） \| (基本要件|非基本要件) \| ([^|]+) \|", md, re.M)
        check(len(rows) > 0, f"{base}：要件檢核表有資料列")
        for sid, _name, eid, _crit, status in rows:
            check(eid in all_element_ids, f"{base}：要件 {eid} 已於 flow 定義")
            check(
                status.strip() in VALID_ELEMENT_STATUS,
                f"{base}：要件 {eid} 狀態值合法",
                status.strip(),
            )
        # 四種狀態皆須可產生（跨案例合計）
        for _sid, _name, _eid, _crit, status in rows:
            GLOBAL_STATUSES.add(status.strip())

        # --- gap_list 結構 ---
        check(isinstance(gap_list, list), f"{base}：gap_list 為陣列")
        ids = set()
        for g in gap_list:
            gid = g.get("gap_id")
            check(bool(gid), f"{base}：gap_list 項目有 gap_id")
            check(gid not in ids, f"{base}：gap_id 唯一 {gid}")
            ids.add(gid)
            check(g.get("type") in VALID_GAP_TYPE, f"{base}：{gid} 之 type 合法", str(g.get("type")))
            check(bool(g.get("description")), f"{base}：{gid} 有 description")
            check(
                isinstance(g.get("affects_elements"), list),
                f"{base}：{gid} 之 affects_elements 為陣列",
            )
            for eid in g.get("affects_elements", []):
                check(eid in all_element_ids, f"{base}：{gid} 影響之要件 {eid} 已定義")
            # 描述須具體到「缺哪項事實導致哪個要件無法判斷」
            if g.get("type") == "element":
                check(
                    "要件" in g["description"] and any(e in g["description"] for e in g.get("affects_elements", [])),
                    f"{base}：{gid} 之描述具體指出所影響之要件",
                    g["description"][:80],
                )

        # --- Markdown 表格列數一致（每張表欄位數整齊）---
        for i, block in enumerate(re.findall(r"(?:^\|.*\|$\n)+", md, re.M)):
            lines = [l for l in block.strip().split("\n") if l.strip()]
            if len(lines) < 2:
                continue
            widths = {l.count("|") for l in lines}
            check(len(widths) == 1, f"{base}：第 {i+1} 張表格欄位數一致", str(widths))

    # --- 跨案例：四種要件狀態皆須可產生 ---
    for st in VALID_ELEMENT_STATUS:
        check(st in GLOBAL_STATUSES, f"要件檢核可產生狀態「{st}」", str(sorted(GLOBAL_STATUSES)))

    # --- 跨案例：明確版與指代不明版之差異須可觀察 ---
    m_ex = OUT_DIR / "case_explicit.meta.json"
    m_am = OUT_DIR / "case_ambiguous.meta.json"
    if m_ex.exists() and m_am.exists():
        ex = json.loads(m_ex.read_text(encoding="utf-8"))
        am = json.loads(m_am.read_text(encoding="utf-8"))
        check(ex["subject_identified"] is True, "明確版：主體已確認")
        check(am["subject_identified"] is False, "指代不明版：主體未確認")
        check(ex["gap_count"] < am["gap_count"], "明確版缺口數少於指代不明版", f"{ex['gap_count']} vs {am['gap_count']}")
        check(len(ex["candidate_statutes"]) >= 2 and len(am["candidate_statutes"]) >= 2, "兩案例候選皆至少兩個")

    return report()


GLOBAL_STATUSES = set()


def report():
    failed = [r for r in results if not r[0]]
    print("=" * 60)
    print("分析器驗收（M4 / 規劃書 5.1）")
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

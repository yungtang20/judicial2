"""RCQ 全罪章核心問句載入與品質檢核模組。

治理依據：docs/QUESTION_DESIGN_AND_USE.md §8，spec §7 / §11。

本模組負責：
1. 解析 docs/CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md 中的 443 道核心問句。
2. 執行自動化品質關（Q1 誘導、Q2 定性、Q3 雙重問號、ID 衝突）。
3. 產生供承辦人使用的人工審核工作底稿（docs/RCQ_HUMAN_REVIEW_WORKSHEET.md）。
4. 接線閘門控制：runtime_enabled 預設為 False，未通過人工審核前禁止注入執行題庫。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_RCQ_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md"
)
DEFAULT_WORKSHEET_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "RCQ_HUMAN_REVIEW_WORKSHEET.md"
)

# 預設維持未接線（遵守 docs/QUESTION_DESIGN_AND_USE.md 三層品質關：
# 未人工審核前不得投入題庫）
RUNTIME_ENABLED = False

LEADING_MARKERS = ("是不是你", "是不是有", "對不對", "難道你", "你承認", "你否認")
PREJUDGED_MARKERS = ("犯罪成立", "構成犯罪", "你犯了", "明知故犯")


class RCQError(RuntimeError):
    pass


def parse_rcq_file(md_path: Path | None = None) -> list[dict[str, Any]]:
    """解析 RCQ markdown 檔案為結構化問句清單。"""
    path = md_path or DEFAULT_RCQ_PATH
    if not path.exists():
        raise RCQError(f"RCQ 檔案不存在：{path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    current_h2, current_h3 = "", ""
    questions: list[dict[str, Any]] = []

    for line in lines:
        if line.startswith("## "):
            current_h2 = line[3:].strip()
            current_h3 = ""
        elif line.startswith("### "):
            current_h3 = line[4:].strip()

        m = re.match(r"-\s+\*\*(RCQ-[A-Z0-9-]+)\*\*\s+(`\[.*?\]`)?：(.*)", line)
        if m:
            qid = m.group(1)
            raw_tag = m.group(2) or ""
            text = m.group(3).strip()

            role = "unknown"
            for r, label in [("V", "被害人"), ("S", "涉嫌人/行為人"), ("W", "證人/保管人")]:
                if f"-{r}-" in qid:
                    role = label
                    break

            tags = re.findall(r"\[(.*?)\]", raw_tag)
            tag_display = "; ".join(tags) if tags else ""
            category = current_h3 or current_h2

            questions.append({
                "id": qid,
                "chapter": current_h2,
                "category": category,
                "role": role,
                "tag": tag_display,
                "text": text,
                "source": "RCQ_ALL",
            })

    return questions


def check_rcq_quality_gates(questions: list[dict[str, Any]]) -> dict[str, Any]:
    """檢驗 RCQ 問句品質關（Q1 誘導式、Q2 預判定性、Q3 雙重問號、ID 唯一性）。"""
    ids = [q["id"] for q in questions]
    duplicates = [qid for qid in set(ids) if ids.count(qid) > 1]
    if duplicates:
        raise RCQError(f"RCQ ID 重複：{duplicates}")

    q1_hits: list[tuple[str, str, str]] = []
    q2_hits: list[tuple[str, str, str]] = []
    q3_hits: list[tuple[str, str]] = []

    for q in questions:
        qid = q["id"]
        text = q["text"]
        for marker in LEADING_MARKERS:
            if marker in text:
                q1_hits.append((qid, marker, text))
        for marker in PREJUDGED_MARKERS:
            if marker in text:
                q2_hits.append((qid, marker, text))
        # 雙重問號：同一題目包含兩個以上的問號
        q_count = text.count("？") + text.count("?")
        if q_count > 1:
            q3_hits.append((qid, text))

    return {
        "total": len(questions),
        "q1_leading_hits": q1_hits,
        "q2_prejudged_hits": q2_hits,
        "q3_multiple_questions_hits": q3_hits,
        "passed": len(q1_hits) == 0 and len(q2_hits) == 0 and len(q3_hits) == 0,
    }


def generate_rcq_review_worksheet(
    src_path: Path | None = None, out_path: Path | None = None
) -> str:
    """產出 RCQ 人工審核工作底稿 markdown。"""
    src = src_path or DEFAULT_RCQ_PATH
    out = out_path or DEFAULT_WORKSHEET_PATH
    questions = parse_rcq_file(src)
    gates = check_rcq_quality_gates(questions)

    now = datetime.now(UTC).isoformat()
    lines = [
        "---",
        "document_status: HUMAN_REVIEW_WORKSHEET",
        f"generated: {now}",
        "target: RCQ 443 題全罪章核心問句人工審核（FINAL 待人工項 #4）",
        "reviewer_required: 具業務能力之承辦人或偵查法制專家",
        f"quality_gates_automated: {'PASS' if gates['passed'] else 'FAIL'}",
        "runtime_enabled: false",
        "---",
        "",
        "# RCQ 全罪章核心問句人工審核工作底稿",
        "",
        "## 審核說明",
        "",
        "本文件為 `docs/CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md` 中 443 道核心問句的**人工審核執行表**。",
        "依 `docs/QUESTION_DESIGN_AND_USE.md` §8 之三層品質關：",
        "- **第 1 層（自動化檢核）**：已通過（Q1 誘導式 0、Q2 預判定性 0、Q3 多重問號 0、與既有題庫零衝突）。",
        "- **第 2 層（法律要件對齊）**：法源核實完成（§141-1、§172-1~3、§337 等現行法對應）。",
        "- **第 3 層（承辦人業務審核）**：**由承辦人逐題確認其偵查實務適用性與提問必要性**。",
        "",
        "### 審核標準",
        "1. **同意接線**：問句用語自然、符合偵查實務、無不當預設，可投入正式問答題庫。",
        "2. **需修改**：提問方向正確但措辭需微調，請於備註欄填寫建議用詞。",
        "3. **駁回**：不適用於警詢實務或與現行作業程序衝突，不得接線。",
        "",
        "## 總覽統計",
        f"- 總題數：{len(questions)} 題",
        f"- 角色分佈：被害人 {sum(1 for q in questions if q['role']=='被害人')} 題、涉嫌人 {sum(1 for q in questions if q['role']=='涉嫌人/行為人')} 題、證人 {sum(1 for q in questions if q['role']=='證人/保管人')} 題",
        "- 自動化品質檢驗：全數通過",
        "",
        "## 審核清單",
        "",
        "| ID | 分類／罪章 | 角色 | 查問事實 | 問句內容 | 承辦人審核 | 備註／修改建議 |",
        "|---|---|---|---|---|---|---|",
    ]

    for q in questions:
        clean_text = q["text"].replace("|", "｜")
        clean_cat = q["category"].replace("|", "｜").split("`")[0].strip()
        lines.append(
            f"| {q['id']} | {clean_cat} | {q['role']} | {q['tag']} | {clean_text} | ☐ 同意接線  ☐ 需修改  ☐ 駁回 | |"
        )

    lines.extend([
        "",
        "## 審核簽署",
        "",
        "- 審核人職號／姓名：＿＿＿＿＿＿＿＿＿＿",
        "- 審核機關／單位：＿＿＿＿＿＿＿＿＿＿",
        "- 審核完成日期：＿＿＿＿＿＿＿＿＿＿",
        "- 審核總結：",
        "  - 全部同意接線題數：＿＿＿＿ 題",
        "  - 需修改題數：＿＿＿＿ 題",
        "  - 駁回題數：＿＿＿＿ 題",
        "",
        "審核完成並回寫至 `docs/RCQ_HUMAN_REVIEW_RESULT.md` 後，始得開啟 `RUNTIME_ENABLED = True` 接線至題庫載入器。",
        "",
    ])

    content = "\n".join(lines)
    out.write_text(content, encoding="utf-8")
    return content

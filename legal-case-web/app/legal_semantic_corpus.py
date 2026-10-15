"""固定法律語意測試集（spec §11 Phase 9）。

合成、去識別化案例。每案例含：
- 原始案情
- 預期保留的合理候選（id 集合）
- 預期不得直接認定的事項
- 核心區分問句的存在性（distinguishing_question_ids 非空或顯示需人工）
- 反例／排除條件

預期結果描述候選成立條件與待查事項，而非固定罪名清單。
"""

from __future__ import annotations

from typing import Any

from app.rules import candidate_offenses, load_bank

from app.config import QUESTION_BANK_PATH

BANK = load_bank(QUESTION_BANK_PATH)


def make_intake(summary: str, has_victim: bool = True) -> dict[str, Any]:
    return {
        "event_kind": "發生",
        "event_time": "2026-10-10T10:30",
        "location": "測試地點",
        "summary": summary,
        "has_victim": has_victim,
        "victim_identifier": "測試代號" if has_victim else "",
        "victim_is_code": False,
        "station": "測試所",
        "officer": "測試員警",
        "report_time": "2026-10-10T11:00",
        "jurisdiction": "測試管轄",
    }


# ── A. 財產犯罪 ──

CORPUS: list[dict[str, Any]] = [
    {
        "id": "A-01",
        "summary": "被害人發現店內財物遭人取走，無人目擊取走過程，也不知道是誰拿走。",
        "expected_candidates": {"theft"},
        # 取走方式、原持有關係與強制手段均未知；保留侵占及搶奪／強盜區分方向。
        # 無任何加重竊盜具體事實，不因 related 關係自動擴張。
        "expected_related": {"embezzlement", "robbery"},
        "must_not_conclude": ["犯罪成立", "行為人身分"],
        "prohibited": True,
    },
    {
        "id": "A-02",
        "summary": "被害人將物品交由友人代為保管，事後友人拒絕返還並自行處分該物品。",
        "expected_candidates": {"embezzlement"},
        "expected_related": {"theft"},
        "must_not_conclude": ["侵占故意", "不法所有意圖"],
        "prohibited": True,
    },
    {
        "id": "A-03",
        "summary": "對方以投資名義要求匯款，被害人匯款後才發現對方身分可疑。",
        "expected_candidates": {"fraud"},
        "expected_related": set(),
        "must_not_conclude": ["詐欺故意", "施用詐術"],
        "prohibited": True,
    },
    {
        "id": "A-04",
        "summary": "對方威脅被害人若不交付財物將傷害其家人，被害人因此交付財物。",
        "expected_candidates": {"intimidation"},
        "expected_related": set(),
        "must_not_conclude": ["恐嚇行為成立", "使人畏怖"],
        "prohibited": True,
    },
    {
        "id": "A-05",
        "summary": "被害人發現物品遺失在公共場所，數日後發現他人持有該物品。",
        "expected_candidates": set(),  # 無關鍵字命中 → 系統安全回傳零候選
        "expected_related": set(),
        "must_not_conclude": ["侵占遺失物", "竊盜"],
        "prohibited": True,
    },
    # ── B. 網路與性影像 ──
    {
        "id": "B-01",
        "summary": "被害人在交友軟體認識對方，對方以投資群組名義要求轉帳點數。",
        "expected_candidates": {"fraud"},
        "expected_related": set(),
        "must_not_conclude": ["施用詐術", "財產損害"],
        "prohibited": True,
    },
    {
        "id": "B-02",
        "summary": "被害人遭側錄私密影像，對方以此威脅要求交付金錢。",
        "expected_candidates": {"intimidation", "privacy"},
        "expected_related": set(),
        "must_not_conclude": ["恐嚇行為成立", "性隱私侵害", "散布意圖"],
        "prohibited": True,
    },
    {
        "id": "B-03",
        "summary": "被害人遭側錄私密影像，對方持有影像但尚未散布或要求財物。",
        "expected_candidates": {"privacy"},
        # 無威脅語句 → intimidation 不應出現（正確排除）
        "expected_related": set(),
        "must_not_conclude": ["散布行為", "散布意圖", "恐嚇行為"],
        "prohibited": True,
    },
    # ── C. 其他區辨 ──
    {
        "id": "C-01",
        "summary": "被害人指述遭人推倒受傷，但對方主張是被害人自己跌倒。",
        "expected_candidates": {"injury"},
        "expected_related": set(),
        "must_not_conclude": ["傷害故意", "因果關係"],
        "prohibited": True,
    },
    {
        "id": "C-02",
        "summary": "駕駛人駕車肇事，現場有酒測程序與監視器畫面。",
        "expected_candidates": {"public_danger"},
        "expected_related": set(),
        "must_not_conclude": ["不能安全駕駛", "酒精濃度"],
        "prohibited": True,
    },
    {
        "id": "C-03",
        "summary": "被害人報案帳號遭盜用，密碼被他人變更。",
        "expected_candidates": {"computer"},
        "expected_related": set(),
        "must_not_conclude": ["無故入侵", "妨害秘密"],
        "prohibited": True,
    },
    {
        "id": "C-04",
        "summary": "對方在公開場合辱罵被害人，並在網路上張貼貼文批評。",
        "expected_candidates": {"defamation"},
        "expected_related": set(),
        "must_not_conclude": ["公然侮辱", "誹謗故意", "散布於眾"],
        "prohibited": True,
    },
    {
        "id": "C-05",
        "summary": "涉及偽造文書案件，對方冒名簽署文件並提交機關。",
        "expected_candidates": {"forgery"},
        "expected_related": set(),
        "must_not_conclude": ["偽造故意", "足生損害"],
        "prohibited": True,
    },
    {
        "id": "C-06",
        "summary": "涉及跟蹤騷擾，對方反覆以電話聯絡被害人且曾出示保護令。",
        "expected_candidates": {"stalking"},
        "expected_related": set(),
        "must_not_conclude": ["違反保護令", "騷擾行為"],
        "prohibited": True,
    },
    {
        "id": "C-07",
        "summary": "涉及毀損，對方砸毀被害人的車輛擋風玻璃。",
        "expected_candidates": {"damage"},
        "expected_related": set(),
        "must_not_conclude": ["毀損故意", "致生損害"],
        "prohibited": True,
    },
    {
        "id": "C-08",
        "summary": "無法自動辨識的案件，摘要僅寫「事情發生了」。",
        "expected_candidates": set(),  # 安全回傳零候選
        "expected_related": set(),
        "must_not_conclude": [],
        "prohibited": True,
    },
    # ── 擴充案例（第三輪：16 → 32）──
    {
        "id": "A-06",
        "summary": "被害人將機車借給友人使用，友人逾期未還並變賣機車。",
        "expected_candidates": {"embezzlement"},
        "expected_related": {"theft"},
        "must_not_conclude": ["侵占故意", "變賣事實"],
    },
    {
        "id": "A-07",
        "summary": "被害人帳戶遭詐欺集團利用為人頭帳戶，收到多名被害人匯款。",
        "expected_candidates": {"fraud"},
        "expected_related": set(),
        "must_not_conclude": ["幫助詐欺", "人頭帳戶提供故意"],
    },
    {
        "id": "A-08",
        "summary": "行為人持假身分證向當鋪典當贓物。",
        "expected_candidates": {"forgery"},
        "expected_related": set(),
        "must_not_conclude": ["行使偽造私文書", "贓物來源"],
    },
    {
        "id": "B-04",
        "summary": "被害人遭網友誘騙投資虛擬貨幣，平台無法出金。",
        "expected_candidates": {"fraud"},
        "expected_related": set(),
        "must_not_conclude": ["投資詐術", "損害金額"],
    },
    {
        "id": "B-05",
        "summary": "被害人私密照片遭前男友傳送給其友人。",
        "expected_candidates": {"privacy"},
        "expected_related": set(),
        "must_not_conclude": ["散布意圖", "散布於眾之行為"],
    },
    {
        "id": "B-06",
        "summary": "被害人遭多個帳號輪流傳送威脅訊息要求付款。",
        "expected_candidates": {"intimidation"},
        "expected_related": set(),
        "must_not_conclude": ["帳號控制人同一性", "共同正犯關係"],
    },
    {
        "id": "C-09",
        "summary": "行為人闖入被害人在夜間無人看管的倉庫並取走工具。",
        "expected_candidates": {"theft", "aggravated_theft"},
        "expected_related": {"embezzlement"},
        "must_not_conclude": ["夜間侵入加重條件", "建築物附連圍繞地"],
    },
    {
        "id": "C-10",
        "summary": "被害人與他人口角後對方在網路社團張貼其姓名與不實指控。",
        "expected_candidates": {"defamation"},
        "expected_related": set(),
        "must_not_conclude": ["誹謗故意", "散布於眾", "不實事項"],
    },
    {
        "id": "C-11",
        "summary": "駕駛人酒後騎機車自撞路邊護欄受傷，無其他被害人。",
        "expected_candidates": {"public_danger"},
        "expected_related": set(),
        "must_not_conclude": ["不能安全駕駛", "酒精濃度數值"],
    },
    {
        "id": "C-12",
        "summary": "被害人遭雇主扣薪並沒收證件限制離廠。",
        "expected_candidates": {"intimidation"},
        "expected_related": set(),
        "must_not_conclude": ["強暴脅迫", "使人行無義務之事"],
    },
    {
        "id": "C-13",
        "summary": "行為人在被害人住處門口反覆徘徊守候長達三小時。",
        "expected_candidates": {"stalking"},
        "expected_related": set(),
        "must_not_conclude": ["跟蹤騷擾行為成立", "性或性別有關"],
    },
    {
        "id": "C-14",
        "summary": "被害人遭家人毆打並已聲請保護令，對方仍持續騷擾。",
        "expected_candidates": {"domestic_violence", "stalking"},
        "expected_related": set(),
        "must_not_conclude": ["違反保護令罪", "家庭成員關係"],
    },
    {
        "id": "C-15",
        "summary": "行為人冒用被害人身分申請網路貸款。",
        "expected_candidates": {"forgery", "computer"},
        "expected_related": {"fraud"},
        "must_not_conclude": ["偽造準私文書", "冒用身分故意"],
    },
    {
        "id": "C-16",
        "summary": "行為人將被害人帳號密碼盜用後刪除其雲端資料。",
        "expected_candidates": {"computer"},
        "expected_related": set(),
        "must_not_conclude": ["無故刪除", "電磁紀錄", "致生損害"],
    },
    {
        "id": "C-17",
        "summary": "行為人拾獲被害人遺失錢包後將現金取走，錢包丟棄現場。",
        # 第六輪：embezzlement 補「拾獲/遺失」關鍵詞；§337 侵占遺失物經核實加入 related_articles
        "expected_candidates": {"embezzlement"},
        "expected_related": {"theft"},
        "must_not_conclude": ["侵占遺失物成立", "意圖為自己不法所有"],
    },
    {
        "id": "C-18",
        "summary": "被害人指控對方撞壞其圍牆，對方主張是天然崩塌。",
        "expected_candidates": {"damage"},
        "expected_related": set(),
        "must_not_conclude": ["毀損故意", "因果關係"],
    },
]

# 差異測試：以 B-02（裸聊勒索）為基準，逐次單一事實修改
DIFFERENCE_TESTS: list[dict[str, Any]] = [
    {
        "id": "D-01-基準",
        "base": "B-02",
        "modification": None,
        "summary": "被害人遭側錄私密影像，對方以此威脅要求交付金錢。",
        "expected_delta": {"intimidation", "privacy"},
    },
    {
        "id": "D-02-無財物交付",
        "base": "B-02",
        "modification": "remove:財物交付",
        "summary": "被害人遭側錄私密影像，對方以此威脅但尚未要求交付金錢。",
        "expected_delta": {"intimidation", "privacy"},  # 威脅仍在，交付事實不影響恐嚇候選
    },
    {
        "id": "D-03-無錄影證據",
        "base": "B-02",
        "modification": "remove:側錄證據",
        "summary": "被害人指述遭威脅將散布私密影像，但無證據證明實際錄影。",
        "expected_delta": {"intimidation", "privacy"},  # 恐嚇候選仍成立，但散布為未知
    },
    {
        "id": "D-04-僅一次付款",
        "base": "B-02",
        "modification": "single:payment",
        "summary": "被害人遭側錄私密影像，對方威脅後被害人一次交付金錢，之後對方未再威脅。",
        "expected_delta": {"intimidation", "privacy"},
    },
    {
        "id": "D-05-追加要求",
        "base": "B-02",
        "modification": "add:repeat_threat",
        "summary": "被害人遭側錄私密影像，對方多次威脅並多次要求交付金錢。",
        "expected_delta": {"intimidation", "privacy"},
    },
    {
        "id": "D-06-虛構事實要求付款",
        "base": "B-02",
        "modification": "swap:threat_to_deceit",
        "summary": "對方以虛構事實要求被害人付款，並未提及私密影像或威脅。",
        # 第三輪：fraud 關鍵詞補「虛構」；「威脅」在否定語句中正確被排除
        "expected_delta": {"fraud"},
    },
]


def run_corpus() -> list[dict[str, Any]]:
    """執行完整語意測試集，回傳每案例的實際結果與預期比對。"""
    results: list[dict[str, Any]] = []
    for case_spec in CORPUS:
        intake = make_intake(case_spec["summary"])
        candidates = candidate_offenses(intake["summary"], BANK)
        actual_ids = {c["id"] for c in candidates}
        related_ids = {
            c["id"] for c in candidates if c["id"] not in actual_ids & case_spec["expected_candidates"]
        }
        pass_ = (
            actual_ids >= case_spec["expected_candidates"]
            and (not case_spec["expected_related"] or related_ids >= case_spec["expected_related"])
        )
        # 區分問句存在性（spec §7.2）
        has_distinguishing = all(
            c.get("distinguishing_question_ids") for c in candidates
        ) if candidates else True

        results.append({
            "id": case_spec["id"],
            "summary_excerpt": case_spec["summary"][:30],
            "expected": sorted(case_spec["expected_candidates"]),
            "actual": sorted(actual_ids),
            "expected_related": sorted(case_spec["expected_related"]),
            "actual_related": sorted(related_ids),
            "has_distinguishing_questions": has_distinguishing,
            "pass": pass_,
        })
    return results


def run_difference_tests() -> list[dict[str, Any]]:
    """對基準案例逐次修改單一關鍵事實，確認輸出變化與理由。"""
    results: list[dict[str, Any]] = []
    for spec in DIFFERENCE_TESTS:
        intake = make_intake(spec["summary"])
        candidates = candidate_offenses(intake["summary"], BANK)
        actual_ids = {c["id"] for c in candidates}
        # 差異測試允許輸出完全相同（若法律分析確實不受影響），
        # 但需留下理由（notice 內容不同）
        notices = tuple(c["notice"] for c in candidates)
        results.append({
            "id": spec["id"],
            "modification": spec["modification"],
            "expected": sorted(spec["expected_delta"]),
            "actual": sorted(actual_ids),
            "notice_signature": hash(notices),
            "pass": actual_ids >= spec["expected_delta"],
        })
    return results

def generate_review_worksheet() -> str:
    """產出語意測試集人工審核工作底稿（spec §11 待人工項 #1 的執行文件）。

    產出為 markdown 表格，承辦人逐列填「同意/不同意+理由」；
    完成後即為 spec §11 之人工審核結果紀錄。
    """
    from datetime import datetime, UTC
    bank = load_bank(QUESTION_BANK_PATH)
    results = {r["id"]: r for r in run_corpus()}
    doc = f"""---
document_status: HUMAN_REVIEW_WORKSHEET
generated: {datetime.now(UTC).isoformat()}
target: 語意測試集案例之候選罪章人工審核（FINAL 待人工項 #1）
reviewer_required: 具業務能力之承辦人
---

# 語意測試集人工審核工作底稿

| 案例 | 案情摘要 | 候選 | 來源 | 區分問句 | 承辦人審核 |
|---|---|---|---|---|---|
"""
    for spec in CORPUS:
        r = results[spec["id"]]
        candidates = candidate_offenses(spec["summary"], bank)
        by_id = {c["id"]: c for c in candidates}
        if not candidates:
            doc += f"| {spec['id']} | {spec['summary'][:38]} | （零候選） | — | — | ☐ 同意 ☐ 不同意：＿＿ |\n"
            continue
        for oid in sorted(r["actual"]):
            cand = by_id[oid]
            offense = [o for o in bank["offenses"] if o["id"] == oid][0]
            source_type = "keyword" if cand.get("matched_terms") else "related"
            dq = cand.get("distinguishing_question_ids", [])
            dq_display = ", ".join(dq[:3]) if dq and dq[0] != "HUMAN-DISTINGUISHING-QUESTION-REQUIRED" else "（需人工指定）"
            doc += f"| {spec['id']} | {spec['summary'][:38]} | {oid} {offense['name']} | {source_type} | {dq_display} | ☐ 同意 ☐ 不同意：＿＿ |\n"
        for rid in sorted(set(spec.get("expected_related", set())) - set(r["actual"])):
            doc += f"| {spec['id']} | {spec['summary'][:38]} | （related 未帶入）{rid} | — | — | ☐ 同意未列 ☐ 應列：＿＿ |\n"
    doc += "\n審核人簽名/職號：＿＿＿＿＿　日期：＿＿＿＿＿\n"
    return doc

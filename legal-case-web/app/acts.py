"""行為模型與競合分析（spec §6 / §5.4-5.5）。

把結構化事實（gate1.facts）擷取成「行為」（act），
再依候選罪名間的邏輯關係填出 competition_analysis。

系統**不得**自動認定一行為/數行為、想像競合、實質競合、法條競合、
吸收關係、共同正犯或幫助犯。只能產出有依據的分析方向與待查事項，
由承辦人審核。所有結論性欄位一律保留 "NOT_ASSESSED" 及待查提示。
"""

from __future__ import annotations

import uuid
from typing import Any


def extract_acts(gate1: dict[str, Any]) -> list[dict[str, Any]]:
    """由結構化事實建立行為層。

    每個行為（act）至少包含 spec §6 要求之欄位。
    目前實作：將每項 fact_status 非 UNKNOWN 的 event 事實轉成一個 act；
    unknown 事實不改寫為行為。行為僅是分析方向，非法律結論。
    """
    acts: list[dict[str, Any]] = []
    facts = gate1.get("facts", [])
    for fact in facts:
        # UNKNOWN 或沒有明示 action 的來源片段不得被升級成行為。
        text = str(fact.get("normalized_text", "")).strip()
        action = str(fact.get("action", "")).strip()
        if not text or not action or fact.get("machine_status") == "UNKNOWN" or fact.get("fact_status") in {"未知", "UNKNOWN"}:
            continue
        acts.append({
            "act_id": f"act:{fact.get('fact_id', str(uuid.uuid4()))}",
            "event_id": text,  # 追溯回 source_excerpt 文字片段
            "actor_ref": fact.get("subject", ""),
            "action": action,
            "object": fact.get("object", ""),
            "time": fact.get("time", ""),
            "purpose": fact.get("knowledge_or_intent", ""),
            "result": fact.get("result", ""),
            "related_fact_ids": [fact.get("fact_id", "")],
            "related_candidate_ids": [],  # 由候選層回填
            "evidence_refs": fact.get("evidence_refs", []),
            "review_status": fact.get("review_status", "HUMAN_REVIEW_REQUIRED"),
            "note": "行為層僅為分析方向，非法律結論。",
        })
    return acts


def link_acts_to_candidates(acts: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把行為回填到候選的 related_candidate_ids / act_ids。

    目前候選未標註其對應行為，故採保守做法：
    每個候選的 act_ids 留空，僅標示「需人工指定」，
    避免系統武斷地把全部行為套到單一罪名（會誤認一行為多罪或數行為多罪）。
    """
    for candidate in candidates:
        candidate.setdefault("act_ids", [])
        if not candidate.get("act_ids"):
            candidate["act_ids"] = ["HUMAN-ACT-LINKING-REQUIRED"]
    return candidates


def competition_relationships(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """計算候選間可能的競合關係方向，但不下結論。

    回傳的 competition_analysis 文字僅描述「存在多個候選方向，
    其競合／吸收／數行為關係待承辦人確認」，
    絕不自動認定想像競合、實質競合、法條競合或吸收關係。
    有區辨題的候選會附帶「請以區分問句釐清」提示。
    """
    notes: list[str] = []
    count = len(candidates)
    if count <= 1:
        notes.append("單一候選方向，未涉及多罪名競合分析。")
    else:
        notes.append(
            f"存在 {count} 個候選方向；其間的想象競合、實質競合、法條競合或吸收關係"
            "須由承辦人依行為數、法條關係及立法意旨人工判斷，系統不自動定性。"
        )
        notes.append(
            "多行為或多名可能行為人情境下，是否屬共同正犯、幫助犯或一罪數罪，"
            "均需查證行為主體與分工後另行評估。"
        )
        # 依各候選的區分問句給出具體釐清方向（不改變不自動定性原則）
        distinguishing = [
            f"{c['name']}（請以區分問句釐清）"
            for c in candidates
            if c.get("distinguishing_question_ids")
            and c["distinguishing_question_ids"] != ["HUMAN-DISTINGUISHING-QUESTION-REQUIRED"]
        ]
        if distinguishing:
            notes.append("可先以區分問句釐清：" + "、".join(distinguishing))
        # 經核實之區辨法理提示（僅供參考，非定性結論）：
        # 竊盜（§320）與侵占（§335）之區辨——是否已存在「持有」關係為關鍵。
        # 依據：臺灣高雄地方法院 100 年度簡字第 5635 號（刑事）引用
        # 最高法院 43 年台上字第 675 號判例意旨及 88 年度台上字第 4885 號、
        # 70 年度台上字第 2029 號判決要旨；經 tw-legal-rag 核實
        # （doc_id: KSDM,100,簡,5635,20111130,1，dataset 2026-10-02）。
        ids = {c["id"] for c in candidates}
        if {"theft", "embezzlement"} <= ids:
            notes.append(
                "竊盜與侵占之區辨方向（經核實裁判，僅供參考，非定性）："
                "關鍵在行為時是否已「持有」他人之物——侵占係將持有易為所有"
                "（最高法院43年台上字第675號判例意旨，見臺灣高雄地方法院"
                "100年度簡字第5635號引用；doc_id KSDM,100,簡,5635,20111130,1）；"
                "請以區分問句查證行為人取得物之原始狀態。"
            )
        # 詐欺（§339）與恐嚇取財（§346）之區辨——被害人交付財物之主觀心態為關鍵。
        # 依據：最高法院 84 年度台上字第 1993 號判決要旨，見臺灣嘉義地方法院
        # 112 年度易字第 613 號判決引用；經 tw-legal-rag 核實
        # （doc_id: CYDM,112,易,613,20240930,1，dataset 2026-10-02）。
        if {"fraud", "intimidation"} <= ids:
            notes.append(
                "詐欺與恐嚇取財之區辨方向（經核實裁判，僅供參考，非定性）："
                "關鍵在交付財物之原因——前者係受詐術陷於錯誤（誤信為應交付而交付），"
                "後者係受恐嚇心生畏懼（明知不應交付而交付）"
                "（最高法院84年度台上字第1993號判決意旨，見臺灣嘉義地方法院"
                "112年度易字第613號引用；doc_id CYDM,112,易,613,20240930,1）；"
                "請以區分問句查證被害人交付財物時係誤信詐詞或出於畏懼。"
            )
    for candidate in candidates:
        candidate["competition_analysis"] = "；".join(notes)
    return {"count": count, "assessed": "NOT_ASSESSED", "notes": notes}

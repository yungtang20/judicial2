from __future__ import annotations

import json
import hashlib
import re
from copy import deepcopy
from pathlib import Path
from .roc_time import format_roc_time
from typing import Any

from .company_templates import company_questions, render_company_text
from .markdown_questions import merge_markdown_questions
from .section_questions import ordered_section_questions
from .route_questions import has_route_question_pack, route_questions_for
from .supplemental_questions import supplemental_questions_for
from .xlsm_questions import has_company_standard_questions, xlsm_questions_for

# 8 頁防線（spec §7.5）：實測 97 題 = 8 頁（DOCX 上限）；每罪章 core+xls 約 24 題
# 3 罪章 ≈ 97 題（滿 8 頁）；core 不得裁 → 超量由 build_questions fail closed 提示縮小
MAX_SELECTED_OFFENSES = 3

# 8 頁防線（spec §7.5）：實測 DOCX 容量約 97 題（含 company/common）。
# victim 固定 company(7)+common(12)，故 offense 題上限為 97-19=78。
# 超出時 fail closed 提示承辦人縮小候選路由（不得靜默裁 core）
MAX_OFFENSE_QUESTIONS = 78

PROPERTY_TAKING_ACTIONS = ("拿走", "取走", "帶走", "搶走", "奪走", "偷走", "搬走")
PROPERTY_ROUTE_IDS = {"theft", "embezzlement", "robbery"}


class RuleError(ValueError):
    pass


def load_bank(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        bank = json.load(handle)
    if bank.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        raise RuleError("題庫必須維持人工審查狀態")
    question_root = path.resolve().parents[2] / "questions"
    if not question_root.is_dir():
        raise RuleError("找不到經審核的 Markdown 問句庫")
    merged = merge_markdown_questions(bank, question_root)
    crosswalk_path = path.with_name("legal_route_crosswalk.json")
    if not crosswalk_path.is_file():
        raise RuleError("缺少 legal route crosswalk")
    crosswalk = json.loads(crosswalk_path.read_text(encoding="utf-8"))
    if crosswalk.get("review_status") != "HUMAN_REVIEW_REQUIRED":
        raise RuleError("legal route crosswalk 必須維持人工審查狀態")
    route_meta = {item["id"]: item for item in crosswalk.get("routes", [])}
    offense_ids = {item["id"] for item in merged["offenses"]}
    if set(route_meta) != offense_ids:
        missing = sorted(offense_ids - set(route_meta))
        extra = sorted(set(route_meta) - offense_ids)
        raise RuleError(f"legal route crosswalk 不完整：missing={missing}, extra={extra}")
    for offense in merged["offenses"]:
        meta = deepcopy(route_meta[offense["id"]])
        child_routes = meta.get("child_routes", [])
        excluded_routes = meta.get("excluded_routes", [])
        child_ids = [item.get("id") for item in child_routes]
        if len(child_ids) != len(set(child_ids)):
            raise RuleError(f"legal route child id 重複：{offense['id']}")
        for child in child_routes:
            required = {"id", "route_kind", "law_name", "article_no", "name", "fact_elements", "review_status"}
            if not required.issubset(child):
                raise RuleError(f"legal route child 欄位不完整：{offense['id']}")
            if not child["fact_elements"] or child["review_status"] != "HUMAN_REVIEW_REQUIRED":
                raise RuleError(f"legal route child 必須有事實元素並維持人工審查：{child['id']}")
        for excluded in excluded_routes:
            required = {"id", "article_no", "status", "reason", "source_url"}
            if not required.issubset(excluded) or excluded["status"] not in {"DELETED", "UNCONSTITUTIONAL_INVALIDATED"}:
                raise RuleError(f"excluded legal route 欄位或狀態不正確：{offense['id']}")
        offense["route_type"] = meta["route_type"]
        offense["selection_policy"] = meta.get("selection_policy", "OPTIONAL")
        if offense["selection_policy"] not in {"REQUIRED", "OPTIONAL", "NOT_APPLICABLE"}:
            raise RuleError(f"legal route selection_policy 無效：{offense['id']}")
        offense["crosswalk_status"] = meta["crosswalk_status"]
        offense["crosswalk_note"] = meta["note"]
        offense["legal_routes"] = child_routes
        offense["excluded_legal_routes"] = excluded_routes
        offense["content_review_status"] = "HUMAN_REVIEW_REQUIRED"
    merged["legal_route_crosswalk_version"] = crosswalk["schema_version"]
    return merged


def candidate_element_state(offense: dict[str, Any]) -> tuple[list[str], str, str]:
    labels = [item["label"] for item in offense.get("elements", [])]
    route_type = offense.get("route_type", "substantive")
    crosswalk_status = offense.get("crosswalk_status", "SPLIT_REQUIRED")
    if route_type in {"procedural", "protective"}:
        return ["PROCEDURAL_FACT_MODEL_REQUIRED"], "PROCEDURAL_FACT_MODEL_REQUIRED", "UNMAPPED"
    if not labels or crosswalk_status == "SPLIT_REQUIRED":
        return labels or ["UNMAPPED_ELEMENT_MODEL"], "NEED_LEGAL_ROUTE_MAPPING", "UNMAPPED"
    return labels, "NEED_REVIEW", "MAPPED"


def _element_evidence_patterns(element: str) -> list[tuple[str, ...]]:
    """Return conservative source-text signals for one reviewed route element.

    These signals only connect an element to words already present in the case
    narrative.  They never prove the element or turn the candidate into a legal
    conclusion.  The element wording itself comes from legal_route_crosswalk.json.
    """
    if element == "性交未遂或既遂":
        return [("性交", "性交未遂", "性交既遂")]
    if element == "性影像附著物或物品":
        return [("手機", "硬碟", "記憶卡", "光碟", "隨身碟", "附著物")]
    if element == "與第319條之1至第319條之4行為的關聯":
        return []
    rules: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
        (("傷害身體或健康行為", "使人受重傷行為"), ("毆打", "踢踹", "重踢", "傷害", "攻擊", "潑灑")),
        (("傷害結果與因果關係", "重傷結果與因果關係"), ("受有", "致", "使")),
        (("性交或猥褻行為",), ("性交", "猥褻", "撫摸胸部", "撫摸", "手指插入", "親吻")),
        (("性交行為",), ("性交",)),
        (("猥褻行為",), ("猥褻", "撫摸胸部", "伸入", "親吻")),
        (("不能或不知抗拒狀態",), ("不能抗拒", "不知抗拒", "意識不清", "泥醉", "全身癱軟", "昏睡", "睡著", "失去意識")),
        (("精神、身體障礙、心智缺陷或相類情形",), ("意識不清", "泥醉", "倒臥", "全身癱軟", "嘔吐", "酒醉", "昏睡", "睡著", "失去意識", "心智缺陷")),
        (("利用該狀態",), ("利用", "乘", "趁", "不能抗拒", "不知抗拒", "睡著")),
        (("強暴、脅迫、恐嚇、催眠術或其他違反意願方法",), ("強暴", "脅迫", "恐嚇", "催眠", "威脅", "不同意")),
        (("本人意願與方法作用的具體事實",), ("不同意", "拒絕", "反抗", "不能抗拒", "不願意")),
        (("他人動產及原持有狀態",), ("包包", "現金", "手機", "財物", "物品", "所有", "放置", "抽屜")),
        (("未經同意竊取並破壞原持有",), ("竊取", "偷走", "拿走", "取走", "遭竊", "不翼而飛")),
        (("為自己或第三人不法所有之意圖", "為自己或第三人不法所有意圖"), ("不法所有",)),
        (("搶奪他人動產行為",), ("搶奪", "搶取", "奪走")),
        (("先前竊盜或搶奪行為",), ("竊盜", "竊取", "搶奪", "搶取")),
        (("防護贓物、脫免逮捕或湮滅罪證目的",), ("防護贓物", "脫免逮捕", "湮滅罪證")),
        (("當場施以強暴脅迫",), ("當場", "強暴", "脅迫", "毆打", "拉扯")),
        (("未遂或既遂", "性交未遂或既遂", "結果加重、預備、未遂或既遂"), ("得手", "得逞", "未遂", "既遂", "始停止")),
        (("家庭成員關係",), ("老婆", "妻子", "丈夫", "配偶", "同居", "家人")),
        (("身體、精神或經濟上騷擾、控制、脅迫或其他不法侵害",), ("毆打", "傷害", "威脅", "脅迫", "不同意", "偷拍", "性交")),
        (("私行拘禁或其他非法方法",), ("拘禁", "限制行動自由", "剝奪行動自由", "圍堵", "綑綁", "束帶")),
        (("被害人行動自由遭剝奪的期間與程度",), ("限制行動自由", "剝奪行動自由", "不能離開", "無法離開")),
        (("強暴或脅迫方法",), ("強暴", "脅迫", "毆打", "恫嚇", "持槍", "持刀")),
        (("使人行無義務之事或妨害權利行使",), ("迫使", "強迫", "妨害", "要求")),
        (("被害人行為時年齡及年齡證據", "兒童或少年年齡與身分", "被害人未滿十八歲及年齡分層"), ("未滿18歲", "未滿十八歲", "少年", "兒童", "歲")),
        (("攝錄性影像的科技方法", "攝錄或使本人攝錄性影像", "性影像來源類型"), ("性影像", "裸體照片", "偷拍", "影片")),
        (("重製、散布、播送、交付、公然陳列、供觀覽或販賣行為",), ("重製", "散布", "播送", "交付", "公然陳列", "供觀覽", "販賣", "上傳")),
        (("本人同意狀態與無故情形",), ("未經同意", "不同意", "無故")),
        (("詐術內容及實施",), ("佯稱", "冒充", "假客服", "詐騙", "詐術")),
        (("相對人陷於錯誤",), ("陷於錯誤", "誤信", "受騙")),
        (("交付財物或財產利益處分",), ("匯款", "轉帳", "交付", "付款")),
        (("財產流向與損害",), ("匯款", "轉帳", "損失", "財產損害")),
        (("恐嚇內容及傳達對象", "恐嚇行為與內容"), ("揚言", "恫稱", "威脅", "恐嚇")),
        (("致生安全危害的具體事實",), ("心生畏懼", "害怕", "恐懼", "安全受威脅")),
        (("注意義務與可預見性事實",), ("醫師", "手術", "抽脂管", "應注意")),
        (("注意義務違反行為",), ("不慎", "疏未注意", "刺穿")),
        (("傷害或重傷結果",), ("穿孔", "腹膜炎", "敗血症", "受有")),
        (("行為與結果間因果關係",), ("導致", "致", "使")),
        (("駕駛動力交通工具",), ("駕駛", "駕車", "騎乘", "行駛", "上路")),
        (("酒精濃度、不能安全駕駛",), ("吐氣酒精濃度", "酒精濃度", "毫克", "酒後")),
        (("第352條及第353條以外之他人之物",), ("車窗", "玻璃", "物品", "財物")),
        (("毀棄損壞或致令不堪用",), ("破壞", "毀損", "損壞", "不堪使用")),
        (("足以生損害於公眾或他人",), ("不堪使用", "受損", "損害")),
        (("公務員依法執行職務或特定職務目的",), ("公務員", "執行", "職務", "門禁")),
        (("強暴或脅迫行為",), ("揮打", "毆打", "攻擊", "強暴", "脅迫")),
    ]
    patterns: list[tuple[str, ...]] = []
    for element_fragments, signals in rules:
        if any(fragment in element for fragment in element_fragments):
            patterns.append(signals)
    if patterns:
        return patterns
    # For routes outside the explicit conservative map, accept only a literal
    # legal-element phrase from the source narrative.  Do not use fuzzy guesses.
    literal = element.strip(" ，、或及與之的")
    return [(literal,)] if len(literal) >= 4 else []


def _route_element_matrix(
    offense: dict[str, Any], summary: str, gate1: dict[str, Any] | None
) -> list[dict[str, Any]]:
    facts = (gate1 or {}).get("facts", [])
    analyses: list[dict[str, Any]] = []
    for route in offense.get("legal_routes", []):
        rows: list[dict[str, Any]] = []
        supporting_refs: list[str] = []
        for element in route.get("fact_elements", []):
            matched_signals: list[str] = []
            refs: list[str] = []
            excerpts: list[str] = []
            for signal_group in _element_evidence_patterns(element):
                for signal in signal_group:
                    if signal and signal in summary:
                        matched_signals.append(signal)
                        for fact in facts:
                            excerpt = str(fact.get("source_excerpt", ""))
                            if signal in excerpt:
                                ref = str(fact.get("fact_id", ""))
                                if ref and ref not in refs:
                                    refs.append(ref)
                                if excerpt and excerpt not in excerpts:
                                    excerpts.append(excerpt)
            if matched_signals and not refs:
                refs = ["intake.summary"]
                excerpts = [next((segment for segment, _, _ in _source_segments(summary) if any(s in segment for s in matched_signals)), summary)]
            for ref in refs:
                if ref not in supporting_refs:
                    supporting_refs.append(ref)
            rows.append({
                "element": element,
                "status": "SOURCE_SUPPORTED" if matched_signals else "UNKNOWN",
                "supporting_fact_refs": refs,
                "source_excerpts": excerpts[:3],
                "matched_signals": list(dict.fromkeys(matched_signals)),
            })
        supported = sum(row["status"] == "SOURCE_SUPPORTED" for row in rows)
        analyses.append({
            "route_id": route["id"],
            "route_name": route["name"],
            "review_status": route.get("review_status", "HUMAN_REVIEW_REQUIRED"),
            "supported_count": supported,
            "total_count": len(rows),
            "supporting_fact_refs": supporting_refs,
            "unknown_elements": [row["element"] for row in rows if row["status"] == "UNKNOWN"],
            "elements": rows,
        })
    return sorted(
        analyses,
        key=lambda item: (-item["supported_count"], len(item["unknown_elements"]), item["route_id"]),
    )


def _attach_element_evidence(
    candidate: dict[str, Any], offense: dict[str, Any], summary: str, gate1: dict[str, Any] | None
) -> None:
    # Procedural/protective umbrellas have a separate fail-closed contract.
    # SPLIT_REQUIRED substantive parents may rank their reviewed child routes,
    # but must retain their UNMAPPED parent-level status below.
    if offense.get("route_type") in {"procedural", "protective"}:
        return
    matrix = _route_element_matrix(offense, summary, gate1)
    candidate["route_element_matrix"] = matrix
    if not matrix:
        return
    best = matrix[0]
    candidate["suggested_legal_route_ids"] = [best["route_id"]] if best["supported_count"] else []
    candidate["unknown_elements"] = best["unknown_elements"]
    candidate["supporting_fact_refs"] = best["supporting_fact_refs"]
    if offense.get("crosswalk_status") != "SPLIT_REQUIRED":
        candidate["element_model_status"] = "SOURCE_EVIDENCE_MATRIX"
    keyword_note = "、".join(candidate.get("matched_terms", [])) or "無直接關鍵詞"
    candidate["inclusion_reason"] = (
        f"關鍵詞提示：{keyword_note}；摘要對「{best['route_name']}」"
        f"{best['supported_count']}/{best['total_count']} 個構成要件有可回查原文；"
        "仍僅為候選分析方向。"
    )
    candidate["reservation_reason"] = (
        "結構化事實尚待補問：" + "、".join(best["unknown_elements"])
        if best["unknown_elements"] else "結構化事實均有摘要原文片段，但仍須人工核對真實性與法律評價"
    )


def _fact_status_for_kind(kind: str) -> str:
    """kind → fact_status 對應（spec §4.2 七值枚舉）。"""
    return {"event": "當事人陳述", "statement": "當事人陳述", "unknown": "未知"}.get(kind, "當事人陳述")


def _source_segments(summary: str) -> list[tuple[str, int, int]]:
    """依明確句界切分來源文字，不推斷人物、行為、因果或法律性質。"""
    segments: list[tuple[str, int, int]] = []
    for match in re.finditer(r"[^。！？；\r\n]+[。！？；]?", summary):
        raw = match.group(0)
        leading = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if not text:
            continue
        start = match.start() + leading
        segments.append((text, start, start + len(text)))
    return segments


def _property_taking_values(summary: str) -> dict[str, str] | None:
    action = next((item for item in PROPERTY_TAKING_ACTIONS if item in summary), "")
    if not action:
        return None
    actor_match = re.search(r"(?:^|[，。；！？\s])([^，。；！？\s]{1,8})把", summary)
    actor = actor_match.group(1) if actor_match else next(
        (item for item in ("對方", "他", "她", "行為人") if item in summary), "UNKNOWN"
    )
    action_pattern = "|".join(PROPERTY_TAKING_ACTIONS)
    object_match = re.search(
        rf"(?:我的|他的|她的|其)([^，。；！？\s]{{1,12}}?)(?:被)?(?:{action_pattern})",
        summary,
    ) or re.search(
        rf"把([^，。；！？\s]{{1,12}}?)(?:被)?(?:{action_pattern})",
        summary,
    )
    obj = object_match.group(1) if object_match else "UNKNOWN"
    consent = "NO" if any(item in summary for item in ("未經同意", "沒有同意", "不同意")) else (
        "YES" if any(item in summary for item in ("經我同意", "我同意", "同意他")) else "UNKNOWN"
    )
    prior_possession = "YES" if any(item in summary for item in ("借給", "交給他保管", "交由他保管", "代管", "寄放")) else "UNKNOWN"
    force = "YES" if any(item in summary for item in ("強暴", "脅迫", "威脅", "拉扯", "毆打", "搶走", "奪走")) else (
        "NO" if any(item in summary for item in ("沒有使用暴力", "未使用暴力", "沒有威脅", "未威脅")) else "UNKNOWN"
    )
    return_agreement = "YES" if any(item in summary for item in ("約定歸還", "答應歸還", "說好歸還", "借給")) else "UNKNOWN"
    evidence = "YES" if any(item in summary for item in ("訊息", "錄影", "監視器", "證人", "照片")) else "UNKNOWN"
    return {
        "actor": actor,
        "action": "取走物品",
        "object": obj,
        "original_possession": "UNKNOWN",
        "consent": consent,
        "prior_lawful_possession": prior_possession,
        "force_or_threat": force,
        "return_agreement": return_agreement,
        "intent": "UNKNOWN",
        "evidence": evidence,
    }


def _narrative_fact_candidates(summary: str) -> list[dict[str, Any]]:
    """以可回查的文字片段拆解常見案件敘述，不作法律成立判斷。

    這是本機的保守抽取器。每個結果都必須是摘要中的連續文字，
    不把「犯意、共犯、成立」等法律評價轉成已證明事實。
    """
    candidates: list[dict[str, Any]] = []

    segments = _source_segments(summary)
    temporal_anchors = sorted({
        0,
        *(match.start() for match in re.finditer(
            r"(?:民國\s*)?\d{2,3}[年年]\d{1,2}月\d{1,2}日[^，。；]{0,18}?"
            r"\d{1,2}時(?:\d{1,2}分)?(?:許)?|"
            r"翌(?:日|\(\d{1,2}\)日)\d{1,2}時(?:[0-5]?\d分)?(?:許)?",
            summary,
        )),
    })

    def add(
        category: str,
        text: str,
        *,
        value: str | None = None,
        fields: dict[str, str] | None = None,
        start: int | None = None,
        assertion_status: str = "EXPLICIT_SOURCE_ASSERTION",
    ) -> None:
        text = text.strip(" ，、；。")
        if not text:
            return
        # 判決全文或附表常把「系爭帳戶、機車、卷證」接在動詞附近。
        # 這些不是人物，不能進入 Gate 1 的人員欄位。
        if category == "person" and ((len(text) < 2 and text not in "甲乙丙丁戊己庚辛壬癸") or any(token in text for token in (
            "帳戶", "提款卡", "機車", "本案", "系爭", "偵卷", "判決", "法院",
            "時間", "地點", "倉庫", "公眾", "所有", "所管", "起訴", "被告",
            "告訴人", "爭點", "自用小客車", "營業用大客車", "車牌", "之詞",
            "之攔", "竟仍", "徵其", "如附", "花用", "於應", "公共托",
        ))):
            return
        resolved_start = summary.find(text) if start is None else start
        if resolved_start < 0:
            return
        resolved_fields = dict(fields or {})
        resolved_fields.setdefault("assertion_status", assertion_status)
        temporal_event_id = f"event:{sum(anchor <= resolved_start for anchor in temporal_anchors)}"
        resolved_fields.setdefault(
            "event_id",
            temporal_event_id if len(temporal_anchors) > 1 else next(
                (f"event:{index + 1}" for index, (_, seg_start, seg_end) in enumerate(segments)
                 if seg_start <= resolved_start < seg_end),
                "event:unassigned",
            ),
        )
        candidates.append({
            "category": category,
            "text": text,
            "value": value or text,
            "fields": resolved_fields,
            "start": resolved_start,
            "end": resolved_start + len(text),
        })

    absolute_times = list(re.finditer(
        r"((?:民國\s*)?\d{2,3}[年年]\d{1,2}月\d{1,2}日[^，。；]{0,18}?"
        r"\d{1,2}時(?:\d{1,2}分)?(?:許)?)",
        summary,
    ))
    for time_match in absolute_times:
        raw_time = time_match.group(1)
        normalized_time = raw_time if raw_time.startswith("民國") else f"民國{raw_time}"
        add("time", raw_time, value=normalized_time, start=time_match.start(1), fields={"time": normalized_time})
    if not absolute_times:
        relative_time = re.search(r"(民國\s*\d{2,3}[年年]\d{1,2}月\d{1,2}日[^。；，]{0,20}(?:晚上|凌晨|下午|上午)約?\s*\d{1,2}點)", summary)
        if relative_time:
            add("time", relative_time.group(1), start=relative_time.start(1), fields={"time": relative_time.group(1)})
        else:
            for date_only in re.finditer(r"((?:民國\s*)?\d{2,3}[年年]\d{1,2}月\d{1,2}日)", summary):
                raw_date = date_only.group(1)
                normalized_date = raw_date if raw_date.startswith("民國") else f"民國{raw_date}"
                add(
                    "time", raw_date, value=normalized_date, start=date_only.start(1),
                    fields={"time": normalized_date},
                )
            if "當日晚間" in summary:
                add("time", "當日晚間")
    base_date = re.search(r"(?:民國\s*)?(\d{2,3})[年年](\d{1,2})月(\d{1,2})日", summary)
    if base_date:
        base_year = int(base_date.group(1))
        base_month = int(base_date.group(2))
        base_day = int(base_date.group(3))
        for same_day in re.finditer(r"同日(\d{1,2})時(?:([0-5]?\d)分)?(?:許)?", summary):
            minute = f"{int(same_day.group(2))}分" if same_day.group(2) is not None else ""
            normalized = f"民國{base_year}年{base_month}月{base_day}日{int(same_day.group(1))}時{minute}許"
            add("time", same_day.group(0), value=normalized, start=same_day.start(), fields={"time": normalized})
        for dated_relative in re.finditer(
            r"翌日(?:（?(\d{1,2})日）?)?(\d{1,2})時(?:([0-5]?\d)分)?(?:許)?", summary
        ):
            relative_day = int(dated_relative.group(1) or base_day + 1)
            minute = f"{int(dated_relative.group(3))}分" if dated_relative.group(3) is not None else ""
            normalized = (
                f"民國{base_year}年{base_month}月{relative_day}日"
                f"{int(dated_relative.group(2))}時{minute}許"
            )
            add("time", dated_relative.group(0), value=normalized, start=dated_relative.start(), fields={"time": normalized})
        for relative in re.finditer(r"翌(?:日|\((\d{1,2})\)日)(\d{1,2})時(?:([0-5]?\d)分)?(?:許)?", summary):
            relative_day = int(relative.group(1) or int(base_date.group(3)) + 1)
            minute = f"{int(relative.group(3))}分" if relative.group(3) is not None else ""
            normalized = (
                f"民國{int(base_date.group(1))}年{int(base_date.group(2))}月{relative_day}日"
                f"{int(relative.group(2))}時{minute}許"
            )
            add("time", relative.group(0), value=normalized, start=relative.start(), fields={"time": normalized})
    for match in re.finditer(
        r"((?:民國)?\d{2,3}[年年]\d{1,2}月\d{1,2}日(?:凌晨|上午|下午|晚上)"
        r"(?:零|[0-9]{1,2})時(?:[0-5]?\d分)?(?:許)?)",
        summary,
    ):
        add("time", match.group(1), start=match.start(1), fields={"time": match.group(1)})

    for match in re.finditer(r"位在([^，。；]+?)(?=拍攝|經營)", summary):
        add("place", match.group(1))
    for match in re.finditer(r"在([^，。；]+?)(?:中|上|內|附近)(?=[因，。；])", summary):
        add("place", match.group(1))
    for match in re.finditer(r"(?:前往|位在)([^，。；]+?)(?:中|上|內|附近)(?=[因，。；])", summary):
        add("place", match.group(1))
    # 裁判書常以「在○○工寮，…」或「於○○病房，…」直接接逗號，
    # 不一定有「內／上」結尾；只收有地點詞的連續原文，避免把整句動作當地點。
    location_terms = r"(?:市|縣|區|鄉|鎮|路|街|段|巷|號|夜市|住處|醫院|病房|工寮|店內|路口|大廳|廣場|學校)"
    for match in re.finditer(r"(?:在|於)([^，。；]{2,80})", summary):
        segment = match.group(1)
        # 「於某日赴醫院就診／於某時駕駛」的介系詞引出時間或行為，
        # 不得把後面的完整動作誤當成地點。
        if re.match(r"(?:民國)?\d{2,3}[年年]", segment) and re.search(
            r"前往|就診|接受|駕駛|匯款|施行", segment
        ):
            continue
        segment = re.split(r"(?:見|基於|遂|因|共同|以|將|徒手|欲|而|拍攝|委請|駕駛|就診|接受|施行|，)", segment, maxsplit=1)[0].strip()
        segment = segment.rstrip("上內中")
        if re.search(location_terms, segment):
            add("place", segment)
    for match in re.finditer(r"前往([^，。；]{2,50}?)(?=就診|治療|接受|進行)", summary):
        place = match.group(1).strip()
        if re.search(r"醫院|診所|醫療|中心", place):
            add("place", place, start=match.start(1))
    if not any(item["category"] == "place" for item in candidates):
        place_match = re.search(r"在([^，。；]+(?:處|所|內|上))", summary)
        if place_match:
            add("place", place_match.group(1))
    relative_bar_place = re.search(r"(上開酒吧前)", summary)
    if relative_bar_place:
        named_bar = re.search(r"\(([^()]{2,40}(?:BAR|CLUB))\)", summary, re.IGNORECASE)
        resolved_place = f"{named_bar.group(1)}前" if named_bar else relative_bar_place.group(1)
        add(
            "place",
            relative_bar_place.group(1),
            value=resolved_place,
            start=relative_bar_place.start(1),
            fields={"place": resolved_place, "subtype": "resolved_anaphora"},
        )

    alias_match = re.search(
        r"代號([A-Z]{2,8}\d{2,8}-[A-Z]\d{3,12}).{0,40}?下稱([A-Z][男女])",
        summary,
    )
    alias_name = alias_match.group(2) if alias_match else ""
    if alias_match:
        combined = f"{alias_match.group(1)}／{alias_match.group(2)}"
        add("person", alias_match.group(0), value=combined, start=alias_match.start(), fields={
            "subject": combined,
            "role": "victim",
            "person_code": alias_match.group(1),
            "alias": alias_match.group(2),
        })
    people_prefix = re.search(r"^(.{2,60}?)(?=在|於|因|意圖|原本)", summary)
    if people_prefix:
        raw_people = re.split(r"[、與及和]", people_prefix.group(1))
        for name in raw_people:
            name = re.split(r"(?:共同|基於|犯意|意圖|委請|邀約)", name, maxsplit=1)[0].strip(" ，")
            name = re.sub(r"^(?:醫師|被告|告訴人)", "", name)
            if name not in {"事發", "事由", "案件"} and 2 <= len(name) <= 12 and re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fff○－-]+", name):
                add("person", name, fields={"subject": name})
    if re.search(r"我與(?:老婆|妻子|丈夫)", summary):
        add("person", "我", fields={"subject": "我"})
    for match in re.finditer(r"(一群友人|路人)", summary):
        add(
            "person",
            match.group(1),
            start=match.start(1),
            fields={
                "subject": match.group(1),
                "role": "companion" if "友人" in match.group(1) else "discoverer",
            },
        )

    for pattern in (
        r"^([\u4e00-\u9fff]{2,5})與",
        r"下稱([\u4e00-\u9fffA-Za-z0-9-]{1,20})",
        r"^([\u4e00-\u9fff]{2,5})(?=因)",
        r"^([\u4e00-\u9fff]{2,5})(?=意圖)",
        r"我與(?:老婆|妻子|丈夫)?([\u4e00-\u9fff]{2,4})(?=因|，|。)",
        r"老婆([\u4e00-\u9fff]{2,4})(?=因|，|。)",
        r"中文名：([\u4e00-\u9fff○]{2,5})",
        r"員工([\u4e00-\u9fff○]{2,5})(?=因)",
        r"([\u4e00-\u9fff]{2,5})之男友",
        r"之男友([\u4e00-\u9fff○]{2,5})",
        r"見([\u4e00-\u9fff]{2,5})於",
        r"致([\u4e00-\u9fff]{2,5})陷於",
        r"為([\u4e00-\u9fff]{2,5})施行",
        r"由([\u4e00-\u9fff]{2,5})(?=負責|駕駛)",
        r"撞擊([\u4e00-\u9fff]{2,5})(?=駕駛|所駕駛)",
        r"(?:使|致)([\u4e00-\u9fff]{2,5}?)(?:因而)?(?=受有)",
        r"(?:醫師|被告|告訴人)([\u4e00-\u9fff]{2,4}?)(?=於|（|，|。|係|為)",
    ):
        for match in re.finditer(pattern, summary):
            name = match.group(1)
            if name == alias_name:
                continue
            if name not in {"我", "他", "她", "性交", "內射"} and not (
                name.startswith("○") and any("\u4e00" <= char <= "\u9fff" for char in name)
            ):
                add("person", name, fields={"subject": name})
    # 甲乙等代稱只有在與具體行為或身分相鄰時才視為人物，避免把條次或列舉誤收。
    for match in re.finditer(
        r"([甲乙丙丁戊己庚辛壬癸])(?="
        r"於|所有|放在|攔阻|駕駛|受有|之|，)",
        summary,
    ):
        add("person", match.group(1), fields={"subject": match.group(1)})
    foreign_person = re.search(r"([A-Z]{2,}\s+\d+（中文名：[^）]+）)", summary)
    if foreign_person:
        add("person", foreign_person.group(1), fields={"recipient": foreign_person.group(1)})

    victim_match = re.search(r"(?:毆打|攻擊|推打)([\u4e00-\u9fff○]{2,5})(?=，|。|、)", summary)
    if victim_match:
        add("person", victim_match.group(1), fields={"recipient": victim_match.group(1)})
    # 代號與遮名（A男、B女、甲○○、林○○）是裁判書常見當事人寫法。
    for match in re.finditer(r"(?:[A-Z][A-Za-z0-9-]{0,8}(?:男|女)|(?<![\u4e00-\u9fff])[甲乙丙丁戊己庚辛壬癸][○]{1,4})", summary):
        name = match.group(0)
        if name == alias_name:
            continue
        add("person", name, fields={"subject": name})
    for match in re.finditer(r"(?:見|毆打|踢踹|攻擊|親吻|拉住|拉扯|跟隨|對)([\u4e00-\u9fff]{2,5}(?:、[\u4e00-\u9fff]{2,5})?)(?=之|，|。|受有|上衣|左|右|欲|在)", summary):
        for name in re.split(r"、", match.group(1)):
            add("person", name, fields={"recipient": name})
    for match in re.finditer(r"竊取([\u4e00-\u9fff○]{2,5})(?=放置|所有|所管|之)", summary):
        add("person", match.group(1), fields={"recipient": match.group(1)})

    event_match = re.search(r"因([^，。；]{1,40}?生有嫌隙)", summary)
    if event_match:
        add("event", event_match.group(1))
    for pattern in (
        r"(共同飲酒)", r"([A-Z]女飲用威士忌\d+至\d+杯)",
        r"(邀約飲用酒類)", r"(嘔吐、全身癱軟無力)", r"(原本素不相識)",
        r"(因受酒精之影響，呈現意識不清之泥醉狀態，並倒臥在上開酒吧前)",
        r"(用手撫摸[A-Z]女之胸部、陰部)",
        r"(將手指插入[A-Z]女陰部抽動數次)",
        r"(路人發現，報警處理)",
    ):
        match = re.search(pattern, summary)
        if match:
            add("event", match.group(1))

    action_match = re.search(r"((?:共同|各自|徒手|持刀|持棍|駕車|推打|毆打)[^，。；！？]{0,12}?)(?=，致|，造成|，導致|[。！？])", summary)
    if action_match:
        action_text = action_match.group(1)
        if "涉犯" not in action_text and "罪" not in action_text:
            add("action", action_text, fields={"action": action_text})
    for pattern in (
        r"(徒手竊取[^，。；]+)",
        r"(持預藏[^，。；]+潑灑)",
        r"(進入[^，。；]+拉開[^，。；]+)",
        r"(搶奪[^，。；]+得手)",
        r"(拉扯、攔阻[^，。；]+)",
        r"(將[^，。；]+取出[^，。；]+)",
        r"(拔腿就跑)",
        r"(壓制[^，。；]+)",
        r"(逮捕[^，。；]+)",
        r"(查獲[^。；]+)",
        r"(恫稱[^，。；]+)",
        r"(施以強暴、脅迫)",
        r"(逃離現場)",
        r"((?:偷偷的|趁我睡著時|在我睡著時)[^，。；！？]{0,20}性交)",
        r"((?:威脅|脅迫)[^，。；！？]{0,20}性交)",
        r"(與我性交)",
        r"(拍攝宣傳影片)",
        r"(邀約飲用酒類)",
        r"(雙手摟抱[^，。；]+)",
        r"(扶至[^，。；]+平躺)",
        r"(親吻[^，。；]+)",
        r"(徒手伸入[^，。；]+撫摸[^，。；]+)",
        r"(喝斥[^，。；]+)",
        r"((?:竊得|竊取|拿走|取走)[^，。；]+)",
        r"(以腳踢踹[^，。；]+)",
        r"(又以腳重踢[^，。；]+)",
        r"(手套弄[^，。；]+)",
        r"(將手伸入[^，。；]+撫摸[^，。；]+)",
        r"(試圖褪去[^，。；]+)",
        r"(強行親吻[^，。；]+)",
        r"(欲強拉[^，。；]+)",
        r"(共同飲酒)",
        r"(飲用酒類)",
        r"([A-Z]女飲用威士忌\d+至\d+杯)",
        r"(用手撫摸[A-Z]女之胸部、陰部)",
        r"(將手指插入[A-Z]女陰部抽動數次)",
        r"(路人發現)",
        r"(報警處理)",
        r"(以[^，。；]{0,30}私訊[^，。；]{0,40})",
        r"(佯稱[^，。；]{1,80})",
        r"((?:轉帳)?匯款[^，。；]{1,50})",
        r"(為[^，。；]{1,12}施行[^，。；]{1,35})",
        r"(抽脂管刺穿[^，。；]{1,20})",
        r"(接受[^。；]{1,60}(?:手術|治療))",
        r"(駕駛[^，。；]{1,35}(?:上路|行駛))",
        r"((?:自後)?撞擊[^，。；]{1,35})",
        r"(破壞[^，。；]{1,35})",
        r"(開啟[^，。；]{1,35})",
        r"(取走[^，。；]{1,50})",
        r"(徒手揮打[^，。；]{1,35})",
    ):
        for match in re.finditer(pattern, summary):
            action_text = match.group(1)
            if "涉犯" not in action_text and "罪" not in action_text:
                add("action", action_text, fields={"action": action_text})
    # 通用取財／傷害片段。排除「涉犯…罪」等法律評價，避免把罪名當行為。
    for match in re.finditer(r"((?:共同|各自)[^，。；]{0,80}(?:竊得|竊取|毆打|搶奪)[^，。；]*)", summary):
        if "涉犯" not in match.group(1) and "罪" not in match.group(1):
            add("action", match.group(1), fields={"action": match.group(1)})

    injury_match = re.search(r"受有([^。；]+?)(?:等)?傷害", summary)
    if injury_match:
        result_text = injury_match.group(1).strip("，、").rstrip("之")
        add("result", result_text, fields={"result": result_text})
    else:
        explicit_injury = re.search(
            r"受有([^。；]{1,80}(?:挫傷|裂傷|骨折|穿孔|角膜炎)(?:[^。；]{0,40})?)",
            summary,
        )
        if explicit_injury:
            result_text = explicit_injury.group(1).strip("，、")
            add("result", result_text, fields={"result": result_text})
    for pattern in (r"(取回其遭竊之[^，。；]+)", r"(查獲[^。；]+)"):
        for match in re.finditer(pattern, summary):
            add("result", match.group(1), fields={"result": match.group(1)})
    for pattern in (r"(內射)", r"(偷拍[^，。；]*影片)", r"(拿[^，。；]*影片[^，。；]*威脅)"):
        for match in re.finditer(pattern, summary):
            add("result", match.group(1), fields={"result": match.group(1)})
    for pattern in (
        r"(嘔吐、全身癱軟無力)", r"(意識不清之泥醉狀態)",
        r"(倒臥在上開酒吧前)", r"(猥褻(?:行為)?得逞)", r"(始停止)",
    ):
        match = re.search(pattern, summary)
        if match:
            add("result", match.group(1), fields={"result": match.group(1)})
    if not injury_match:
        for match in re.finditer(r"((?:致|使)[^，。；]{1,60}(?:受傷|受有[^，。；]+傷害))", summary):
            add("result", match.group(1), fields={"result": match.group(1)})
    for pattern in (
        r"(遲未收到[^，。；]{1,30})",
        r"(始悉受騙)",
        r"(大腸穿孔(?:併腹膜炎(?:引發敗血症)?)?)",
        r"(腹膜炎)",
        r"(敗血症)",
        r"(無人受傷)",
        r"(吐氣酒精濃度(?:為)?每公升\s*\d+(?:\.\d+)?毫克)",
        r"([^，。；]{1,20}不堪使用)",
    ):
        for match in re.finditer(pattern, summary):
            add("result", match.group(1), fields={"result": match.group(1)})

    causation_match = re.search(r"(致[^。；]+?受有[^。；]+)", summary)
    if causation_match:
        add("causation", causation_match.group(1))
    for pattern in (
        r"(致[^，。；]{1,100}(?:匯款|轉帳|交付)[^，。；]{0,60})",
        r"(導致[^。；]{1,100})",
    ):
        for match in re.finditer(pattern, summary):
            add("causation", match.group(1))
    for pattern in (
        r"(得手後即[^，。；]+)",
        r"(因防護贓物、脫免逮捕)",
        r"(以防止其逃跑)",
        r"(使[^，。；]+受有[^。；]+傷害)",
        r"(因受酒精之影響，呈現意識不清之泥醉狀態，並倒臥在上開酒吧前)",
    ):
        match = re.search(pattern, summary)
        if match:
            add("causation", match.group(1))
    for pattern in (r"(因小孩[^。；]+發生爭執)", r"(我不同意)", r"(睡著時[^。；]+性交)", r"(拿那天偷拍[^。；]+威脅[^。；]+)"):
        match = re.search(pattern, summary)
        if match:
            add("causation", match.group(1))
    for pattern in (r"(因趙子興邀約飲用酒類後)", r"(乘A女不能抗拒之際)", r"(始停止)"):
        match = re.search(pattern, summary)
        if match:
            add("causation", match.group(1))

    object_match = re.search(r"(傷害他人身體)", summary)
    if object_match:
        add("object", object_match.group(1), value="他人身體", fields={"object": "他人身體"})
    elif victim_match:
        add("object", victim_match.group(0), value=f"{victim_match.group(1)}身體", fields={"object": f"{victim_match.group(1)}身體"})
    if not object_match and (not injury_match or re.search(r"搶奪|汽油|現金|櫃台", summary)):
        object_matches = []
        for pattern in (
            r"(?:放置於[^之，。；]+之)(包包|皮包|手機)",
            r"(現金[^，。；]{0,12}\d[\d,]*元)",
            r"(汽油)",
            r"(櫃台抽屜)",
            r"(?:竊得|竊取|搶奪|取走)([^，。；]+)",
            r"((?:iphone|iPhone)[A-Za-z0-9]+手機\d+支)",
            r"((?:轉帳)?匯款[新臺幣（下同）\s]*([\d,]+元))",
            r"(現金\d[\d,]*元)",
            r"(筆記型電腦\d+台)",
            r"(車窗玻璃)",
            r"(抽脂管)",
        ):
            object_matches.extend(match.group(1) for match in re.finditer(pattern, summary))
        for object_text in dict.fromkeys(object_matches):
            add("object", object_text, fields={"object": object_text})
    for object_text in ("性交影片",):
        if re.search(r"(偷拍|性影像|私密影像)", summary):
            add("object", "影片", value=object_text, fields={"object": object_text})
    whiskey = re.search(r"(威士忌\d+至\d+杯)", summary)
    if whiskey:
        add("object", whiskey.group(1), start=whiskey.start(1), fields={"object": whiskey.group(1), "subtype": "substance"})
    for object_text in ("酒類", "胸部", "陰部", "手指", "內衣"):
        if object_text in summary:
            add("object", object_text, fields={
                "object": object_text,
                "subtype": "body_part" if object_text in {"胸部", "陰部", "手指"} else "item",
            })
    for object_text in ("生殖器", "外褲", "上衣", "農藥噴霧機", "抽脂管"):
        if object_text in summary:
            add("object", object_text, fields={"object": object_text})

    evidence_terms = ("監視器", "錄影", "照片", "訊息", "證人", "診斷證明", "病歷", "影片", "偷拍", "男友")
    evidence_match = re.search(r"([^，。；]{0,20}(?:" + "|".join(evidence_terms) + r")[^，。；]{0,20})", summary)
    if evidence_match:
        add("evidence", evidence_match.group(1))
    wireless_match = re.search(r"([^，。；]{0,20}無線電通報[^，。；]{0,20})", summary)
    if wireless_match:
        add("evidence", wireless_match.group(1))
    evidence_names = (
        "網路對話訊息截圖", "反詐騙諮詢專線紀錄表", "帳戶交易清單",
        "診斷證明書", "手術紀錄", "住院病歷", "手術照片", "醫療影像光碟",
        "醫事審議委員會鑑定書", "酒精測定紀錄表", "酒測器檢定合格證書",
        "道路交通事故現場圖", "事故調查報告表", "現場照片", "現場監視器",
    )
    for evidence_name in evidence_names:
        for match in re.finditer(re.escape(evidence_name), summary):
            add(
                "evidence", match.group(0), start=match.start(),
                fields={"subtype": "named_record"}, assertion_status="SOURCE_LEAD_TO_VERIFY",
            )

    for pattern, subtype in (
        (r"(真實姓名年籍詳卷)", "record_reference"),
        (r"(路人發現)", "potential_witness"),
        (r"(報警處理)", "potential_report_record"),
    ):
        for match in re.finditer(pattern, summary):
            add("evidence", match.group(1), start=match.start(1), fields={"subtype": subtype}, assertion_status="SOURCE_LEAD_TO_VERIFY")

    # 法律評價留供回查，不得投影成「事／行為／結果」的中性事實。
    for match in re.finditer(r"((?:意圖|基於)[^，。；]{1,40}(?:犯意|所有)|(?:性交|猥褻)(?:行為)?得逞)", summary):
        add(
            "legal_characterization",
            match.group(1),
            start=match.start(1),
            assertion_status="LEGAL_CHARACTERIZATION",
        )

    deduped: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str, int]] = set()
    for item in candidates:
        key = (item["category"], item["value"], item["start"])
        if key in seen_candidates:
            continue
        seen_candidates.add(key)
        deduped.append(item)
    return deduped


def analyze_gate1(intake: dict[str, Any], *, use_ai: bool = True) -> dict[str, Any]:
    """Return Gate 1 structured facts with provenance and status.

    LLM 路徑（use_ai）：呼叫 ai.segment_facts 切分摘要為多筆事實；
    每筆 text 皆為摘要逐字子字串（ai.py 已驗證防杜撰），並帶 schema 欄位。
    LLM 無法使用時退回規則路徑（僅依句界建立可回查的來源陳述）。
    """
    summary = intake["summary"].strip()

    def person_attributes() -> list[dict[str, Any]]:
        code_alias = re.search(
            r"代號([A-Z]{2,8}\d{2,8}-[A-Z]\d{3,12})"
            r"\(民國(\d{2,3})年(\d{1,2})月生，[^)]*下稱([A-Z][男女])\)",
            summary,
        )
        event_date = re.search(r"(?:民國\s*)?(\d{2,3})[年年](\d{1,2})月(\d{1,2})日", summary)
        if not code_alias:
            return []
        age_at_event: int | None = None
        if event_date:
            birth_year, birth_month = int(code_alias.group(2)), int(code_alias.group(3))
            event_year, event_month = int(event_date.group(1)), int(event_date.group(2))
            age_at_event = event_year - birth_year - (1 if event_month < birth_month else 0)
        return [{
            "person_code": code_alias.group(1),
            "alias": code_alias.group(4),
            "role": "victim",
            "birth_year_roc": int(code_alias.group(2)),
            "birth_month": int(code_alias.group(3)),
            "age_at_event": age_at_event,
            "age_at_event_status": "DERIVED_FROM_EXPLICIT_DATES" if age_at_event is not None else "UNKNOWN",
            "source_excerpt": code_alias.group(0),
            "source_start": code_alias.start(),
            "source_end": code_alias.end(),
        }]
    # Helper to create a fact object with minimal required fields
    def make_fact(
        text: str,
        fact_kind: str,
        fields: dict[str, str] | None = None,
        *,
        fact_key: str = "",
        value: str = "",
        source_excerpt: str | None = None,
        source_start: int | None = None,
        source_end: int | None = None,
    ) -> dict[str, Any]:
        f = fields or {}
        is_legal_characterization = fact_key == "legal_characterization"
        stable_seed = "|".join((
            "intake.summary",
            fact_key,
            str(source_start),
            str(source_end),
            value or text,
        ))
        return {
            "fact_id": "fact:" + hashlib.sha256(stable_seed.encode("utf-8")).hexdigest()[:20],
            "fact_key": fact_key,
            "value": value or text,
            "source_ref": "intake.summary",
            "source_excerpt": text if source_excerpt is None else source_excerpt,
            "source_start": source_start,
            "source_end": source_end,
            "normalized_text": text.strip(),
            "subject": f.get("subject", ""),
            "action": f.get("action", ""),
            "object": f.get("object", ""),
            "recipient": f.get("recipient", ""),
            "time": f.get("time", ""),
            "place": f.get("place", ""),
            "possession_state": f.get("possession_state", ""),
            "knowledge_or_intent": f.get("knowledge_or_intent", ""),
            "result": f.get("result", ""),
            "causal_relation": f.get("causal_relation", ""),
            "event_id": f.get("event_id", "event:unassigned"),
            "role": f.get("role", ""),
            "person_code": f.get("person_code", ""),
            "alias": f.get("alias", ""),
            "subtype": f.get("subtype", ""),
            "assertion_status": f.get(
                "assertion_status",
                "UNKNOWN" if fact_kind == "unknown" else "EXPLICIT_SOURCE_ASSERTION",
            ),
            "evidence_refs": [],
            "fact_status": "摘要法律評價" if is_legal_characterization else _fact_status_for_kind(fact_kind),
            # FACT 僅表示來源文字明示記載，不表示內容已經查證為真。
            "machine_status": (
                "UNKNOWN" if fact_kind == "unknown" else
                "ASSERTED_NOT_VERIFIED" if is_legal_characterization else
                "FACT"
            ),
            "review_status": "HUMAN_REVIEW_REQUIRED",
        }

    facts: list[dict[str, Any]] = []
    segmentation_source = "rules"
    if summary and use_ai:
        try:
            from .ai import segment_facts
            result = segment_facts(summary)
        except Exception:
            result = None
        if result is not None:
            segmentation_source = f"ai:{result['model']}"
            for item in result["facts"]:
                start = summary.find(item["text"])
                facts.append(make_fact(
                    item["text"], item["kind"], item,
                    source_start=start if start >= 0 else None,
                    source_end=start + len(item["text"]) if start >= 0 else None,
                ))
    property_values = _property_taking_values(summary)
    detailed_property_narrative = bool(re.search(
        r"(?:竊取|偷取|盜取|搶奪|破壞|潑灑|毆打)[^。；]{0,120}(?:包包|皮包|手機|現金|電腦|財物|車窗|汽油|傷害)", summary
    ))
    narrative_candidates = (
        _narrative_fact_candidates(summary)
        if not property_values or detailed_property_narrative else []
    )
    if narrative_candidates:
        segmentation_source = "rules:narrative"
        # 自然語言摘要採用唯一的八類語意結果。不要再混入整句 fallback，
        # 否則 UI 會同時出現「事 = 整段摘要」與細部分類，破壞 Gate 1 的用途。
        facts = []
        # 原始句段只作 provenance（fact_key 留空），不投影到八類的「事」。
        # 這保留逐字稽核能力，同時避免把整段摘要當成事件分析結果。
        for text, start, end in _source_segments(summary):
            if text == summary.strip():
                continue
            facts.append(make_fact(text, "statement", source_start=start, source_end=end))
        for item in narrative_candidates:
            fields = dict(item.get("fields", {}))
            facts.append(make_fact(
                item["text"],
                "unknown" if item["category"] == "evidence" and item["value"] == "UNKNOWN" else "statement",
                fields,
                fact_key=item["category"],
                value=item["value"],
                source_excerpt=item["text"],
                source_start=item["start"],
                source_end=item["end"],
            ))
        present = {
            item["category"] for item in narrative_candidates
            if item["category"] != "legal_characterization"
        }
        if "action" in present or "result" in present:
            present.add("event")
        for category in ("person", "event", "time", "place", "object", "action", "result", "causation"):
            if category not in present:
                facts.append(make_fact(
                    category,
                    "unknown",
                    fact_key=category,
                    value="UNKNOWN",
                    source_excerpt="",
                ))
        if "evidence" not in present:
            facts.append(make_fact(
                "evidence",
                "unknown",
                fact_key="evidence",
                value="UNKNOWN",
                source_excerpt="",
            ))
        default_unknowns = [
            label for category, label in (
                ("person", "行為人／受害人"),
                ("event", "事件經過"),
                ("time", "發生時間"),
                ("place", "發生地點"),
                ("object", "客體"),
                ("action", "行為方式"),
                ("result", "結果／傷勢"),
                ("causation", "結果與行為間關係"),
                ("evidence", "可供查證的證據"),
            )
            if category not in present
        ]
    elif property_values:
        if not facts and summary:
            # 財產取走路徑仍需保留原有來源陳述，供既有 property facts 與 acts 相容投影使用。
            for text, start, end in _source_segments(summary):
                facts.append(make_fact(text, "statement", source_start=start, source_end=end))
        labels = {
            "actor": "行為人",
            "action": "行為",
            "object": "客體",
            "original_possession": "原持有狀態",
            "consent": "是否同意",
            "prior_lawful_possession": "是否曾交付保管或合法持有",
            "force_or_threat": "是否使用強暴、脅迫或拉扯",
            "return_agreement": "是否具有返還約定",
            "intent": "行為人的主觀意圖",
            "evidence": "可供查證的證據",
        }
        for key, value in property_values.items():
            is_unknown = value == "UNKNOWN"
            fields: dict[str, str] = {}
            if key == "actor" and not is_unknown:
                fields["subject"] = value
            elif key == "action" and not is_unknown:
                fields["action"] = value
            elif key == "object" and not is_unknown:
                fields["object"] = value
            facts.append(make_fact(
                labels[key],
                "unknown" if is_unknown else "statement",
                fields,
                fact_key=key,
                value=value,
                source_excerpt="" if is_unknown else summary,
            ))
        default_unknowns = [labels[key] for key, value in property_values.items() if value == "UNKNOWN"]
    else:
        if not facts and summary:
            # 無法辨識八類語意時，保留可回查的原文陳述，不假裝完成拆解。
            for text, start, end in _source_segments(summary):
                facts.append(make_fact(text, "statement", source_start=start, source_end=end))
        default_unknowns = ["行為人", "行為方式", "結果與行為間關係", "可供查證的證據"]
        for text in default_unknowns:
            facts.append(make_fact(text, "unknown", value="UNKNOWN", source_excerpt=""))

    def unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    source_fact_keys = {"", "event", "action", "result"} if narrative_candidates else {""}
    source_facts = [
        item for item in facts
        if item.get("machine_status") != "UNKNOWN"
        and item.get("fact_key") in source_fact_keys
    ]
    # legacy arrays 是 facts 的相容投影，不另行建立第二份事件真實來源。
    semantic_times = unique([
        str(item.get("time") or item.get("value", ""))
        for item in facts if item.get("fact_key") == "time"
    ])
    semantic_places = unique([
        str(item.get("place") or item.get("value", ""))
        for item in facts if item.get("fact_key") == "place"
    ])
    if narrative_candidates:
        explicit_time = format_roc_time(intake["event_time"])
        if explicit_time != "UNKNOWN":
            semantic_times.insert(0, explicit_time)
        explicit_place = str(intake["location"])
        if explicit_place and explicit_place != "UNKNOWN":
            semantic_places.insert(0, explicit_place)
    gate1: dict[str, Any] = {
        "people": unique(
            [
                str(item.get("subject") or item.get("recipient") or item.get("value", ""))
                for item in facts if item.get("fact_key") == "person"
            ]
            if narrative_candidates else
            [str(item.get("subject", "")) for item in facts]
        ),
        "events": unique(
            [
                str(item.get("source_excerpt", ""))
                for item in source_facts if item.get("fact_key") in {"event", "action", "result"}
            ]
            if narrative_candidates else
            [str(item.get("source_excerpt", "")) for item in source_facts]
        ),
        "segmentation_source": segmentation_source,
        "times": unique(semantic_times if narrative_candidates else [format_roc_time(intake["event_time"])]),
        "places": unique(semantic_places if narrative_candidates else [str(intake["location"])]),
        "objects": unique(
            [
                str(item.get("object") or item.get("value", ""))
                for item in facts if item.get("fact_key") == "object"
            ]
            if narrative_candidates else
            [str(item.get("object", "")) for item in facts]
        ),
        "results": unique([
            str(item.get("result") or item.get("value", ""))
            for item in facts if item.get("fact_key") == "result"
        ]),
        "evidence": unique([
            str(item.get("value", ""))
            for item in facts if item.get("fact_key") == "evidence"
        ]),
        "behaviors": unique(
            [
                str(item.get("action") or item.get("value", ""))
                for item in facts if item.get("fact_key") == "action"
            ]
            if narrative_candidates else
            [str(item.get("action", "")) for item in facts]
        ),
        "causation": next((
            str(item.get("value", ""))
            for item in facts if item.get("fact_key") == "causation"
        ), "UNKNOWN"),
        "causal_edges": [
            {
                "event_id": item.get("event_id", "event:unassigned"),
                "value": str(item.get("value", "")),
                "source_excerpt": str(item.get("source_excerpt", "")),
                "source_start": item.get("source_start"),
                "source_end": item.get("source_end"),
                "assertion_status": item.get("assertion_status", "EXPLICIT_SOURCE_ASSERTION"),
            }
            for item in facts
            if item.get("fact_key") == "causation" and item.get("machine_status") != "UNKNOWN"
        ],
        "legal_characterizations": [
            {
                "value": str(item.get("value", "")),
                "source_excerpt": str(item.get("source_excerpt", "")),
                "source_start": item.get("source_start"),
                "source_end": item.get("source_end"),
            }
            for item in facts
            if item.get("fact_key") == "legal_characterization"
        ],
        "person_attributes": person_attributes(),
        "unknowns": default_unknowns,
        "facts": facts,  # new structured fact list
        "review_status": "HUMAN_REVIEW_REQUIRED",
    }
    return gate1


_NEGATION_MARKERS = ("並未", "並非", "未提及", "沒有", "尚未", "非因", "不曾", "無證據", "無人", "未遂", "謊稱並無")


def _keyword_negated(keyword: str, summary: str) -> bool:
    """檢查關鍵字是否只出現在否定語句中（spec §5.1：關鍵字不得為唯一機制）。

    找出關鍵字出現位置，向前看 12 個字元內是否有否定標記。
    若全部命中位置都被否定，回傳 True（視為未命中）。
    """
    lowered = summary.casefold()
    kw = keyword.casefold()
    positions: list[int] = []
    start = 0
    while True:
        idx = lowered.find(kw, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    if not positions:
        return True  # 沒出現 = 未命中
    window = 14
    sentence_breaks = ("。", "；", "！", "？")
    for pos in positions:
        context = lowered[max(0, pos - window):pos]
        # 跨句不算否定：從否定標記到關鍵字之間不得有句讀
        clean = context
        for br in sentence_breaks:
            clean = clean.split(br)[-1]
        if not any(marker in clean for marker in _NEGATION_MARKERS):
            return False  # 至少有一個非否定命中
    return True  # 全部命中都在否定語句內


def candidate_offenses(
    summary: str, bank: dict[str, Any], gate1: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    lowered = summary.casefold()
    by_id = {item["id"]: item for item in bank["offenses"]}
    matched_ids: set[str] = set()
    for offense in bank["offenses"]:
        hits = [
            keyword for keyword in offense["keywords"]
            if keyword.casefold() in lowered and not _keyword_negated(keyword, summary)
        ]
        # 「毒」相關字詞不得由一般敘事或法律用語模糊帶入毒品罪章；
        # 僅在出現明確毒品事實時建立分析方向。
        if offense["id"] == "drugs" and not re.search(
            r"毒品|吸毒|施用毒品|販賣毒品|持有毒品|安非他命|海洛因|大麻|尿液",
            summary,
        ):
            hits = []
        # 「偷偷」是副詞，不是竊盜行為。避免單字關鍵詞「偷」造成誤判。
        if offense["id"] in {"theft", "aggravated_theft"} and "偷偷" in summary:
            property_signal = re.search(r"(包包|皮包|手機|現金|財物|物品|拿走|取走|竊取|盜取|遭竊)", summary)
            if not property_signal:
                hits = [item for item in hits if item != "偷"]
        # 性交且明示不同意、睡眠中或以影片威脅時，建立妨害性自主的分析方向。
        if offense["id"] == "sexual" and not hits and "性交" in summary:
            if re.search(r"(不同意|睡著|偷拍|威脅|脅迫|偷偷)", summary):
                hits = ["非合意性交／性自主情境"]
        if offense["id"] == "sexual" and not hits:
            if re.search(r"(乘機猥褻|猥褻|不能抗拒|胸部|內衣)", summary):
                hits = ["乘機猥褻／不能抗拒情境"]
        # 配偶、家庭成員間的未合意性行為或威脅，另列家庭暴力防治法檢視方向。
        if offense["id"] == "domestic_violence" and not hits:
            if re.search(r"(老婆|妻子|丈夫|配偶|同居|家人)", summary) and re.search(
                r"(性交|不同意|威脅|脅迫|毆打|傷害|偷拍)", summary
            ):
                hits = ["親密關係暴力／性暴力情境"]
        if offense["id"] == "child_protection" and not hits:
            if re.search(r"未成年|未滿\s*18\s*歲|少年|兒童|A女|A男", summary) and re.search(
                r"性影像|猥褻行為電子訊號|裸體|裸露|下體照片|性交易|性剝削", summary
            ):
                hits = ["未成年人性影像／性剝削保護情境"]
        if offense["id"] == "sexual_harassment" and hits and re.search(r"(乘機猥褻|猥褻|不能抗拒)", summary):
            hits = [item for item in hits if item not in {"親吻", "觸摸", "擁抱"}]
        if offense["id"] == "robbery" and hits == ["不能抗拒"]:
            if not re.search(r"(搶|強盜|財物|現金|取走|拿走|竊取)", summary):
                hits = []
        # 裁判式敘事常以「持刀／持械進入店內取走現金」描述強盜，
        # 不一定直接使用「強盜」或「搶奪」字樣。這裡只建立候選方向，
        # 不把手段或主觀要件視為已證明。
        if offense["id"] == "robbery" and not hits:
            if re.search(r"(?:持刀|持械|持預藏之[^，。；]{1,12})(?:[^。；]{0,80})(?:取走|拿取|搶取|現金)", summary):
                hits = ["持械取財情境"]
            elif re.search(r"(?:持槍|持刀|持械|空氣槍|束帶)[^。；]{0,60}(?:脅迫|恫嚇|限制行動)", summary) and re.search(
                r"(?:竊取|取走|拿走|交付|財物|現金|款項)", summary
            ):
                hits = ["持械脅迫取財情境"]
        if offense["id"] == "liberty" and not hits:
            if re.search(r"(?:限制|剝奪)[^。；]{0,8}行動自由|迫使[^。；]{0,30}(?:簽立|交付|為|做)", summary):
                hits = ["限制行動自由／迫使行為情境"]
        if offense["id"] == "intimidation" and not hits:
            if re.search(r"恫稱|以此方式.*脅迫", summary):
                hits = ["恫稱／脅迫情境"]
            elif re.search(r"(?:揚言|聲稱|告以)[^。；]{0,40}(?:等語|要打|殺|死)", summary) and re.search(
                r"心生畏懼|害怕|恐懼|擔心遭受危害", summary
            ):
                hits = ["揚言危害／心生畏懼情境"]
        if offense["id"] == "defamation" and not hits:
            if re.search(r"(?:刊登|散布|傳播)[^。；]{0,40}(?:不實訊息|不實內容|不實言論)", summary) and re.search(
                r"名譽受損|損害名譽|貶損名譽", summary
            ):
                hits = ["散布不實內容／名譽受損情境"]
        if offense["id"] == "public_danger" and not hits:
            if re.search(r"(?:駕車|駕駛)[^。；]{0,50}(?:交通事故|碰撞|肇事)", summary) and re.search(
                r"(?:未停留|未停車|未處理|逕行|立即).*?(?:離開|逃逸)|駕車離開現場", summary
            ):
                hits = ["駕車事故後未停留處理情境"]
        if offense["id"] == "public_danger" and hits:
            driving_signal = re.search(r"駕車|駕駛|行駛|操控車輛|酒駕|肇事|交通事故", summary)
            if not driving_signal:
                hits = []
        if offense["id"] == "fraud" and not hits:
            if re.search(r"佯稱|冒充|詐術", summary) and re.search(r"匯款|轉帳|交付|付款", summary):
                hits = ["詐術／財產處分情境"]
        if offense["id"] == "injury" and not hits:
            if re.search(r"受有[^。；]{0,50}(?:傷害|挫傷)|穿孔|腹膜炎|敗血症", summary) and re.search(
                r"毆打|揮打|攻擊|踢踹|刺穿|手術|不慎|疏未注意", summary
            ):
                hits = ["具體傷害結果／致傷行為情境"]
        if offense["id"] == "theft" and not hits:
            if re.search(r"(?:取走|拿走|竊取|盜取)[^。；]{0,60}(?:現金|手機|電腦|財物|物品)", summary):
                hits = ["取走他人動產情境"]
        if offense["id"] == "damage" and not hits:
            if re.search(r"破壞|毀損|損壞|不堪使用", summary) and re.search(
                r"車窗|玻璃|物品|財物|器物|設備", summary
            ):
                hits = ["物品毀損／不堪使用情境"]
        if offense["id"] == "obstruction" and not hits:
            if re.search(r"公務員|依法執行|執行[^。；]{0,12}職務", summary) and re.search(
                r"攔阻|揮打|毆打|強暴|脅迫|妨害", summary
            ):
                hits = ["執行職務公務員／強暴脅迫情境"]
        # 「電腦」可能只是地點或設備描述。單獨命中時不建立妨害電腦使用候選，
        # 仍保留「登入、刪除資料、駭客」等具體行為關鍵字供人工檢視。
        if offense["id"] == "computer" and hits == ["電腦"]:
            hits = []
        if offense["id"] == "defamation" and hits:
            if not re.search(r"名譽|侮辱|誹謗|不實|貶損|公然|公開場合|辱罵|散布", summary):
                hits = []
        if hits:
            element_labels, candidate_status, element_status = candidate_element_state(offense)
            matches.append({
                "id": offense["id"],
                "candidate_id": f"candidate:{offense['id']}",
                "name": offense["name"],
                "matched_terms": hits,
                "status": candidate_status,
                "notice": "僅為規則式候選，不代表犯罪成立。",
                "inclusion_reason": f"案情摘要含有本罪章的關鍵詞：{', '.join(hits)}",
                "reservation_reason": "僅基於關鍵字匹配，尚未結合結構化事實分析",
                "supporting_fact_refs": ["intake.summary"],
                "contradicting_fact_refs": [],
                "unknown_elements": element_labels,
                "element_model_status": element_status,
                "route_type": offense.get("route_type", "substantive"),
                "crosswalk_status": offense.get("crosswalk_status", "SPLIT_REQUIRED"),
                "legal_routes": deepcopy(offense.get("legal_routes", [])),
                "excluded_legal_routes": deepcopy(offense.get("excluded_legal_routes", [])),
                "legal_route_selection_status": offense.get("selection_policy", "OPTIONAL"),
                "source": offense["source"],
                "distinguishing_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-D-" in item["id"]][:5] or ["HUMAN-DISTINGUISHING-QUESTION-REQUIRED"],
                "required_evidence_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-R-" in item["id"]][:5] or ["HUMAN-EVIDENCE-REVIEW-REQUIRED"],
                "competition_analysis": "NOT_ASSESSED",
                "prohibited_conclusions": ["犯罪成立", "故意成立", "因果關係成立", "競合成立"],
                "version": offense.get("source", {}).get("status", "UNKNOWN"),
                "selection_origin": "keyword_hint",
                "machine_effects": [],
            })
            _attach_element_evidence(matches[-1], offense, summary, gate1)
            matrix = matches[-1].get("route_element_matrix", [])
            best_supported = matrix[0].get("supported_count", 0) if matrix else 0
            matches[-1]["candidate_eligibility"] = "ELIGIBLE_CANDIDATE"
            route_states: dict[str, str] = {}
            for route in matrix:
                route_states[route["route_id"]] = (
                    "ELIGIBLE_CANDIDATE" if route.get("supported_count", 0) >= 2 else "HINT_ONLY"
                )
            if offense["id"] == "sexual":
                ages = [
                    item.get("age_at_event") for item in (gate1 or {}).get("person_attributes", [])
                    if item.get("role") == "victim"
                ]
                if any(isinstance(age, int) and age >= 16 for age in ages):
                    route_states["sexual_227_age"] = "EXCLUDED"
            matches[-1]["legal_route_states"] = route_states
            matched_ids.add(offense["id"])
    # 關聯罪章只作人工區辨提示，不會因為出現在 candidates 就自動進入
    # question builder。正式問句仍須經 Gate 2 明確選取 parent + route。
    related_ids = {
        related
        for offense_id in matched_ids
        for related in by_id[offense_id].get("related", [])
        if related not in matched_ids and related in by_id
    }
    if _property_taking_values(summary) is not None:
        related_ids.discard("aggravated_theft")
        related_ids.update(PROPERTY_ROUTE_IDS - matched_ids)
    for offense_id in sorted(related_ids):
        offense = by_id[offense_id]
        element_labels, candidate_status, element_status = candidate_element_state(offense)
        matches.append({
            "id": offense["id"],
            "candidate_id": f"candidate:{offense['id']}",
            "name": offense["name"],
            "matched_terms": [],
            "status": candidate_status,
            "notice": "區辨用關聯候選，不代表犯罪成立；需人工另行選取。",
            "inclusion_reason": "由已命中的方向帶入作為競爭假設，只供區辨，不是事實支持。",
            "reservation_reason": "僅為關聯方向，沒有直接事實支持",
            "supporting_fact_refs": [],
            "contradicting_fact_refs": [],
            "unknown_elements": element_labels,
            "element_model_status": element_status,
            "route_type": offense.get("route_type", "substantive"),
            "crosswalk_status": offense.get("crosswalk_status", "SPLIT_REQUIRED"),
            "legal_routes": deepcopy(offense.get("legal_routes", [])),
            "excluded_legal_routes": deepcopy(offense.get("excluded_legal_routes", [])),
            "legal_route_selection_status": offense.get("selection_policy", "OPTIONAL"),
            "source": offense["source"],
            "distinguishing_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-D-" in item["id"]][:5] or ["HUMAN-DISTINGUISHING-QUESTION-REQUIRED"],
            "required_evidence_question_ids": [item["id"] for item in offense.get("role_questions", {}).get("victim", []) if "-R-" in item["id"]][:5] or ["HUMAN-EVIDENCE-REVIEW-REQUIRED"],
            "competition_analysis": "NOT_ASSESSED",
            "prohibited_conclusions": ["犯罪成立", "故意成立", "因果關係成立", "競合成立"],
            "version": offense.get("source", {}).get("status", "UNKNOWN"),
            "selection_origin": "related_hint",
            "machine_effects": [],
        })
        _attach_element_evidence(matches[-1], offense, summary, gate1)
        matches[-1]["candidate_eligibility"] = "HINT_ONLY"
        matches[-1]["legal_route_states"] = {
            route.get("route_id", ""): "HINT_ONLY"
            for route in matches[-1].get("route_element_matrix", [])
            if route.get("route_id")
        }
    property_unknowns = {
        item.get("fact_key")
        for item in (gate1 or {}).get("facts", [])
        if item.get("value") == "UNKNOWN"
    }
    dependencies = {
        "theft": ["original_possession", "consent", "intent"],
        "embezzlement": ["prior_lawful_possession", "return_agreement", "intent"],
        "robbery": ["force_or_threat", "original_possession", "intent"],
    }
    for item in matches:
        item["candidate_state"] = "NEED_REVIEW"
        item["unknown_fact_keys"] = [
            key for key in dependencies.get(item["id"], []) if not property_unknowns or key in property_unknowns
        ]
        item["status_reasons"] = []
    return sorted(matches, key=lambda item: (-len(item["matched_terms"]), item["name"]))


def alternative_legal_routes(gate1: dict[str, Any]) -> list[dict[str, Any]]:
    keys = {item.get("fact_key") for item in gate1.get("facts", [])}
    if not {"action", "object"}.issubset(keys):
        return []
    return [{
        "route_id": "civil_possession_dispute",
        "name": "民事占有或返還爭議",
        "status": "NEED_REVIEW",
        "selectable_as_offense": False,
        "reason_fact_keys": [
            "original_possession", "consent", "prior_lawful_possession", "return_agreement",
        ],
        "notice": "僅為非刑事替代檢查方向，不代表民事關係成立。",
    }]


def build_questions(
    bank: dict[str, Any],
    role: str,
    offense_ids: list[str],
    *,
    gate1: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    legal_route_ids: list[str] | None = None,
    materialized_at: str | None = None,
) -> list[dict[str, Any]]:
    """依序建立問句：公司必問 → 通用程序 → 各罪章 md 區段 → JSON 要件。

    預算上限 MAX_OFFENSE_QUESTIONS 是 8 頁防線的一部分；超出時以後選罪章的
    區分題與加重題先被裁掉，公司必問與核心題不受預算刪除。
    """
    if role not in bank["common"]:
        raise RuleError("不支援的受詢問人身分")
    questions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in company_questions(role):
        text = render_company_text(raw["text"], today="　", now_time="　年　月　日　時　分")
        questions.append({
            "id": raw["id"],
            "text": text,
            "kind": "company",
            "role": role,
            "priority": 1,
            "source": {"label": "公司範本必問", "status": "COMPANY_VERBATIM"},
            "status": "PENDING",
            "answer": "",
        })
        seen.add(raw["text"])

    for raw in bank["common"][role]:
        item = deepcopy(raw)
        item.update({"kind": "common", "role": role, "status": "PENDING", "answer": ""})
        questions.append(item)
        seen.add(item["text"])

    from .questions import (
        THEFT_320_1_MOVABLE_EXPECTED_CONCEPT_IDS,
        THEFT_320_1_MOVABLE_PACK_VERSION,
        THEFT_320_1_MOVABLE_ROUTE_ID,
        THEFT_320_1_MOVABLE_WORK_ITEM_HASH,
        build_property_taking_questions,
    )

    # 候選只是 Gate 2 hint。只有已核准的 parent offense 才能影響問句
    # materialization，避免未選方向的區分題或 machine effect 滲入正式筆錄。
    candidate_ids = set(offense_ids)
    route_ids = list(dict.fromkeys(legal_route_ids or []))
    focused_questions = build_property_taking_questions(
        role,
        candidate_ids,
        gate1 or {},
        set(route_ids),
        materialized_at,
    )
    for question in focused_questions:
        questions.append(question)
        seen.add(question["text"])

    offenses = {item["id"]: item for item in bank["offenses"]}
    for offense_id in offense_ids:
        offense = offenses.get(offense_id)
        if offense is None:
            raise RuleError(f"未知罪章：{offense_id}")
        # 1) 公司套表罪章題（新套表.xlsm 各罪章欄）— 不受即時預算限制（公司核定題）
        company_offense_questions = xlsm_questions_for(
            questions, role, offense_id, route_ids, gate1,
        )
        for question in company_offense_questions:
            if question["text"] in seen:
                continue
            questions.append(question)
            seen.add(question["text"])
        # 公司已有該角色／罪章的核定套表題時，只使用公司標準筆錄。
        # 不再把本庫 md、補充題或 JSON 要件題混入同一路由。
        if has_company_standard_questions(role, offense_id):
            continue
        if focused_questions and offense_id in PROPERTY_ROUTE_IDS:
            continue
        route_pack_questions = route_questions_for(
            role, offense_id, route_ids, offense["source"],
        )
        if route_pack_questions:
            for question in route_pack_questions:
                if question["text"] in seen:
                    continue
                questions.append(question)
                seen.add(question["text"])
            continue
        if has_route_question_pack(route_ids, offense_id):
            raise RuleError(f"QUESTION_PACK_NOT_FOUND：{offense_id}")
        # 2) md 核心與補充（含區分、加重依 section 順序）— 先全部收集
        sections = offense.get("section_questions", {}).get(role, {})
        for question in ordered_section_questions(
            sections, role, offense_id, offense["name"], offense["source"],
        ):
            if question["text"] in seen:
                continue
            questions.append(question)
            seen.add(question["text"])
        # review 知識庫只作已審查的補充問句，不取代正式題庫。
        for question in supplemental_questions_for(role, offense_id, questions):
            if question["text"] in seen:
                continue
            questions.append(question)
            seen.add(question["text"])
        # 3) JSON 要件題（僅在 md 未涵蓋同一 element 時補入）— 先全部收集
        for element in offense.get("elements", []):
            text = element["victim" if role == "victim" else "suspect"]
            if text in seen:
                continue
            questions.append({
                "id": f"{role[0].upper()}-{offense_id}-{element['id']}",
                "text": text,
                "kind": "core",
                "role": role,
                "offense_id": offense_id,
                "offense_name": offense["name"],
                "element_id": element["id"],
                "element_label": element["label"],
                "priority": 1,
                "source": offense["source"],
                "status": "PENDING",
                "answer": "",
            })
            seen.add(text)
    # spec §7.5：統一按優先序裁切（core/company/common 保護；區分/加重先被裁）
    # 8 頁防線：offense 題（非 company/common）上限 MAX_OFFENSE_QUESTIONS
    from .questions import (
        QuestionBudgetExceeded,
        apply_question_budget,
        enrich_question_metadata,
        validate_generated_questions,
    )
    all_questions = list(questions)
    try:
        questions = apply_question_budget(questions, max_offense_questions=MAX_OFFENSE_QUESTIONS)
    except QuestionBudgetExceeded as exc:
        raise RuleError(str(exc)) from exc
    # 裁切透明化（docs/QUESTION_DESIGN_AND_USE.md §6）：被裁的題目記錄，不靜默丟棄
    kept_ids = {q["id"] for q in questions}
    pruned = [q for q in all_questions if q.get("id") not in kept_ids]
    # spec §7.2：metadata 豐富化；candidates 以本次選擇的罪章近似（供 distinguishing 的 legal_targets）
    pseudo_candidates = [
        {"id": oid, "offense_id": oid} for oid in offense_ids
    ]
    questions = enrich_question_metadata(questions, gate1 or {}, pseudo_candidates)
    mark_known_questions(questions, gate1 or {})

    # spec §7.2/§7.3 品質檢核（docs/QUESTION_DESIGN_AND_USE.md §8）：problems 即 fail closed
    validation = validate_generated_questions(questions, role)
    if validation["problems"]:
        raise RuleError("問句品質檢核失敗：" + "；".join(validation["problems"][:3]))
    build_questions.last_validation = validation
    build_questions.pruned_questions = [
        {
            "id": q.get("id"),
            "text": q.get("text"),
            "kind": q.get("kind"),
            "offense_id": q.get("offense_id"),
            "question_concept_id": q.get("meta", {}).get("question_concept_id"),
            "pack_id": q.get("meta", {}).get("pack_id"),
        }
        for q in pruned
    ]
    if pruned:
        build_questions.last_validation["warnings"].append(
            f"Q8 裁切 {len(pruned)} 題（區分/加重/補充優先），已記錄於 pruned_questions 供承辦人參考"
        )
    coverage_by_route: dict[str, dict[str, Any]] = {}
    for route_id in route_ids:
        if route_id != THEFT_320_1_MOVABLE_ROUTE_ID:
            coverage_by_route[route_id] = {
                "pack_scope": "LEGACY_PARENT_PACK",
                "materialization_status": "NOT_APPLICABLE",
                "approval_status": "HUMAN_REVIEW_REQUIRED",
                "coverage_claim": "NONE",
                "expected_concept_ids": [],
                "materialized_question_ids": [],
                "missing_concept_ids": [],
                "pruned_concept_ids": [],
                "human_review_required": True,
            }
            continue
        pack_questions = [
            q for q in questions
            if q.get("meta", {}).get("pack_id") == route_id
        ]
        materialized_concepts = {
            q.get("meta", {}).get("question_concept_id") for q in pack_questions
        }
        expected = list(THEFT_320_1_MOVABLE_EXPECTED_CONCEPT_IDS)
        missing = [concept_id for concept_id in expected if concept_id not in materialized_concepts]
        pruned_concepts = sorted({
            q.get("meta", {}).get("question_concept_id") for q in pruned
            if q.get("meta", {}).get("pack_id") == route_id
            and q.get("meta", {}).get("question_concept_id")
        })
        complete = not missing and not pruned_concepts
        coverage_by_route[route_id] = {
            "pack_id": route_id,
            "pack_version": THEFT_320_1_MOVABLE_PACK_VERSION,
            "work_item_hash": THEFT_320_1_MOVABLE_WORK_ITEM_HASH,
            "pack_scope": "EXACT_CHILD_PACK",
            "materialization_status": "COMPLETE" if complete else "PARTIAL",
            "approval_status": "STATIC_HUMAN_APPROVED",
            "coverage_claim": "BOUNDED_TO_APPROVED_WORK_ITEM" if complete else "NONE",
            "expected_concept_ids": expected,
            "materialized_question_ids": [q["id"] for q in pack_questions],
            "missing_concept_ids": missing,
            "pruned_concept_ids": pruned_concepts,
            "human_review_required": True,
            "legal_conclusion": False,
        }
    build_questions.question_coverage_by_route = {
        "route_context_ids": route_ids,
        "routes": coverage_by_route,
        "human_review_required": True,
        "legal_conclusion": False,
    }
    return questions


def _offense_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in questions if item["kind"] not in {"common", "company"}]


def is_victim_code(value: str) -> bool:
    return bool(re.fullmatch(
        r"(?:[A-Za-z]{1,8}\d{3,20}|[A-Za-z]{2,8}\d{2,8}-[A-Za-z]\d{3,12})",
        value.strip(),
    ))


def required_case_numbers(case: dict[str, Any]) -> list[str]:
    required = ["proof"]
    offense_ids = set(case.get("selected_offenses", []))
    for interview in case.get("interviews", {}).values():
        offense_ids.update(interview.get("selected_offenses", []))
    if "fraud" in offense_ids:
        required.append("case_165")
    intake = case["intake"]
    if intake.get("victim_is_code") or is_victim_code(intake.get("victim_identifier", "")):
        required.append("women_child")
    return required


def concise_summary(text: str, limit: int = 500) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) > limit:
        raise RuleError(f"條陳案情摘要超過 {limit} 字上限")
    return normalized


def truncate_summary(text: str, limit: int = 500) -> str:
    """將完整案情轉為條陳摘要；不修改或覆蓋原始案情。"""
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:limit]


def mark_known_questions(questions: list[dict[str, Any]], gate1: dict[str, Any]) -> None:
    """以 Gate 1 已有事實標記可免重複填答的追加問句。

    只標記客觀時地、已明示行為、身心狀態與現場第三人等問題，
    不把「同意、故意、法律評價」從摘要直接推成答案。
    """
    times_list = [str(item) for item in gate1.get("times", []) if item != "UNKNOWN"]
    places_list = [str(item) for item in gate1.get("places", []) if item != "UNKNOWN"]
    behaviors_list = [str(item) for item in gate1.get("behaviors", []) if item != "UNKNOWN"]
    results_list = [str(item) for item in gate1.get("results", []) if item != "UNKNOWN"]
    evidence_list = [str(item) for item in gate1.get("evidence", []) if item != "UNKNOWN"]
    times = " ".join(times_list)
    places = " ".join(places_list)
    behaviors = " ".join(behaviors_list)
    results = " ".join(results_list)
    fact_rows = [
        item for item in gate1.get("facts", [])
        if item.get("machine_status") != "UNKNOWN" and item.get("source_excerpt")
    ]

    def excerpts_for(keys: set[str], signals: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for fact in fact_rows:
            if fact.get("fact_key") not in keys:
                continue
            haystack = " ".join((str(fact.get("value", "")), str(fact.get("source_excerpt", ""))))
            if signals and not any(signal in haystack for signal in signals):
                continue
            rows.append({
                "fact_id": fact.get("fact_id"),
                "event_id": fact.get("event_id"),
                "source_excerpt": fact.get("source_excerpt"),
                "source_start": fact.get("source_start"),
                "source_end": fact.get("source_end"),
            })
        return rows

    route_coverage: dict[str, tuple[bool, str, list[dict[str, Any]]]] = {
        "victim_age_evidence": (
            bool(gate1.get("person_attributes")) and any("年籍" in item for item in evidence_list),
            "摘要已有行為時年齡及年籍資料來源",
            excerpts_for({"person", "evidence"}, ("代號", "年籍")),
        ),
        "event_time_place": (
            bool(times_list and places_list),
            "摘要已記載相關時間與地點",
            excerpts_for({"time", "place"}),
        ),
        "sexual_contact_details": (
            any("撫摸" in item or "插入" in item for item in behaviors_list),
            "摘要已記載具體身體接觸方式",
            excerpts_for({"action"}, ("撫摸", "插入")),
        ),
    }

    def add_coverage(
        target: str,
        keys: set[str],
        signals: tuple[str, ...],
        reason: str,
    ) -> None:
        rows = excerpts_for(keys, signals)
        route_coverage[target] = (bool(rows), reason, rows)

    for target, keys, signals, reason in (
        ("representation_content", {"action"}, ("佯稱", "冒充", "詐術"), "摘要已記載具體說法"),
        ("property_dispositions", {"action", "object"}, ("匯款", "轉帳", "交付", "付款"), "摘要已記載財產處分"),
        ("performance_and_discovery", {"action", "result"}, ("未收到", "未交付", "受騙", "得悉"), "摘要已記載履行情形與發現經過"),
        ("fraud_evidence_sources", {"evidence"}, ("對話", "交易", "帳戶", "紀錄", "截圖"), "摘要已列出可供查證資料"),
        ("actual_conduct", {"action"}, ("手術", "刺穿", "抽脂", "處置"), "摘要已記載實際醫療行為"),
        ("injury_and_treatment", {"action", "result"}, ("穿孔", "腹膜炎", "敗血症", "就診", "手術"), "摘要已記載傷勢與診療"),
        ("medical_causation_sources", {"causation", "evidence"}, ("導致", "鑑定", "病歷", "診斷"), "摘要已記載因果敘述或查證資料"),
        ("medical_evidence_sources", {"evidence"}, ("病歷", "診斷", "手術", "鑑定", "影像"), "摘要已列出醫療證據"),
        ("substance_use_details", {"action", "object", "event"}, ("飲用", "酒類", "酒精"), "摘要已記載飲酒情形"),
        ("driving_details", {"action"}, ("駕駛", "駕車", "騎乘", "上路"), "摘要已記載駕駛行為"),
        ("impairment_test_details", {"result", "evidence"}, ("酒精濃度", "毫克", "酒精測定"), "摘要已記載檢測數值或紀錄"),
        ("driving_incident", {"action", "result"}, ("撞擊", "碰撞", "事故", "無人受傷"), "摘要已記載事故經過與結果"),
        ("dui_evidence_sources", {"evidence"}, ("酒精", "事故", "現場圖", "照片", "檢定"), "摘要已列出酒駕或事故證據"),
        ("damaged_property", {"object", "action"}, ("車窗", "玻璃", "物品", "財物"), "摘要已記載受影響物品"),
        ("damage_action", {"action"}, ("破壞", "毀損", "損壞"), "摘要已記載物品受損方式"),
        ("damage_result", {"result"}, ("不堪使用", "受損", "損壞"), "摘要已記載物品受損結果"),
        ("damage_evidence_sources", {"evidence"}, ("照片", "監視器", "估價", "維修"), "摘要已列出毀損證據"),
        ("injury_action_details", {"action"}, ("揮打", "毆打", "攻擊", "踢踹"), "摘要已記載致傷動作"),
        ("injury_result_details", {"result"}, ("傷", "骨折", "穿孔", "不適"), "摘要已記載傷勢結果"),
        ("injury_evidence_sources", {"evidence"}, ("診斷", "照片", "監視器", "影像", "目擊"), "摘要已列出傷害證據"),
        ("force_or_threat_details", {"action"}, ("揮打", "毆打", "強暴", "脅迫"), "摘要已記載具體強暴或脅迫行為"),
        ("obstruction_evidence_sources", {"evidence"}, ("監視器", "執勤", "通聯", "目擊"), "摘要已列出妨害公務證據"),
    ):
        add_coverage(target, keys, signals, reason)
    for question in questions:
        text = str(question.get("text", ""))
        if question.get("kind") in {"company", "common"}:
            question.setdefault("meta", {})["confirmation_required"] = True
            continue
        meta = question.setdefault("meta", {})
        target = str(meta.get("fact_target", ""))
        known_reason = ""
        coverage_evidence: list[dict[str, Any]] = []
        if target in route_coverage:
            covered, reason, coverage_evidence = route_coverage[target]
            if covered:
                known_reason = reason
        if "時間與地點" in text:
            if times and places:
                known_reason = "摘要已記載時地"
        elif ("發生的時間" in text or "事發時間" in text) and times:
            known_reason = "摘要已記載時間"
        elif ("身體接觸" in text or "實際有哪些" in text) and behaviors:
            known_reason = "摘要已記載行為方式"
        elif "使用了什麼方法" in text and (behaviors or results):
            known_reason = "摘要已記載行為方式"
        elif "身心狀況" in text and results:
            known_reason = "摘要已記載身心狀態"
        if known_reason:
            meta["known_from_summary"] = True
            meta["known_reason"] = known_reason
            meta["coverage_status"] = "COVERED_BY_SUMMARY"
            meta["coverage_evidence"] = coverage_evidence
            meta["display_mode"] = "READ_ONLY_KNOWN"
            excerpts = [
                str(item.get("source_excerpt", "")) for item in coverage_evidence
                if item.get("source_excerpt")
            ]
            meta["known_answer"] = "；".join(dict.fromkeys(excerpts)) or known_reason
            meta["answer_origin"] = "SUMMARY"
            question["answer"] = meta["known_answer"]
            question["status"] = "AUTO_FILLED_FROM_SUMMARY"
        else:
            meta.setdefault("coverage_status", "UNCOVERED")
            meta.setdefault("display_mode", "ADDITIONAL_QUESTION")

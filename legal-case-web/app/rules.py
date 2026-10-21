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

# 一條法規路線至少要能在摘要中找到幾個構成要件的可回查原文，才足以被「建議」
# 為本案方向，也才列為合格候選（ELIGIBLE_CANDIDATE）。建議與狀態兩處必須共用
# 同一門檻，否則會出現「建議某路線、該路線狀態卻是 HINT_ONLY」的自相矛盾。
ROUTE_MIN_SUPPORTED_ELEMENTS = 2

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
    if element == "是否逾越一般人可合理忍受範圍":
        return []
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
        (("他人動產及原持有狀態",), ("包包", "現金", "手機", "財物", "物品", "所有", "放置", "抽屜", "貨架", "洗髮精")),
        (("未經同意竊取並破壞原持有",), ("竊取", "偷走", "拿走", "拿取", "取走", "未結帳", "遭竊", "不翼而飛")),
        (("為自己或第三人不法所有之意圖", "為自己或第三人不法所有意圖"), ("不法所有",)),
        (("搶奪他人動產行為",), ("搶奪", "搶取", "奪走")),
        (("先前竊盜或搶奪行為",), ("竊盜", "竊取", "搶奪", "搶取")),
        (("防護贓物、脫免逮捕或湮滅罪證目的",), ("防護贓物", "脫免逮捕", "湮滅罪證")),
        (("當場施以強暴脅迫",), ("當場", "強暴", "脅迫", "毆打", "拉扯")),
        (("未遂或既遂", "性交未遂或既遂", "結果加重、預備、未遂或既遂"), ("得手", "得逞", "得款", "轉帳匯款", "再次匯款", "已交付", "未遂", "既遂", "始停止")),
        (("家庭成員關係",), ("老婆", "妻子", "丈夫", "配偶", "同居", "家人")),
        (("身體、精神或經濟上騷擾、控制、脅迫或其他不法侵害",), ("毆打", "傷害", "威脅", "脅迫", "不同意", "偷拍", "性交")),
        (("私行拘禁或其他非法方法",), ("拘禁", "限制行動自由", "剝奪行動自由", "圍堵", "綑綁", "束帶")),
        (("被害人行動自由遭剝奪的期間與程度",), ("限制行動自由", "剝奪行動自由", "不能離開", "無法離開")),
        (("強暴或脅迫方法",), ("強暴", "脅迫", "毆打", "恫嚇", "持槍", "持刀")),
        (("強暴、脅迫、藥劑、催眠術或其他方法",), ("強暴", "脅迫", "持刀", "持槍", "捆綁", "勒住", "毆打")),
        (("被害人達不能抗拒程度",), ("不能抗拒", "無法抗拒")),
        (("取物、使交付或取得財產上不法利益",), ("搶走", "奪走", "取走", "交付現金", "交付財物", "交付金錢")),
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
        (("第352條及第353條以外之他人之物",), ("車窗", "車燈", "自小客車", "玻璃", "物品", "財物", "所有")),
        (("毀棄損壞或致令不堪用",), ("破壞", "毀損", "砸毀", "損壞", "不堪使用")),
        (("足以生損害於公眾或他人",), ("不堪使用", "受損", "損害")),
        (("公務員依法執行職務或特定職務目的",), ("公務員", "員警", "警察", "執勤", "依法執行", "執行", "職務", "門禁")),
        (("強暴或脅迫行為",), ("推開", "推打", "推擠", "扯住", "拉扯", "揮打", "毆打", "攻擊", "強暴", "脅迫")),
        (("意圖性騷擾",), ("性騷擾", "觸摸臀部", "觸摸胸部", "摸臀", "摸胸")),
        (("乘被害人不及抗拒之際",), ("不及抗拒", "趁", "突然")),
        (("親吻、擁抱或觸摸臀部、胸部或其他身體隱私處之行為",), ("親吻", "擁抱", "觸摸", "臀部", "胸部", "身體隱私處")),
        (("施用行為、時間、地點及方法",), ("施用", "吸食", "燒烤方式")),
        (("毒品品項及第一級或第二級分類", "毒品品項及級別"), ("第一級毒品", "第二級毒品", "甲基安非他命", "海洛因", "大麻")),
        (("採尿、鑑驗或其他可回查證據",), ("採尿", "尿液", "鑑驗", "搜索票", "查獲", "坦承", "吸食器")),
        (("指摘或傳述具體事項",), ("指稱", "貼文", "刊登", "傳述", "具體事項")),
        (("足以毀損他人名譽",), ("名譽受損", "毀損名譽", "貶損名譽")),
        (("散布於眾意圖及文字圖畫態樣",), ("公開貼文", "社群平台", "網路", "散布", "文字", "圖畫")),
        (("故意發表公然貶損他人名譽之言論",), ("辱罵", "侮辱", "貶損", "貶低")),
        (("個案表意脈絡及公然性",), ("不特定人", "共見共聞", "公開場合", "公開場所")),
        (("是否逾越一般人可合理忍受範圍",), ("辱罵", "侮辱", "貶損人格", "人格評價")),
        (("以人員設備通訊網路或其他方法對特定人",), ("住處", "工作地點", "傳送訊息", "盯梢", "等候")),
        (("反覆或持續且違反意願",), ("反覆", "持續", "多次", "遭拒")),
        (("與性或性別有關，或對密切關係人之法定例外",), ("追求", "交往", "性別", "性")),
        (("使人心生畏怖且足以影響日常生活或社會活動",), ("心生畏怖", "心生畏懼", "影響日常生活", "影響工作")),
        (("八款法定行為態樣",), ("監視", "觀察", "跟蹤", "盯梢", "守候", "等候", "傳送訊息", "通訊")),
    ]
    patterns: list[tuple[str, ...]] = []
    for element_fragments, signals in rules:
        if any(fragment in element for fragment in element_fragments):
            patterns.append(signals)
    if patterns:
        return patterns
    # 沒有受審查的比對依據時回傳空清單，呼叫端據此標為 NOT_CHECKABLE。
    # 不得退回「要求要件字面出現在摘要」：散文不會寫出法條字面，那是不可能命中的
    # 假比對，只會把工具的覆蓋缺口誤導成「已比對而摘要未見」。
    return []


def _unnegated_signal_occurrences(
    signal: str, summary: str, source_segments: list[tuple[str, int, int]]
) -> list[tuple[str, int, int, int, int]]:
    """Return source-backed, individually unnegated literal signal spans."""
    occurrences: list[tuple[str, int, int, int, int]] = []
    for segment, segment_start, segment_end in source_segments:
        for match in re.finditer(re.escape(signal), segment):
            local_start, local_end = match.span()
            context = segment[max(0, local_start - 14):local_end]
            if _keyword_negated(signal, context):
                continue
            occurrences.append((
                segment,
                segment_start,
                segment_end,
                segment_start + local_start,
                segment_start + local_end,
            ))
    return occurrences


def _route_element_matrix(
    offense: dict[str, Any], summary: str, gate1: dict[str, Any] | None
) -> list[dict[str, Any]]:
    facts = (gate1 or {}).get("facts", [])
    source_segments = _source_segments(summary)
    analyses: list[dict[str, Any]] = []
    for route in offense.get("legal_routes", []):
        rows: list[dict[str, Any]] = []
        supporting_refs: list[str] = []
        for element in route.get("fact_elements", []):
            patterns = _element_evidence_patterns(element)
            matched_signals: list[str] = []
            refs: list[str] = []
            excerpts: list[str] = []
            for signal_group in patterns:
                for signal in signal_group:
                    occurrences = _unnegated_signal_occurrences(signal, summary, source_segments) if signal else []
                    if not occurrences:
                        continue
                    matched_signals.append(signal)
                    for segment, _, _, _, _ in occurrences:
                        if segment not in excerpts:
                            excerpts.append(segment)
                    for fact in facts:
                        source_start = fact.get("source_start")
                        source_end = fact.get("source_end")
                        if not isinstance(source_start, int) or not isinstance(source_end, int):
                            continue
                        if not any(
                            source_start < occurrence_end and source_end > occurrence_start
                            for _, _, _, occurrence_start, occurrence_end in occurrences
                        ):
                            continue
                        ref = str(fact.get("fact_id", ""))
                        if ref and ref not in refs:
                            refs.append(ref)
            if matched_signals and not refs:
                refs = ["intake.summary"]
            for ref in refs:
                if ref not in supporting_refs:
                    supporting_refs.append(ref)
            # 三值不得混為一談：NOT_CHECKABLE 是「本工具沒有這個要件的比對依據」
            # （覆蓋缺口），ABSENT 才是「已比對而摘要未見」。前者不可被讀成事實
            # 缺失，後者不可被讀成工具沒查。
            if not patterns:
                status = "NOT_CHECKABLE"
            elif matched_signals:
                status = "SOURCE_SUPPORTED"
            else:
                status = "ABSENT"
            rows.append({
                "element": element,
                "status": status,
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
            "not_checkable_count": sum(row["status"] == "NOT_CHECKABLE" for row in rows),
            "total_count": len(rows),
            "supporting_fact_refs": supporting_refs,
            "unknown_elements": [row["element"] for row in rows if row["status"] != "SOURCE_SUPPORTED"],
            "elements": rows,
        })
    return sorted(
        analyses,
        key=lambda item: (-item["supported_count"], len(item["unknown_elements"]), item["route_id"]),
    )


def _union_unknown_elements(matrix: list[dict[str, Any]]) -> list[str]:
    """所有路線皆未被支持時，列出整章的待補問要件（去重、保留順序）。"""
    union: dict[str, None] = {}
    for row in matrix:
        for element in row.get("unknown_elements", []):
            union.setdefault(element, None)
    return list(union)


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
    supported = best["supported_count"]
    candidate["suggested_legal_route_ids"] = (
        [best["route_id"]] if supported >= ROUTE_MIN_SUPPORTED_ELEMENTS else []
    )
    # 全部路線都沒有可回查原文時，matrix[0] 只是「元素最少」的排序結果，不代表
    # 本案方向。此時不得指名任何路線，否則會把無關罪名的要件寫進候選說明
    # （實例：竊盜案被說明成「電能、熱能或其他能量準動產」）。
    candidate["unknown_elements"] = (
        best["unknown_elements"] if supported else _union_unknown_elements(matrix)
    )
    candidate["supporting_fact_refs"] = best["supporting_fact_refs"]
    if offense.get("crosswalk_status") != "SPLIT_REQUIRED":
        candidate["element_model_status"] = "SOURCE_EVIDENCE_MATRIX"
    keyword_note = "、".join(candidate.get("matched_terms", [])) or "無直接關鍵詞"
    if supported:
        candidate["inclusion_reason"] = (
            f"關鍵詞提示：{keyword_note}；摘要對「{best['route_name']}」"
            f"{supported}/{best['total_count']} 個構成要件有可回查原文；"
            "仍僅為候選分析方向。"
        )
        uncheckable_note = (
            f"（其中 {best['not_checkable_count']} 項本工具無比對依據，須由人工閱讀原文判斷）"
            if best.get("not_checkable_count") else ""
        )
        candidate["reservation_reason"] = (
            "結構化事實尚待補問：" + "、".join(best["unknown_elements"]) + uncheckable_note
            if best["unknown_elements"]
            else "結構化事實均有摘要原文片段，但仍須人工核對真實性與法律評價"
        )
        return
    candidate["inclusion_reason"] = (
        f"關鍵詞提示：{keyword_note}；摘要尚無足以支持任何特定法規路線的可回查原文，"
        "路線須由人工判斷；仍僅為候選分析方向。"
    )
    candidate["reservation_reason"] = (
        "本罪章結構化事實尚待補問：" + "、".join(candidate["unknown_elements"])
        if candidate["unknown_elements"]
        else "結構化事實均有摘要原文片段，但仍須人工核對真實性與法律評價"
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
    # 侵占／拒不返還敘述（「保管公款後拒不返還」）沒有「拿走」類動作詞；
    # 需同時具備持有／保管訊號才視為摘要自身描述的財產處分行為，
    # 引述指控句（他人說我侵占）不觸發本路徑。
    embezzle_action = ""
    if not action:
        possession_signal = re.search(r"保管|代管|寄放|經手|代收|受託|持有", summary)
        embezzle_match = re.search(r"侵占|拒不返還", summary)
        if possession_signal and embezzle_match:
            embezzle_action = embezzle_match.group(0)
    if not action and not embezzle_action:
        return None
    actor_match = re.search(r"(?:^|[，。；！？\s])([^，。；！？\s]{1,8})把", summary)
    actor = actor_match.group(1) if actor_match else next(
        (item for item in ("對方", "他", "她", "行為人") if item in summary), "UNKNOWN"
    )
    action_pattern = "|".join(PROPERTY_TAKING_ACTIONS) + (f"|{embezzle_action}" if embezzle_action else "")
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
        "action": "取走物品" if action else (embezzle_action or "取走物品"),
        "object": obj,
        "original_possession": "UNKNOWN",
        "consent": consent,
        "prior_lawful_possession": prior_possession,
        "force_or_threat": force,
        "return_agreement": return_agreement,
        "intent": "UNKNOWN",
        "evidence": evidence,
    }


# 財物罪章共用錨點（E4 輪，2026-10-20）：區辨訊號與候選閘門共用同一
# 份取財／使人交付錨點。「要／喊著要」引導的搶奪只是表達意圖，不作為
# 已描述之取財事實（lookbehind 排除）。
# E5 輪（人工複審 2026-10-20 第四輪 ✗）：泛用「交(出|付|給)」會讓無關的
# 「不能抗拒」語境＋任意「交付」（契約義務、文件往來）誤觸 robbery；
# 交付面改為綁定財物對象（交出錢包／交付財物／使人交付）。
_ROBBERY_TAKE_ANCHOR = (
    r"(?<!要)(?<!喊著)(?:搶(走|奪|取|劫|得)|強搶|(強|奪)(取|走))"
    r"|劫(走|取|財)"
    r"|交出.{0,20}(現金|錢包|皮包|財物|手機|錢|鑰匙|存摺|車|證件|珠寶|金器)"
    r"|交付(財物|金錢|現金|贓款|款項|皮包|手機|車)"
    r"|使人(不能抗拒)?(而)?交付(財物|金錢|現金|贓款|款項|皮包|手機|車|鑰匙|存摺|證件|珠寶|金器)"
    r"|(?:店員|店裡的人|對方|被害人).{0,8}給(?:了)?(?:錢|現金|財物)?"
    r"|給(?:了)?(?:錢|現金|財物)"
    r"|(?<!要)(?<!喊著)強行.{0,8}(拿|帶)"
    r"|把.{0,10}(現金|錢包|皮包|手機|錢|車).{0,10}(交|奪|搶)"
)


def _property_discriminators(summary: str) -> dict[str, bool]:
    """財物罪章三路區辨訊號（人工核定 D1「B 修正版」，2026-10-20）。

    只回報摘要中是否存在對應的「區辨事實語句」，不判定任何法律要件
    成立，也不改變 candidate 狀態語義。三路依人工審查定案：
    - consent_take：未經同意取走／破壞原持有（theft 方向）。
    - entrusted_possession：先前合法持有／受託保管（embezzlement 前提）。
    - conversion：變易持有、處分或拒不返還（embezzlement 方向）。
    - violence_take：強暴／脅迫等手段＋奪取或使人交付（robbery 方向）。
    缺對應區辨事實時，對應 related 候選不會被建立。
    E4 輪（人工複審 2026-10-20）：全部改用 14 字元否定窗口評估
    （_patterns_unnegated），「沒有侵占／沒有搶走」等否定敘述不得
    作為區辨事實把 related 候選帶回。
    """
    return {
        "consent_take": _patterns_unnegated([
            r"未經.{0,8}(同意|允許)|沒有同意|擅自|偷偷|悄悄|趁.{0,10}不(注意|備)|偷(走|拿|翻)|闖入",
        ], summary),
        "entrusted_possession": _patterns_unnegated([
            r"保管|代管|代收|受託|經手|業務上|公款|拾得|撿到",
        ], summary),
        "conversion": _patterns_unnegated([
            r"拒不返還|占為己有|據為己有|花用|侵吞|轉(到|入|進)自己(的)?(帳戶|名下)",
        ], summary),
        "violence_take": _patterns_unnegated([
            r"強暴|脅迫|持(刀|槍|械)|菜刀|兇器|捅|行兇|捆綁|勒住|毆打",
        ], summary) and _patterns_unnegated([_ROBBERY_TAKE_ANCHOR], summary),
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
            "共聞", "不特定人",
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
    for match in re.finditer(
        r"(?:在|於)(?:不特定人可共見共聞之)?([^，。；]{1,30}?(?:休息室|辦公室|包廂|廁所))(?:內)?",
        summary,
    ):
        place = re.sub(r"^不特定人可共見共聞之", "", match.group(1))
        add("place", match.group(0), value=place, start=match.start(), fields={"place": place})
    for match in re.finditer(r"在([^，。；]+?)(?:中|上|內|附近)(?=[因，。；])", summary):
        place = re.sub(r"^不特定人可共見共聞之", "", match.group(1))
        add("place", match.group(1), value=place, fields={"place": place})
    for match in re.finditer(r"(?:前往|位在)([^，。；]+?)(?:中|上|內|附近)(?=[因，。；])", summary):
        add("place", match.group(1))
    # 裁判書常以「在○○工寮，…」或「於○○病房，…」直接接逗號，
    # 不一定有「內／上」結尾；只收有地點詞的連續原文，避免把整句動作當地點。
    location_terms = r"(?:市|縣|區|鄉|鎮|路|街|段|巷|號|夜市|住處|醫院|病房|工寮|店內|路口|大廳|廣場|學校)"
    for match in re.finditer(r"(?:在|於)([^，。；]{2,80})", summary):
        segment = match.group(1)
        # 「於某日赴醫院就診／於某時駕駛」的介系詞引出時間或行為，
        # 不得把後面的完整動作誤當成地點。
        if re.match(r"(?:民國)?\d{2,3}[年年]", segment) and "至" in segment:
            segment = segment.split("至", 1)[1]
        if re.match(r"(?:民國)?\d{2,3}[年年]", segment) and re.search(
            r"前往|就診|接受|駕駛|匯款|施行", segment
        ):
            continue
        # 「於114年…時許在○○市公車上」的第一個介系詞引出時間；
        # 地點值只能保留第二個「在」之後的原文，不得混入日期時間。
        segment = re.sub(
            r"^(?:民國)?\d{2,3}[年年]\d{1,2}月\d{1,2}日"
            r"(?:(?:凌晨|上午|下午|晚上)?(?:零|[0-9]{1,2})時(?:[0-5]?\d分)?(?:許)?)?在",
            "",
            segment,
        )
        segment = re.split(r"(?:見|基於|遂|因|共同|以|將|徒手|欲|而|拍攝|委請|駕駛|就診|接受|施行|協商|，)", segment, maxsplit=1)[0].strip()
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
        r"^([\u4e00-\u9fff]{2,5})(?=係)",
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
        r"與([\u4e00-\u9fff○]{2,5})(?=協商|爭執|共同)",
        r"對([\u4e00-\u9fff○]{2,5})(?=辱罵|侮辱|指稱|指摘|傳述)",
        r"(?:醫師|被告|告訴人)([\u4e00-\u9fff]{2,4}?)(?=於|（|，|。|係|為)",
    ):
        for match in re.finditer(pattern, summary):
            name = match.group(1)
            if name == alias_name:
                continue
            if name not in {"我", "他", "她", "性交", "內射", "共聞"} and not (
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
        r"((?:以手|用手|徒手)?觸摸[^，。；]{1,40})",
        r"(擁抱[^，。；]{1,40})",
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
        r"((?:以「[^」]+」等言語)?辱罵[^，。；]{1,40})",
        r"((?:指摘|傳述|指稱)[^，。；]{1,60})",
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
        r"([^。；]{1,60}(?:失眠|請假就醫|工作受影響|生活受影響|人際關係受影響)[^。；]{0,60})",
    ):
        for match in re.finditer(pattern, summary):
            add("result", match.group(1), fields={"result": match.group(1)})

    causation_match = re.search(r"(致[^。；]+?受有[^。；]+)", summary)
    if causation_match:
        add("causation", causation_match.group(1))
    for pattern in (
        r"(致[^。；]{1,120}?陷於錯誤[^。；]{0,100}?(?:匯款|轉帳|交付)[^。；]{0,60})",
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
    explicit_evidence = list(re.finditer(r"證據(?:有|包括|如下)[:：]?([^。；]+)", summary))
    for evidence_group in explicit_evidence:
        for raw_item in re.split(r"、|及(?=[^、，。；]{2,})", evidence_group.group(1)):
            evidence_item = raw_item.strip(" ，、；。")
            if not evidence_item:
                continue
            item_start = summary.find(evidence_item, evidence_group.start(1), evidence_group.end(1))
            add(
                "evidence", evidence_item, start=item_start,
                fields={"subtype": "listed_evidence"}, assertion_status="SOURCE_LEAD_TO_VERIFY",
            )
    if not explicit_evidence:
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
        "被告供述", "丁立文供述", "張芸瑋指訴", "案發錄影光碟", "勘驗筆錄",
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
    for match in re.finditer(
        r"((?:意圖|基於)[^，。；]{1,40}(?:犯意|所有)|(?:性交|猥褻)(?:行為)?得逞|足以貶損[^，。；]{1,50}(?:人格評價|名譽))",
        summary,
    ):
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


# E5 輪（人工複審 2026-10-20 第四輪 ✗）：否定詞表補「從未」群——
# 「我從未騷擾她，她也從未明確拒絕」「從未攔阻或脅迫」「從未脅迫／
# 從未搶走」等完整否定句，原 14 字元窗口沒有任何標記可擋，導致
# 錨點／區辨訊號被誤判為已建立事實。
_NEGATION_MARKERS = (
    "並未", "並非", "未提及", "沒有", "沒", "尚未", "非因", "不曾", "無證據",
    "無人", "未遂", "謊稱並無",
    "從未", "未曾", "從沒", "從來沒有", "從來不", "從來未",
)


def _keyword_negated(keyword: str, summary: str) -> bool:
    """檢查關鍵字是否只出現在否定語句中（spec §5.1：關鍵字不得為唯一機制）。

    找出關鍵字出現位置，向前看 14 個字元內是否有否定標記。
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
    sentence_breaks = ("。", "；", "！", "？", "，", ",")
    for pos in positions:
        context = lowered[max(0, pos - window):pos]
        # 跨句不算否定：從否定標記到關鍵字之間不得有句讀
        clean = context
        for br in sentence_breaks:
            clean = clean.split(br)[-1]
        if not any(marker in clean for marker in _NEGATION_MARKERS):
            return False  # 至少有一個非否定命中
    return True  # 全部命中都在否定語句內


_OBSTRUCTION_PHYSICAL_FORCE = r"推開|推打|推擠|推拉|推人|扯住|撞開|揮打|揮拳|毆打|拉扯|強暴|脅迫"
_OBSTRUCTION_FORCE = rf"(?:{_OBSTRUCTION_PHYSICAL_FORCE})|攔阻|阻礙"


# 白話情境語句提示（recall 補強，基於 R1 探針實測漏失的表述）。
# 只在對應罪章「零關鍵字命中」時評估；patterns 必須全部命中才觸發。
# 這裡只建立候選方向（NEED_REVIEW），不把任何語句要件視為已證明；
# 正式定性仍須 Gate 1 回查原文與人工審查。不改動已審查的題庫關鍵字。
_PHRASE_HINTS: list[dict[str, Any]] = [
    {
        "offense_id": "injury",
        "hint": "動手傷害情境",
        "patterns": [
            r"動手打|打了(我|人|他|她|乙|另一方|另一個人)|被打|被揍|推我撞|撞到(桌|牆|柱|電線桿)|不慎",
            r"瘀青|腫起|腫了|流血|破皮|骨折|驗傷|受傷|有傷|撞傷|痕跡|傷口|撕裂|疼痛|覺得痛|身體有不適|身體不適",
        ],
    },
    {
        "offense_id": "intimidation",
        "hint": "加害言詞恫嚇情境",
        # 刑法 §305：以「通知將加惡害之旨」為要件。「小心一點」等一般提醒
        # （如警衛值勤提醒）沒有惡害內容，不是惡害通知，不觸發（人工審查
        # E-1 ✗ 修正，2026-10-20）。
        "patterns": [
            r"(要|會)讓(我|你|他|她|妳)好看|讓(我|你|他|她|妳)後悔|別以為躲得掉|不會放過(你|我|他|她|妳)|知道我(住|家)|知道你(住|家)|我知道你(住|家)|記得(我|你)(家|住)哪|不告訴就傷害|報警就.{0,8}(傷害|找|打)|捅(你|死)|砍(你|死)|弄死你|處理你",
        ],
        # 新聞／聽聞不是本案事實：摘要只在敘述自己遭惡害通知時才觸發。
        "exclude": r"新聞|報導|聽說|聽到有人|電影|小說|歷史",
    },
    {
        "offense_id": "intimidation",
        "hint": "疑似威脅內容但具體語句待確認",
        "patterns": [
            r"說了一些話|說了一些內容|訊息和電話|簡訊及電話|傳訊息|簡訊",
            r"害怕|恐懼|畏懼|不安",
        ],
        "exclude": r"新聞|報導|聽說|聽到有人|電影|小說|歷史",
    },
    {
        "offense_id": "damage",
        "hint": "摔毀／損壞他人物品情境",
        "patterns": [
            r"摔(在|到)(地|牆|桌)|摔破|摔壞|踹壞|踩破|踩壞",
            r"手機|螢幕|眼鏡|車|電腦|花瓶|杯子",
        ],
    },
    {
        "offense_id": "fraud",
        "hint": "匯款未交付／交易失聯情境",
        "patterns": [
            r"匯錢|匯款|匯.{0,2}(錢|款)|轉錢|下訂|付訂金|付款",
            r"沒(到|收到)|未到貨|未收到|人(不回|消失|失聯)|被封鎖|沒消?息|沒消息|沒下文|聯絡不上|聯繫不上",
        ],
    },
    {
        "offense_id": "public_danger",
        "hint": "酒後駕駛情境",
        "patterns": [
            r"喝酒|喝了酒|酒後|飲酒|酒精",
            r"自己開車|自己騎車|開車回家|騎車回家|開車上路|騎車上路|駕車上路|駕駛上路",
        ],
    },
    {
        "offense_id": "obstruction",
        "hint": "妨害公務／阻撓執行職務情境",
        # 刑法 §135 第 1 項：以「施強暴脅迫」為要件。單純拒絕配合或口頭
        # 辱罵不是強暴脅迫，不觸發（人工審查 E-3 ✗ 修正，2026-10-20）。
        "patterns": [
            r"公務員|警察|員警|執法人員|交警|交通警察|執勤|依法執行|執行職務|執行工作|查封|封印",
            rf"{_OBSTRUCTION_FORCE}|干擾|插手|無法(完成|繼續|順利進行)",
        ],
        # 新聞／聽聞不是本案事實：摘要只在敘述自己阻撓執勤時才觸發。
        "exclude": r"新聞|報導|聽說|聽到有人|電影|小說|歷史",
    },
    {
        "offense_id": "stalking",
        "hint": "尾隨／持續接近情境",
        # 跟騷法 §3：反覆或持續「違反其意願」為要件。缺少拒絕／反對事實
        # 的日常串門敘述（如同事相約吃飯）不觸發（人工審查 E-2 ✗ 修正，
        # 2026-10-20）。
        "patterns": [
            r"跟(在)?(我|人|乙|他|她)(的)?(後面|身後)|跟著(我|人|乙|他|她)|附近出現|定位|尾隨|守候|徘徊|守在|等候|等在|聯絡|電話|(到|來)(我|你|人|乙)(家|學校|公司|工作|住處|門口|樓下|附近)|在門口|等在門口|寄送.{0,8}(信件|禮物)|送東西",
            r"反覆|一直|老是|多次|持續|每天|一週|每個月|常常|經常|連續|長時間",
            r"明確拒絕|拒絕(過)?|說不要了|不要再(來|跟|找|聯絡)|別再(來|找|跟|聯絡)|叫我不要再|早就拒絕|不喜歡|不安|很煩",
        ],
        "exclude": r"新聞|報導|聽說|聽到有人|電影|小說|歷史|包裹|外送|快遞|郵件|簽收|派送",
    },
    {
        "offense_id": "stalking",
        "hint": "定位／持續監看情境，意願與生活影響待確認",
        "patterns": [r"定位|監看", r"持續|反覆|多次"],
    },
    {
        "offense_id": "robbery",
        "hint": "強搶／搶奪財物情境",
        # 刑法 §328：以強暴、脅迫等「使人不能抗拒」之手段＋奪取財物或
        # 「使人交付」為要件。只有威脅而無取財／使交付事實（如威脅公開
        # 照片）不觸發（人工審查 E-4 ✗ 修正，2026-10-20）。
        "patterns": [
            r"強暴|脅迫|持(刀|槍|械)|菜刀|兇器|捅|砍.{0,4}(你|人)|行兇|捆綁|勒住|毆打|搶走|強搶|搶劫|要.{0,8}(錢|現金|財物)",
            # E5 輪：交付面綁定財物對象（與候選閘門共用 _ROBBERY_TAKE_ANCHOR），
            # 裸「交付」配合無關的「不能抗拒」語境不得觸發。
            _ROBBERY_TAKE_ANCHOR,
        ],
        # 新聞／聽聞不是本案事實：摘要只在敘述自己遭搶時才觸發。
        "exclude": r"新聞|報導|聽說|聽到有人|電影|小說|歷史",
    },
    {
        "offense_id": "embezzlement",
        "hint": "保管他人財物後拒不返還／占為己有情境",
        # 刑法 §335：侵占「自己持有之他人之物」。僅職稱（會計／財務）或
        # 第三人欠款往來（客戶不還欠款）不構成受託持有可能，不觸發
        # （人工審查 E-5 ✗ 修正，2026-10-20）。
        "patterns": [
            r"保管|代管|代收|受託|經手|業務上|公款|拾得|撿到",
            r"拒不返還|占為己有|據為己有|花用|侵吞|轉(到|入|進)自己(的)?(帳戶|名下)",
        ],
        # 新聞／聽聞與金錢借貸往來不是受託持有事實。
        "exclude": r"新聞|報導|聽說|聽到有人|電影|小說|歷史|欠款|借款|貸款",
    },
    {
        "offense_id": "defamation",
        "hint": "公開場合辱罵情境",
        "patterns": [
            r"群組|網路上|公開|很多人面前|眾人面前|臉書|IG|論壇|留言板",
            r"罵(我|他|人)|羞辱|辱罵|不要臉|說.{0,8}壞話|難聽的話|負面內容|不實內容|稱.{0,8}侵占|指.{0,8}侵占|受損",
        ],
    },
    {
        "offense_id": "liberty",
        "hint": "強暴脅迫使人為無義務行為情境",
        "patterns": [
            r"強迫|逼迫|逼(我|你|他|她|乙|另一個人)|威脅.{0,20}(簽署|簽名|交出|提供|做)",
            r"交出.{0,12}(密碼|手機|文件)|簽署|簽名|不想做|不得不|只好",
        ],
    },
]


def _phrase_hint_for(offense_id: str, summary: str) -> str | None:
    """評估白話情境語句提示；全部 patterns 命中且各 pattern 至少
    有一處未在否定語句內的命中時，回傳提示詞。"""
    for rule in _PHRASE_HINTS:
        if rule["offense_id"] != offense_id:
            continue
        if not _patterns_unnegated(rule["patterns"], summary):
            continue
        exclude = rule.get("exclude")
        if exclude and re.search(exclude, summary):
            continue
        return rule["hint"]
    return None


def _patterns_unnegated(patterns: list[str], summary: str) -> bool:
    for pattern in patterns:
        matches = list(re.finditer(pattern, summary))
        if not matches:
            return False
        if all(_keyword_negated(match.group(0), summary) for match in matches):
            return False
    return True


# E3 輪（人工複審 2026-10-20）構成要件最小錨點閘門。
# 題庫關鍵字（凍結）與結構式規則會在提示層之前建立候選，即使缺構成
# 要件對應事實也會命中；故在程式碼層要求該章「最小構成要件錨點」
# 存在（沿用 14 字元否定窗口的 _patterns_unnegated），缺任一錨點即
# 清除該章候選。錨點只回報摘要是否「含有對應區辨事實語句」，不判定
# 任何法律要件成立；正式定性仍須 Gate 1 回查原文與人工審查。
# 外層 list＝全部必備；內層 list＝任一即可（同反義群組）。
# E3→E4 輪（人工複審 2026-10-20）構成要件最小錨點閘門。
# 題庫關鍵字（凍結）、結構式規則與提示層都可能在缺構成要件對應事實時
# 建立候選；故在程式碼層要求該章「最小構成要件錨點」存在。
# - patterns 型：外層 list＝全部必備；內層 list＝任一即可（同反義群組）。
# - bound 型：行為語句與錨點必須落在「同一句」（依 。；！？分行），
#   且兩者皆未落在否定窗口內——避免「機關安排強制休假」「公司通知我
#   無須再填寫報告」等無關句放行（人工複審第三輪 ✗ 事由）。
# 關鍵字回顯豁免（整句＝單一關鍵字即不套閘門）已依人工裁定撤除：
# 該豁免是全題庫關鍵字的全域例外，會讓「性騷擾」「冒充公務員」等
# 其他章關鍵字漏出錨點檢查；佈線測試改用關鍵字＋最小事實敘述。
# 錨點只回報摘要是否「含有對應區辨事實語句」，不判定任何法律要件
# 成立；正式定性仍須 Gate 1 回查原文與人工審查。
_STALKING_ACT = (
    r"跟蹤|騷擾|尾隨|守候|徘徊|盯梢|守在|等在|等候"
    r"|跟著|附近出現|定位|寄送|送東西|聯絡|聯繫|電話|傳(送)?訊息|來訊|接近|到我家|到住處"
)
# 裁定③（ACCEPT_WITH_MODIFICATIONS）＋E5 輪修正：「無須再」不可裸用，
# 限縮於聯繫／接觸／傳訊／接近語境；害怕／保護令須與行為同句才
# 有關聯；「拒絕」須指向聯繫／接觸類對象或句尾收束，避免同句其他
# 主體的無關邀約（「他騷擾同事，我明確拒絕另一人的邀約」）放行。
_STALKING_ANCHOR = (
    r"拒絕(過)?(見面|聯絡|聯繫|接觸|來往|跟蹤|騷擾|傳訊|來電|通話|相見|靠近|繼續(聯絡|接觸))"
    r"|明確拒絕(?=[，,。；！？仍但後]|$)"
    # E6 輪（人工複審 2026-10-20 第五輪 ✗）：裸「拒絕過」未綁接觸對象，
    # 「他騷擾同事，我拒絕過另一人的邀約」仍回填；改為僅承認頻率補語
    # （拒絕過很多次／多次…）之拒絕。
    r"|拒絕過(很多次|多次|好幾次|無數次|一次又一次|一再)"
    r"|早(已|就|曾)拒絕(?=[，,。；！？]|$|見面|聯絡|聯繫|接觸)|表示拒絕|說不要了"
    r"|不要再(來|跟|找|聯絡|聯繫|傳|送|打)"
    r"|別再(來|找|跟|聯絡|聯繫)|叫我不要再|違反.{0,6}意願"
    r"|無須再(私下)?(聯繫|聯絡|傳|接觸|來)|不必再(聯繫|聯絡|傳|接觸)"
    r"|不用再(聯絡|聯繫|傳|接觸)"
    r"|心生畏怖|心生畏懼|嚇得|不敢出門|不安|很煩|不喜歡|保護令"
)
_OBSTRUCTION_ACT = r"公務員|員警|警察|執法人員|依法執行|執法|執行[^。；]{0,8}(?:職務|工作)|執勤|開罰單|處理違規|查封|封印"
# 裁定②修正（第三輪 ✗）：裸「強制」會讓「強制休假」等無衝突敘述放行，
# 移除；錨點限物理性強暴脅迫動作。E5 輪：法律程序／救濟語境的
# 「攔阻」（程序攔阻／依法聲明異議等）不是物理強暴脅迫，以 veto 剔除。
_OBSTRUCTION_FORCE_VETO = r"程序|法律途徑|聲明異議|訴願|行政救濟|訴訟|聲請停止執行|依法聲請|聲請"

_ELEMENT_ANCHOR_GATES: dict[str, dict[str, Any]] = {
    # 跟騷法 §3：反覆或持續「違反其意願」之行為並使之心生畏怖。
    "stalking": {"bound": [(_STALKING_ACT, _STALKING_ANCHOR, None)]},
    # 刑法 §135 第 1 項：對執行職務之公務員施強暴脅迫。
    "obstruction": {
        "bound": [
            (_OBSTRUCTION_ACT, _OBSTRUCTION_PHYSICAL_FORCE, None),
            (_OBSTRUCTION_ACT, r"攔阻", _OBSTRUCTION_FORCE_VETO),
        ],
    },
    # 刑法 §328：使人不能抗拒之手段而奪取財物或使人交付。
    "robbery": {"patterns": [[_ROBBERY_TAKE_ANCHOR]]},
    # 刑法 §335：變易持有為所有、處分或拒不返還。「沒有占為己有」
    # 「沒有侵占」等否定敘述由否定窗口擋掉，已完成返還者不觸發。
    "embezzlement": {"patterns": [[
        r"侵占|拒不返還|拒絕返還|自行處分|占為己有|據為己有|花用|侵吞|轉(到|入|進)自己|當(作|成)自己|變賣|逾期未還|取走",
    ]]},
}

_SENTENCE_SPLIT_RE = re.compile(r"[。；！？\n]")


def _sentence_bound_anchor(
    act_pattern: str,
    anchor_pattern: str,
    summary: str,
    anchor_veto: str | None = None,
) -> bool:
    # E6 輪（人工複審 2026-10-20 第五輪 ✗）：逐一列舉同句內所有
    # act×anchor 配對（原實作找到第一個未否定 act 即 break，未真正
    # 逐一枚舉配對）。任一配對成立（兩者皆未否定、錨點未落 veto）
    # 即視為同句綁定成立。
    for sentence in _SENTENCE_SPLIT_RE.split(summary):
        for act_match in re.finditer(act_pattern, sentence):
            if _keyword_negated(act_match.group(0), sentence):
                continue
            for anchor_match in re.finditer(anchor_pattern, sentence):
                if _keyword_negated(anchor_match.group(0), sentence):
                    continue
                if anchor_veto:
                    preceding = sentence[max(0, anchor_match.start() - 12):anchor_match.start()]
                    if re.search(anchor_veto, preceding):
                        continue
                return True
    return False


def _element_anchor_ok(offense_id: str, summary: str) -> bool:
    # 缺事實案例仍可保留妨害公務候選，但必須把強暴／脅迫列為待確認，
    # 不把「插手／干擾」直接當成已具備的法定手段。
    if offense_id == "stalking" and re.search(r"定位|監看", summary) and re.search(r"持續|反覆|多次", summary):
        return True
    if offense_id == "obstruction" and re.search(
        r"(?:警察|員警|執法人員|公務員).{0,30}(?:插手|干擾|阻礙).{0,20}(?:無法|不能).{0,8}(?:繼續|完成|順利)|(?:插手|干擾|阻礙).{0,20}(?:警察|員警|執法人員|公務員).{0,20}(?:無法|不能).{0,8}(?:繼續|完成|順利)",
        summary,
    ):
        return True
    gate = _ELEMENT_ANCHOR_GATES.get(offense_id)
    if not gate:
        return True
    if "bound" in gate:
        return any(
            _sentence_bound_anchor(act_pattern, anchor_pattern, summary, anchor_veto)
            for act_pattern, anchor_pattern, anchor_veto in gate["bound"]
        )
    return all(
        _patterns_unnegated(group, summary)
        for group in gate.get("patterns", [])
    )


# ── 階段 2（2026-10-20）：actor—conduct—target 關係綁定 ──
# 結構化匹配結果：識別摘要中「誰對誰做了什麼」，避免同句不同主體的
# 污染（跨人物拒絕、程序性攔阻、非財物交付）。無法可靠配對時回傳
# UNKNOWN_RELATION，不得自動選入 ELIGIBLE_CANDIDATE。
#
# 本階段新增結構化匹配，不破壞既有布林函式；由現有 gate 逐步改用。
_CLAUSE_SPLIT_RE = re.compile(r"[，、；]")
_ACTOR_RE = re.compile(r"(?:甲|乙|丙|丁|戊|己|庚|辛|壬|癸|他|她|它|他們|她們|員警|警察|公務員|行為人|被害人)")


def _identify_clause_actor(clause: str) -> str | None:
    """識別子句的主體（actor）。回傳人名/代詞或 None。"""
    match = _ACTOR_RE.search(clause)
    return match.group(0) if match else None


def _bound_relation_matches(summary: str, offense_id: str) -> list[dict[str, Any]]:
    """回傳結構化 actor—conduct—target 匹配結果。

    每個結果包含：sentence_id、actor、conduct、target、object、negated、
    veto_reason、source_excerpt。無法可靠配對時回傳 UNKNOWN_RELATION。
    """
    matches: list[dict[str, Any]] = []
    sentences = _SENTENCE_SPLIT_RE.split(summary)
    for sent_idx, sentence in enumerate(sentences):
        clauses = _CLAUSE_SPLIT_RE.split(sentence)
        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            actor = _identify_clause_actor(clause)
            if not actor:
                continue
            # 檢查是否被否定
            negated = False
            for neg_marker in _NEGATION_MARKERS:
                if neg_marker in clause:
                    negated = True
                    break
            # 檢查是否為程序語境（veto）
            veto_reason = None
            if offense_id == "obstruction":
                if re.search(r"程序|法律途徑|聲明異議|訴願|行政救濟|訴訟|聲請停止執行|依法聲請|聲請", clause):
                    veto_reason = "法律程序語境"
            # 檢查是否為跨主體（子句中有另一個不同的人名）
            other_actors = [a for a in _ACTOR_RE.findall(clause) if a != actor]
            if other_actors:
                # 子句中有多個不同主體，無法確認配對
                matches.append({
                    "sentence_id": sent_idx,
                    "actor": actor,
                    "conduct": clause,
                    "target": None,
                    "object": None,
                    "negated": negated,
                    "veto_reason": "UNKNOWN_RELATION：子句含多主體",
                    "source_excerpt": clause,
                })
                continue
            matches.append({
                "sentence_id": sent_idx,
                "actor": actor,
                "conduct": clause,
                "target": None,
                "object": None,
                "negated": negated,
                "veto_reason": veto_reason,
                "source_excerpt": clause,
            })
    return matches


def _relation_binding_ok(offense_id: str, summary: str) -> bool:
    """檢查 actor—conduct—target 關係綁定是否成立。

    跟騷：接觸行為人、被接觸對象、拒絕者必須相符。
    妨害公務：強暴脅迫行為必須指向正在依法執行職務的公務員。
    強盜：強暴脅迫、不能抗拒及財物取得必須屬於同一事件鏈。
    無法可靠配對時回傳 False（UNKNOWN_RELATION）。
    """
    matches = _bound_relation_matches(summary, offense_id)
    if not matches:
        return False
    # 檢查是否有任何有效的（非 UNKNOWN、非 veto、非否定）匹配
    for match in matches:
        if match.get("veto_reason") and "UNKNOWN_RELATION" in match["veto_reason"]:
            continue
        if match.get("veto_reason"):
            continue
        if match.get("negated"):
            continue
        return True
    return False


# 轉述指控護欄資料表（依 R-fuzz 探針實測雜訊罪章建立）。
# attribution + (我|我方) + verbs 命中、且摘要無 independent 事實訊號時，
# 清除該罪章關鍵字命中；被指控的內容由妨害名譽／誣告方向處理。
ATTRIBUTION_PREDICATE = (
    r"(?:跟別人|跟他人|跟公司|跟主管|向老師|向學校|向警察|跟警察|到處|逢人"
    r"|在群組|在網路上|發文|留言|貼文|指稱|指摘|指控|聲稱|他說"
    r"|向[^。；]{0,6}(?:公司|主管|警方|警察|學校|老師)[^。；]{0,10}說"
    # 家屬／長官等特定第三者轉述（探針 B 組：我媽跟訓導主任說我偷同學的錢）
    r"|(?:我(?:媽|爸|母親|父親|老師|主管|老闆|同事|同學|太太|先生|老婆|老公)"
    r"|訓導主任|導師|教官|上司|親友|家人)[^。；]{0,10}說)"
)
ATTRIBUTED_ALLEGATION_GUARDS: list[dict[str, str]] = [
    {
        "offense_id": "theft",
        "verbs": r"偷|竊|拿走",
        # 拿走本身可能出現在引述句內（說我拿走）也可能出現在真實事實
        # （另一名同事拿走了營業款）；以引述區間外的出現位置為準。
        "independent": r"取走|遭竊|失竊|不翼而飛|闖入|未結帳|盜取|竊取|拿走|短少|不見|少了|消失|減少",
    },
    {
        "offense_id": "fraud",
        "verbs": r"騙|詐",
        "independent": r"匯款|轉帳|付款|訂金|到貨|未收到|交付",
    },
    {
        "offense_id": "intimidation",
        "verbs": r"恐嚇|威脅",
        "independent": r"揚言|害怕|恐懼|心生畏|不敢",
    },
    {
        "offense_id": "injury",
        "verbs": r"打|傷害",
        "independent": r"驗傷|瘀青|受傷|骨折|傷口|流血",
    },
    {
        "offense_id": "embezzlement",
        "verbs": r"侵占",
        "independent": r"保管|代管|受託|經手",
    },
    {
        "offense_id": "stalking",
        "verbs": r"跟蹤|騷擾",
        "independent": r"守候|尾隨|反覆|訊息",
    },
    {
        "offense_id": "robbery",
        "verbs": r"搶劫|搶了|搶走|強搶|搶奪",
        "independent": r"遭搶|被搶|失竊|盜走|短少|不見|少了|消失",
    },
]


def _has_independent_outside(rule: dict[str, str], summary: str, attributed: re.Match) -> bool:
    """獨立事實訊號只有出現在引述句（predicate 起、動詞止）之外才算數。

    引述句中間重複出現的行為詞（「說我拿走」的「拿走」）不能當成摘要
    自己描述的獨立事實；引述句前後的真實敘述（例如監視器畫面證實他人
    拿走）才構成獨立事實。
    """
    start, end = attributed.start(), attributed.end()
    for match in re.finditer(rule["independent"], summary):
        if match.start() < start or match.start() >= end:
            return True
    return False


def _attributed_allegation_guard(offense_id: str, summary: str) -> bool:
    """摘要只是引述他人對本人的指控（且無獨立事實）時回傳 True。"""
    rule = next(
        (item for item in ATTRIBUTED_ALLEGATION_GUARDS if item["offense_id"] == offense_id),
        None,
    )
    if rule is None:
        return False
    attributed = re.search(
        ATTRIBUTION_PREDICATE + r"[^。；]{0,40}(?:我|我方)(?:" + rule["verbs"] + r")",
        summary,
    )
    if not attributed:
        return False
    return not _has_independent_outside(rule, summary, attributed)


def _attribution_spans(summary: str) -> list[tuple[int, int]]:
    """在無獨立事實時，回傳「轉述指控」句段的字元區間。

    區間內出現的其他罪章關鍵詞（例如引述句裡的場景名詞「倉庫」）只是
    被指控內容的一部分，不得作為該罪章的關鍵字命中。
    """
    spans: list[tuple[int, int]] = []
    for rule in ATTRIBUTED_ALLEGATION_GUARDS:
        attributed = re.search(
            ATTRIBUTION_PREDICATE + r"[^。；]{0,40}(?:我|我方)(?:" + rule["verbs"] + r")",
            summary,
        )
        if attributed and not _has_independent_outside(rule, summary, attributed):
            # 區間延伸到句末標點：受詞或情境名詞（倉庫、存貨、金錢）也是被
            # 指控內容的一部分，一起納入引述區間。
            tail = re.search(r"[。；！？]", summary[attributed.end():])
            end = attributed.end() + tail.start() if tail else len(summary)
            spans.append((attributed.start(), end))
    return spans


def _hits_inside_attributed_spans(
    hits: list[str], summary: str, spans: list[tuple[int, int]]
) -> bool:
    """所有命中詞的出現位置都落在轉述指控區間內時回傳 True。"""
    for term in hits:
        occurrences = list(re.finditer(re.escape(term), summary))
        # 命中詞在原文找不到（例如提示語句本身）時，無法證明它位於引述
        # 區間內，不得清除。
        if not occurrences:
            return False
        # 摘要中另有區間外的實際命中時，視為摘要本身的事實敘述，保留候選。
        inside_only = all(
            any(not (match.end() <= span_start or match.start() >= span_end) for span_start, span_end in spans)
            for match in occurrences
        )
        if not inside_only:
            return False
    return True


def candidate_offenses(
    summary: str, bank: dict[str, Any], gate1: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    lowered = summary.casefold()
    by_id = {item["id"]: item for item in bank["offenses"]}
    matched_ids: set[str] = set()
    attributed_spans = _attribution_spans(summary)
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
            if re.search(r"(不同意|違反.{0,3}意願|強暴|睡著|偷拍|威脅|脅迫|偷偷)", summary):
                hits = ["非合意性交／性自主情境"]
        if offense["id"] == "sexual" and not hits:
            if re.search(r"(乘機猥褻|猥褻|不能抗拒|胸部|內衣)", summary):
                hits = ["乘機猥褻／不能抗拒情境"]
        # 失能／不能抗拒只是狀態，未與明確性行為同時出現時，
        # 不得單獨建立妨害性自主候選。純猥褻／強行親吻等明確行為仍保留。
        if offense["id"] == "sexual" and hits and not re.search(
            r"性侵害|強制性交|強制猥褻|性交|猥褻|撫摸胸部|觸摸胸部|摸胸|伸入內衣|強行親吻|親吻性部位",
            summary,
        ):
            hits = []
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
        if offense["id"] == "robbery" and not hits:
            # 只有對人施加暴力、脅迫或使人因恐懼交付財物時，才建立強盜候選。
            if re.search(r"(?:持刀|持械|持武器|暴力|強暴|脅迫|威脅|恐嚇|迫使)[^。；]{0,80}(?:交出|交付|給予)[^。；]{0,30}(?:財物|現金|款項|錢)", summary):
                hits = ["對人施暴／脅迫交付財物情境"]
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
            driving_signal = re.search(r"駕車|駕駛|騎乘|行駛|上路|操控車輛|酒駕|肇事|交通事故", summary)
            if not driving_signal:
                hits = []
        if offense["id"] == "fraud" and not hits:
            if re.search(r"佯稱|冒充|詐術", summary) and re.search(r"匯款|轉帳|交付|付款", summary):
                hits = ["詐術／財產處分情境"]
        if offense["id"] == "injury" and not hits:
            if re.search(r"受有[^。；]{0,50}(?:傷害|挫傷)|穿孔|腹膜炎|敗血症", summary) and re.search(
                r"毆打|揮打|攻擊|踢踹|腳踢|推擠|刺穿|手術|不慎|疏未注意", summary
            ):
                hits = ["具體傷害結果／致傷行為情境"]
        if offense["id"] == "theft" and not hits:
            if re.search(r"(?:取走|拿走|拿取|竊取|盜取)[^。；]{0,60}(?:現金|手機|電腦|財物|物品|商品|貨架|洗髮精)", summary) or re.search(
                r"(?:現金|手機|電腦|財物|物品|商品|貨架|洗髮精)[^。；]{0,30}遭?(?:取走|拿走|拿取|竊取|盜取)", summary
            ):
                hits = ["取走他人動產情境"]
            elif re.search(r"(?:砸破|打破|弄破).{0,20}(?:車窗|玻璃).{0,30}(?:強行)?(?:取走|拿走|拿取|拿).{0,20}(?:公事包|物品|東西|財物)", summary):
                hits = ["破壞車窗後取走車內物品情境"]
            elif re.search(r"(?:進入|到|去).{0,20}(?:住家|房子|屋內|店裡).{0,20}(?:拿了|拿走|取走)" , summary):
                hits = ["進入場所後取走物品情境"]
            elif re.search(r"(?:騎走|駛離|開走).{0,20}(?:機車|汽車|車輛|車)", summary):
                hits = ["取走他人交通工具情境"]
            elif re.search(r"(?:拿了|拿走|取走)\s*(?:東西|物品|財物)" , summary):
                hits = ["拿取他人物品情境"]
        if offense["id"] == "aggravated_theft" and not hits:
            if (
                re.search(r"(?:夜間|夜晚|凌晨|陽台|窗戶|後窗|翻入|爬入)", summary)
                and re.search(r"(?:住宅|住家|房子|屋內|後院|公寓)", summary)
                and re.search(r"(?:撬開|撬|工具|後門|門窗|窗戶|翻牆|翻入|爬入|闖入|破壞)", summary)
                and re.search(r"(?:竊取|偷走|偷|拿走|取走|拿了|現金|財物|金飾|物品)", summary)
            ):
                hits = ["夜間住宅／工具侵入取財情境"]
        if offense["id"] == "damage" and not hits:
            if re.search(r"破壞|毀損|砸毀|損壞|敲打|不堪使用", summary) and re.search(
                r"車窗|玻璃|物品|財物|器物|設備|腳踏車|機車|汽車", summary
            ):
                hits = ["物品毀損／不堪使用情境"]
            elif re.search(r"(?:交通工具|車).{0,20}(?:弄壞|不能用|損壞)", summary):
                hits = ["交通工具損壞／不能使用情境"]
            elif re.search(r"(?:物品|東西).{0,12}(?:弄壞|不能用|損壞)", summary):
                hits = ["他人物品損壞情境"]
        if offense["id"] == "stalking" and not hits:
            if re.search(r"反覆|持續|多次", summary) and re.search(
                r"跟蹤|盯梢|守候|等候|尾隨|傳送訊息|住處|工作地點", summary
            ) and re.search(r"心生畏怖|心生畏懼|害怕|恐懼", summary):
                hits = ["反覆跟蹤騷擾／心生畏怖情境"]
        if offense["id"] == "obstruction" and not hits:
            if re.search(r"公務員|依法執行|執行[^。；]{0,12}職務", summary) and re.search(
                r"攔阻|揮打|毆打|強暴|脅迫|妨害", summary
            ):
                hits = ["執行職務公務員／強暴脅迫情境"]
        if offense["id"] == "obstruction" and not hits:
            if re.search(_OBSTRUCTION_ACT, summary) and re.search(_OBSTRUCTION_FORCE, summary):
                hits = ["執行職務公務員／強暴脅迫情境"]
        # 「電腦」可能只是地點或設備描述。單獨命中時不建立妨害電腦使用候選，
        # 仍保留「登入、刪除資料、駭客」等具體行為關鍵字供人工檢視。
        if offense["id"] == "computer" and hits == ["電腦"]:
            hits = []
        if offense["id"] == "defamation" and hits:
            if not re.search(r"名譽|侮辱|誹謗|不實|貶損|公然|公開場合|辱罵|散布", summary):
                hits = []
        # 公開貼文中的「侵占」可能只是被指摘的內容，不等於摘要已描述
        # 行為人實際持有或處分他人財物。此時不得把侵占罪章帶入正式候選。
        if offense["id"] == "embezzlement" and hits:
            allegation_context = re.search(r"(?:公開貼文|貼文|發文|指稱|指摘)[^。；]{0,60}侵占", summary)
            possession_context = re.search(r"(?:保管|持有|代收|受託|業務上)[^。；]{0,60}(?:占為己有|拒不返還|侵占)", summary)
            if allegation_context and not possession_context:
                hits = []
        # E3→E4 輪（人工複審 2026-10-20）：構成要件最小錨點閘門。
        # keyword／結構式 fallback 建立的候選若缺對應構成要件區辨事實
        # （否定窗口生效；stalking／obstruction 另要求行為與錨點同句
        # 綁定），在此清除；清除後若白話敘述另含完整要件仍可能由下方
        # 的提示層觸發。
        if hits and not _element_anchor_ok(offense["id"], summary):
            hits = []
        # 白話情境語句提示：僅在零關鍵字命中時建立候選方向，
        # 供人工從白話描述回查法定要件，不升級為任何正式結論。
        if not hits:
            hint = _phrase_hint_for(offense["id"], summary)
            if hint:
                hits = [hint]
                # 第三輪複審 ✗（E-4）：gate 清除 keyword 命中後，提示層
                # 不得繞過相同錨點檢查重新帶回候選；hint 命中同樣套用。
                if not _element_anchor_ok(offense["id"], summary):
                    hits = []
        # 轉述指控護欄：被罵或被爆料時引述的「（他們）說我偷／說我拿走」
        # 屬於妨害名譽爭執中被指控的內容，不是摘要對該罪章事實的敘述；
        # 摘要另有獨立事實描述時不觸發本護欄（鏡射既有侵占護欄精神）。
        if hits:
            attributed = _attributed_allegation_guard(offense["id"], summary)
            if attributed:
                hits = []
        # 引述句內的場景名詞（如「說我拿走倉庫的存貨」的「倉庫」）只是被
        # 指控內容的一部分：當命中的所有出現位置都落在轉述區間內時，
        # 該罪章的關鍵字命中不得成立。
        if hits and attributed_spans:
            if _hits_inside_attributed_spans(hits, summary, attributed_spans):
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
            matches[-1]["missing"] = list(matches[-1].get("unknown_elements", []))
            matrix = matches[-1].get("route_element_matrix", [])
            matches[-1]["candidate_eligibility"] = "ELIGIBLE_CANDIDATE"
            route_states: dict[str, str] = {}
            for route in matrix:
                route_states[route["route_id"]] = (
                    "ELIGIBLE_CANDIDATE"
                    if route.get("supported_count", 0) >= ROUTE_MIN_SUPPORTED_ELEMENTS
                    else "HINT_ONLY"
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
    # 財物走向的關聯擴展只在「真的有財物罪章命中」或「摘要沒有被轉述
    # 指控區間主導」時進行：引述句中的財物名詞（存貨、金錢）不是摘要
    # 自己描述的取財事實。
    property_family_matched = any(
        offense_id in PROPERTY_ROUTE_IDS or "aggravated_theft" == offense_id
        for offense_id in matched_ids
    )
    property_wanted = (
        _property_taking_values(summary) is not None
        or bool(matched_ids & PROPERTY_ROUTE_IDS)
    )
    if property_wanted and (not attributed_spans or property_family_matched):
        # D1（人工核定「B 修正版」，2026-10-20）：財物三路區辨——
        # theft＝未經同意取走／破壞原持有；embezzlement＝先前合法持有／
        # 受託後變易持有、處分或拒不返還；robbery＝強暴／脅迫等手段＋
        # 奪取或使人交付。缺對應區辨事實時不新增，並撤銷 bank related
        # 帶入的該 routes 相關候選（不修改 legal_route_crosswalk.json）。
        signals = _property_discriminators(summary)
        related_ids.discard("aggravated_theft")
        related_ids -= PROPERTY_ROUTE_IDS
        if signals["consent_take"]:
            related_ids.add("theft")
        if signals["entrusted_possession"] and signals["conversion"]:
            related_ids.add("embezzlement")
        if signals["violence_take"]:
            related_ids.add("robbery")
        related_ids -= matched_ids
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
        matches[-1]["missing"] = list(matches[-1].get("unknown_elements", []))
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


def classify_candidates(
    summary: str,
    bank: dict[str, Any],
    gate1: dict[str, Any] | None = None,
    *,
    max_candidates: int = 4,
) -> dict[str, Any]:
    """規則式 fallback 的 v3 外層結果。

    候選本身仍由 ``candidate_offenses`` 產生，這層只補上狀態、缺口與
    優先排序，避免代稱不明或缺事實摘要被錯誤降成空陣列。
    """
    text = summary.strip()
    explicit_subject = bool(re.search(r"甲|乙|丙|丁|被告|嫌疑人|行為人|監視器.{0,12}(辨識|顯示)|鎖定", text))
    ambiguous_subject = bool(re.search(r"他|她|對方|某人|一人|男子|女子|有人|不詳|另一個人", text))
    status = {
        "subject_identified": "true" if explicit_subject else ("false" if ambiguous_subject else "unknown"),
        "has_victim": "true" if re.search(r"被害人|報案人|屋主|事主|店員|乙|對方|受有|遭", text) else "unknown",
        "is_solved": "true" if re.search(r"已尋獲|已逮捕|已到案|監視器.{0,12}(辨識|顯示)|鎖定", text) else (
            "false" if re.search(r"尚未|未尋獲|逃逸|失聯|不知是誰", text) else "unknown"
        ),
    }
    global_missing: list[str] = []
    if status["subject_identified"] == "false":
        global_missing.append("主體不明")
    if status["is_solved"] == "true" and re.search(r"未尋獲|尚未尋獲", text):
        global_missing.append("贓物流向待查")
    priority = {
        "aggravated_theft": 100,
        "robbery": 95,
        "theft": 90,
        "fraud": 85,
        "intimidation": 80,
        "obstruction": 78,
        "residential_trespass": 77,
        "liberty": 76,
        "injury": 75,
        "stalking": 74,
        "defamation": 70,
        "damage": 68,
    }
    candidates = candidate_offenses(text, bank, gate1)
    # 題庫目前沒有第 306 條獨立罪名項目。僅在案情明確描述未經允許
    # 進入住家時提供可審核的模型補充候選，法源狀態明確標為 NOT_FOUND，
    # 不把既有「妨害自由」項目誤當作侵入住居。
    has_residential_trespass = bool(re.search(
        r"(?:未經.{0,12}(?:同意|允許)|沒有經過.{0,8}允許|無故|進了|進入).{0,18}(?:住宅|住家|家|房子|屋內)",
        text,
    ))
    if has_residential_trespass and not any(item["id"] == "residential_trespass" for item in candidates):
        candidates.append({
            "id": "residential_trespass",
            "candidate_id": "candidate:residential_trespass",
            "name": "侵入住居（刑法第306條）（模型補充）",
            "matched_terms": ["未經允許進入住家情境"],
            "status": "NEED_REVIEW",
            "notice": "模型補充候選，法源資料待補；不代表犯罪成立。",
            "inclusion_reason": "案情描述未經允許進入住宅或住家，可能涉及侵入住居方向。",
            "reservation_reason": "題庫缺少第306條獨立項目，需人工核對現行法源與構成要件。",
            "supporting_fact_refs": ["intake.summary"],
            "contradicting_fact_refs": [],
            "unknown_elements": ["無故狀態", "住宅或建築物範圍", "是否有退去要求"],
            "missing": ["無故狀態", "住宅或建築物範圍", "是否有退去要求"],
            "element_model_status": "SOURCE_EVIDENCE_MATRIX",
            "route_type": "substantive",
            "crosswalk_status": "NOT_FOUND",
            "legal_routes": [],
            "excluded_legal_routes": [],
            "legal_route_selection_status": "HUMAN_REVIEW_REQUIRED",
            "source": {"status": "NOT_FOUND", "law_name": "中華民國刑法", "article_no": "第306條"},
            "distinguishing_question_ids": ["HUMAN-DISTINGUISHING-QUESTION-REQUIRED"],
            "required_evidence_question_ids": ["HUMAN-EVIDENCE-REVIEW-REQUIRED"],
            "competition_analysis": "NOT_ASSESSED",
            "prohibited_conclusions": ["犯罪成立", "故意成立", "因果關係成立", "競合成立"],
            "version": "NOT_FOUND",
            "selection_origin": "model_supplement",
            "machine_effects": [],
            "candidate_eligibility": "HINT_ONLY",
            "legal_route_states": {},
            "candidate_state": "NEED_REVIEW",
            "unknown_fact_keys": [],
            "status_reasons": [],
        })
    for candidate in candidates:
        candidate["missing"] = list(dict.fromkeys(global_missing + list(candidate.get("missing", []))))
        candidate["classification_missing"] = list(candidate["missing"])
    candidates.sort(key=lambda item: (-priority.get(item["id"], 0), -len(item.get("matched_terms", [])), item["name"]))
    return {"candidates": candidates[:max_candidates], "status": status, "source": "rules"}


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


# 已審查 child route 的法律要件，必須連回實際問句。這份 sidecar 只增加
# metadata，不改公司套表或既有題庫文字；值同時可比對問句本文與 fact_target。
ROUTE_ELEMENT_QUESTION_SIGNALS: dict[str, dict[str, tuple[str, ...]]] = {
    "theft_320_1_movable": {
        "他人動產及原持有狀態": ("何人實際持有", "何人所有", "持有、保管或控制"),
        "未經同意竊取並破壞原持有": ("允許，範圍", "是否曾同意", "如何竊取"),
        "為自己或第三人不法所有之意圖": ("用途", "為何要拿取", "移轉、出售、隱匿"),
        "未遂或既遂": ("物品不在", "取得後", "被取得後"),
    },
    "injury_277_general": {
        "傷害身體或健康行為": ("具體動作", "如何遭人傷害", "用何種器具傷害"),
        "傷害結果與因果關係": ("哪些傷勢", "使你何處受傷", "造成對方受傷"),
        "死亡或重傷結果與因果關係": ("傷勢如何", "何種診療", "診斷證明書"),
    },
    "fraud_339_general": {
        "詐術內容及實施": ("representation_content", "遭何人詐騙", "說明哪些具體內容"),
        "相對人陷於錯誤": ("reliance_and_verification", "如何理解這些內容", "曾查證哪些事項"),
        "交付財物或財產利益處分": ("property_dispositions", "各筆款項或財物", "具體損害金額"),
        "財產流向與損害": ("property_dispositions", "performance_and_discovery", "具體損害金額"),
        "不法所有意圖": ("履行", "準備", "取得款項", "為何"),
        "未遂或既遂": ("performance_and_discovery", "交付給何人", "後來如何履行"),
    },
    "sexual_harassment_25_unwanted_touch": {
        "意圖性騷擾": ("目的", "性騷擾申訴事件", "為何要為上開行為", "接觸前後"),
        "乘被害人不及抗拒之際": ("不及抗拒", "突然", "當時情況", "能做哪些反應", "有哪些言語、動作或反應"),
        "親吻、擁抱或觸摸臀部、胸部或其他身體隱私處之行為": ("親吻", "擁抱", "觸摸", "身體隱私", "身體接觸"),
        "權勢性騷擾之加重關係": ("權勢性騷擾", "任職單位", "監督", "從屬"),
        "告訴意思與提出情形": ("提出告訴", "申訴", "報案"),
    },
    "drugs_10_use": {
        "施用行為、時間、地點及方法": ("何時、在何處取得、持有或施用", "施用的種類、時間與次數", "做了什麼"),
        "毒品品項及第一級或第二級分類": ("毒品種類", "第一級", "第二級", "甲基安非他命"),
        "採尿、鑑驗或其他可回查證據": ("採尿", "尿液", "鑑驗", "搜索", "查獲", "證據"),
    },
    "sexual_221_nonconsensual_intercourse": {
        "性交行為": ("性交", "發生了什麼", "行為經過", "實際有哪些身體接觸或其他行為"),
        "強暴、脅迫、恐嚇、催眠術或其他違反意願方法": ("使用了什麼方法", "暴力、威脅", "強暴"),
        "本人意願與方法作用的具體事實": ("是否同意", "確認對方同意", "表達方式"),
        "未遂或既遂": ("發生了什麼", "事發後", "行為經過", "實際有哪些身體接觸或其他行為"),
    },
    "privacy_319_3_sexual_image_distribution": {
        "重製、散布、播送、交付、公然陳列、供觀覽或販賣行為": ("重製、散布", "是否有散布", "散布的管道"),
        "本人同意狀態與無故情形": ("是否曾同意", "取得了被攝錄", "同意的範圍"),
        "性影像來源類型": ("取得影像或資料的來源", "攝錄的載體", "保存於何處"),
        "營利意圖": ("營利", "獲取金錢", "收費、販售"),
        "未遂或既遂": ("目前保存在何處", "是否曾將內容", "散布的管道與範圍"),
    },
    "intimidation_305_safety": {
        "告知加害生命、身體、自由、名譽或財產之事": ("何種言語", "何種方式", "說出上開言語"),
        "恐嚇內容及傳達對象": ("對你恐嚇", "平台或管道", "被害人說出"),
        "致生安全危害的具體事實": ("心生畏懼", "感到害怕", "有何感受"),
    },
    "damage_354_property": {
        "第352條及第353條以外之他人之物": ("damaged_property", "受影響的物品", "遭毀損何物", "何人所有"),
        "毀棄損壞或致令不堪用": ("damage_action", "如何受到破壞", "如何毀損", "不堪用"),
        "足以生損害於公眾或他人": ("damage_result", "能否正常使用", "毀損程度", "價值為何"),
    },
    "defamation_310_defamation": {
        "指摘或傳述具體事項": ("具體事件或事實", "言論之內容", "原話或內容"),
        "足以毀損他人名譽": ("損害你的名譽", "貶損他人名譽", "故意貶低"),
        "散布於眾意圖及文字圖畫態樣": ("散布於眾", "公開場所發表", "散布管道"),
        "真實性、公共利益與私德範圍": ("證明其為真實", "自衛、自辯", "可受公評"),
        "相當理由確信為真實之證據資料": ("相當理由確信", "事前查證", "證據可提供", "證明其為真實"),
    },
    "defamation_309_public_insult": {
        "故意發表公然貶損他人名譽之言論": ("insult_words", "說了哪些原話", "人格評價"),
        "個案表意脈絡及公然性": ("insult_context", "public_audience", "哪些人可能聽見或看見"),
        "是否逾越一般人可合理忍受範圍": ("insult_words", "reputation_effect", "人格評價造成哪些具體影響"),
        "名譽權與公共事務、文學藝術、學術專業等言論價值之權衡": ("speech_value_context", "公共事務、評論"),
        "強暴態樣": ("insult_force_details", "推擠、毆打或其他強暴行為"),
    },
    "stalking_3_definition": {
        "以人員設備通訊網路或其他方法對特定人": ("電話、簡訊", "監視、觀察", "對被害人"),
        "反覆或持續且違反意願": ("一共發生幾次", "反覆或持續", "明確表達不願"),
        "與性或性別有關，或對密切關係人之法定例外": ("不當追求", "性別", "與你之關係", "為何要為上開行為"),
        "使人心生畏怖且足以影響日常生活或社會活動": ("心生畏怖", "日常生活", "工作", "精神上"),
        "八款法定行為態樣": ("監視、觀察、跟蹤", "電子設備對你進行干擾", "警告、威脅"),
    },
    "public_danger_185_3_impaired_driving": {
        "駕駛動力交通工具": ("driving_details", "駕駛何種動力交通工具", "飲酒後騎乘何駕駛工具"),
        "酒精濃度、不能安全駕駛，或毒品麻醉藥品品項濃度及不能安全駕駛之法定態樣": ("impairment_test_details", "數值、單位", "施測", "酒測"),
        "死亡或重傷結果、因果關係及可預見性": ("driving_incident", "碰撞或其他事故", "造成任何人受傷"),
        "十年內再犯與前案確定狀態": ("十年內", "前案", "前科", "酒駕紀錄"),
    },
}


def _attach_route_elements_to_questions(
    questions: list[dict[str, Any]],
    offenses: dict[str, dict[str, Any]],
    route_ids: list[str],
) -> None:
    """以人工審查 sidecar 把 child route 要件連到既有問句，不改題目本文。"""
    route_parent: dict[str, str] = {}
    route_elements: dict[str, list[str]] = {}
    for offense_id, offense in offenses.items():
        for route in offense.get("legal_routes", []):
            route_parent[route["id"]] = offense_id
            route_elements[route["id"]] = list(route.get("fact_elements", []))
    for route_id in route_ids:
        signals_by_element = ROUTE_ELEMENT_QUESTION_SIGNALS.get(route_id, {})
        parent = route_parent.get(route_id)
        if not parent:
            continue
        for element in route_elements.get(route_id, []):
            signals = signals_by_element.get(element, ())
            if not signals:
                continue
            for question in questions:
                if question.get("offense_id") != parent:
                    continue
                meta = question.setdefault("meta", {})
                haystack = "｜".join((str(question.get("text", "")), str(meta.get("fact_target", ""))))
                if not any(signal in haystack for signal in signals):
                    continue
                targets = meta.setdefault("target_elements", [])
                if element not in targets:
                    targets.append(element)
                legal_targets = meta.setdefault("legal_targets", [])
                if route_id not in legal_targets:
                    legal_targets.append(route_id)
                meta["element_mapping_status"] = "REVIEWED_SIDECAR"


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
        # 公司固定題逐字保留；若 child route 有經審查的中性核心缺口題，
        # 只插入該 route pack，不混入整套 md／JSON 題庫。
        if has_company_standard_questions(role, offense_id):
            for question in route_questions_for(
                role, offense_id, route_ids, offense["source"],
            ):
                if question["text"] in seen:
                    continue
                questions.append(question)
                seen.add(question["text"])
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
    _attach_route_elements_to_questions(questions, offenses, route_ids)
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
        "sexual_harassment_contact": (
            any(
                signal in item
                for item in behaviors_list
                for signal in ("觸摸", "親吻", "擁抱", "臀部", "胸部", "大腿")
            ),
            "摘要已記載身體接觸方式與部位",
            excerpts_for({"action"}, ("觸摸", "親吻", "擁抱", "臀部", "胸部", "大腿")),
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
        ("insult_words", {"action"}, ("辱罵", "侮辱", "言語"), "摘要已記載言語原文或內容"),
        ("public_audience", {"place"}, ("不特定人", "共見共聞", "公開", "休息室"), "摘要已記載發表場所及公然情境"),
        (
            "reputation_effect", {"result"},
            ("失眠", "請假就醫", "工作受影響", "生活受影響", "人際關係受影響"),
            "摘要已記載言語造成的具體生活影響",
        ),
        ("defamation_evidence_sources", {"evidence"}, ("錄音", "錄影", "指訴", "供述", "勘驗", "在場"), "摘要已列出可供查證資料"),
    ):
        add_coverage(target, keys, signals, reason)
    disposition_rows = [
        row for row in excerpts_for({"action", "object"}, ("匯款", "轉帳", "交付", "付款"))
        if not any(
            marker in str(row.get("source_excerpt", ""))
            for marker in ("佯稱", "即可", "要求", "指示")
        )
    ]
    route_coverage["property_dispositions"] = (
        bool(disposition_rows), "摘要已記載實際財產處分", disposition_rows
    )
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

"""問句生成邏輯：補充 metadata、動態預算、條件觸發、答案驅動重評估。

所有函數為純函數、無副作用、可獨立測試，不改動既有 build_questions。
"""

from __future__ import annotations


from copy import deepcopy
from typing import Any


# ── 1. 問句 metadata 擴充 ──

DEFAULT_QUESTION_META = {
    "fact_target": "",          # 本題要確認的中性事實（例：是否經同意）
    "legal_targets": [],        # 該事實會支持/排除/區分哪些法律路由（例：["theft","robbery"]）
    "alternative_targets": [],  # 非罪章審查議題；不得參與候選、路由或法律效果
    "target_fact_ids": [],      # 要追溯/補齊的 fact_id
    "target_elements": [],      # 對應罪章構成要件（element label）
    "purpose": "",              # "補齊事實" | "區分競爭假設" | "確認構成要件" | "核對矛盾" | "尋找證據"
    "trigger_condition": "always",  # "always" | "answer:<qid>:<value>" | "candidate:<cid>:present" | "fact:<fid>:status"
    "expected_distinction": "", # 預期區分的情況
    "evidence_to_verify": [],   # 可查證的證據
}

PROPERTY_FACT_TARGETS = {
    "original_possession": {
        "elements": ["原持有狀態"],
        "targets": ["theft", "embezzlement", "robbery"],
        "effects": {"theft": {"YES": "ACTIVE"}},
    },
    "consent": {
        "elements": ["同意範圍"],
        "targets": ["theft", "embezzlement"],
        "alternative_targets": ["civil_possession_dispute"],
        "effects": {"theft": {"YES": "LOWERED", "NO": "ACTIVE"}},
    },
    "prior_lawful_possession": {
        "elements": ["原合法持有關係"],
        "targets": ["theft", "embezzlement"],
        "alternative_targets": ["civil_possession_dispute"],
        "effects": {"theft": {"YES": "LOWERED"}, "embezzlement": {"YES": "ACTIVE", "NO": "LOWERED"}},
    },
    "force_or_threat": {
        "elements": ["取得手段"],
        "targets": ["theft", "robbery"],
        "effects": {"robbery": {"YES": "ACTIVE", "NO": "LOWERED"}},
    },
    "return_agreement": {
        "kind": "core",
        "elements": ["返還約定"],
        "targets": ["embezzlement"],
        "alternative_targets": ["civil_possession_dispute"],
        "effects": {"embezzlement": {"YES": "ACTIVE"}},
    },
    "stated_use_or_return_plan": {
        "kind": "core",
        "elements": ["取得後表示及處分計畫"],
        "targets": ["theft", "embezzlement", "robbery"],
        "alternative_targets": ["civil_possession_dispute"],
        "effects": {},
    },
    "evidence": {
        "kind": "core",
        "elements": ["證據來源"],
        "targets": ["theft", "embezzlement", "robbery"],
        "effects": {},
    },
}

PROPERTY_ROLE_QUESTIONS = {
    "victim": {
        "original_possession": "手機被拿走前，是否由你實際持有或保管？",
        "consent": "你是否曾同意對方拿走、使用或保管手機？",
        "prior_lawful_possession": "對方在本次處置前，是否因借用、保管或業務關係合法持有手機？",
        "force_or_threat": "對方取得手機時，是否使用拉扯、暴力或威脅？",
        "return_agreement": "對方取得手機時，是否有約定歸還？",
        "stated_use_or_return_plan": "對方當時是否表示用途或預計歸還時間？",
        "evidence": "是否有訊息、錄影或證人可供查證？",
    },
    "suspect": {
        "original_possession": "你取得手機前，是否由對方實際持有或保管？",
        "consent": "對方是否曾同意你拿取、使用或保管手機？",
        "prior_lawful_possession": "你在本次處置前，是否因借用、保管或業務關係合法持有手機？",
        "force_or_threat": "你取得手機時，是否有拉扯、使用暴力或威脅？",
        "return_agreement": "你取得手機時，是否有約定歸還？",
        "stated_use_or_return_plan": "你當時是否曾表示用途或預計歸還時間？",
        "evidence": "是否有訊息、錄影或證人可供查證？",
    },
    "transfer": {
        "original_possession": "你取得該物前，是否由他人實際持有或保管？",
        "consent": "他人是否曾同意你拿取、使用或保管該物？",
        "prior_lawful_possession": "你在本次處置前，是否因借用、保管或業務關係合法持有該物？",
        "force_or_threat": "你取得該物時，是否有拉扯、使用暴力或威脅？",
        "return_agreement": "你取得該物時，是否有約定歸還？",
        "stated_use_or_return_plan": "你當時是否曾表示用途或預計歸還時間？",
        "evidence": "是否有訊息、錄影或證人可供查證？",
    },
}


THEFT_320_1_MOVABLE_ROUTE_ID = "theft_320_1_movable"
THEFT_320_1_MOVABLE_PACK_VERSION = "theft-320-1-movable-v1"
THEFT_320_1_MOVABLE_WORK_ITEM_HASH = "524515AFD490E51FC790EEA3808C79B03869706D86F5AE1424004DE02B61B2DD"
THEFT_320_1_MOVABLE_REPLACED_FACT_TARGETS = {
    "original_possession", "consent", "force_or_threat",
}
THEFT_320_1_MOVABLE_LEGACY_FACT_TARGETS = {
    "prior_lawful_possession", "return_agreement",
    "stated_use_or_return_plan", "evidence",
}


def _review_effects(*codes: str) -> dict[str, str]:
    return {code: "NEED_REVIEW" for code in (*codes, "UNKNOWN", "CONFLICT")}


THEFT_320_1_MOVABLE_CONCEPTS: tuple[dict[str, Any], ...] = (
    {
        "concept_id": "THF3201MOV-C01",
        "phase": "narrative",
        "fact_target": "event_sequence",
        "distinction_axis": "neutral_event_sequence",
        "codes": (),
        "targets": {},
        "roles": {
            "victim": "請就你親自知曉的情形，依時間順序說明與本案財物取走相關的經過。可先整體陳述，不必擔心法律定性。",
            "suspect": "請就你親自知曉或參與的情形，依時間順序說明與本案財物取走相關的經過。可先整體陳述，不必擔心法律定性。",
            "transfer": "請依案卷或查獲情形，依時間順序說明與本案財物取走相關的經過。",
        },
    },
    {
        "concept_id": "THF3201MOV-C02",
        "phase": "single_fact",
        "fact_target": "possession_before_taking",
        "distinction_axis": "lawful_possession_pre_taking",
        "codes": ("OTHER_PERSON_CONTROL", "SUSPECT_PREEXISTING_CONTROL", "NO_IDENTIFIED_CONTROL"),
        "labels": {
            "OTHER_PERSON_CONTROL": "由他人實際持有、保管或控制",
            "SUSPECT_PREEXISTING_CONTROL": "行為人原已實際持有、保管或控制",
            "NO_IDENTIFIED_CONTROL": "未辨識出實際控制人",
        },
        "targets": {
            "theft_320_1_movable": {"OTHER_PERSON_CONTROL": "ACTIVE", "SUSPECT_PREEXISTING_CONTROL": "LOWERED", "NO_IDENTIFIED_CONTROL": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
            "embezzlement_335_general": {"OTHER_PERSON_CONTROL": "LOWERED", "SUSPECT_PREEXISTING_CONTROL": "NEED_REVIEW", "NO_IDENTIFIED_CONTROL": "LOWERED", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
            "embezzlement_337_lost_property": {"OTHER_PERSON_CONTROL": "LOWERED", "SUSPECT_PREEXISTING_CONTROL": "LOWERED", "NO_IDENTIFIED_CONTROL": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        },
        "roles": {
            "victim": "請說明物品被移動前由何人實際持有、保管或控制，以及你如何知道。",
            "suspect": "請說明你接觸該物品前由何人實際持有、保管或控制，以及你當時如何知道。",
            "transfer": "請依案卷說明該物品在行為人接觸前由何人實際持有、保管或控制，並指出記載來源。",
        },
    },
    {
        "concept_id": "THF3201MOV-C03",
        "phase": "single_fact",
        "fact_target": "authorization_scope_status",
        "distinction_axis": "authorization_scope",
        "codes": ("WITHIN_SCOPE", "BEYOND_SCOPE", "NO_CONSENT"),
        "labels": {"WITHIN_SCOPE": "在允許範圍內", "BEYOND_SCOPE": "超出允許範圍", "NO_CONSENT": "未曾同意"},
        "targets": {
            "theft_320_1_movable": {"WITHIN_SCOPE": "LOWERED", "BEYOND_SCOPE": "NEED_REVIEW", "NO_CONSENT": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
            "embezzlement_335_general": _review_effects("WITHIN_SCOPE", "BEYOND_SCOPE", "NO_CONSENT"),
        },
        "alternative_target": "civil_possession_dispute",
        "roles": {
            "victim": "請說明你與對方曾就拿取、使用或保管該物品談過哪些內容；如有允許，範圍與條件為何？",
            "suspect": "請說明你與物品持有人曾就拿取、使用或保管談過哪些內容；你如何理解允許的範圍與條件？",
            "transfer": "請依案卷說明雙方就拿取、使用或保管曾表示哪些內容，並指出允許範圍與記載來源。",
        },
    },
    {
        "concept_id": "THF3201MOV-C05",
        "phase": "single_fact",
        "fact_target": "control_status_at_discovery",
        "distinction_axis": "already_lost_property",
        "codes": ("WITHIN_HOLDER_CONTROL", "OUTSIDE_HOLDER_CONTROL"),
        "labels": {"WITHIN_HOLDER_CONTROL": "仍在原持有人控制範圍", "OUTSIDE_HOLDER_CONTROL": "位於原持有人控制範圍之外"},
        "targets": {
            "theft_320_1_movable": {"WITHIN_HOLDER_CONTROL": "ACTIVE", "OUTSIDE_HOLDER_CONTROL": "LOWERED", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
            "embezzlement_337_lost_property": {"WITHIN_HOLDER_CONTROL": "LOWERED", "OUTSIDE_HOLDER_CONTROL": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        },
        "roles": {
            "victim": "請說明你最後掌握物品的位置、保管方式，以及發現物品不在時的周遭情形。",
            "suspect": "請說明你在何處、以何種情況接觸該物品，以及當時觀察到哪些可能辨識持有人或控制範圍的情形。",
            "transfer": "請依案卷說明物品被發現或取得的位置、外觀、周遭情形及相關記載來源。",
        },
    },
    {
        "concept_id": "THF3201MOV-C06",
        "phase": "single_fact",
        "fact_target": "physical_forcing",
        "distinction_axis": "sudden_force_taking",
        "codes": ("OBJECT_MOVEMENT_ONLY_DESCRIBED", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED"),
        "labels": {"OBJECT_MOVEMENT_ONLY_DESCRIBED": "只描述物品本身的移動", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED": "另有接觸或力量描述"},
        "targets": {
            "theft_320_1_movable": _review_effects("OBJECT_MOVEMENT_ONLY_DESCRIBED", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED"),
            "robbery_325_snatching": _review_effects("OBJECT_MOVEMENT_ONLY_DESCRIBED", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED"),
        },
        "roles": {
            "victim": "請說明物品被拿取、移動或帶走時，對方做了哪些動作，以及你當時看到或感受到哪些接觸或力量。",
            "suspect": "請說明物品被拿取、移動或帶走時，你做了哪些動作，以及與在場人或物品有何接觸。",
            "transfer": "請依案卷說明物品被拿取、移動或帶走時的具體動作、接觸或力量及記載來源。",
        },
    },
    {
        "concept_id": "THF3201MOV-C07",
        "phase": "single_fact",
        "fact_target": "violence_threat",
        "distinction_axis": "force_or_threat_means",
        "codes": ("NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED"),
        "labels": {"NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "未描述其他言語或方法", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "另有言語、動作或方法描述"},
        "targets": {
            "theft_320_1_movable": _review_effects("NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED"),
            "robbery_328_robbery": _review_effects("NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED"),
        },
        "roles": {
            "victim": "請說明對方在物品被移動或交付前後說了哪些話、做了哪些動作，或使用了哪些物品與方法。",
            "suspect": "請說明物品被移動或交付前後，你說了哪些話、做了哪些動作，或使用了哪些物品與方法。",
            "transfer": "請依案卷說明物品被移動或交付前後的言語、動作、使用物品與記載來源。",
        },
    },
    {
        "concept_id": "THF3201MOV-C08",
        "phase": "single_fact",
        "fact_target": "resistance_capability",
        "distinction_axis": "cannot_resist_outcome",
        "codes": ("RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED", "RESPONSE_LIMIT_DESCRIBED"),
        "labels": {"RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED": "被害人明確陳述反應能力未受限制", "RESPONSE_LIMIT_DESCRIBED": "描述反應能力受到限制"},
        "targets": {
            "theft_320_1_movable": _review_effects("RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED", "RESPONSE_LIMIT_DESCRIBED"),
            "robbery_328_robbery": _review_effects("RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED", "RESPONSE_LIMIT_DESCRIBED"),
        },
        "roles": {
            "victim": "請說明對方上述言語或動作發生時，你能做哪些反應、實際做了什麼，以及哪些情況影響你的行動或判斷。",
            "suspect": "請說明當時對方有哪些言語、動作或反應，以及你如何觀察到。",
            "transfer": "請依案卷說明被害人當時的言語、動作、身體狀態、現場條件及各項記載來源。",
        },
    },
    {
        "concept_id": "THF3201MOV-C09",
        "phase": "single_fact",
        "fact_target": "post_acquisition_conduct",
        "distinction_axis": "owner_like_post_acquisition_conduct",
        "codes": ("RETURNED", "CONTACTED_ONLY", "RETAINED", "TRANSFERRED_OR_SOLD", "CONCEALED", "MIXED_SEQUENCE"),
        "labels": {"RETURNED": "已返還", "CONTACTED_ONLY": "僅有聯絡", "RETAINED": "持續保留", "TRANSFERRED_OR_SOLD": "已移轉或出售", "CONCEALED": "有隱匿情形", "MIXED_SEQUENCE": "有兩種以上事件"},
        "targets": {
            "theft_320_1_movable": _review_effects("RETURNED", "CONTACTED_ONLY", "RETAINED", "TRANSFERRED_OR_SOLD", "CONCEALED", "MIXED_SEQUENCE"),
            "embezzlement_335_general": _review_effects("RETURNED", "CONTACTED_ONLY", "RETAINED", "TRANSFERRED_OR_SOLD", "CONCEALED", "MIXED_SEQUENCE"),
            "embezzlement_337_lost_property": _review_effects("RETURNED", "CONTACTED_ONLY", "RETAINED", "TRANSFERRED_OR_SOLD", "CONCEALED", "MIXED_SEQUENCE"),
        },
        "roles": {
            "victim": "請依時間順序說明物品被取得後，你所知道的聯絡、返還、保管、使用、移轉、出售、隱匿或其他處理情形，並說明如何得知及是否發生在報案或查獲後。",
            "suspect": "請依時間順序說明你取得物品後如何聯絡持有人，以及何時、因何原因返還、保管、使用、移轉、出售、隱匿或以其他方式處理；請區分報案或查獲前後。",
            "transfer": "請依案卷及時間順序說明物品取得後的聯絡、返還、保管、使用、移轉、出售、隱匿或其他處理情形，並指出記載來源及報案或查獲前後。",
        },
    },
)

THEFT_320_1_MOVABLE_EXPECTED_CONCEPT_IDS = tuple(
    item["concept_id"] for item in THEFT_320_1_MOVABLE_CONCEPTS
)


def _materialize_theft_320_1_movable_questions(
    role: str, materialized_at: str | None,
) -> list[dict[str, Any]]:
    role_code = {"victim": "V", "suspect": "S", "transfer": "T"}[role]
    questions: list[dict[str, Any]] = []
    for concept in THEFT_320_1_MOVABLE_CONCEPTS:
        text = concept["roles"].get(role)
        if not text:
            continue
        codes = tuple(concept.get("codes", ()))
        answer_map = ({code: code for code in (*codes, "UNKNOWN")} if codes else None)
        target_details = [
            {"route_id": route_id, "effects": deepcopy(effects), "exclusion_safe": False}
            for route_id, effects in concept.get("targets", {}).items()
        ]
        alternative_details: list[dict[str, Any]] = []
        if concept.get("alternative_target"):
            alternative_details.append({
                "route_id": concept["alternative_target"],
                "effects": _review_effects(*codes),
                "candidate_eligible": False,
                "routing_eligible": False,
                "question_generation_eligible": False,
                "template_activation_eligible": False,
                "effect_executable": False,
                "exclusion_safe": False,
                "human_review_required": True,
            })
        questions.append({
            "id": f"{concept['concept_id']}-{role_code}",
            "text": text,
            "kind": "core" if concept["phase"] == "narrative" else "distinguishing",
            "role": role,
            "offense_id": "theft",
            "offense_name": "竊盜",
            "element_id": concept["fact_target"],
            "element_label": concept["fact_target"],
            "priority": 1,
            "source": {"label": "第320條第1項動產竊盜核准工作單", "status": "STATIC_HUMAN_APPROVED"},
            "status": "PENDING",
            "answer": "",
            "answer_code": "UNKNOWN",
            "meta": {
                "pack_id": THEFT_320_1_MOVABLE_ROUTE_ID,
                "pack_version": THEFT_320_1_MOVABLE_PACK_VERSION,
                "work_item_hash": THEFT_320_1_MOVABLE_WORK_ITEM_HASH,
                "materialized_at": materialized_at or "NOT_PERSISTED",
                "question_concept_id": concept["concept_id"],
                "target_interview_role": role,
                "question_phase": concept["phase"],
                "fact_target": concept["fact_target"],
                "distinction_axis": concept["distinction_axis"],
                "legal_targets": list(concept.get("targets", {})),
                "legal_target_details": target_details,
                "alternative_targets": [item["route_id"] for item in alternative_details],
                "alternative_target_details": alternative_details,
                "purpose": "補齊事實" if concept["phase"] == "narrative" else "區分競爭假設",
                "trigger_condition": f"candidate:{THEFT_320_1_MOVABLE_ROUTE_ID}:present",
                "answer_mode": "enum" if codes else "narrative_only",
                "answer_map": answer_map,
                "answer_labels": {**deepcopy(concept.get("labels", {})), "UNKNOWN": "UNKNOWN／無法確認"} if codes else {},
                "mapping_version": THEFT_320_1_MOVABLE_PACK_VERSION,
                "exclusion_safe": False,
                "human_review_required": True,
                "legal_conclusion": False,
            },
        })
    return questions


def build_property_taking_questions(
    role: str,
    candidate_ids: set[str],
    gate1: dict[str, Any],
    legal_route_ids: set[str] | None = None,
    materialized_at: str | None = None,
) -> list[dict[str, Any]]:
    fact_keys = {item.get("fact_key") for item in gate1.get("facts", [])}
    if not {"action", "object"}.issubset(fact_keys) or not candidate_ids.intersection({"theft", "embezzlement", "robbery"}):
        return []
    prefix = {"victim": "V", "suspect": "S", "transfer": "T"}[role]
    selected_route_ids = legal_route_ids or set()
    exact_pack_enabled = THEFT_320_1_MOVABLE_ROUTE_ID in selected_route_ids
    questions = (
        _materialize_theft_320_1_movable_questions(role, materialized_at)
        if exact_pack_enabled else []
    )
    for index, (fact_key, text) in enumerate(PROPERTY_ROLE_QUESTIONS[role].items(), start=1):
        if exact_pack_enabled and fact_key not in THEFT_320_1_MOVABLE_LEGACY_FACT_TARGETS:
            continue
        spec = PROPERTY_FACT_TARGETS[fact_key]
        target_ids = [item for item in spec["targets"] if item in candidate_ids]
        if not target_ids:
            continue
        alternative_ids = list(spec.get("alternative_targets", []))
        questions.append({
            "id": f"{prefix}-FACT-{index:02d}-{fact_key}",
            "text": text,
            "kind": spec.get("kind", "distinguishing" if len(target_ids) > 1 else "core"),
            "role": role,
            "offense_id": target_ids[0],
            "element_id": fact_key,
            "element_label": spec["elements"][0],
            "priority": 1,
            "source": {"label": "中性事實區分流程", "status": "HUMAN_REVIEW_REQUIRED"},
            "status": "PENDING",
            "answer": "",
            "answer_code": "UNKNOWN",
            "meta": {
                "fact_target": fact_key,
                "legal_targets": target_ids,
                "legal_target_details": [
                    {"route_id": target, "effects": spec["effects"].get(target, {}), "exclusion_safe": False}
                    for target in target_ids
                ],
                "alternative_targets": alternative_ids,
                "alternative_target_details": [
                    {
                        "route_id": target,
                        "effects": {
                            "YES": "NEED_REVIEW",
                            "NO": "NEED_REVIEW",
                            "UNKNOWN": "NEED_REVIEW",
                            "CONFLICT": "NEED_REVIEW",
                        },
                        "candidate_eligible": False,
                        "routing_eligible": False,
                        "question_generation_eligible": False,
                        "template_activation_eligible": False,
                        "effect_executable": False,
                        "exclusion_safe": False,
                        "human_review_required": True,
                    }
                    for target in alternative_ids
                ],
                "target_elements": spec["elements"],
                "purpose": "區分競爭假設" if len(target_ids) > 1 else "補齊事實",
                "trigger_condition": "always",
                "answer_map": {"YES": "YES", "NO": "NO", "UNKNOWN": "UNKNOWN"},
                "mapping_version": "property-taking-v1",
            },
        })
    return questions


class QuestionBudgetExceeded(ValueError):
    """必要核心題已超過題量上限，必須縮小法律路由而非靜默裁題。"""


def enrich_question_metadata(
    questions: list[dict[str, Any]],
    gate1: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """為每個問句補充 metadata，不修改原始 list。

    - core/補充/補強：通常 "always"，目的=確認構成要件/補齊事實
    - distinguishing：trigger_condition 依候選；purpose="區分競爭假設"
    - aggravating：若無加重條件可略過
    """
    enriched: list[dict[str, Any]] = []
    for q in questions:
        eq = deepcopy(q)
        kind = eq.get("kind", "")
        offense_id = eq.get("offense_id", "")

        meta = deepcopy(DEFAULT_QUESTION_META)
        meta.update(deepcopy(eq.get("meta", {})))

        element_ref = eq.get("element_id") or eq.get("element_label")
        if meta.get("fact_target"):
            meta["element_mapping_status"] = "EXACT"
        elif element_ref:
            meta["target_elements"] = [element_ref]
            # fact_target：本題要確認的中性事實 = 構成要件 label（例：是否經同意）
            meta["fact_target"] = element_ref
            meta["element_mapping_status"] = "EXACT"
        else:
            # md 題無 JSON element 對應：fact_target 以問句 ID 標記（T-C-01），
            # 查問目的即為題目本文（text）；由題庫審核
            #（docs/QUESTION_DESIGN_AND_USE.md）保證一事實一題。
            meta["fact_target"] = eq.get("id", "")
            meta["fact_target_text"] = eq.get("text", "")
            meta["element_mapping_status"] = "MD_SOURCE"

        # legal_targets：本題所屬罪章 + 事實會支持/排除/區分的其他候選路由
        if kind in ("core", "supplemental", "reinforce"):
            if not meta.get("legal_targets"):
                meta["legal_targets"] = [offense_id] if offense_id else []
            if not meta.get("pack_id"):
                meta["trigger_condition"] = "always"
                meta["purpose"] = "確認構成要件" if kind == "core" else "補齊事實"
            # 只有題目本身的 canonical element reference 才能建立映射。
            # 不得把候選的前三個 unknown elements 任意複製到每一題。

        elif kind == "distinguishing":
            others = sorted({c.get("id") or c.get("offense_id") for c in candidates} - {offense_id})
            if not meta.get("legal_targets"):
                meta["legal_targets"] = ([offense_id] if offense_id else []) + others
            if not meta.get("pack_id"):
                meta["trigger_condition"] = f"candidate:{offense_id}:present"
                meta["purpose"] = "區分競爭假設"
                meta["expected_distinction"] = f"釐清 {offense_id} 與其他候選的關鍵差異"

        elif kind == "aggravating":
            meta["legal_targets"] = [offense_id] if offense_id else []
            meta["trigger_condition"] = f"candidate:{offense_id}:present"
            meta["purpose"] = "確認加重情節"

        else:
            # company/common 通用程序題：不屬於單一法律路由，跨所有候選共通
            meta["legal_targets"] = ["ALL_ROUTES"]

        eq["meta"] = meta
        enriched.append(eq)
    return enriched


# ── 2. 動態問題預算 ──


def apply_question_budget(
    questions: list[dict[str, Any]],
    max_offense_questions: int = 30,
) -> list[dict[str, Any]]:
    """依 spec §7.5 裁切：company/common 全保護；罪章間公平分配預算。

    超額時裁切順序：加重 → 區分 → 補充 → 補強 → core（core 最後裁，
    且多罪章時各罪章 core 輪流保留，避免單一罪章壟斷額度）。
    回傳裁切後的 list（不修改原 list）。
    """
    offense_questions = [q for q in questions if q.get("kind") not in {"company", "common"}]
    if len(offense_questions) <= max_offense_questions:
        return questions

    core_questions = [q for q in offense_questions if q.get("kind") == "core"]
    company_offense = [q for q in offense_questions if q.get("kind") == "company_offense"]
    required_questions = core_questions + company_offense
    if len(required_questions) > max_offense_questions:
        apply_question_budget.last_prune_info = {
            "pruned_core": 0,
            "pruned_company_offense": 0,
            "pruned_removable": 0,
            "total_pruned": 0,
            "required_count": len(required_questions),
            "budget": max_offense_questions,
            "status": "BUDGET_EXCEEDED",
        }
        raise QuestionBudgetExceeded(
            f"必要核心／公司罪章題共 {len(required_questions)} 題，超過 {max_offense_questions} 題上限；"
            "請先縮小候選法律路由，禁止裁除必要題。"
        )

    # 選配題才可裁切。保留順序與裁切順序相反：補強、補充、區分、加重。
    kind_priority = {"reinforce": 0, "supplemental": 1, "distinguishing": 2, "aggravating": 3}
    removable = [q for q in offense_questions if q.get("kind") in kind_priority]
    removable.sort(key=lambda q: kind_priority.get(q.get("kind", ""), 99))

    def _round_robin(items: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
        """依 offense_id 分組輪流保留，確保每罪章公平。"""
        if len(items) <= budget:
            return list(items)
        by_offense: dict[str, list[dict[str, Any]]] = {}
        for q in items:
            by_offense.setdefault(q.get("offense_id", ""), []).append(q)
        kept: list[dict[str, Any]] = []
        round_idx = 0
        while budget > 0:
            progress = False
            for oid in sorted(by_offense):
                group = by_offense[oid]
                if round_idx < len(group):
                    kept.append(group[round_idx])
                    budget -= 1
                    progress = True
                    if budget <= 0:
                        break
            if not progress:
                break
            round_idx += 1
        return kept

    kept_core = list(core_questions)
    kept_co = list(company_offense)
    removable_budget = max_offense_questions - len(kept_core) - len(kept_co)
    kept_removable = _round_robin(removable, removable_budget) if removable_budget > 0 else []

    pruned_core_count = 0
    pruned_co_count = 0

    kept_ids = {id(q) for q in kept_removable} | {id(q) for q in kept_core} | {id(q) for q in kept_co}
    protected = [q for q in questions if q.get("kind") in {"company", "common"}]
    kept_offense = [q for q in offense_questions if id(q) in kept_ids]
    # 裁切透明化（spec §7.5 不得假裝完成）：附加 pruned 統計屬性供呼叫端記錄
    apply_question_budget.last_prune_info = {
        "pruned_core": pruned_core_count,
        "pruned_company_offense": pruned_co_count,
        "pruned_removable": len(removable) - len(kept_removable),
        "total_pruned": pruned_core_count + pruned_co_count + len(removable) - len(kept_removable),
    }
    return protected + kept_offense


# ── 3. 條件式問句觸發 ──


def filter_active_questions(
    questions: list[dict[str, Any]],
    case: dict[str, Any],
) -> list[dict[str, Any]]:
    """依 trigger_condition 決定哪些問句當前應呈現。

    trigger_condition 格式：
      - "always"
      - "candidate:<offense_id>:present"  # 候選被選中
      - "answer:<qid>:<value>"            # 特定題目被作答且符合值
      - "fact:<fid>:status"               # 某事實狀態
    """
    active: list[dict[str, Any]] = []
    selected_offense_ids = set(case.get("selected_offenses", []))
    answers = {q["id"]: q.get("answer", "") for q in case.get("questions", [])}
    facts = {f["fact_id"]: f.get("fact_status") for f in case.get("gate1", {}).get("facts", [])}

    for q in questions:
        cond = q.get("meta", {}).get("trigger_condition", "always")
        if cond == "always":
            active.append(q)
        elif cond.startswith("candidate:"):
            _, oid, _ = cond.split(":")
            if oid in selected_offense_ids:
                active.append(q)
        elif cond.startswith("answer:"):
            _, qid, expected = cond.split(":")
            if answers.get(qid, "") == expected:
                active.append(q)
        elif cond.startswith("fact:"):
            _, fid, expected_status = cond.split(":")
            if facts.get(fid, "") == expected_status:
                active.append(q)
        else:
            # 未知 activation 不得默認顯示，避免未核准題目進入 runtime。
            continue
    return active


# ── 4. 答案驅動候選重評估 ──


# 回答分類（spec §7.4）
ANSWER_AFFIRMATIVE_HINTS = ("有看到", "我看到", "有發生", "有交付", "有收", "有拿", "有同意", "有使用", "他有拿走", "有遭")
# 明確肯定句式：開頭「是，」「對，」或「我曾／我之前／我有／我有過」（spec §7.4 明確肯定）
ANSWER_AFFIRMATIVE_PREFIXES = ("是，", "是的", "是的，", "對，", "是的，", "我曾", "我之前", "我有")
ANSWER_NEGATIVE_HINTS = ("沒有", "並非", "並未", "無證據", "不確定是否", "未曾")
ANSWER_UNKNOWN_HINTS = ("不知道", "不記得", "不清楚", "忘記")
ANSWER_NA_HINTS = ("不適用",)


def classify_answer(text: str) -> str:
    """把回答分類為 affirmative/negative/unknown/not_applicable/other。

    「不知道」不得視為否認（spec §7.4）；無回答不是否定事實。
    只以完整詞組判斷（單字「有/是/對」過於寬鬆，會誤判普通敘述）。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return "other"
    if any(h in cleaned for h in ANSWER_UNKNOWN_HINTS):
        return "unknown"
    if any(h in cleaned for h in ANSWER_NA_HINTS):
        return "not_applicable"
    if any(h in cleaned for h in ANSWER_NEGATIVE_HINTS):
        return "negative"
    if any(h in cleaned for h in ANSWER_AFFIRMATIVE_HINTS):
        return "affirmative"
    if cleaned.startswith(ANSWER_AFFIRMATIVE_PREFIXES):
        return "affirmative"
    return "other"


def reevaluate_candidates_from_answers(
    case: dict[str, Any],
    bank: dict[str, Any],
) -> dict[str, Any]:
    """依最新答案更新候選：矛盾偵測與 unknown_elements 收縮。

    規則（保守，不自動定性）：
    1. 核心題（kind=core）有 element 對應；答案分類為 affirmative →
       該 element 從 unknown_elements 移除（有陳述支持，仍非證實）。
    2. 答案為 negative → 在候選 contradictory_answers 記錄（供承辦人注意）。
    3. 答案為 unknown → 不改變 unknown_elements（不知道 ≠ 否認）。
    4. 有答案且與其他回答語意矛盾（同 element 一正一反）→ 記錄矛盾。
    回傳 {"candidates": [...], "updated": bool, "contradictions": [...]}。
    """
    candidates = deepcopy(case.get("candidates", []))
    by_offense = {(c.get("id") or c.get("offense_id")): c for c in candidates}
    contradictions: list[dict[str, str]] = []
    updated = False

    # 逐題檢查有作答的核心題
    element_answer_map: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    for q in case.get("questions", []):
        if q.get("kind") != "core" or not q.get("answer", "").strip():
            continue
        if q.get("meta", {}).get("mapping_version") == "property-taking-v1":
            continue
        offense_id = q.get("offense_id", "")
        element_label = q.get("element_label", "")
        category = classify_answer(q["answer"])
        element_answer_map.setdefault((offense_id, element_label), []).append(
            (q["id"], category, q["answer"])
        )

    for (offense_id, element_label), entries in element_answer_map.items():
        candidate = by_offense.get(offense_id)
        if candidate is None:
            continue
        categories = {c for _, c, _ in entries}
        # 同 element 一正一反 → 矛盾
        if "affirmative" in categories and "negative" in categories:
            qids = [qid for qid, _, _ in entries]
            contradictions.append({
                "offense_id": offense_id,
                "element": element_label,
                "question_ids": qids,
                "note": "同一構成要件之回答同時含肯定與否認陳述，需承辦人核對。",
            })
        # affirmative → element 從 unknown_elements 移除（有陳述支持）
        if "affirmative" in categories and element_label in candidate.get("unknown_elements", []):
            candidate["unknown_elements"] = [
                e for e in candidate["unknown_elements"] if e != element_label
            ]
            candidate.setdefault("supported_elements", [])
            if element_label not in candidate["supported_elements"]:
                candidate["supported_elements"].append(element_label)
            updated = True
        # negative → 記錄反向資訊（不改 unknown_elements，因否定未必排除成立）
        if "negative" in categories:
            candidate.setdefault("contradictory_answers", [])
            for qid, _, text in entries:
                if classify_answer(text) == "negative":
                    entry = {"element": element_label, "question_id": qid}
                    if entry not in candidate["contradictory_answers"]:
                        candidate["contradictory_answers"].append(entry)
                        updated = True

    current_question_ids = {q.get("id") for q in case.get("questions", [])}
    fact_updates = [
        deepcopy(item) for item in case.get("fact_updates", [])
        if item.get("question_id") not in current_question_ids
    ]
    for question in case.get("questions", []):
        meta = question.get("meta", {})
        if meta.get("mapping_version") != "property-taking-v1":
            continue
        answer_code = question.get("answer_code", "UNKNOWN")
        if answer_code not in {"YES", "NO", "UNKNOWN"}:
            answer_code = "UNKNOWN"
        fact_updates.append({
            "fact_key": meta["fact_target"],
            "value": answer_code,
            "question_id": question["id"],
            "source_role": question.get("role", case.get("question_role", "")),
            "answer_code": answer_code,
            "provenance": "interview.answer_code",
        })

    overlay: dict[str, str] = {}
    for fact_key in {item["fact_key"] for item in fact_updates}:
        values = {item["value"] for item in fact_updates if item["fact_key"] == fact_key and item["value"] != "UNKNOWN"}
        overlay[fact_key] = "CONFLICT" if values == {"YES", "NO"} else (next(iter(values)) if values else "UNKNOWN")

    mapped_questions = [
        question for question in case.get("questions", [])
        if question.get("meta", {}).get("mapping_version") == "property-taking-v1"
    ]
    for candidate in candidates:
        if not mapped_questions and not fact_updates:
            continue
        candidate_id = candidate.get("id") or candidate.get("offense_id")
        reasons: list[dict[str, Any]] = []
        effects: set[str] = set()
        for question in mapped_questions:
            meta = question.get("meta", {})
            fact_key = meta.get("fact_target")
            fact_value = overlay.get(fact_key, "UNKNOWN")
            for target in meta.get("legal_target_details", []):
                if target.get("route_id") != candidate_id:
                    continue
                effect = target.get("effects", {}).get(fact_value, "NEED_REVIEW")
                effects.add(effect)
                reasons.append({
                    "rule_id": meta.get("mapping_version"),
                    "fact_key": fact_key,
                    "fact_value": fact_value,
                    "question_id": question.get("id"),
                    "effect": effect,
                })
        if "CONFLICT" in overlay.values() or ({"ACTIVE", "LOWERED"} <= effects):
            state = "NEED_REVIEW"
        elif "ACTIVE" in effects:
            state = "ACTIVE"
        elif "LOWERED" in effects:
            state = "LOWERED"
        else:
            state = "NEED_REVIEW"
        candidate["candidate_state"] = state
        candidate["status_reasons"] = reasons

    return {
        "candidates": candidates,
        "updated": updated or bool(fact_updates),
        "contradictions": contradictions,
        "fact_updates": fact_updates,
        "fact_overlay": overlay,
    }


def reevaluate_legal_routes_from_answers(case: dict[str, Any]) -> dict[str, Any]:
    """從目前題目與有效訪談快照完整重算 exact child route 觀察與狀態。"""
    selected_route_ids = {
        item.get("route_id") for item in case.get("selected_legal_routes", [])
        if isinstance(item, dict) and isinstance(item.get("route_id"), str)
    }
    current_role = case.get("question_role", "")
    sources: list[tuple[str, str, list[dict[str, Any]]]] = []
    for interview_id, interview in case.get("interviews", {}).items():
        if not isinstance(interview, dict) or interview.get("role") == current_role:
            continue
        sources.append((interview_id, str(interview.get("role", "")), interview.get("questions", [])))
    sources.append((f"{current_role}:active", current_role, case.get("questions", [])))

    observations: dict[str, dict[str, list[dict[str, Any]]]] = {
        route_id: {} for route_id in selected_route_ids
    }
    route_questions: dict[str, dict[str, dict[str, Any]]] = {
        route_id: {} for route_id in selected_route_ids
    }
    for interview_id, role, questions in sources:
        for question in questions:
            meta = question.get("meta", {})
            if meta.get("mapping_version") != THEFT_320_1_MOVABLE_PACK_VERSION:
                continue
            fact_target = meta.get("fact_target")
            if not fact_target or not isinstance(meta.get("answer_map"), dict):
                continue
            for detail in meta.get("legal_target_details", []):
                route_id = detail.get("route_id")
                if route_id not in selected_route_ids:
                    continue
                route_questions[route_id][fact_target] = detail
                answer_code = question.get("answer_code", "UNKNOWN")
                if answer_code not in meta["answer_map"]:
                    answer_code = "UNKNOWN"
                observations[route_id].setdefault(fact_target, []).append({
                    "question_id": question.get("id"),
                    "question_concept_id": meta.get("question_concept_id"),
                    "interview_id": interview_id,
                    "role": role,
                    "answer_code": answer_code,
                    "source": "ANSWER",
                    "pack_version": meta.get("pack_version"),
                    "work_item_hash": meta.get("work_item_hash"),
                })

    overlays: dict[str, dict[str, dict[str, Any]]] = {}
    states: dict[str, dict[str, Any]] = {}
    for route_id in selected_route_ids:
        route_overlay: dict[str, dict[str, Any]] = {}
        effects: set[str] = set()
        reason_fact_targets: list[str] = []
        unknown_fact_targets: list[str] = []
        conflict_fact_targets: list[str] = []
        for fact_target, detail in route_questions[route_id].items():
            fact_observations = observations[route_id].get(fact_target, [])
            values = {
                item["answer_code"] for item in fact_observations
                if item["answer_code"] != "UNKNOWN"
            }
            question_ids = [
                str(item["question_id"]) for item in fact_observations
                if item.get("question_id")
            ]
            if len(values) > 1:
                status = "CONFLICT"
                value = None
                conflict_fact_targets.append(fact_target)
                effect_key = "CONFLICT"
            elif len(values) == 1:
                status = "KNOWN"
                value = next(iter(values))
                effect_key = value
            else:
                status = "UNKNOWN"
                value = None
                unknown_fact_targets.append(fact_target)
                effect_key = "UNKNOWN"
            effect = detail.get("effects", {}).get(effect_key, "NEED_REVIEW")
            effects.add(effect)
            reason_fact_targets.append(fact_target)
            route_overlay[fact_target] = {
                "status": status,
                "value": value,
                "effect": effect,
                "observation_question_ids": question_ids,
            }
        overlays[route_id] = route_overlay
        if (
            unknown_fact_targets
            or conflict_fact_targets
            or "NEED_REVIEW" in effects
            or {"ACTIVE", "LOWERED"} <= effects
        ):
            state = "NEED_REVIEW"
        elif "ACTIVE" in effects:
            state = "ACTIVE"
        elif "LOWERED" in effects:
            state = "LOWERED"
        else:
            state = "NEED_REVIEW"
        states[route_id] = {
            "state": state,
            "reason_fact_targets": reason_fact_targets,
            "unknown_fact_targets": unknown_fact_targets,
            "conflict_fact_targets": conflict_fact_targets,
            "legal_conclusion": False,
            "human_review_required": True,
        }
    return {
        "route_fact_observations": observations,
        "route_fact_overlay": overlays,
        "selected_legal_route_states": states,
    }


# ── 5. 問句去重與排序 ──


def deduplicate_questions(
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """依 full text 去重；保留第一個（依優先序）"""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for q in questions:
        if q["text"] in seen:
            continue
        seen.add(q["text"])
        unique.append(q)
    return unique


def sort_questions_by_priority(
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """依 kind 優先序排序：company > common > core > supplemental > reinforce > distinguishing > aggravating"""
    kind_order = {"company": 0, "common": 1, "core": 2, "supplemental": 3, "reinforce": 4, "distinguishing": 5, "aggravating": 6}
    return sorted(questions, key=lambda q: (kind_order.get(q.get("kind", ""), 99), q.get("priority", 99)))

# ── 6. 生成時程式化品質檢核（docs/QUESTION_DESIGN_AND_USE.md §8，Q1–Q10）──

LEADING_PATTERNS = (
    "是不是你", "是不是有", "對不對", "難道你", "你承認", "你否認",
    "你是否有竊盜", "你是否同意你", "你知不知道你犯罪",
)
CONCLUSION_PATTERNS = (
    "犯罪成立", "構成犯罪", "你犯了", "你的罪行", "明知故犯",
    "竊盜罪成立", "詐欺罪成立", "恐嚇罪成立", "侵占罪成立",
)


def validate_generated_questions(
    questions: list[dict[str, Any]],
    role: str,
    *,
    max_offense_questions: int = 30,
) -> dict[str, Any]:
    """生成後品質檢核（docs/QUESTION_DESIGN_AND_USE.md §8）。

    回傳 {"problems": [...], "warnings": [...]}。

    problems：Q1–Q5、Q9 違規（生成應失敗）
    warnings：Q6–Q8（預算物理限制，記錄透明化）
    """
    from .company_templates import COMPANY_QUESTIONS, render_company_text

    problems: list[str] = []
    warnings: list[str] = []

    seen_texts: set[str] = set()
    offense_count = 0
    core_by_offense: dict[str, int] = {}

    for q in questions:
        qid = q.get("id", "?")
        kind = q.get("kind", "")
        text = q.get("text", "")
        # company 題逐字保留（spec §3.3），其多重問句為公司核定原文，不適用 Q1/Q2
        is_company_verbatim = kind in ("company", "company_offense")

        # Q1 主題單一性（僅非公司逐字題）。
        # 多重問號 = 可能多重主題（spec §7.3），但同一主題的多個子問合乎偵查實務
        # （手冊 §120 問答式筆錄）。程式無法以 NLP 判定主題歸屬 → 一律 warning，
        # 由第 3 層人工審核（docs/QUESTION_DESIGN_AND_USE.md §8）判定是否應拆題。
        if not is_company_verbatim and text.count("？") > 1:
            warnings.append(f"Q1 多重問號（請人工確認是否應拆題）：{qid}")

        # Q2 無誘導（僅非公司逐字題）
        if not is_company_verbatim:
            for pattern in LEADING_PATTERNS:
                if pattern in text:
                    problems.append(f"Q2 誘導語句「{pattern}」：{qid}")

        # Q3 無結論預設（全部題目均適用，含公司題）
        for pattern in CONCLUSION_PATTERNS:
            if pattern in text:
                problems.append(f"Q3 定性語句「{pattern}」：{qid}")

        # Q5 去重
        if text in seen_texts:
            problems.append(f"Q5 重複題：{qid}")
        seen_texts.add(text)

        # Q7 core 統計
        if kind == "core":
            oid = q.get("offense_id", "")
            core_by_offense[oid] = core_by_offense.get(oid, 0) + 1

        if kind not in ("company", "common"):
            offense_count += 1

        # Q9 metadata 完整（core/supplemental/reinforce/distinguishing/aggravating）
        if kind not in ("company", "common", "company_offense"):
            meta = q.get("meta")
            if not meta or not str(meta.get("purpose", "")).strip():
                problems.append(f"Q9 缺 purpose：{qid}")
            if not meta or not str(meta.get("trigger_condition", "")).strip():
                problems.append(f"Q9 缺 trigger_condition：{qid}")

    # Q4 公司題逐字
    for expected in COMPANY_QUESTIONS.get(role, []):
        rendered = render_company_text(expected, today="　", now_time="　年　月　日　時　分")
        if not any(q.get("text") == rendered for q in questions):
            problems.append(f"Q4 公司題缺失或遭改寫：{expected[:20]}")

    # Q6 預算上限
    if offense_count > max_offense_questions:
        warnings.append(f"Q6 offense 題 {offense_count} 超 {max_offense_questions} 上限")

    # Q7 core 保底（round-robin 應保證每罪章 ≥ 1）
    for oid, count in core_by_offense.items():
        if count < 1:
            warnings.append(f"Q7 罪章 {oid} 無 core 題")

    return {"problems": problems, "warnings": warnings, "offense_count": offense_count}
## COVERAGE GAP DETECTOR ##

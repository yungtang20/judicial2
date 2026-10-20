from __future__ import annotations

from copy import deepcopy
from typing import Any


ROUTE_QUESTION_PACKS: dict[str, dict[str, Any]] = {
    "sexual_225_incapacity": {
        "version": "sexual-225-v1",
        "review_status": "HUMAN_REVIEW_REQUIRED",
        "questions": {
            "victim": [
                {
                    "id": "V-S225-K-AGE",
                    "text": "行為時你的年齡為何？可由哪一項身分或年籍資料確認？",
                    "fact_target": "victim_age_evidence",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "core",
                },
                {
                    "id": "V-S225-K-WHEN-WHERE",
                    "text": "相關接觸發生的時間與地點為何？",
                    "fact_target": "event_time_place",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "core",
                },
                {
                    "id": "V-S225-K-CONTACT",
                    "text": "對方實際有哪些身體接觸或其他行為？請以你能接受的程度說明。",
                    "fact_target": "sexual_contact_details",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "core",
                },
                {
                    "id": "V-S225-Q-CAPACITY",
                    "text": "當時你理解現場情形、表達意思及採取行動的能力如何？請說明具體狀況。",
                    "fact_target": "capacity_detail",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "core",
                },
                {
                    "id": "V-S225-Q-MEMORY",
                    "text": "從最後一次清楚記得的事情到恢復清楚意識之間，你記得哪些事情？",
                    "fact_target": "memory_timeline",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "core",
                },
                {
                    "id": "V-S225-Q-OBSERVERS",
                    "text": "哪些人曾親自看到你當時的言語、動作或身體狀況？各自看到什麼？",
                    "fact_target": "state_observation_sources",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "reinforce",
                },
                {
                    "id": "V-S225-Q-DISCOVERY",
                    "text": "發現現場及報案的人是誰？何時發現、何時報案，當時看到什麼？",
                    "fact_target": "discovery_report_details",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "reinforce",
                },
                {
                    "id": "V-S225-Q-RECORDS",
                    "text": "現場是否有監視器、消費或點酒紀錄、報案紀錄，或其他可以查證的資料？",
                    "fact_target": "scene_record_sources",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "reinforce",
                },
                {
                    "id": "V-S225-Q-MEDICAL",
                    "text": "事件後你的身體或心理狀況如何？是否曾就醫、驗傷或接受相關採證？",
                    "fact_target": "post_event_medical_evidence",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "reinforce",
                },
                {
                    "id": "V-S225-Q-INTERACTION",
                    "text": "在相關接觸前後，對方曾與你說什麼或做什麼？你當時能記得哪些內容？",
                    "fact_target": "observable_prior_interaction",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "distinguishing",
                },
            ],
            "suspect": [
                {
                    "id": "S-S225-Q-SEQUENCE",
                    "text": "請依時間順序說明你與對方接觸前後發生的事情。",
                    "fact_target": "event_sequence",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "core",
                },
                {
                    "id": "S-S225-Q-OBSERVED-STATE",
                    "text": "接觸前，你親自看到或聽到對方有哪些言語、動作或身體狀況？",
                    "fact_target": "suspect_observed_state",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "core",
                },
                {
                    "id": "S-S225-Q-AGE",
                    "text": "你當時知道對方的年齡嗎？所依據的資訊為何？",
                    "fact_target": "suspect_age_knowledge",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "distinguishing",
                },
                {
                    "id": "S-S225-Q-EVIDENCE",
                    "text": "現場有哪些人或資料可以查證你所說的經過？",
                    "fact_target": "scene_record_sources",
                    "ask_policy": "ASK_IF_UNCOVERED",
                    "kind": "reinforce",
                },
            ],
        },
    },
}


def _neutral_pack(
    offense_id: str,
    offense_name: str,
    version: str,
    rows: list[tuple[str, str, str, str]],
) -> dict[str, Any]:
    questions = [
        {
            "id": question_id,
            "text": text,
            "fact_target": fact_target,
            "ask_policy": "ASK_IF_UNCOVERED",
            "kind": kind,
        }
        for question_id, text, fact_target, kind in rows
    ]
    return {
        "offense_id": offense_id,
        "offense_name": offense_name,
        "version": version,
        "review_status": "HUMAN_REVIEW_REQUIRED",
        "questions": {"victim": questions, "suspect": deepcopy(questions)},
    }


ROUTE_QUESTION_PACKS.update({
    "sexual_harassment_25_unwanted_touch": {
        "offense_id": "sexual_harassment",
        "offense_name": "性騷擾",
        "version": "sexual-harassment-25-v1",
        "review_status": "HUMAN_REVIEW_REQUIRED",
        "questions": {
            "victim": [{
                "id": "V-SH25-CONTACT",
                "text": "請以你能接受的程度說明，雙方有哪些身體接觸，以及接觸的身體部位。",
                "fact_target": "sexual_harassment_contact",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "core",
            }, {
                "id": "V-SH25-RESPONSE",
                "text": "事發時對方如何接近並開始接觸？你當時能做哪些反應，實際做了什麼？",
                "fact_target": "sexual_harassment_response",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "core",
            }, {
                "id": "V-SH25-CONTEXT",
                "text": "接觸前後，對方曾說什麼或做什麼？請說明你親自見聞的內容。",
                "fact_target": "sexual_harassment_context",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "distinguishing",
            }, {
                "id": "V-SH25-COMPLAINT",
                "text": "你是否已提出申訴或告訴？如有，何時向哪個機關或單位提出？",
                "fact_target": "sexual_harassment_complaint",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "core",
            }],
            "suspect": [{
                "id": "S-SH25-CONTACT",
                "text": "請依時間順序說明你與對方當時有哪些身體接觸，以及接觸的身體部位。",
                "fact_target": "sexual_harassment_contact",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "core",
            }, {
                "id": "S-SH25-RESPONSE",
                "text": "接觸開始前後，對方有哪些言語、動作或反應？你當時如何觀察到？",
                "fact_target": "sexual_harassment_response",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "core",
            }, {
                "id": "S-SH25-CONTEXT",
                "text": "接觸前後，你曾說什麼或做什麼？請依時間順序說明。",
                "fact_target": "sexual_harassment_context",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "distinguishing",
            }, {
                "id": "S-SH25-COMPLAINT",
                "text": "你所知對方是否已提出申訴或告訴？你如何得知提出的時間與受理單位？",
                "fact_target": "sexual_harassment_complaint",
                "ask_policy": "ASK_IF_UNCOVERED",
                "kind": "core",
            }],
        },
    },
    "fraud_339_general": _neutral_pack("fraud", "詐欺", "fraud-339-v1", [
        ("Q-F339-SEQUENCE", "請依時間順序說明雙方如何開始聯絡，以及其後發生的事情。", "contact_sequence", "core"),
        ("Q-F339-REPRESENTATION", "對方曾說明哪些具體內容？你當時如何理解這些內容？", "representation_content", "core"),
        ("Q-F339-DISPOSITION", "各筆款項或財物於何時、以何方式、交付給何人或哪一帳戶？", "property_dispositions", "core"),
        ("Q-F339-RELIANCE", "你決定交付款項或財物前，曾查證哪些事項？查證結果為何？", "reliance_and_verification", "distinguishing"),
        ("Q-F339-NONPERFORMANCE", "約定內容後來如何履行？你在何時發現與原先說明不一致？", "performance_and_discovery", "core"),
        ("Q-F339-EVIDENCE", "有哪些對話、交易、帳戶、商品或其他資料可以查證上述經過？", "fraud_evidence_sources", "reinforce"),
    ]),
    "injury_284_negligent": _neutral_pack("injury", "過失傷害", "injury-284-v1", [
        ("Q-I284-SEQUENCE", "請依時間順序說明相關作業、處置或操作的完整經過。", "negligent_event_sequence", "core"),
        ("Q-I284-DUTY", "當時應遵守哪些作業步驟、注意事項或專業規範？依據為何？", "duty_source", "core"),
        ("Q-I284-ACTION", "實際採取了哪些作業或處置？與原定步驟有何差異？", "actual_conduct", "core"),
        ("Q-I284-INJURY", "事件後出現哪些身體狀況？何時發現並接受何種診療？", "injury_and_treatment", "core"),
        ("Q-I284-CAUSATION", "醫療人員或鑑定資料如何說明行為與傷勢之間的關係？", "medical_causation_sources", "distinguishing"),
        ("Q-I284-EVIDENCE", "有哪些同意書、紀錄、影像、病歷、診斷或鑑定資料可供查證？", "medical_evidence_sources", "reinforce"),
    ]),
    "injury_277_general": _neutral_pack("injury", "傷害", "injury-277-v1", [
        ("Q-I277-SEQUENCE", "請依時間順序說明衝突發生前後的經過。", "injury_event_sequence", "core"),
        ("Q-I277-ACTION", "對方有哪些具體動作？接觸到哪些身體部位？", "injury_action_details", "core"),
        ("Q-I277-RESULT", "你出現哪些傷勢或不適？何時發現並接受何種診療？", "injury_result_details", "core"),
        ("Q-I277-EVIDENCE", "有哪些目擊者、影像、照片、診斷或其他資料可供查證？", "injury_evidence_sources", "reinforce"),
    ]),
    "public_danger_185_3_impaired_driving": _neutral_pack("public_danger", "公共危險", "public-danger-185-3-v1", [
        ("Q-PD1853-DRINK", "飲用或使用的物質、數量、時間及地點為何？", "substance_use_details", "core"),
        ("Q-PD1853-DRIVE", "其後於何時、何地駕駛何種動力交通工具？行駛經過為何？", "driving_details", "core"),
        ("Q-PD1853-TEST", "檢測於何時、何地進行？數值、單位及使用設備為何？", "impairment_test_details", "core"),
        ("Q-PD1853-INCIDENT", "駕駛期間是否發生碰撞或其他事故？請說明經過及結果。", "driving_incident", "core"),
        ("Q-PD1853-PRIOR", "是否有資料可確認駕駛人過去十年內的酒駕前案及其確定情形？", "prior_dui_record", "distinguishing"),
        ("Q-PD1853-PERSONS", "車內及事故現場有哪些人？各自看到或經歷什麼？", "scene_persons", "distinguishing"),
        ("Q-PD1853-EVIDENCE", "有哪些檢測、攔查、事故、影像或車籍資料可供查證？", "dui_evidence_sources", "reinforce"),
    ]),
    "damage_354_property": _neutral_pack("damage", "毀損", "damage-354-v1", [
        ("Q-D354-OBJECT", "受影響的物品為何？由誰所有或管理？原本狀態如何？", "damaged_property", "core"),
        ("Q-D354-ACTION", "物品如何受到破壞、損壞或改變？使用了哪些工具或方法？", "damage_action", "core"),
        ("Q-D354-RESULT", "物品受影響後還能否正常使用？修復方式及費用依據為何？", "damage_result", "core"),
        ("Q-D354-CONTEXT", "事件發生前後，相關人員曾說什麼或做什麼？", "damage_context", "distinguishing"),
        ("Q-D354-EVIDENCE", "有哪些照片、影像、估價、維修或其他資料可供查證？", "damage_evidence_sources", "reinforce"),
    ]),
    "defamation_309_public_insult": _neutral_pack("defamation", "公然侮辱", "defamation-309-v1", [
        ("Q-DF309-CONTEXT", "請依時間順序說明言語發生前後的完整經過。", "insult_context", "core"),
        ("Q-DF309-WORDS", "當時說了哪些原話？請說明你親自聽到的內容。", "insult_words", "core"),
        ("Q-DF309-AUDIENCE", "言語發生在何處？當時有哪些人可能聽見或看見？", "public_audience", "core"),
        ("Q-DF309-EFFECT", "這些言語對你的生活、人際關係或人格評價造成哪些具體影響？", "reputation_effect", "distinguishing"),
        ("Q-DF309-VALUE", "這些言語是否與公共事務、評論、文學藝術、學術或專業意見有關？請說明具體脈絡。", "speech_value_context", "distinguishing"),
        ("Q-DF309-FORCE", "言語發生前後是否伴隨推擠、毆打或其他強暴行為？如有，請說明。", "insult_force_details", "distinguishing"),
        ("Q-DF309-EVIDENCE", "有哪些錄音、錄影、訊息、在場人員或其他資料可供查證？", "defamation_evidence_sources", "reinforce"),
    ]),
    "obstruction_135_violence_threat": _neutral_pack("obstruction", "妨害公務", "obstruction-135-v1", [
        ("Q-O135-DUTY", "事發時相關人員正在執行何種職務？其身分及職務依據如何辨識？", "official_duty", "core"),
        ("Q-O135-NOTICE", "執行職務的人員曾如何表明身分、目的或要求？現場人員如何回應？", "official_notice", "core"),
        ("Q-O135-ACTION", "衝突中有哪些具體動作或言語？各發生在何時、何處？", "force_or_threat_details", "core"),
        ("Q-O135-EFFECT", "相關職務是否因此中斷、延誤或受到其他影響？具體情形為何？", "duty_effect", "distinguishing"),
        ("Q-O135-EVIDENCE", "有哪些執勤紀錄、影像、通聯或目擊者可供查證？", "obstruction_evidence_sources", "reinforce"),
    ]),
})


def has_route_question_pack(route_ids: list[str], offense_id: str) -> bool:
    return any(
        route_id in ROUTE_QUESTION_PACKS
        and ROUTE_QUESTION_PACKS[route_id].get("offense_id", "sexual") == offense_id
        for route_id in route_ids
    )


def route_questions_for(
    role: str,
    offense_id: str,
    route_ids: list[str],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    effective_role = "suspect" if role == "transfer" else role
    for route_id in route_ids:
        pack = ROUTE_QUESTION_PACKS.get(route_id)
        if pack is None or pack.get("offense_id", "sexual") != offense_id:
            continue
        for raw in pack["questions"].get(effective_role, []):
            item = deepcopy(raw)
            item.update({
                "role": role,
                "offense_id": offense_id,
                "offense_name": pack.get("offense_name", "妨害性自主"),
                "priority": 1 if item["kind"] == "core" else 3,
                "source": deepcopy(source),
                "status": "PENDING",
                "answer": "",
                "meta": {
                    "pack_id": route_id,
                    "pack_version": pack["version"],
                    "fact_target": item.pop("fact_target"),
                    "ask_policy": item.pop("ask_policy"),
                    "legal_targets": [route_id],
                    "trigger_condition": f"candidate:{route_id}:present",
                    "review_status": pack["review_status"],
                    "purpose": "補齊未覆蓋的中性事實" if item["kind"] != "reinforce" else "查證資料來源",
                    "question_phase": "evidence_followup" if item["kind"] == "reinforce" else "single_fact",
                },
            })
            questions.append(item)
    return questions

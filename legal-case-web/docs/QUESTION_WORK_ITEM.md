<!-- SUBMISSION_START -->

```yaml
document_status: DESIGN_DRAFT
runtime_enabled: false
review_status: CODEX_REVIEWED
submission_status: READY_FOR_HUMAN_REVIEW
handoff_status: WAITING_FOR_HUMAN_GATE
last_completed_section: O
resume_from_section: HUMAN_GATE
current_blockers: [HUMAN_GATE_NOT_ESTABLISHED, RUNTIME_SEMANTIC_DEDUPE_NOT_RUN, OUTPUT_PAGE_VALIDATION_NOT_RUN]
last_validation: READY_FOR_HUMAN_REVIEW_ITERATION_4
last_executor_summary: "ITERATION_4：完成靜態結構、角色、effects 與校準審查；所有新觀察代碼維持 NEED_REVIEW，尚未接線、未完成 runtime 語意去重及 PDF 八頁驗證。"
designer_role: TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT
author_role: TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT
question_ruleset_version: question-rules-v2-draft
ruleset_status: CALIBRATION_REQUIRED
failure_scope: NONE
task_type: BASELINE_RECOVERY
queue_no: 1
target_route_id: theft
target_child_route_id: theft_320_1_movable
target_interview_roles: [victim, suspect, transfer, witness_review_only]
iteration: 4
allowed_output: WORK_ITEM_FILE_ONLY
allowed_write_path: docs/QUESTION_WORK_ITEM.md
automatic_advance: false
next_route: NOT_AUTHORIZED
```

## A. 工作單 Metadata 與法源

```yaml
artifact_type: BASELINE_STANDARD_WORK_ITEM
iteration: 4
execution_mode: SINGLE_EXECUTOR
runtime_enabled: false
review_status: CODEX_REVIEWED
submission_status: READY_FOR_HUMAN_REVIEW
primary_route: theft
primary_child_route: theft_320_1_movable
parent_route_status: PARTIAL_SCOPE
child_count_in_crosswalk: 4
question_concept_count: 8
question_concept_budget: 8
case_selection_budget: 3-5 core concepts
evidence_followup_budget: max 2
output_page_budget: 8
human_gate: REQUIRED
```

本輪為 iteration 4 review revision。iteration 3 經 Codex 與獨立唯讀審查判定 `CHANGES_REQUESTED`；其 submission SHA-256 為 `3703D04379E4A3C9A57DD3832125CD5BEED5390C2E9BD02BB46A41353AEF747F`。本輪不得沿用該審核結論，修正後須以新的 submission SHA-256 重新送審。

## B. Route Scope

```yaml
route_scope:
  primary_route: theft_320_1_movable
  allowed_comparison_routes:
    - embezzlement_335_general
    - embezzlement_336_2_business
    - embezzlement_337_lost_property
    - robbery_325_snatching
    - robbery_328_robbery
  allowed_alternative_routes:
    - civil_possession_dispute
```

校準 allowlist 只限上方明列之 exact child route ID。`distinction_axis` 不得自行發現、建立或加入新罪章。不在 allowlist 之 route 必須輸出 `ROUTE_SCOPE_EXPANSION_REQUIRED` 並停止。`civil_possession_dispute` 是 alternative label，不是 offense，也不得混入犯罪候選或產生定罪效果。

## C. 中性事實表與區分軸

### 可中性抽取

| fact_key | 中性描述 | 本基準是否可直接判定 |
|---|---|---|
| event_sequence | 自由敘述的取得經過、物件、時地、人 | 只作背景，不產效果 |
| possession_before_taking | 行為人接觸前由何人實際持有、保管或控制 | 可，且為竊盜與侵占之必要區分 |
| consent_status | 行為前被害人是否曾明確同意交付、借用或保管，以及授權範圍 | 可，但三態，不得以單答排除竊盜 |
| prior_lawful_custody | 行為人於本次行為前是否已因交付保管、借用或業務關係而合法持有 | 可，指向侵占系 |
| control_status_at_discovery | 被發現或取得時，物品是否仍在原持有人支配管領範圍 | 可，指向竊盜或侵占離本人持有物之區分 |
| physical_forcing | 取得時是否拉扯、抓奪或施加突然力量 | 可，指向搶奪 |
| violence_threat | 取得時出現哪些言語、動作、藥劑或其他手段 | 可，僅作強盜候選之手段事實 |
| resistance_capability | 上述方法對被害人行動、判斷及反應造成何種具體影響 | 可由被害人主述，其他角色只得說明親見反應 |
| post_acquisition_conduct | 取得後之聯絡、返還、保管、使用、移轉、出售、隱匿或其他處理 | 可作不法所有意圖之外部事實，不直接判定主觀意圖 |

### 不可直接判定，一律保留

- `unlawful_possession_intent`：不法所有之意圖，須由取得理由、返還表示、處分行為與有利不利資料供人工評價。
- `return_agreement_status`：由既有聚焦題取得返還約定；實際返還與處分另由 C09 取得。
- `aggravation_presence`：第321條六款加重事實不在本 route scope；應由 `aggravated_theft_321` 自身工作單另行校準。
- `completed_or_attempted`：既遂與未遂，本基準不直接判定。
- `civil_possession_conclusion`：民事占有爭議成立與否，只列為替代方向。

### 區分軸

| distinction_axis | fact_target | candidate_a | candidate_b | observable_basis | unknown_effect |
|---|---|---|---|---|---|
| 取得前是否因交付保管而合法持有 | prior_lawful_custody | theft_320_1_movable | embezzlement_335_general | 交付、保管、借用或業務關係的具體行為與言詞 | NEED_REVIEW |
| 取得時是否仍在原持有人支配管領範圍 | control_status_at_discovery | theft_320_1_movable | embezzlement_337_lost_property | 發現位置、物品狀態、周遭環境與各角色親身認知來源 | NEED_REVIEW |
| 取得時是否有拉扯或突然力量 | physical_forcing | theft_320_1_movable | robbery_325_snatching | 拉扯、抓奪的具體動作與被害人陳述 | NEED_REVIEW |
| 取得時是否以強暴脅迫使人不能抗拒 | violence_threat | theft_320_1_movable | robbery_328_robbery | 言語、動作、傷勢與被害人陳述 | NEED_REVIEW |
| 行為前是否有被害人同意及授權範圍 | consent_status | theft_320_1_movable | embezzlement_335_general | 被害人明確允諾之內容、範圍與對象 | NEED_REVIEW |
| 被害人是否實際上不能抗拒 | resistance_capability | theft_320_1_movable | robbery_328_robbery | 被害人自身的身體與情境能力 | NEED_REVIEW |
| 取得後如何聯絡、返還、使用或處分 | post_acquisition_conduct | theft_320_1_movable | embezzlement_335_general | 實際聯絡、返還、保管、移轉、出售、隱匿等外部行為 | NEED_REVIEW |

`violence_threat` 與 `resistance_capability` 拆成兩個單一事實，避免一題同時回答手段與程度。任一軸無法確認時一律維持 `NEED_REVIEW`，不得靜默排除。

## D. 正確法條

| route_id | 條號 | 條文要旨 |
|---|---|---|
| theft_320_1_movable | 刑法第320條第1項 | 意圖為自己或第三人不法之所有而竊取他人動產，處五年以下有期徒刑、拘役或五十萬元以下罰金 |
| embezzlement_335_general | 刑法第335條第1項 | 普通侵占：意圖為自己或第三人不法所有而侵占自己持有之他人之物 |
| embezzlement_336_2_business | 刑法第336條第2項 | 對於業務上所持有之物，犯第335條第1項侵占罪 |
| embezzlement_337_lost_property | 刑法第337條 | 意圖為自己或第三人不法所有而侵占遺失物、漂流物或其他離本人持有之物 |
| robbery_325_snatching | 刑法第325條第1項 | 意圖為自己或第三人不法所有而搶奪他人動產 |
| robbery_328_robbery | 刑法第328條第1項 | 以強暴、脅迫、藥劑、催眠術或他法，至使不能抗拒，而取他人之物或使其交付 |

第322條已刪除，不得使用；任何 parent／alias route ID 不得替代上表之 exact child route ID。

## E. 官方條文版本狀態

```yaml
official_source: 中華民國刑法
official_url: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=C0000001
law_retrieved_at: 2026-10-14
law_status_at_retrieval: AVAILABLE
law_version_effective_at_offense_time: UNKNOWN
dataset_version: UNCHANGED_RUNTIME
behavior_in_time_status: MANUAL_REVIEW_REQUIRED
```

行為時法須由人工核對條文版本與生效日期。本檔條號僅為結構參考，不構成行為時法證據，也不構成法律結論。

## F. Parent／Child Route 與 Element 表

| parent_route | child_route | route_kind | elements |
|---|---|---|---|
| theft | theft_320_1_movable | offense | 動產客體、原持有狀態、未經同意取得、破壞原持有、不法所有之意圖、既遂或未遂 |
| theft | theft_320_2_real_estate | offense | 不動產客體、排除權利人建立占有支配 |
| theft | theft_323_energy | definition | 電能熱能等能量之準動產 |
| theft | theft_324_relative | procedure | 親屬間竊盜減免與告訴條件 |

本工作單只處理 `theft_320_1_movable`。其餘 child route 未授權，`automatic_advance: false`。

## G. Question Concepts（8 個，單一 route 生命週期內保持穩定）

| id | phase | fact_target | distinction_axis | 角色 | answer_mode | legal_targets |
|---|---|---|---|---|---|---|
| THF3201MOV-C01 | narrative | event_sequence | neutral_event_sequence | victim, suspect, transfer, witness_review_only | narrative_only | theft_320_1_movable |
| THF3201MOV-C02 | single_fact | possession_before_taking | lawful_possession_pre_taking | victim, suspect, transfer, witness_review_only | enum | theft_320_1_movable, embezzlement_335_general, embezzlement_337_lost_property |
| THF3201MOV-C03 | single_fact | consent_status | authorization_scope | victim, suspect, transfer, witness_review_only | enum | theft_320_1_movable, embezzlement_335_general |
| THF3201MOV-C05 | single_fact | control_status_at_discovery | already_lost_property | victim, suspect, transfer, witness_review_only | enum | theft_320_1_movable, embezzlement_337_lost_property |
| THF3201MOV-C06 | single_fact | physical_forcing | sudden_force_taking | victim, suspect, transfer, witness_review_only | enum | theft_320_1_movable, robbery_325_snatching |
| THF3201MOV-C07 | single_fact | violence_threat | force_or_threat_means | victim, suspect, transfer, witness_review_only | enum | theft_320_1_movable, robbery_328_robbery |
| THF3201MOV-C08 | single_fact | resistance_capability | cannot_resist_outcome | victim, suspect, transfer, witness_review_only | enum | theft_320_1_movable, robbery_328_robbery |
| THF3201MOV-C09 | single_fact | post_acquisition_conduct | owner_like_post_acquisition_conduct | victim, suspect, transfer, witness_review_only | enum | theft_320_1_movable, embezzlement_335_general, embezzlement_337_lost_property |

原 C04 與 runtime `prior_lawful_possession` 語意重複，iteration 4 以 `REUSE_OR_REPLACE_DO_NOT_COEMIT` 退役，不再列入 active concept；空出的 concept 預算改由 C09 取得實際返還與處分外部行為。`violence_threat`（手段）與 `resistance_capability`（結果）仍分兩題，不得合題。C05、C08 對非 victim 角色只問親身行為或親見反應，不得代答被害人內心或作法律評價。

<!-- STANDARD_SET_START -->
```json
[
  {
    "question_concept_id": "THF3201MOV-C01",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "narrative",
    "parent_question_id": null,
    "trigger_condition": "candidate:theft_320_1_movable:present",
    "fact_target": "event_sequence",
    "distinction_axis": "neutral_event_sequence",
    "source_basis": "刑法第320條第1項：先取得中性事件順序，不預設罪名。",
    "rationale": "先敘述、再釐清；後續只針對仍為 UNKNOWN 的單一事實問。",
    "answer_mode": "narrative_only",
    "answer_codes": [],
    "legal_targets": ["theft_320_1_movable"],
    "legal_target_details": [],
    "answer_map": null,
    "existing_question_refs": [],
    "dedupe_action": "NEW_GAP",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請就你親自知曉的情形，依時間順序說明與本案財物取走相關的經過。可先整體陳述，不必擔心法律定性。",
      "suspect": "請就你親自知曉或參與的情形，依時間順序說明與本案財物取走相關的經過。可先整體陳述，不必擔心法律定性。",
      "transfer": "請依案卷或查獲情形，依時間順序說明與本案財物取走相關的經過。",
      "witness_review_only": "請就你親自看到或聽到的情形，依時間順序說明與本案財物取走相關的經過；不是親自見聞的部分請分開說明。"
    }
  },
  {
    "question_concept_id": "THF3201MOV-C02",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "single_fact",
    "parent_question_id": "THF3201MOV-C01",
    "trigger_condition": "candidate:theft_320_1_movable:present AND after:THF3201MOV-C01 AND fact:possession_before_taking:UNKNOWN",
    "fact_target": "possession_before_taking",
    "distinction_axis": "lawful_possession_pre_taking",
    "source_basis": "刑法第320條第1項：他人之動產，須確認取得前之實際持有狀態。",
    "rationale": "區分動產竊盜與侵占、遺失物侵占之必要事實。",
    "answer_mode": "enum",
    "answer_codes": ["OTHER_PERSON_CONTROL", "SUSPECT_PREEXISTING_CONTROL", "NO_IDENTIFIED_CONTROL"],
    "legal_targets": ["theft_320_1_movable", "embezzlement_335_general", "embezzlement_337_lost_property"],
    "legal_target_details": [
      {
        "route_id": "theft_320_1_movable",
        "effects": {"OTHER_PERSON_CONTROL": "ACTIVE", "SUSPECT_PREEXISTING_CONTROL": "LOWERED", "NO_IDENTIFIED_CONTROL": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "embezzlement_335_general",
        "effects": {"OTHER_PERSON_CONTROL": "LOWERED", "SUSPECT_PREEXISTING_CONTROL": "NEED_REVIEW", "NO_IDENTIFIED_CONTROL": "LOWERED", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "embezzlement_337_lost_property",
        "effects": {"OTHER_PERSON_CONTROL": "LOWERED", "SUSPECT_PREEXISTING_CONTROL": "LOWERED", "NO_IDENTIFIED_CONTROL": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      }
    ],
    "answer_map": {"OTHER_PERSON_CONTROL": "OTHER_PERSON_CONTROL", "SUSPECT_PREEXISTING_CONTROL": "SUSPECT_PREEXISTING_CONTROL", "NO_IDENTIFIED_CONTROL": "NO_IDENTIFIED_CONTROL", "UNKNOWN": "UNKNOWN"},
    "existing_question_refs": [
      {"source": "app/questions.py", "fact_key": "original_possession", "role_question_key": "original_possession"}
    ],
    "dedupe_action": "REUSE_OR_REPLACE_DO_NOT_COEMIT",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請說明物品被移動前由何人實際持有、保管或控制，以及你如何知道。",
      "suspect": "請說明你接觸該物品前由何人實際持有、保管或控制，以及你當時如何知道。",
      "transfer": "請依案卷說明該物品在行為人接觸前由何人實際持有、保管或控制，並指出記載來源。",
      "witness_review_only": "你親自看到物品被移動前，它由何人實際持有、保管或控制？不是親自見聞的部分請分開說明。"
    }
  },
  {
    "question_concept_id": "THF3201MOV-C03",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "single_fact",
    "parent_question_id": "THF3201MOV-C01",
    "trigger_condition": "candidate:theft_320_1_movable:present AND after:THF3201MOV-C01 AND fact:authorization_scope_status:UNKNOWN",
    "fact_target": "authorization_scope_status",
    "distinction_axis": "authorization_scope",
    "source_basis": "刑法第320條第1項：未經同意取得為必要事實；同意須確認授權範圍。",
    "rationale": "同意改為授權範圍三態，禁止以單一肯定答案直接排除竊盜或認定民事爭議。",
    "answer_mode": "enum",
    "answer_codes": ["WITHIN_SCOPE", "BEYOND_SCOPE", "NO_CONSENT"],
    "legal_targets": ["theft_320_1_movable", "embezzlement_335_general"],
    "legal_target_details": [
      {
        "route_id": "theft_320_1_movable",
        "effects": {
          "WITHIN_SCOPE": "LOWERED",
          "BEYOND_SCOPE": "NEED_REVIEW",
          "NO_CONSENT": "NEED_REVIEW",
          "UNKNOWN": "NEED_REVIEW",
          "CONFLICT": "NEED_REVIEW"
        },
        "exclusion_safe": false
      },
      {
        "route_id": "embezzlement_335_general",
        "effects": {
          "WITHIN_SCOPE": "NEED_REVIEW",
          "BEYOND_SCOPE": "NEED_REVIEW",
          "NO_CONSENT": "NEED_REVIEW",
          "UNKNOWN": "NEED_REVIEW",
          "CONFLICT": "NEED_REVIEW"
        },
        "exclusion_safe": false
      }
    ],
    "alternative_target_details": [
      {
        "route_id": "civil_possession_dispute",
        "effects": {
          "WITHIN_SCOPE": "NEED_REVIEW",
          "BEYOND_SCOPE": "NEED_REVIEW",
          "NO_CONSENT": "NEED_REVIEW",
          "UNKNOWN": "NEED_REVIEW",
          "CONFLICT": "NEED_REVIEW"
        },
        "exclusion_safe": false,
        "candidate_eligible": false,
        "routing_eligible": false,
        "question_generation_eligible": false,
        "template_activation_eligible": false,
        "effect_executable": false,
        "human_review_required": true
      }
    ],
    "answer_map": {"WITHIN_SCOPE": "WITHIN_SCOPE", "BEYOND_SCOPE": "BEYOND_SCOPE", "NO_CONSENT": "NO_CONSENT", "UNKNOWN": "UNKNOWN"},
    "existing_question_refs": [
      {"source": "app/questions.py", "fact_key": "consent", "role_question_key": "consent"}
    ],
    "dedupe_action": "REPLACE_COMPOUND_QUESTION_DO_NOT_COEMIT",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請說明你與對方曾就拿取、使用或保管該物品談過哪些內容；如有允許，範圍與條件為何？",
      "suspect": "請說明你與物品持有人曾就拿取、使用或保管談過哪些內容；你如何理解允許的範圍與條件？",
      "transfer": "請依案卷說明雙方就拿取、使用或保管曾表示哪些內容，並指出允許範圍與記載來源。",
      "witness_review_only": "請說明你親自聽到雙方就拿取、使用或保管談過哪些內容；不是親自見聞的部分請分開說明。"
    }
  },
  {
    "question_concept_id": "THF3201MOV-C05",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "single_fact",
    "parent_question_id": "THF3201MOV-C01",
    "trigger_condition": "candidate:theft_320_1_movable:present AND after:THF3201MOV-C01 AND fact:control_status_at_discovery:UNKNOWN",
    "fact_target": "control_status_at_discovery",
    "distinction_axis": "already_lost_property",
    "source_basis": "刑法第337條：須確認取得時物品是否仍在原持有人支配管領範圍。",
    "rationale": "各角色只陳述拾得位置、物品狀態、周遭控制與親身認知來源；是否屬離本人持有之物由 Human Gate 評價。",
    "answer_mode": "enum",
    "answer_codes": ["WITHIN_HOLDER_CONTROL", "OUTSIDE_HOLDER_CONTROL"],
    "legal_targets": ["theft_320_1_movable", "embezzlement_337_lost_property"],
    "legal_target_details": [
      {
        "route_id": "theft_320_1_movable",
        "effects": {"WITHIN_HOLDER_CONTROL": "ACTIVE", "OUTSIDE_HOLDER_CONTROL": "LOWERED", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "embezzlement_337_lost_property",
        "effects": {"WITHIN_HOLDER_CONTROL": "LOWERED", "OUTSIDE_HOLDER_CONTROL": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      }
    ],
    "answer_map": {"WITHIN_HOLDER_CONTROL": "WITHIN_HOLDER_CONTROL", "OUTSIDE_HOLDER_CONTROL": "OUTSIDE_HOLDER_CONTROL", "UNKNOWN": "UNKNOWN"},
    "existing_question_refs": [],
    "dedupe_action": "NEW_GAP",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請說明你最後掌握物品的位置、保管方式，以及發現物品不在時的周遭情形。",
      "suspect": "請說明你在何處、以何種情況接觸該物品，以及當時觀察到哪些可能辨識持有人或控制範圍的情形。",
      "transfer": "請依案卷說明物品被發現或取得的位置、外觀、周遭情形及相關記載來源。",
      "witness_review_only": "請說明你親自看到物品被發現或取得時的位置、外觀及周遭情形；不是親自見聞的部分請分開說明。"
    }
  },
  {
    "question_concept_id": "THF3201MOV-C06",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "single_fact",
    "parent_question_id": "THF3201MOV-C01",
    "trigger_condition": "candidate:theft_320_1_movable:present AND after:THF3201MOV-C01 AND fact:physical_forcing:UNKNOWN",
    "fact_target": "physical_forcing",
    "distinction_axis": "sudden_force_taking",
    "source_basis": "刑法第325條第1項：搶奪他人動產；具體取物動作與力量程度須另由事實判斷。",
    "rationale": "先開放詢問取物動作，再由承辦人依明確陳述編碼；不得以突然力量替代第321條六款事由。",
    "answer_mode": "enum",
    "answer_codes": ["OBJECT_MOVEMENT_ONLY_DESCRIBED", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED"],
    "legal_targets": ["theft_320_1_movable", "robbery_325_snatching"],
    "legal_target_details": [
      {
        "route_id": "theft_320_1_movable",
        "effects": {"OBJECT_MOVEMENT_ONLY_DESCRIBED": "NEED_REVIEW", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "robbery_325_snatching",
        "effects": {"OBJECT_MOVEMENT_ONLY_DESCRIBED": "NEED_REVIEW", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      }
    ],
    "answer_map": {"OBJECT_MOVEMENT_ONLY_DESCRIBED": "OBJECT_MOVEMENT_ONLY_DESCRIBED", "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED": "ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED", "UNKNOWN": "UNKNOWN"},
    "coding_rule": "原始敘述僅記載拿取、移動或帶走物品本身，且沒有記載對人、隨身持有物或其他物體的額外接觸或力量時，編為 OBJECT_MOVEMENT_ONLY_DESCRIBED；有描述拉扯、抓奪、碰撞或其他額外接觸或力量時，編為 ADDITIONAL_CONTACT_OR_FORCE_DESCRIBED。未提及、不記得、未詢問或來源衝突一律為 UNKNOWN；任一代碼均不得單獨降低或成立第325條方向。",
    "existing_question_refs": [],
    "dedupe_action": "NEW_GAP",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請說明物品被拿取、移動或帶走時，對方做了哪些動作，以及你當時看到或感受到哪些接觸或力量。",
      "suspect": "請說明物品被拿取、移動或帶走時，你做了哪些動作，以及與在場人或物品有何接觸。",
      "transfer": "請依案卷說明物品被拿取、移動或帶走時的具體動作、接觸或力量及記載來源。",
      "witness_review_only": "請說明你親自看到物品被拿取、移動或帶走時有哪些動作、接觸或力量；不是親自見聞的部分請分開說明。"
    }
  },
  {
    "question_concept_id": "THF3201MOV-C07",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "single_fact",
    "parent_question_id": "THF3201MOV-C01",
    "trigger_condition": "candidate:theft_320_1_movable:present AND after:THF3201MOV-C01 AND fact:violence_threat:UNKNOWN",
    "fact_target": "violence_threat",
    "distinction_axis": "force_or_threat_means",
    "source_basis": "刑法第328條第1項：強暴、脅迫、藥劑、催眠術或他法，至使不能抗拒而取物或使其交付。",
    "rationale": "只取得言語、動作或其他手段，不在本題判斷不能抗拒；手段與取財之時間及目的關係仍須人工評價。",
    "answer_mode": "enum",
    "answer_codes": ["NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED"],
    "legal_targets": ["theft_320_1_movable", "robbery_328_robbery"],
    "legal_target_details": [
      {
        "route_id": "theft_320_1_movable",
        "effects": {"NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "NEED_REVIEW", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "robbery_328_robbery",
        "effects": {"NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "NEED_REVIEW", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      }
    ],
    "answer_map": {"NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED", "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED": "ADDITIONAL_WORDS_OR_MEANS_DESCRIBED", "UNKNOWN": "UNKNOWN"},
    "coding_rule": "原始敘述明確表示除拿取、移動或交付物品本身外，沒有其他言語、對人動作、使用物品或方法，且來源無衝突時，編為 NO_ADDITIONAL_WORDS_OR_MEANS_DESCRIBED；有具體描述時編為 ADDITIONAL_WORDS_OR_MEANS_DESCRIBED。未提及、不記得或未詢問一律為 UNKNOWN；任一代碼均不得單獨降低或成立第328條方向。",
    "existing_question_refs": [
      {"source": "app/questions.py", "fact_key": "force_or_threat", "role_question_key": "force_or_threat"}
    ],
    "dedupe_action": "REPLACE_COMPOUND_QUESTION_DO_NOT_COEMIT",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請說明對方在物品被移動或交付前後說了哪些話、做了哪些動作，或使用了哪些物品與方法。",
      "suspect": "請說明物品被移動或交付前後，你說了哪些話、做了哪些動作，或使用了哪些物品與方法。",
      "transfer": "請依案卷說明物品被移動或交付前後的言語、動作、使用物品與記載來源。",
      "witness_review_only": "請說明你親自聽到哪些話、看到哪些動作或使用物品；不是親自見聞的部分請分開說明。"
    }
  },
  {
    "question_concept_id": "THF3201MOV-C08",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "single_fact",
    "parent_question_id": "THF3201MOV-C01",
    "trigger_condition": "candidate:theft_320_1_movable:present AND after:THF3201MOV-C01 AND fact:resistance_capability:UNKNOWN",
    "fact_target": "resistance_capability",
    "distinction_axis": "cannot_resist_outcome",
    "source_basis": "刑法第328條：使人不能抗拒為結果事實。",
    "rationale": "被害人主述自身反應；涉嫌人、transfer 與 witness 只陳述親見行動及環境，不得代答被害人內心或直接作成不能抗拒之法律評價。",
    "answer_mode": "enum",
    "answer_codes": ["RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED", "RESPONSE_LIMIT_DESCRIBED"],
    "legal_targets": ["theft_320_1_movable", "robbery_328_robbery"],
    "legal_target_details": [
      {
        "route_id": "theft_320_1_movable",
        "effects": {"RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED": "NEED_REVIEW", "RESPONSE_LIMIT_DESCRIBED": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "robbery_328_robbery",
        "effects": {"RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED": "NEED_REVIEW", "RESPONSE_LIMIT_DESCRIBED": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      }
    ],
    "answer_map": {"RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED": "RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED", "RESPONSE_LIMIT_DESCRIBED": "RESPONSE_LIMIT_DESCRIBED", "UNKNOWN": "UNKNOWN"},
    "coding_rule": "只有被害人明確陳述其行動、判斷及求助能力均未受限制，且其他來源無衝突時，才能編為 RESPONSE_ABILITY_EXPLICITLY_UNRESTRICTED；涉嫌人、transfer 或 witness 的觀察不得單獨產生此代碼。有具體描述行動、判斷或求助受限時編為 RESPONSE_LIMIT_DESCRIBED。未提及、不記得、未詢問或來源衝突一律為 UNKNOWN；任一代碼均不等於法律上不能抗拒或其反面。",
    "existing_question_refs": [],
    "dedupe_action": "NEW_GAP",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請說明對方上述言語或動作發生時，你能做哪些反應、實際做了什麼，以及哪些情況影響你的行動或判斷。",
      "suspect": "請說明當時對方有哪些言語、動作或反應，以及你如何觀察到。",
      "transfer": "請依案卷說明被害人當時的言語、動作、身體狀態、現場條件及各項記載來源。",
      "witness_review_only": "請說明你親自看到或聽到被害人有哪些反應及現場情況；不是親自見聞的部分請分開說明。"
    }
  },
  {
    "question_concept_id": "THF3201MOV-C09",
    "designer_role": "TW_CRIMINAL_INTERVIEW_QUESTION_DESIGN_EXPERT",
    "target_interview_roles": ["victim", "suspect", "transfer", "witness_review_only"],
    "question_phase": "single_fact",
    "parent_question_id": "THF3201MOV-C01",
    "trigger_condition": "candidate:theft_320_1_movable:present AND after:THF3201MOV-C01 AND fact:post_acquisition_conduct:UNKNOWN",
    "fact_target": "post_acquisition_conduct",
    "distinction_axis": "owner_like_post_acquisition_conduct",
    "source_basis": "刑法第320條、第335條及第337條：不法所有意圖須綜合取得理由與取得後外部行為供人工評價；C09 只取得後者。",
    "rationale": "記錄取得後事件序列、時間、是否自發、是否在查獲後及物品去向，不直接詢問或認定不法所有意圖；取得理由未由 C01 或其他題目取得時維持 UNKNOWN。",
    "answer_mode": "enum",
    "answer_codes": ["RETURNED", "CONTACTED_ONLY", "RETAINED", "TRANSFERRED_OR_SOLD", "CONCEALED", "MIXED_SEQUENCE"],
    "legal_targets": ["theft_320_1_movable", "embezzlement_335_general", "embezzlement_337_lost_property"],
    "legal_target_details": [
      {
        "route_id": "theft_320_1_movable",
        "effects": {"RETURNED": "NEED_REVIEW", "CONTACTED_ONLY": "NEED_REVIEW", "RETAINED": "NEED_REVIEW", "TRANSFERRED_OR_SOLD": "NEED_REVIEW", "CONCEALED": "NEED_REVIEW", "MIXED_SEQUENCE": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "embezzlement_335_general",
        "effects": {"RETURNED": "NEED_REVIEW", "CONTACTED_ONLY": "NEED_REVIEW", "RETAINED": "NEED_REVIEW", "TRANSFERRED_OR_SOLD": "NEED_REVIEW", "CONCEALED": "NEED_REVIEW", "MIXED_SEQUENCE": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      },
      {
        "route_id": "embezzlement_337_lost_property",
        "effects": {"RETURNED": "NEED_REVIEW", "CONTACTED_ONLY": "NEED_REVIEW", "RETAINED": "NEED_REVIEW", "TRANSFERRED_OR_SOLD": "NEED_REVIEW", "CONCEALED": "NEED_REVIEW", "MIXED_SEQUENCE": "NEED_REVIEW", "UNKNOWN": "NEED_REVIEW", "CONFLICT": "NEED_REVIEW"},
        "exclusion_safe": false
      }
    ],
    "answer_map": {"RETURNED": "RETURNED", "CONTACTED_ONLY": "CONTACTED_ONLY", "RETAINED": "RETAINED", "TRANSFERRED_OR_SOLD": "TRANSFERRED_OR_SOLD", "CONCEALED": "CONCEALED", "MIXED_SEQUENCE": "MIXED_SEQUENCE", "UNKNOWN": "UNKNOWN"},
    "coding_rule": "同一物品在取得後出現兩種以上事件時編為 MIXED_SEQUENCE；系統或承辦人仍須完整保存每一事件的原始敘述、發生時間、先後順序、資訊來源，以及事件在報案或查獲前後。只有單一事件且時序明確時，才使用其單一代碼；未提及、不記得、時序不明或來源衝突一律為 UNKNOWN。",
    "existing_question_refs": [
      {"source": "app/questions.py", "fact_key": "return_agreement", "runtime_ids": ["V-FACT-05-return_agreement", "S-FACT-05-return_agreement", "T-FACT-05-return_agreement"]},
      {"source": "app/questions.py", "fact_key": "stated_use_or_return_plan", "runtime_ids": ["V-FACT-06-stated_use_or_return_plan", "S-FACT-06-stated_use_or_return_plan", "T-FACT-06-stated_use_or_return_plan"]}
    ],
    "dedupe_action": "NEW_GAP",
    "exclusion_safe": false,
    "role_variants": {
      "victim": "請依時間順序說明物品被取得後，你所知道的聯絡、返還、保管、使用、移轉、出售、隱匿或其他處理情形，並說明如何得知及是否發生在報案或查獲後。",
      "suspect": "請依時間順序說明你取得物品後如何聯絡持有人，以及何時、因何原因返還、保管、使用、移轉、出售、隱匿或以其他方式處理；請區分報案或查獲前後。",
      "transfer": "請依案卷及時間順序說明物品取得後的聯絡、返還、保管、使用、移轉、出售、隱匿或其他處理情形，並指出記載來源及報案或查獲前後。",
      "witness_review_only": "請依時間順序說明你親自看到或聽到物品取得後有哪些聯絡、返還、保管、使用、移轉、出售、隱匿或其他處理；不是親自見聞的部分請分開說明。"
    }
  }
]
```
<!-- STANDARD_SET_END -->

## H. 角色邊界與程序題

victim 問本人同意、認知、持有變化、受影響結果及證據來源，不問對方未表達之內心意圖。suspect 問取得依據、本人認知、處分返還及有利不利資料，不問「你為什麼偷」。transfer 問與 suspect 相同的實體事實，另有移送來源、既有筆錄、權利告知與扣押程序。witness_review_only 只問親自見聞、觀察條件與親自製作或取得的資料，不代答他人同意、意圖或抗拒能力。

Transfer 的移送來源、既有筆錄及刑事訴訟法第95條權利告知獨立為程序題，不作為犯罪構成要件，並一併接受八頁輸出預算檢查。程序題不得因概念預算被刪除；若固定題加必要新題超過八頁，輸出 `BUDGET_EXCEEDED`，不得靜默裁切。

witness_review_only 的問句 variant 一律維持 `runtime_enabled: false`，不接入 runtime 邏輯；其存在是為了定義該事實是否可由第三方見聞證明。

## I. Concept → Instance Materialization

每個適用角色各產生一個 question instance，形成穩定 ID `<question_concept_id>-<role_code>`：victim → V、suspect → S、transfer → T、witness_review_only → W。複製 concept 共用欄位，角色 key 寫入單數 `target_interview_role` 對應欄位 `target_interview_role`，對應文字寫入 `text`。沒有該角色 variant 時不得生成題目。

- iteration 4 的八個 active concepts（C01、C02、C03、C05、C06、C07、C08、C09）各產生 V、S、T、W 四版本，W 版本 `runtime_enabled: false`。
- C05、C08 的 S／T／W 版本只能取得角色親身行為、親見反應或案卷記載來源，不得將其他角色的觀察直接編碼成被害人內心狀態。
- 全 route 生命週期內 `question_concept_id` 保持穩定；wording 或 mapping 調整不得改 ID，只有 `fact_target` 本質改變才 bump 版本。

## J. Question Phase Linkage 與 Aggregation 契約

每個 `single_fact` 皆連回同一題組之 narrative parent `THF3201MOV-C01`，並帶有可機械判讀的 `trigger_condition`。聚合依序：先依 provenance 合併同一 `fact_target`，跨角色衝突時該 fact 為 `CONFLICT`；route 必要前提仍為 `UNKNOWN`、`CONFLICT` 或未詢問時聚合固定 `NEED_REVIEW`；前提完整且無衝突時只有 `LOWERED` 則 `LOWERED`，只有 `ACTIVE` 則 `ACTIVE`，同時出現 `ACTIVE` 與 `LOWERED` 則 `NEED_REVIEW`；`narrative_only` 與無 mapping 自由文字不直接改變 route；每次作答後從完整 facts 重算。任何 route 不得自動輸出 `EXCLUDED`。

侵占系 route 即使因「先合法持有」成為 `ACTIVE` 候選，若侵占行為、返還義務、拒不返還、隱匿、處分或其他外部事實仍為 `UNKNOWN`，聚合結果維持 `NEED_REVIEW`。

## K. Dedupe 與去重

exact dedupe：C02 取代 `app/questions.py` 的 `original_possession` 二元題，改以三態描述取得前的控制狀態，`dedupe_action: REUSE_OR_REPLACE_DO_NOT_COEMIT`，不得同場併送。

retired reuse：iteration 3 的 C04 不再是 active concept。先合法持有由 runtime 已可到達之 `V/S/T-FACT-03-prior_lawful_possession` 取得；materialization 路徑為 `app.rules.build_questions → app.questions.build_property_taking_questions`。若該題在實際個案未產生或遭裁切，侵占相關前提維持 `UNKNOWN`，不得以文件宣稱補足。

semantic dedupe：C03 取代既有 `consent` 二元問法（改為授權範圍三態），C07 取代既有 `force_or_threat` 複合問法（拆為手段題與結果題），兩者 `dedupe_action: REPLACE_COMPOUND_QUESTION_DO_NOT_COEMIT`。

existing adjacency：`V/S/T-FACT-05-return_agreement` 只取得返還約定，`V/S/T-FACT-06-stated_use_or_return_plan` 只取得當時表示的用途或計畫；兩者在 theft＋embezzlement dry run 均可到達且未被裁切，但都不能代替實際後續處分。

新增缺口：C01、C05、C06、C08、C09 為 `NEW_GAP`。C09 專問實際聯絡、返還與後續處理，與上述「約定／表示計畫」不屬相同事實，不得以文字相近而去除。

## L. 未採用問句及理由

| 未採用問句 | 理由 |
|---|---|
| 有無犯意、是否構成某罪 | 直接詢問法律評價，違反中性事實原則 |
| 是否有不法所有之意圖 | 主觀要件須由取得理由、返還表示與處分行為供人工評價 |
| 直接問是否有返還或侵占犯意 | 改問返還約定、聯絡與實際處理之外部事實，由 Human Gate 評價 |
| 是否侵入、毀越、持兇器、結夥 | 第321條六款事由應由 `aggravated_theft_321` 自身工作單校準，不混入本 route scope |
| 既遂或未遂 | 屬另一事實軸，本基準未列候選 |
| 一次性問同意與返還與暴力 | 複合題，違反單一事實原則 |
| 一題問被害人內心意圖 | witness 與 suspect 不得代答他人主觀狀態 |

## M. 題數與輸出預算

```yaml
new_concepts: 8
concept_budget: 8
case_core_selection: 3-5
evidence_followup_max: 2
single_case_total_max: 8
output_page_budget: 8
company_question_protection: PRESERVED
xlsm_question_protection: PRESERVED
common_question_protection: PRESERVED
budget_exceeded_policy: OUTPUT_BUDGET_EXCEEDED
```

公司逐字題、common 題及 XLSM 題不因概念預算而刪除；若固定題加必要新題超過八頁，輸出 `BUDGET_EXCEEDED`。

本輪只完成 theft＋embezzlement、victim／suspect／transfer 的 `build_questions` dry run；返還約定與用途計畫題均產生且 `pruned_questions` 為空。C09 尚未接入 runtime，完整個案 materialization、語意去重及 DOCX／PDF 八頁渲染一律維持 `NOT_RUN`。

## N. 最低校準案例

| 案例 | 期望輸出 |
|---|---|
| 單純「把手機拿走」 | 只輸出已知中性事實、`UNKNOWN`、候選路由與 `NEED_REVIEW`，不定罪 |
| 先交付保管後拒絕返還 | 先合法持有與後續處理均只形成侵占審查方向；主觀意圖及其他前提仍由 Human Gate 評價 |
| 明確同意暫時使用 | 同意在範圍內，竊盜 `LOWERED`，不得直接排除竊盜或認定民事爭議 |
| 拉扯取得 | 搶奪候選維持 `NEED_REVIEW`，須核對具體取物動作與力量程度 |
| 暴力或威脅取得 | 強盜候選維持 `NEED_REVIEW`，手段、抗拒影響及與取財之密接關係分開核對 |
| 拾得疑似離本人持有之物後處分 | 第337條審查方向提高，但物品狀態、所有權、取得後行為及主觀意圖仍由 Human Gate 評價 |
| 返還約定說法不同 | 跨角色 `CONFLICT`，聚合 `NEED_REVIEW` |
| 跨角色回答衝突 | 該 fact 為 `CONFLICT`，聚合 `NEED_REVIEW` |
| 不知道或不清楚 | `UNKNOWN`，聚合 `NEED_REVIEW` |

最低校準輸出只限已知中性事實、`UNKNOWN`、候選路由、啟用問句、保守狀態變化及 Human Gate。

## O. Self-Check 與 Gate

```yaml
self_check:
  structural_review: PASS
  route_id_exactness: PASS
  article_number: PASS
  schema: PASS
  static_dedupe_contract: PASS
  runtime_semantic_dedupe: NOT_RUN
  generation_budget_dry_run: PASS_NO_PRUNING
  output_page_budget_validation: NOT_RUN
  question_method_review: PASS
  role_boundary: PASS
  effects_aggregation_contract: PASS
  unknown_and_conflict_handling: PASS
  legal_effect_review: PASS
  calibration_review: PASS
  human_gate: REQUIRED
runtime_enabled: false
review_status: CODEX_REVIEWED
submission_status: READY_FOR_HUMAN_REVIEW
automatic_advance: false
next_route: NOT_AUTHORIZED
```

審核順序固定為 `STRUCTURAL_REVIEW`、`QUESTION_METHOD_REVIEW`、`LEGAL_EFFECT_REVIEW`、`CALIBRATION_REVIEW`、`HUMAN_GATE`。前一關非 `PASS` 時，後續關卡一律 `NOT_RUN`。本輪前四關已完成靜態審查；`READY_FOR_HUMAN_REVIEW` 只代表可送人工審核，不代表 Human Gate、runtime 接線、法律結論或八頁輸出驗證通過。

本檔不輸出犯罪成立、不成立、有罪、無罪或最終罪名，只輸出候選方向、支持或降低適配度、仍為 `UNKNOWN`、以及需人工核對。三層通過仍不會自動改變 runtime flag，接線需要另行明確授權。

<!-- SUBMISSION_END -->

## Reviewer Decision

```yaml
gate_id: GATE-TH320-1-MOV-20261014-04
current_route_id: theft_320_1_movable
iteration: 4
ruleset_version: question-rules-v2-draft
ruleset_hash: UNKNOWN_RULESET_HASH_NOT_FORMALLY_DEFINED
hash_scope: UTF8_LF_BYTES_BETWEEN_SUBMISSION_MARKERS
submission_sha256: 524515AFD490E51FC790EEA3808C79B03869706D86F5AE1424004DE02B61B2DD
calibration_artifact_hash: 524515AFD490E51FC790EEA3808C79B03869706D86F5AE1424004DE02B61B2DD
official_source_status: SOURCE_URL_RECORDED_BEHAVIOR_TIME_UNKNOWN
role_matrix_status: REVIEWED
adjacent_route_matrix_status: REVIEWED
schema_validation: PASS
static_dedupe_contract: PASS
runtime_semantic_dedupe: PASS
runtime_wiring_status: LOCAL_VERIFIED
human_gate_decision: APPROVED_FOR_RUNTIME_WIRING
human_gate_evidence: USER_EXPLICIT_THREAD_MESSAGE
question_generation_dry_run: PASS_NO_PRUNING
output_page_budget_validation: PASS
test_results:
  - "build_questions theft+embezzlement victim: 36 questions; required FACT-05/06 present; pruned_questions=0"
  - "build_questions theft+embezzlement suspect: 51 questions; required FACT-05/06 present; pruned_questions=0"
  - "build_questions theft+embezzlement transfer: 29 questions; required FACT-05/06 present; pruned_questions=0"
  - "exact theft_320_1_movable runtime: 8 approved concepts materialized; 4 allowlisted adjacent legacy facts retained; replaced legacy facts not co-emitted"
  - "mixed route coverage: exact theft child pack remains isolated from parent-only comparison routes"
  - "pytest focused runtime and contract suites: 90 passed"
  - "py -3 -X utf8 -m pytest -q: 193 passed"
  - "node --check app/static/app.js: PASS"
  - "node --test tests/test_frontend_api_errors.mjs: 19 passed"
  - "pyflakes scoped changed Python files: PASS"
  - "actual LibreOffice DOCX-to-PDF victim: 37 questions, 4 pages"
  - "actual LibreOffice DOCX-to-PDF suspect: 39 questions, 4 pages"
  - "actual LibreOffice DOCX-to-PDF transfer: 34 questions, 3 pages"
  - "pytest document, P0 rules, and work-item contract suites: 34 passed"
  - "browser full victim flow: Gate 1 through output, 37 questions, DOCX HTTP 200, 4 pages, brief copy PASS"
  - "browser responsive checks: desktop and 390px mobile horizontal overflow 0; unnamed controls 0; console/page errors 0"
  - "browser Gate 4 continuation: victim 37 questions and suspect 39 questions retained in one case; both DOCX HTTP 200 and 4 pages"
  - "browser Gate 5 transfer: no-victim case materialized 40 questions; transfer DOCX HTTP 200 and 4 pages; victim and regular suspect outputs disabled"
  - "browser Gate 4-5 responsive checks: 390px horizontal overflow 0; console/page errors and failed responses 0"
open_blockers:
  - NOT_DEPLOYED
reviewer_decision: LOCAL_THEFT_ROUTE_GATE1_TO_5_BROWSER_PASS
review_execution_mode: REVIEWED_PIPELINE
prior_independent_review_model: UNVERIFIED
reviewer_identity: Codex GPT-5
latest_validation_execution_mode: SINGLE_EXECUTOR
latest_validation_model: gpt-5.6-sol
reviewed_at: 2026-10-14T21:57:05+08:00
decision_reason: Human Gate explicitly authorized runtime wiring. The selected theft_320_1_movable route now materializes the approved versioned pack, applies allowlisted semantic replacement, validates frozen enum snapshots, records per-route provenance and coverage, and keeps legal_conclusion false. Browser QA found and repaired the profile form name mapping that blocked document output. Local tests and the bounded theft-route browser flows for victim, continued suspect, and no-victim transfer passed. Actual LibreOffice DOCX-to-PDF rendering verified all three role outputs within the eight-page budget. This is not a legal conclusion or proof that other routes are complete. Deployment remains unperformed.
next_route_id: null
next_route: NOT_AUTHORIZED
automatic_advance: false
```

本 Reviewer Decision 段落位於 `SUBMISSION_END` 之後，不納入 `submission_sha256` 計算範圍，以避免自我參照。Reviewer Decision 必須放在 marker 外；此處不宣告 Human Gate 通過。

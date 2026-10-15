# Lifecycle Record

> 本檔保留階段與驗證歷史。下方早期 `COMPLETE` 僅代表當時有界線的實作輪次，不能作為目前法律完整、Human Gate、部署或整體驗收證明。現況應以實際 checkout、測試及 [README.md](README.md) 的證據規則重新確認。

## 2026-10-14 審核責任與 loop 邊界修正

```yaml
route_review_owner: CODEX_REVIEWER
user_review_mode: FINAL_BATCH_ONLY
case_human_gate_owner: HUMAN_CASE_OFFICER
route_execution_unit: ONE_CHILD_ROUTE_AT_A_TIME
route_auto_advance_after_codex_pass_and_archive: true
runtime_auto_advance: false
user_final_acceptance: PENDING
```

- 使用者不再逐 route 設定規則、核准問句或選擇下一罪章。
- 執行 AI 每次只製作一個 child route，完成後停下交給 Codex 審核；不得自行批次生成或切換 route。
- Codex 負責逐 route 的結構、問法、法律 effects 與校準審核。通過並完成完整歸檔後，controller 依鎖定 queue 接續下一個 route。
- 使用者只在整個已授權 queue 完成後做最終成果驗收。
- 實際案件仍保留承辦人 `CASE_HUMAN_GATE`，本次治理修正不授權 runtime、題庫、crosswalk 或部署變更。

---

## 2026-10-14 標準問句修正版 iteration 2

```yaml
execution_mode: REVIEWED_PIPELINE
routing_triggers: [H2, S3, S5]
primary_model: GPT-5
independent_reviewer_model: UNVERIFIED
submission_hash_scope: UTF8_LF_BYTES_BETWEEN_SUBMISSION_MARKERS
submission_sha256: F91844D0A73F7E77718614B06ED30441190D197FCD524E5ACD7A1DB98FFEC73A
work_item_file_sha256: 0E8060400AB96F65EC1F8CFF67C5BE1BAC05F9ADF5379EA6DA0EBEF79A534E71
runtime_enabled: false
human_gate: REQUIRED
next_route: NOT_AUTHORIZED
final_status: REFERENCE_STANDARD_READY_FOR_HUMAN_LEGAL_REVIEW
```

### 修正內容

- 將 concept 展開為單一 `target_interview_role` instance，並固定穩定 ID 與 witness review-only 邊界。
- 每題加入可機械判斷的 `trigger_condition`、明示 enum `answer_map`、既有題引用及 dedupe action。
- 將同意改為授權範圍三態，禁止以單一同意答案直接排除 theft 或認定民事爭議。
- 限制遺失狀態及抗拒能力只能向有直接知識的 victim 詢問，避免由 witness 或涉嫌人推論他人主觀狀態。
- 補上逐題 effects 聚合、必要前提、衝突處理及完整 facts 重算規則；任何 route 均不得自動輸出 `EXCLUDED`。
- 工作單審核雜湊改用 submission marker 內的 canonical UTF-8 LF bytes，Reviewer Decision 排除於雜湊範圍外。

### 獨立審查決策

- R1：`ACCEPT_WITH_MODIFICATIONS`；`questions/theft.md` 實際存在，E2E timeout 隔離重跑通過，其餘結構缺口納入修正。
- R2：`ACCEPT`；角色實體化、trigger、mapping、dedupe 與聚合契約均需修正。
- R3：`ACCEPT_WITH_MODIFICATIONS`；先合法持有可提高侵占候選，但返還、拒還或處分等必要事實未齊時，聚合結果維持 `NEED_REVIEW`。
- R4～R6：`ACCEPT`；同意範圍、witness 知識邊界及 fail-closed 校準均納入修正。
- 獨立審查實際模型身分為 `UNVERIFIED`，本輪不得標記 `DUAL_MODEL_PASS`。

### 驗證

- 問句契約、question logic 與 RCQ loader：47 passed。
- E2E 套件：2 passed，文件下載測試於整組執行時 timeout；該測試隔離重跑為 1 passed。合計 50 個唯一測試已有通過證據，但不是同一次整組全綠。
- 法務部官方刑法頁面於 2026-10-14 回查成功；本紀錄不取代行為時法與人工法律審查。
- Runtime、題庫接線及下一罪章均未獲授權，也未修改。

---

## 2026-10-14 標準問句版本與分層審核規則

```yaml
execution_mode: REVIEWED_PIPELINE
routing_triggers: [H2, S3, S5]
rejected_artifact_sha256: C19F52D017DB2737D64906E1ADF50ED78E05F0E6735B17EC371845916C145141
reference_standard_sha256: F20E332EC016AD337995476B1AE82803B165E199B52D5D1550FE138AB6CE659B
runtime_enabled: false
human_gate: REQUIRED
next_route: NOT_AUTHORIZED
final_status: REFERENCE_STANDARD_READY_FOR_HUMAN_LEGAL_REVIEW
```

### 設計決策

- 將題數單位固定為 `question_concept_id`；每 route 最多 8 個新 concepts，同一中性事實的角色 variants 不重複計數。
- 實際個案只選 3～5 個 core concepts，linked evidence follow-up 最多 2 題；固定公司題不得為符合預算而刪除。
- 建立 8 個 `theft_320_1_movable` 標準 concepts，依序涵蓋自由敘述、原持有、同意、先合法持有、遺失狀態、突然力量、暴力脅迫及抗拒能力。
- 使用 canonical exact child route IDs，移除 fraud、damage 及所有 parent／alias route ID。
- 將暴力脅迫與抗拒能力拆成兩個單一事實，避免一題同時回答手段及程度。
- Transfer 的移送來源、既有筆錄及刑事訴訟法第95條權利告知獨立為程序題，不作為犯罪構成要件。
- 審核順序固定為 Structural、Question Method、Legal Effect、Calibration、Human Gate；前一關失敗時後續一律 `NOT_RUN`。

### Sol Review Decision

- R1～R3：`ACCEPT`；拒絕前一 artifact、阻擋下一罪章，N-1～N-6 因前提失敗不審。
- R4：`ACCEPT_WITH_MODIFICATIONS`；題數計算矛盾屬 systemic rule defect，其餘 route、條號、schema 及問句缺陷由新 iteration 修正。
- R5～R9：`ACCEPT`；採 exact child IDs、正確條號、單一事實、角色契約與只輸出候選 effects 的校準格式。
- 獨立審查實際模型身分：`UNVERIFIED`，不得標記 `DUAL_MODEL_PASS`。

### 驗證

- `tests/test_question_work_item_contract.py`：5 passed。
- 問句 contract、question logic、RCQ loader、E2E：46 passed。
- Markdown 相對連結：PASS。
- `git diff --check`：PASS。
- 法務部官方刑法及刑事訴訟法頁面於 2026-10-14 回查成功。
- 法律 effects、語意去重、行為時法及接線仍需 Human Gate；runtime 未修改。

---

## 2026-10-14 單一問句工作檔

- 建立 `QUESTION_WORK_ITEM.md` 作為唯一 active child route 的交付及審核檔。
- 建立 `AI_HANDOFF_PROMPT.md` 作為下一位 AI 的唯一固定接手提示詞；`AI_EXECUTION_PROTOCOL.md` 只保留連結，不維護重複副本。
- 問句製作輸出由 `CHAT_ONLY` 改為 `WORK_ITEM_FILE_ONLY`，唯一可寫路徑是該檔。
- 聊天限制為 12 行摘要，避免重貼完整問句、矩陣及案例。
- 禁止每個罪章新增一份 Markdown；工作單在覆蓋前須記錄 SHA-256 與 Gate 決定。
- 新增 handoff checkpoint；下一位 AI 依 `resume_from_section` 接續，禁止清空或重做已完成段落。
- Runtime、題庫、crosswalk 及測試邏輯未修改。

---

## 2026-10-14 問句規則缺陷修正與基準路由校準

```yaml
execution_mode: REVIEWED_PIPELINE
routing_triggers: [H2, S3]
failure_scope: SYSTEMIC_RULE_DEFECT
question_ruleset_version: question-rules-v2-draft
ruleset_status: CALIBRATION_REQUIRED
calibration_route: theft_320_1_movable
queue_status: BLOCKED_BY_RULESET
automatic_advance: false
final_status: DOCUMENT_REMEDIATION_COMPLETE_CALIBRATION_PENDING
```

### Root cause

- 前一版 canonical 規則雖要求中性事實、角色與 `legal_targets`，但沒有強制以 `distinction_axis` 選擇相鄰路由。
- `target_role: ALL` 沒有明文要求展開各角色實際問法，執行者可能只交付通用問句或只換稱謂。
- 沒有明文區分「單一內容錯誤」與「共通規則錯誤」，兩輪 loop 可能在錯誤規則內反覆修題。
- 缺少規則集基準路由與下一罪章准入 Gate，導致錯誤可能被帶入後續罪章。

### 修正

- 問句作者角色固定為台灣刑事案件筆錄問句與詢問方法設計專家。
- 問法固定為開放敘述 → 單一事實釐清 → 證據追問。
- 相鄰路由由區分軸、可觀察事實與保守 UNKNOWN 效果共同決定，不得直接複製一般 `related` 清單。
- victim、suspect、transfer 及 witness_review_only 必須依各自知識範圍分別設計。
- 新增 `SYSTEMIC_RULE_DEFECT`、`BLOCKED_BY_RULESET` 及 `INVALIDATED_BY_RULESET_CHANGE` 狀態。
- 規則缺陷不計一般內容修正輪次；修規則後以同一基準 route 的 iteration 0 重新校準。
- `theft_320_1_movable` 未通過校準及 Human Gate 前，下一罪章為 `NOT_AUTHORIZED`。

### 獨立審查補強

- 決策：`ACCEPT_WITH_MODIFICATIONS`；停止佇列與回到規則層的方向接受，但 draft 不得直接升級。
- 新增人工核准的 primary／comparison／alternative route allowlist，禁止 `distinction_axis` 自行擴張罪章。
- 分離 `designer_role` 與 `target_interview_role`，persona 本身不構成品質或法律權威證據。
- 同一 `defect_id` 最多一次 ruleset revision 及一次重新校準；再失敗為 `BLOCKED_NEEDS_HUMAN_DECISION`。
- 補齊 question phase linkage、角色知識矩陣、基準相鄰路由 effects 矩陣與可重現 Gate evidence schema。
- 明確區分 `active_question_ruleset: UNCHANGED_RUNTIME` 與候選 `question-rules-v2-draft`。

### 驗證

- Canonical Markdown link 與規則契約檢查：PASS。
- 基準 route allowlist 六個 child route 均存在於 `legal_route_crosswalk.json`：PASS。
- `git diff --check -- legal-case-web/docs/LIFECYCLE_RECORD.md`：PASS。
- 目標問句／RCQ／E2E 測試：41 passed。
- 完整 pytest：153 passed。
- 文件修正完成不等於候選 ruleset 已通過；`theft_320_1_movable` 校準與 Human Gate 仍為 `NOT_RUN`。

### 影響範圍

- `QUESTION_DESIGN_AND_USE.md`
- `AI_EXECUTION_PROTOCOL.md`
- `OFFENSE_QUESTION_WORK_QUEUE.md`
- `README.md`
- Runtime 程式、題庫、crosswalk 與接線狀態均未修改。

---

## 2026-10-14 法規生命週期與文件再收斂

```yaml
execution_mode: REVIEWED_PIPELINE
routing_triggers: [H2, S3]
runtime_reported_model: UNVERIFIED
authorization_status: LOCAL_DOCUMENT_RESTRUCTURE_AND_EXPLICIT_DELETION_AUTHORIZED
included_phases: [PLAN, DESIGN, BUILD, TEST]
skipped_phases:
  - phase: DEPLOY
    status: SKIPPED_WITH_REASON
    reason: 本次只整理本機文件
  - phase: MAINTAIN
    status: SKIPPED_WITH_REASON
    reason: 未建立自動監控或 runtime 命令服務
final_status: COMPLETE_REVIEWED_PIPELINE_UNVERIFIED
```

### 目標結構

- `SYSTEM_ARCHITECTURE.md`：系統元件、runtime 來源與信任邊界。
- `QUESTION_DESIGN_AND_USE.md`：合併 Gate、角色流程、候選路由、問句、回答重評估及 Human Gate。
- `LAW_REGISTRY.md`：法規身分、別名、版本線索與 route 關聯的人類索引。
- `LAW_LIFECYCLE.md`：新增／更新法規、條文分類、版本差異與影響分析。
- `OFFENSE_QUESTION_WORK_QUEUE.md`：現有 routes 的工作狀態，不維護法規版本。
- `AI_EXECUTION_PROTOCOL.md`：自然命令分類、提示詞及最多兩輪的修正控制。

### 合併與刪除映射

| 被取代文件 | 唯一內容移入 | bytes | SHA-256 |
|---|---|---:|---|
| `CASE_WORKFLOW.md` | `QUESTION_DESIGN_AND_USE.md` 第 1–4、8–10 節 | 3915 | `87E0AADF2897021F9111F465C7521AEE3C3D66F2906F598C6B0956EB868073F1` |
| `OFFENSE_ROUTING_AND_HUMAN_REVIEW.md` | `QUESTION_DESIGN_AND_USE.md` 第 3、7–10 節 | 5262 | `6DC87E353710E1552EEC6EDD23313F6B8927F428B61E06410A00869A4166DF80` |

刪除理由：兩份文件的 Gate、候選狀態、重評估及 Human Gate 與問句使用流程不可分割，分開維護會產生規則漂移。刪除前已記錄大小與 SHA-256；兩檔原為未追蹤檔時，Git 無法直接還原，須依本紀錄與歷史內容重建。

### 獨立審查決策

- `ACCEPT`：以六個核心面向收斂文件，保留既有固定 RCQ 與審查工作表路徑。
- `ACCEPT_WITH_MODIFICATIONS`：`LAW_LIFECYCLE.md` 管法律 domain 流程；`AI_EXECUTION_PROTOCOL.md` 只管任務與 loop，避免重複。
- `ACCEPT_WITH_MODIFICATIONS`：`LAW_REGISTRY.md` 是人類索引；runtime JSON 仍是產品行為來源，衝突時 fail closed。
- `ACCEPT`：新增／更新都保存歷史、未來生效、廢止、改號、拆分與合併沿革。
- `ACCEPT`：自然語言命令只建立有界線工作單，不宣稱已是 runtime 自動功能。

### 驗證

- `MARKDOWN_LINKS_OK`：11 份保留 Markdown 的相對連結均存在。
- `ROUTE_COVERAGE_OK`：runtime 44 個 parent routes 均出現在工作佇列，無未知 route。
- `REGISTRY_ROUTE_IDS_OK`：法規登錄引用的 route 均存在於 `question_bank.json`。
- `NO_ACTIVE_STALE_REFERENCES`：被刪除文件只保留於本檔歷史／manifest，其他有效文件與測試無引用。
- `py -3 -X utf8 -m pytest -q tests/test_question_logic.py tests/test_rcq_loader.py tests/test_e2e_flow.py`：41 passed。
- `py -3 -X utf8 -m pytest -q`：153 passed。
- Runtime 程式、題庫與資料 schema：本輪未修改。

---

## 2026-10-14 文件治理收斂

```yaml
execution_mode: REVIEWED_PIPELINE
routing_triggers: [H2, S3]
included_phases: [PLAN, DESIGN, BUILD, TEST]
skipped_phases:
  - phase: DEPLOY
    status: SKIPPED_WITH_REASON
    reason: 本次只整理本機文件
  - phase: MAINTAIN
    status: SKIPPED_WITH_REASON
    reason: 未要求持續監控
authorization_status: LOCAL_DOCUMENT_RESTRUCTURE_AND_EXPLICIT_DELETION_AUTHORIZED
final_status: COMPLETE
```

### PLAN

- Input：使用者要求建立架構、流程、問句製作／使用及罪章判斷文件，並刪除不必要 Markdown。
- Output：五份 canonical 文件、四份保留審查／治理資料、明確刪除清單。
- Gate：不得刪除 runtime/test 固定路徑；不得改變 runtime 行為；不得以舊報告宣稱目前驗收完成。

### DESIGN

- Input：舊文件內容、README、`app/workflow.py`、`app/rules.py`、`app/questions.py`、`app/rcq_loader.py`。
- Output：`README.md`、`SYSTEM_ARCHITECTURE.md`、`CASE_WORKFLOW.md`、`QUESTION_DESIGN_AND_USE.md`、`OFFENSE_ROUTING_AND_HUMAN_REVIEW.md`。
- Gate：文件責任不得重疊；`UNKNOWN`、Human Gate、公司題、RCQ 隔離及 witness review-only 邊界必須保留。

### 刪除前 manifest

下列檔案均位於 `legal-case-web/docs`。刪除原因為內容已由 canonical 文件取代，或只是過時輪次提示詞、協作紀錄、一次性報告與未接線設計稿。由於它們在刪除前多為 untracked，本清單保留大小與 SHA-256 證據。

| 檔案 | bytes | SHA-256 |
|---|---:|---|
| `1.md` | 5539 | `867FCE24E8E1D1FE0D809A537E61B3175A7E1BD22816492AE931B02EA2E0283D` |
| `2.md` | 6775 | `9838935DFF3C4125180299318E5B7040B21258043C26BE04190481F1BB43BFA0` |
| `3.md` | 33533 | `71DDE88E6CFC6AD1510B0EB0C432789B8F04555C6CDD77DAF0E15814E21B4900` |
| `4.md` | 22884 | `C7BD02405ED61F058F616E1D079674C3FD0CE245AEBD626F1860419CDBC16AE9` |
| `ACT_OFFENSE_COMPETITION_DESIGN.md` | 7608 | `EF96C89214A27D22A626E32F90F5EFBA43EA2E2FB60FA1DEC04889A1125DDE89` |
| `AI_COORDINATION.md` | 38533 | `0E00A6D71AA0D3DAD1053699890533FFCA6331618F039020AF14A75FE3ED2715` |
| `AUTHORIZED_FIX_REPORT.md` | 25715 | `FBB7EF51D01A15C5E87F8E2C9DD7E870B46E461185CA2A882601244964155CDF` |
| `CORE_QUESTION_BATCH_01_DRAFT.md` | 36511 | `B8F94F01FBD120B49B792BAEBD7A2D7F707FFFE47ED9C67FE0D79356455C6001` |
| `CORE_QUESTION_CONTENT_BASELINE.md` | 18170 | `A343379EC5592A80453A6B323B3FDD9951946E32D9EFE8718E9EB22519A6F189` |
| `CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_REVIEW_DESIGN.md` | 11650 | `2812F9F4AF6E286B7634F75AFA2BC490784D56CF58B0D0FD9DAC6142D0A6D6D8` |
| `EXTERNAL_ROUTE_RESEARCH_BATCH_A.md` | 6076 | `2AD5D88691ADB3475EA118A4C78A0D8675509B0B0D67DCEE2AE293E90D8` |
| `EXTERNAL_ROUTE_RESEARCH_PROMPT.md` | 6082 | `AE6063AB9655D32FB82240F4EA4236918121637301959002BECAED6FB89BDDE4` |
| `FINAL_ACCEPTANCE_REPORT.md` | 6443 | `12C3C51C0D16B5EF48B9B1272E9094B41700A59370475A1964D629A776A62491` |
| `FINAL_PASS_FAIL_BLOCKED_NOT_RUN.md` | 5693 | `C7CD58BD10B05BCE1E9B0435DD2C4BEC4C07BE0294D271E59B2F34C9D3F9A004` |
| `RCQ_QUALITY_REVIEW_REPORT.md` | 2103 | `1FEB9913FC59FFFF2457AF9264A80742959E8C7FBC02E95AD6493566BD26C1A1` |
| `RED_TEAM_REVIEW.md` | 8047 | `94F3B6D7BAF0780DB138A453337652DE313558548FBF1D98A5C9790788E6CF47` |
| `SEMANTIC_CASE_GAP_MATRIX.md` | 7682 | `7CDEC28B451FAFB27E846692B7914F67259F0EE066275DB74F6DA1AA89CE3429` |
| `SEMANTIC_REASONING_AUDIT.md` | 30504 | `BCC7373FFDEDCDF2C4236EE08515982FB4E85F46E5AC136A708679F3A9F76EBE` |
| `FINAL_PASS_FAIL_BLOCKED_NOT_RUN.md` | 5693 | `C7CD58BD10B05BCE1E9B0435DD2C4BEC4C07BE0294D271E59B2F34C9D3F9A004` |
| `RCQ_QUALITY_REVIEW_REPORT.md` | 2103 | `1FEB9913FC59FFFF2457AF9264A80742959E8C7FBC02E95AD6493566BD26C1A1` |
| `RED_TEAM_REVIEW.md` | 8047 | `94F3B6D7BAF0780DB138A453337652DE313558548FBF1D98A5C9790788E6CF47` |
| `SEMANTIC_CASE_GAP_MATRIX.md` | 7682 | `7CDEC28B451FAFB27E846692B7914F67259F0EE066275DB74F6DA1AA89CE3429` |
| `SEMANTIC_REASONING_AUDIT.md` | 30504 | `BCC7373FFDEDCDF2C4236EE08515982FB4E85F46E5AC136A708679F3A9F76EBE` |

保留且不得改名：`CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md`、`RCQ_HUMAN_REVIEW_WORKSHEET.md`、`SEMANTIC_TEST_SET_REVIEW_WORKSHEET.md`、`LIFECYCLE_RECORD.md`。

### BUILD

- Output：建立五份 canonical 文件；更新 README、程式註解、測試說明及三份保留工作表的舊連結；依 manifest 刪除 18 份被取代文件。
- Gate：未修改 runtime 邏輯、資料 schema、法律題庫內容、資料庫或部署設定。
- Evidence：文件 inventory、無失效 Markdown 連結、無舊檔有效引用。

### TEST

- Input：規則、Gate、儲存、HTTP 安全、文件與無障礙驗收條件。
- Output：pytest、JavaScript 語法、實際 LibreOffice 頁數、手動瀏覽器驗證結果。
- Gate：失敗先修產品程式碼；同根因最多修復兩次。
- Evidence：`tests/` 與最終驗證紀錄。

最終驗證紀錄：

- `py -3 -X utf8 -m pytest -q`：20 passed。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- JSON 載入：2 files PASS。
- Playwright 桌面及 390px 手機：無 console error、無水平溢位、所有表單控制項有 label。
- Playwright 完整流程：首頁 → Gate 1 → Gate 2 → Gate 2.5 → 條陳 → DOCX；DOCX HTTP 200，LibreOffice 實際排版 2 頁。
- Git 範圍：新增內容僅在 `legal-case-web/`；263 個既有刪除未復原，0 個既有追蹤檔被修改。

## DEPLOY

- Output：`NOT_DEPLOYED`
- Gate：需另行取得部署位置、資料處理與外部服務的人工作業授權。

## 2026-10-14 Invalidated Human Gate Claim for theft_320_1_movable

```yaml
execution_mode: RECOVERY_AUDIT
routing_triggers: [H2, S3, S5]
gate_id: GATE-TH320-1-MOV-20261014-01
current_route_id: theft_320_1_movable
ruleset_version: question-rules-v2-draft
ruleset_hash: UNKNOWN_RULESET_HASH_NOT_FORMALLY_DEFINED
calibration_artifact_id: theft_320_1_movable-v2
calibration_artifact_hash: F91844D0A73F7E77718614B06ED30441190D197FCD524E5ACD7A1DB98FFEC73A
official_source_status: VERIFIED_CURRENT
role_matrix_status: PASS
adjacent_route_matrix_status: PASS
schema_validation: PASS
dedupe_validation: PASS
budget_validation: PASS
test_results:
  - test_question_work_item_contract.py: 9/9 PASSED
  - full_pytest: 162/162 PASSED
open_blockers: [NO_VERIFIABLE_EXPLICIT_HUMAN_APPROVAL, ORIGINAL_WORK_ITEM_OVERWRITTEN, UNAUTHORIZED_BATCH_GENERATION]
reviewer_decision: INVALIDATED_UNSUPPORTED_HUMAN_GATE_CLAIM
reviewer_identity: UNVERIFIED_GENERATED_CLAIM
reviewed_at: 2026-10-14T15:18:37+08:00
decision_reason: The record asserted a user Human Gate approval that is not supported by an explicit approval instruction in the available task history. Engineering tests do not establish legal approval.
next_route_id: NOT_AUTHORIZED
automatic_advance: false
```

### Unauthorized batch evidence

```yaml
incident_status: QUARANTINED
work_item_route_found: fraud_344_1_aggravated_usury
queue_target_found: aggravated_theft_321
generated_route_count_reported_by_executor: 14
active_work_item_sha256_before_recovery: B67CE581BEB0B211A77909BF9B69389C01A7627DB39AE58946FC264D3EF21353
batch_review_sha256: EE6AEB1EADA48578EE5F3260888EECE5C0F987637A5A76FBC447300C11F2F8B0
generator_sha256: 84904A6439B90B6CD402DF078C3DD829C86709A8C7D14DF6726E3EDCB074D5C0
unauthorized_docs_agents_sha256: B1F3DA0567F89B51527F849C31795DEE355D9DF007ACC9D5A93449F1B179A7F9
backup_sha256: 989E7128410E107BC28B396B3C66B268839EF3305042B52023737FB0875962ED
runtime_enabled: false
next_route: NOT_AUTHORIZED
```

- 未授權批次及 generator 不列入完成罪章數，也不作為 Human Gate 證據。
- `QUESTION_WORK_ITEM.md.bak_orig` 實際是未核准的 `aggravated_theft_321`，不是已驗證的竊盜基線，因此不得用於復原。
- 原始 `theft_320_1_movable` 完整工作單已被覆寫；目前只剩可回查的 submission hash 與標準摘要，不能憑摘要重建後宣稱 hash 相同。

---

## 2026-10-15 離線罪章關聯 PoC

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1, S3]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
human_gate: REQUIRED_BEFORE_RUNTIME_INTEGRATION
final_status: ENGINEERING_VALIDATION_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：使用者要求繼續前一輪「法條、裁判、公開書類如何連結罪章」設計。
- Output：只涵蓋 `theft_320_1_movable`、`aggravated_theft_321`、`embezzlement_335_general` 的離線 PoC。
- Gate：不得接入 Gate 2；不得匯入案件個資；不得把起訴書或裁判文字相似度當成犯罪成立判斷。

### DESIGN

- `data/offense_linkage_poc.json` 保存來源、child route、typed relation、區分軸、內容 hash 與人工審查狀態。
- `app/offense_linkage.py` 只驗證 schema 並把人工觀察狀態投影為逐 route 缺漏表。
- `OBSERVED / UNKNOWN / CONFLICT / NOT_FOUND` 只描述資料狀態；輸出固定 `legal_conclusion: false`。
- 公開書類只登錄官方範圍說明，起訴書維持 `NOT_INGESTED`。

### BUILD

- 新增 PoC validator、來源化 JSON 與獨立測試。
- 重用既有 `THF3201MOV-C02 / prior_lawful_custody`，不改寫公司題、問句工作單或 runtime。
- 既有裁判錨點標記 `PROJECT_EXISTING_ANCHOR_NOT_LIVE_REVERIFIED`；本輪工具無法直接開啟該裁判深層 URL，不升級為本輪官方重驗證。

### TEST

- Targeted pytest：66 passed。
- Full pytest：199 passed。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- 工程驗證不等於法律內容驗收；runtime 接線仍需獨立 Human Gate。

### DEPLOY

- `SKIPPED_WITH_REASON`：本輪未取得部署或 runtime 接線授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：未要求持續監控；PSUE adapter 與起訴書 ingest 仍需獨立設計及 Human Gate。

---

## 2026-10-15 去識別法律檢索 adapter PoC

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
external_network_enabled: false
human_gate: REQUIRED_BEFORE_EXTERNAL_OR_GATE2_INTEGRATION
final_status: ENGINEERING_VALIDATION_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：上一階段離線罪章關聯 PoC 與使用者「下一步」。
- Output：結構性去識別查詢產生器、adapter protocol、離線 adapter 與外部 fail-closed adapter。
- Gate：不接受案情全文或任意字串；不發出網路請求；不接 Gate 2；不改變候選狀態。

### DESIGN

- 查詢輸入只允許已核准 route ID、該 route 的 `fact_target` 及 `OBSERVED / UNKNOWN / CONFLICT / NOT_FOUND`。
- 查詢文字全部由程式固定詞彙產生，並以 SHA-256 封存；adapter 收到竄改內容時拒絕執行。
- `OfflineLinkageAdapter` 只回傳既有 PoC 來源 metadata，不回傳法律結論。
- `DisabledExternalAdapter` 即使查詢有效也拋出 `ExternalRetrievalNotAuthorized`，防止未核准外送。

### BUILD

- 新增 `app/legal_retrieval.py` 與 `tests/test_legal_retrieval.py`。
- 未修改 `server.py`、`workflow.py`、`rules.py`、Gate 2 API 或案件資料格式。

### TEST

- 初次 targeted suite：1 failed、66 passed。失敗原因為測試把侵占 fact target 放入僅竊盜 route，產品正確先拒絕越界欄位。
- 修正測試案例後 targeted suite：67 passed。
- Full pytest：208 passed。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- 工程驗證不等於法律內容、外部來源或 Gate 2 接線驗收。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得外部服務、runtime 接線或部署授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：未啟用遠端檢索或持續監控。

---

## 2026-10-15 法律檢索 metadata 正規化與快取 PoC

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
external_network_enabled: false
default_cache_path: NONE
human_gate: REQUIRED_BEFORE_EXTERNAL_OR_GATE2_INTEGRATION
final_status: ENGINEERING_VALIDATION_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：去識別查詢與離線 adapter 結果。
- Output：來源 response 正規化、hash scope、兩層完整性驗證及明示路徑的本機 metadata cache。
- Gate：不得保存全文、節錄、案件 payload 或個資；不得建立預設正式資料檔；不得接 Gate 2。

### DESIGN

- 正規化輸出只保存來源 ID、類型、機關、標題、官方 URL、文件日期、來源指紋、hash scope 與 relation IDs。
- 現有離線 hash 明示為 `REGISTERED_SOURCE_FINGERPRINT_NOT_FULL_DOCUMENT`，不冒充官方全文 hash。
- 每筆 record 與整份 response 分別計算完整性 SHA-256；載入時另做嚴格 schema、官方網域、日期與狀態驗證。
- 即使攻擊者加入全文欄位並重算兩層 hash，嚴格欄位 allowlist 仍拒絕寫入。
- cache 使用同目錄暫存檔、flush、fsync 與 `os.replace` 原子替換；呼叫者必須明示 cache 路徑。

### BUILD

- `app/legal_retrieval.py`：離線 hit 新增 `hash_scope`。
- 新增 `app/legal_retrieval_cache.py` 與 `tests/test_legal_retrieval_cache.py`。
- 未修改 runtime、案件 schema、Gate 2 或外部連線設定。

### TEST

- Targeted pytest：27 passed。
- Full pytest：220 passed。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- 工程驗證不等於官方全文 hash、外部來源或 Gate 2 接線驗收。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得 runtime、外部服務或部署授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：沒有建立正式快取檔或持續監控。

---

## 2026-10-15 法律來源離線 fixture 契約

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
external_network_enabled: false
human_gate: REQUIRED_BEFORE_EXTERNAL_OR_GATE2_INTEGRATION
provider_contracts:
  mcp_taiwan_legal_db: FIXTURE_CONTRACT_SUPPORTED
  tlr_anchor: FIXTURE_CONTRACT_SUPPORTED
  judicial_jdoc: FIXTURE_CONTRACT_SUPPORTED
  taiwan_law_mcp: DISCOVERY_ONLY_SCHEMA_UNKNOWN
  psue: DISCOVERY_ONLY_SCHEMA_UNKNOWN
final_status: ENGINEERING_VALIDATION_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：去識別查詢、來源 metadata 正規化器與使用者提供的公開法律來源方向。
- Output：只讀取離線 fixture 的 provider adapters 與契約測試。
- Gate：不呼叫外部服務；不保存全文；不接 Gate 2；不把命中來源解讀為罪章成立。

### DESIGN

- `mcp-taiwan-legal-db` 只接受已公開的 `success / results / jid` 搜尋結果形狀，且只映射已登錄的裁判 JID。
- TLR anchor 只有 `allowed_citations` 內、已讀且 `fulltext_available` 的裁判可成為 hit；`unread_candidates` 永不提升為引用。
- 司法院 `JDoc` 檢查請求 JID、JID 內日期與 `JDATE` 一致，只在記憶體中計算 `JFULLCONTENT` hash，輸出不保存全文。
- 司法院來源移除回應拋出 `SourceRemovalRequired`。正式 cache purge 尚未接線，因此不得宣稱已完成移除同步。
- Taiwan Law MCP 與 PSUE 的公開資料不足以固定本 PoC 的 response/API schema，使用 discovery-only adapter 明確拒絕執行。

### BUILD

- 新增 `app/legal_provider_fixtures.py` 與 `tests/test_legal_provider_fixtures.py`。
- `data/offense_linkage_poc.json` 的既有裁判來源增加 provider locator，未改變 runtime flag 或來源 fingerprint。
- 未修改 `server.py`、`workflow.py`、`rules.py`、Gate 2 API、案件 schema 或連線設定。

### TEST

- Targeted pytest：36 passed。
- Full pytest：229 passed。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- 工程驗證不等於外部 provider 上線驗收、法律內容正確性或 Gate 2 接線核准。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得外部服務、runtime 接線或部署授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：沒有正式 provider fixture 資料檔、正式快取或持續監控。

---

## 2026-10-15 法律來源移除 reconciliation PoC

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1, S4]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
external_network_enabled: false
cache_schema: legal-retrieval-metadata-cache-v2
human_gate: REQUIRED_BEFORE_EXTERNAL_OR_GATE2_INTEGRATION
final_status: ENGINEERING_VALIDATION_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：司法院 fixture adapter 的 `SourceRemovalRequired` 與既有明示路徑 metadata cache。
- Output：registry 精確映射、原子 metadata 移除、去識別 tombstone 與防回填規則。
- Gate：不模糊比對 locator；不保存原始 JID；不建立正式 cache；不接 runtime、外部服務或 Gate 2。

### DESIGN

- 只有 provider allowlist 內的 locator key 可參與 reconciliation；locator 必須精確映射一筆已登錄來源，否則 fail closed。
- cache schema v2 在同一 JSON 檔保存 entries 與 removal audit。v1 可讀取，並在下一次成功寫入時升級。
- 每個 audit event 保存 locator SHA-256、`source_id`、受影響 cache keys、移除筆數及前後 entries hash，不保存原始 locator、全文或案件資料。
- 成功移除後 tombstone 阻止相同 `source_id` 被舊 adapter 結果回填。相同觀察事件保持冪等。
- metadata 移除與 audit event 使用同一個 temp file、`fsync` 與 `os.replace`；替換失敗時原 cache 不變且不殘留 temp file。
- 官方撤除可能涉及隱私，因此不建立可恢復的來源備份；同一 cached response 的無關來源 metadata 仍保留。

### BUILD

- 擴充 `app/legal_retrieval_cache.py`：v2 schema、audit 驗證、原子 writer、tombstone 防回填與精確來源移除。
- 新增 `app/legal_retrieval_reconciliation.py` 與 `tests/test_legal_retrieval_reconciliation.py`。
- 補充 v1 cache 讀取與寫入升級測試。
- 未修改 `server.py`、`workflow.py`、`rules.py`、Gate 2 API、案件 schema 或外部連線設定。

### TEST

- 首次 targeted suite：12 failed、16 passed。單一根因為新增 UTC helper 時使 `_is_iso_date` 本體不可達；修正產品程式碼後重測。
- 修正後 targeted pytest：30 passed。
- Full pytest：238 passed。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- 工程驗證不等於官方來源移除流程上線、法律內容正確性或 Gate 2 接線核准。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得 runtime、外部服務、正式 cache 或部署授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：未啟用來源輪詢、正式 cache 或持續監控；tombstone 解除只允許未來另行設計並經 Human Gate。

---

## 2026-10-15 離線 provider sync coordinator

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1, S4]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
external_network_enabled: false
default_mode: DRY_RUN
default_cache_path: NONE
human_gate: REQUIRED_BEFORE_EXTERNAL_OR_GATE2_INTEGRATION
final_status: ENGINEERING_VALIDATION_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：去識別 query、離線 fixture adapter、明示路徑 metadata cache 及來源移除 reconciliation。
- Output：單一受控函式完成 dry-run、metadata commit 或來源移除 commit。
- Gate：不接受外部網路 adapter；不建立預設 cache；不接 Gate 2；不把同步命中解讀為法律結論。

### DESIGN

- `run_offline_sync` 預設 `commit=False`。dry-run 會完成 query、adapter response 與正規化驗證，但不建立或修改 cache。
- adapter 必須明示 `external_network is False`；adapter 實例 ID、正常回應 ID 與移除事件 provider ID 必須一致，否則 fail closed。
- 正常 commit 只保存既有 allowlist 定義的公開 metadata。報告不包含 query text、fixture summary、官方錯誤文字、原始 locator 或全文。
- 移除 dry-run 只預覽精確 registry 映射與受影響紀錄。移除 commit 另須 UTC `observed_at`，並交由原子 reconciliation 寫入 tombstone。
- 相同移除事件再次 commit 時維持冪等，報告 `cache_mutated: false`，不新增第二筆 audit event。
- discovery-only 或外部 adapter、身分偽造、未提供時間的移除 commit 都不得建立 cache。

### BUILD

- 新增 `app/legal_retrieval_sync.py` 與 `tests/test_legal_retrieval_sync.py`。
- `app/legal_retrieval_reconciliation.py` 拆出 locator resolution 與只讀 preview，commit 行為仍使用既有原子 cache transaction。
- 未修改 `server.py`、`workflow.py`、`rules.py`、Gate 2 API、案件 schema 或外部連線設定。

### TEST

- Targeted pytest：48 passed。
- Full pytest：247 passed。
- `pyflakes`（本階段模組與測試）：PASS。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- 工程驗證不等於外部 provider 可用、正式同步排程、法律內容正確性或 Gate 2 接線核准。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得 runtime、外部服務、正式 cache、排程或部署授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：未啟用來源輪詢、正式 cache、tombstone 解除或持續監控。

---

## 2026-10-15 離線多 provider batch transaction

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1, S4]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
external_network_enabled: false
default_mode: DRY_RUN
partial_commit_allowed: false
default_cache_path: NONE
human_gate: REQUIRED_BEFORE_EXTERNAL_OR_GATE2_INTEGRATION
final_status: ENGINEERING_VALIDATION_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：離線 sync coordinator、明示路徑 metadata cache、fixture adapters 與固定去識別 queries。
- Output：deterministic manifest、記憶體 transaction、順序化 dry-run 及全批次原子 commit。
- Gate：不保存 manifest；不接受自由文字 query；不允許部分提交；不接排程、runtime、外部服務或 Gate 2。

### DESIGN

- manifest 只能由 `(adapter_id, validated query)` 經 builder 產生；`batch_id`、item IDs 與 manifest SHA-256 均可重建。空 manifest、重複 provider/query 或任意欄位竄改會 fail closed。
- transaction 從已驗證 cache payload 建立記憶體副本。每個 batch item 依 manifest 順序呼叫既有 offline sync，讓前項 store/removal 對後項可見。
- dry-run 完成全部模擬後丟棄 transaction，不建立 cache 或 temp file。報告只含 item ID 與去識別 sync metadata，不回傳 manifest query。
- commit 只有在全部 item 成功後才執行一次 cache 原子替換。後段 adapter 失敗、移除後舊來源回填或底層 `os.replace` 失敗時，不提交 staged 結果。
- transaction 記錄起始 payload hash，commit 前重讀 cache；若其他寫入者造成漂移，拒絕覆寫並保留外部最新狀態。
- item report 的 `would_mutate` 表示記憶體模擬影響；只有 batch report 的 `cache_mutated` 可表示最終 cache 是否提交。

### BUILD

- `app/legal_retrieval_cache.py`：抽出純記憶體 stage 操作，新增 `RetrievalMetadataCacheTransaction`、dirty tracking、discard、基線漂移檢查及單次 commit。
- 新增 `app/legal_retrieval_batch.py` 與 `tests/test_legal_retrieval_batch.py`。
- 未修改 `server.py`、`workflow.py`、`rules.py`、Gate 2 API、案件 schema、排程或外部連線設定。

### TEST

- Targeted pytest：39 passed。
- Full pytest：256 passed。
- `pyflakes`（本階段模組與測試）：PASS。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- 覆蓋 deterministic manifest、竄改／重複拒絕、順序化 dry-run、store→remove、remove→stale-store、後段失敗、cache 漂移、adapter mapping 及原子替換失敗。
- 工程驗證不等於外部 provider 可用、正式批次排程、法律內容正確性或 Gate 2 接線核准。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得 runtime、外部服務、正式 cache、排程或部署授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：未啟用來源輪詢、正式 batch manifest 持久化、tombstone 解除或持續監控。

---

## 2026-10-15 離線 golden fixture replay harness

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1, S4]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
runtime_enabled: false
external_network_enabled: false
contains_case_data: false
corpus_sha256: ad8e787338e35be3b72badf7588be437cb30a4636fabe8aee5f7e0e2ee6808ed
suite_evidence_sha256: eb7638295f9b9265ade2c9a35791894d9aeafcd49d0a7f7cf02f5db996a50b9b
human_gate: REQUIRED_BEFORE_EXTERNAL_OR_GATE2_INTEGRATION
final_status: ENGINEERING_REPLAY_PASS_RUNTIME_NOT_CONNECTED
```

### PLAN

- Input：離線 batch transaction、已驗證 fixture adapters 與明示 scratch 目錄。
- Output：嚴格合成 corpus、固定結果投影、逐情境 evidence hash 與 suite evidence hash。
- Gate：不讀取案件資料；不輸出 query、locator、fixture／錯誤內文或 traceback；不接 runtime、外部服務或 Gate 2。

### DESIGN

- corpus 僅允許 `mcp_taiwan_legal_db` 與 `judicial_jdoc`，最多 32 個情境、每情境最多 8 個不重複 provider operations。
- query 只能由既有 route IDs 與有限 observation status 重建。JDoc locator 必須符合既有 JID 格式，`observed_at` 必須為 UTC ISO timestamp。
- fixture 禁止姓名、地址、案件 payload、個資、全文、摘要與節錄欄位。corpus 明示 `contains_case_data: false`。
- expected projection 僅包含結果種類、batch 狀態、operation 類型、cache 是否存在、entry／audit／record 計數及 allowlist error type；REPORT 與 ERROR 欄位必須語意一致。
- replay 捕捉錯誤後只記錄類別，不保存 message 或 traceback。每個 scenario 使用獨立明示 cache；同名 scratch cache 已存在時 fail closed，不覆寫。
- expected drift 產生 `FAIL` 證據而不是改寫 golden。suite output 不包含 corpus query 或 provider locator。

### BUILD

- 新增 `app/legal_retrieval_replay.py`。
- 新增 `tests/fixtures/legal_retrieval_replay.json` 與 `tests/test_legal_retrieval_replay.py`。
- 四個情境：正常 store dry-run、store→remove commit、provider schema drift、remove→stale-store rollback。
- 未修改 `server.py`、`workflow.py`、`rules.py`、Gate 2 API、案件 schema、排程或外部連線設定。

### TEST

- Targeted pytest：46 passed。
- Full pytest：263 passed。
- Golden replay：4 passed、0 failed。
- `pyflakes`（本階段模組與測試）：PASS。
- `python compileall`：PASS。
- Golden corpus JSON parse：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- Corpus SHA-256：`ad8e787338e35be3b72badf7588be437cb30a4636fabe8aee5f7e0e2ee6808ed`。
- Suite evidence SHA-256：`eb7638295f9b9265ade2c9a35791894d9aeafcd49d0a7f7cf02f5db996a50b9b`。
- 工程 replay PASS 不等於官方 provider、法律內容、正式案件、Human Gate 或 Gate 2 接線驗收。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得 runtime、外部服務、正式 cache、排程或部署授權。

### MAINTAIN

- `SKIPPED_WITH_REASON`：沒有啟用自動 golden 更新；預期值變更必須人工審查原因，不得以覆寫 golden 消除失敗。

---

## 2026-10-15 法律檢索 Human Gate 證據包

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1, S4]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
included_phases: [PLAN, DESIGN, BUILD, TEST]
packet_id: LR-HG-20261015-01
packet_sha256: 469e2f56c93f0b4b57a93094793a6c40ae7d66b730591c612b5399a461a44acd
decision_status: PENDING_HUMAN_APPROVAL
runtime_enabled: false
external_network_enabled: false
gate2_connected: false
final_status: ENGINEERING_EVIDENCE_PACKET_READY_HUMAN_GATE_PENDING
```

### PLAN

- Input：離線法律檢索 PoC、golden replay、目前 checkout 與 bounded verification results。
- Output：machine-readable packet、人工 checklist、hash/replay/runtime reachability 驗證測試。
- Gate：證據包不得自行核准 Human Gate；不得把工程 PASS、靜態不可達性或 golden replay 解讀為法律／runtime／部署完成。

### DESIGN

- packet 凍結 10 個 PoC 核心檔案與 4 個 runtime surface SHA-256。任何 hash 漂移會使測試失敗並要求重新基線。
- runtime surfaces 固定為 `server.py`、`workflow.py`、`rules.py` 與 `static/app.js`；三個法律檢索 token 的預期引用數均為 0。
- replay evidence 同時保存 corpus file hash、canonical corpus hash 與 suite evidence hash，驗證測試會實際重播四個情境。
- verification 區只記錄本輪實際執行結果。它與 decision status 分離；五項 approvals 仍全部為 `PENDING`。
- approvals 涵蓋 provider 契約、隱私／資安、cache lifecycle、法律使用邊界及 runtime／UI／稽核驗收。
- packet 明列五項 `UNKNOWN` 與五項禁止宣稱事項；沒有儲存案件資料、金鑰、query、provider 錯誤內容或正式 cache。

### BUILD

- 新增 `docs/evidence/legal_retrieval_human_gate_packet.json`。
- 新增 `docs/LEGAL_RETRIEVAL_HUMAN_GATE.md`。
- 新增 `tests/test_legal_retrieval_human_gate_packet.py`。
- 未修改 runtime、Gate 2、外部連線、案件 schema、正式 cache 或部署設定。

### TEST

- Human Gate packet targeted pytest：6 passed。
- Full pytest：269 passed。
- Golden replay：4 passed、0 failed。
- `pyflakes`（packet test）：PASS。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- `git diff --check`：PASS。
- Packet SHA-256：`469e2f56c93f0b4b57a93094793a6c40ae7d66b730591c612b5399a461a44acd`。

### DEPLOY

- `SKIPPED_WITH_REASON`：Human Gate 尚未核准，且未取得 runtime、外部服務、正式 cache 或部署授權。

### MAINTAIN

- frozen file 或 runtime surface hash 漂移時，本 packet 立即失效；不得只更新 hash 而跳過原因審查與完整重測。

---

## 2026-10-15 HG-LR-01 provider 公開契約審查

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
risk_level: MEDIUM
included_phases: [PLAN, DESIGN, BUILD, TEST]
skipped_phases:
  - phase: DEPLOY
    status: SKIPPED_WITH_REASON
    reason: 未取得外部連線、runtime 或部署授權
  - phase: MAINTAIN
    status: SKIPPED_WITH_REASON
    reason: 本輪只建立 2026-10-15 公開證據快照，不建立自動監測
human_gate_id: HG-LR-01
human_gate_status: PENDING
review_status: PARTIAL_REVIEW_HUMAN_APPROVAL_REQUIRED
review_sha256: dc912a580351fbf4b71a4a77a5e9229338095733f188479bfe3191952ec1fce5
automatic_fix_attempts: 0
final_status: EVIDENCE_REVIEW_PASS_HUMAN_APPROVAL_PENDING
```

### PLAN

- Input：`LR-HG-20261015-01` frozen packet、五個候選來源及 2026-10-15 可回查的第一方／官方公開文件。
- Output：provider 決策矩陣、FACT／INFERENCE／UNKNOWN、逐來源 blocking unknowns 與核准前最低條件。
- Gate：證據審查不得自行勾選 `HG-LR-01`，也不得呼叫 live provider、使用憑證、傳送案件資料或修改 runtime。
- Evidence：原 packet SHA-256 重驗為 `469e2f56c93f0b4b57a93094793a6c40ae7d66b730591c612b5399a461a44acd`。

### DESIGN

- 來源分為 official REST API、public search UI、hosted MCP／REST 及 self-hosted local MCP，不建立等價 fallback 假設。
- 每筆 provider 記錄 endpoint、response contract、authentication、rate／availability、terms／license、privacy／removal、disposition、blocking unknowns 及 evidence URLs。
- `PSUE` 在沒有公開 machine API contract 前維持 discovery-only。
- 所有候選都保留至少一項 blocking unknown；review 明列不宣稱 provider selected、production ready、live schema verified、legal completeness 或 runtime authorization。

### BUILD

- 新增 `docs/evidence/hg_lr_01_provider_contract_review.json`。
- 新增 `docs/HG_LR_01_PROVIDER_REVIEW.md`。
- 新增 `tests/test_hg_lr_01_provider_review.py`。
- 更新 README 與 Human Gate 索引；未改寫 frozen packet，也未修改 `server.py`、`workflow.py`、`rules.py` 或 `static/app.js`。

### TEST

- Provider review + frozen packet targeted pytest：12 passed。
- Full pytest：275 passed。
- Python `compileall`：PASS。
- `pyflakes tests/test_hg_lr_01_provider_review.py`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- JSON parse：PASS。
- `git diff --check`：PASS（只有既存 LF→CRLF warning）。
- Review SHA-256：`dc912a580351fbf4b71a4a77a5e9229338095733f188479bfe3191952ec1fce5`。
- Packet SHA-256：`469e2f56c93f0b4b57a93094793a6c40ae7d66b730591c612b5399a461a44acd`，未漂移。

### DEPLOY

- `SKIPPED_WITH_REASON`：未核准 provider、外部連線、runtime、Gate 2 或部署。

### MAINTAIN

- `SKIPPED_WITH_REASON`：外部契約可能變更；正式接線前必須重新查證並凍結選定 provider 的 request／response fixture、版本及變更通知規則。

---

## 2026-10-15 HG-LR-02 隱私與資安證據審查

```yaml
execution_mode: SINGLE_EXECUTOR
agent_mode: SINGLE_AGENT_MODE
routing_triggers: [H2, S1, S4]
downgrade_reason: 上層執行規則禁止未經使用者明示啟用子代理，改採單一執行者自我審查
risk_level: HIGH
included_phases: [PLAN, DESIGN, BUILD, TEST]
skipped_phases:
  - phase: DEPLOY
    status: SKIPPED_WITH_REASON
    reason: 未取得外部連線、runtime 或部署授權
  - phase: MAINTAIN
    status: SKIPPED_WITH_REASON
    reason: 本輪不建立正式 cache、provider 監測或資料保存作業
human_gate_id: HG-LR-02
human_gate_status: PENDING
review_status: CHANGES_REQUIRED_HUMAN_APPROVAL_PENDING
review_sha256: d7c4686b68f618a80bf72d94e1daee84c163f47f4bdd4c89b1a448af196b6bc4
automatic_fix_attempts: 0
final_status: PRIVACY_EVIDENCE_REVIEW_PASS_REMEDIATION_REQUIRED
```

### PLAN

- Input：frozen Human Gate packet、HG-LR-01 provider review、query／adapter／cache／reconciliation／sync／batch／replay 模組及官方個資法來源。
- Output：端到端資料流、資料分類、已驗證控制、阻擋 finding 與核准前條件。
- Gate：不得把 `DEIDENTIFIED_BY_CONSTRUCTION` 解讀為匿名或合規；不得核准外部傳輸、正式 cache、runtime 或 Gate 2。
- Evidence：前置 packet 與 HG-LR-01 review SHA-256 均未漂移。

### DESIGN

- 資料流分成 runtime reachability、query build、hosted boundary、normalization、cache、removal audit 及 reports 七段。
- 每段記錄 current state、data、persistence、classification 與 evidence。
- 法律來源只提供目的限制及安全維護控制參考；實際 operator、目的、法律依據及生效版本保留人工法律審查。
- review 明列 `ANONYMOUS_DATA`、`LEGAL_COMPLIANCE_CONFIRMED`、`CACHE_SECURITY_APPROVED`、`HOSTED_TRANSFER_APPROVED` 等禁止宣稱事項。

### BUILD

- 新增 `docs/evidence/hg_lr_02_privacy_security_review.json`。
- 新增 `docs/HG_LR_02_PRIVACY_SECURITY_REVIEW.md`。
- 新增 `tests/test_hg_lr_02_privacy_security_review.py`。
- 更新 README 與 Human Gate 索引；未改寫 frozen packet、HG-LR-01 evidence 或 runtime surfaces。

### TEST

- HG-LR-02 + HG-LR-01 + frozen packet targeted pytest：20 passed。
- 既有法律檢索隱私相關 pytest：55 passed。
- Full pytest：283 passed。
- Python `compileall`：PASS。
- `pyflakes tests/test_hg_lr_02_privacy_security_review.py`：PASS。
- `node --check app/static/app.js`：PASS。
- Node 前端行為測試：19 passed。
- JSON parse：PASS。
- Runtime review token scan：0 references。
- `git diff --check`：PASS（只有既存 LF→CRLF warning）。
- Review SHA-256：`d7c4686b68f618a80bf72d94e1daee84c163f47f4bdd4c89b1a448af196b6bc4`。
- Packet SHA-256：`469e2f56c93f0b4b57a93094793a6c40ae7d66b730591c612b5399a461a44acd`，未漂移。
- HG-LR-01 review SHA-256：`dc912a580351fbf4b71a4a77a5e9229338095733f188479bfe3191952ec1fce5`，未漂移。

### 已確認阻擋項

- `P01`：cache title 與 canonical URL 保留公開裁判案號線索，與「不保存案號」的廣義文件敘述不一致。
- `P02`：caller-controlled invalid status value 會被插入 exception；未來若被 log 或顯示可能洩漏。
- `P03`：commit cache 是明文 JSON，沒有模組層 encryption、ACL、retention 或 verified deletion。
- `P04`：hosted provider 第一方政策允許記錄完整 query parameters 或 query text。
- `P05`：deterministic unkeyed SHA-256 不是匿名化證明，也不是簽章。
- `P06`：正式目的、retention、access、deletion 與 incident owner 未指定。

### DEPLOY

- `SKIPPED_WITH_REASON`：`HG-LR-02` 明確為 changes required，未授權外部查詢、正式 cache、runtime 或部署。

### MAINTAIN

- `SKIPPED_WITH_REASON`：修正 `P01`／`P02` 及完成儲存、provider、retention、incident 決策後，必須重建 evidence review 並由隱私／資安角色核准。

## 2026-10-15：最小可運行網頁閉環與 P02 修正

execution_mode: `SINGLE_EXECUTOR`
agent_mode: `SINGLE_AGENT_MODE`

### PLAN

- Input：使用者要求一路執行到可在本機網頁輸入案情，取得候選罪章、問句、提問方式與條陳。
- Gate：只允許本機合成案件驗證；外部 provider、正式 cache、正式案件與部署維持停用。
- Evidence：確認 `/api/cases`、Gate action、brief 與 DOCX routes 已存在，再以隔離暫存 SQLite 跑瀏覽器旅程。

### DESIGN

- 保留既有 Gate 1–5、候選非結論、`HUMAN_REVIEW_REQUIRED`、公司範本逐字題與八頁文件上限。
- 問句畫面新增獨立「提問方式」，依公司題、敘述題、單一事實題與證據追問題提供中立操作提示；不得把候選罪章當成已成立。
- 以 `data:,` favicon 消除瀏覽器自動 favicon 請求造成的 404 console error。
- `P02` 驗證錯誤改用穩定 error code 與欄位層級訊息，不回顯 caller-controlled value。

### BUILD

- 更新 `app/static/app.js`：顯示可讀的提問方式與人工確認邊界。
- 更新 `app/static/index.html`：加入內嵌空 favicon。
- 更新 `tests/test_frontend_api_errors.mjs`：鎖定提問方式、單一事實與候選非結論文字。
- 重建 `LR-HG-20261015-03`、`HG-LR-01-REVIEW-20261015-02` 與 `HG-LR-02-REVIEW-20261015-02` 證據鏈；沒有改變任何 Human Gate 核准狀態。

### TEST

- 本機瀏覽器合成竊盜案：首頁 HTTP 200；Gate 1 產生 12 筆結構化事實；候選顯示竊盜、侵占、搶奪／強盜／海盜；動產竊盜 child route 可選。
- 被害人題包：37 題；逐題作答後補登證明單案號，產生 205 字條陳；條陳 DOCX 35,897 bytes、筆錄 DOCX 38,818 bytes，筆錄由 LibreOffice 實際排版為 4 頁。
- 提問方式瀏覽器驗證：涉嫌人題包 39 題，畫面可見公司逐字題的中立提問方式。
- 瀏覽器 console error 0、request failure 0；375px、768px、1440px 均無水平溢位；複製內容以換行正規化後一致。
- 基礎可及性檢查：可見 controls 無未標籤項目、無重複 ID、存在 main/nav landmarks、第一個 Tab 焦點為「跳到主要內容」。未安裝 axe，完整 WCAG 2.2 AA 自動掃描為 `NOT_RUN`。
- 視覺回歸：沒有既有 baseline，狀態為 `INCONCLUSIVE`；人工檢視首頁、問句與輸出畫面未見阻斷操作的版面問題。
- Core Web Vitals：CLS 0.0095；headless run 未取得 LCP 與 INP，兩者為 `UNKNOWN`，不得宣稱完整達標。
- Full pytest：286 passed。
- Python `compileall`：PASS。
- JavaScript syntax：PASS。
- Node 前端行為測試：20 passed。
- `git diff --check`：PASS（只有既存 LF→CRLF warning）。
- Packet SHA-256：`5bfb369395f10bd74bb4e1ed7b43093d0e2cc9f8855ffebfca33cf069941db11`。
- HG-LR-01 review SHA-256：`3642b635f95056a7173335b5c32d20d2933209d470e0b8993059d6e1a845a435`。
- HG-LR-02 review SHA-256：`1dc4676a371966e8bdf5514372dc0aa24e9ad3859f1766d6828f6c45e7af23f0`。

### DEPLOY

- `SKIPPED_WITH_REASON`：未取得外部部署授權。本輪只證明本機 `127.0.0.1` 最小運行閉環。

### MAINTAIN

- `P01`、`P03`、`P04`、`P05`、`P06` 與 `HG-LR-01` 至 `HG-LR-05` 仍維持人工核准邊界；本機功能通過不等於外部法律檢索或法律正確性通過。

## 2026-10-15：首頁改為摘要單一輸入

execution_mode: `SINGLE_EXECUTOR`
agent_mode: `SINGLE_AGENT_MODE`

### PLAN

- Input：移除首頁的時間類型、發生／破獲時間及發生／破獲地點三個欄位，改由使用者寫入案情摘要。
- Gate：不得從一般敘述猜測時間或地點；後續 Gate 1 與條陳仍須有可人工修正的明確值。

### DESIGN

- 摘要欄位提供可直接照抄的「發生／破獲／查獲時間：」「發生／破獲／查獲地點：」「案情經過：」格式。
- 後端只讀取明示標籤；標籤缺漏時保存 `UNKNOWN`。
- 舊 API 傳入 `event_kind`、`event_time`、`location` 時仍優先採用，維持既有案件與整合相容性。
- Gate 1 人工修正「時／地」後，同步更新條陳使用的 intake 值。

### BUILD

- `app/static/index.html`：移除三個首頁欄位，增加摘要 placeholder 與提示。
- `app/workflow.py`：新增明示標籤解析、`UNKNOWN` fail-closed 與 Gate 1 修正同步。
- `tests/test_workflow.py`：新增摘要標籤、缺漏 `UNKNOWN`、舊欄位優先及 Gate 1 修正測試。
- 重建 `LR-HG-20261015-04`、`HG-LR-01-REVIEW-20261015-03`、`HG-LR-02-REVIEW-20261015-03` 證據鏈；Human Gate 狀態未變。

### TEST

- 摘要單一輸入 targeted pytest：33 passed。
- Browser QA：三個舊欄位 selector 均為 0；摘要 placeholder 與提示可見；空摘要由瀏覽器 required validation 阻擋。
- Browser QA：明示「發生時間」「發生地點」後，Gate 1 的時、地分別完整帶入，並產生竊盜、侵占、搶奪／強盜／海盜候選。
- 375px、768px、1440px 均 HTTP 200、無水平溢位；console error 0、request failure 0；可見 controls 無未標籤項目。
- 視覺回歸沒有既有 baseline，狀態為 `INCONCLUSIVE`。
- Full pytest：289 passed；Python `compileall`、JavaScript syntax、Node 前端行為測試 20 passed 及 `git diff --check` 均為 PASS。

### DEPLOY

- `SKIPPED_WITH_REASON`：未執行外部部署；本機服務依專案 `start.ps1` 重新啟動。

### MAINTAIN

- 若摘要未使用明示標籤，後續時間、地點保持 `UNKNOWN`，必須在 Gate 1 人工補正；不得以候選或其他上下文推測。

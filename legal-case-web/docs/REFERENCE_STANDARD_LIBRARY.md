# Reference Standard Library

本文件作為已核准過的 `theft_320_1_movable` iteration 2 標準的存檔與索引。僅作為治理證據，不代表 runtime 生效，亦不代表下一個子路由已自動接續。

## 2026-10-14 theft_320_1_movable iteration 2

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

### 獨立審查決策

- R1：`ACCEPT_WITH_MODIFICATIONS`；`questions/theft.md` 實際存在，E2E timeout 隔離重跑通過，其餘結構缺口納入修正。
- R2：`ACCEPT`；角色實體化、trigger、mapping、dedupe 與聚合契約均需修正。
- R3：`ACCEPT_WITH_MODIFICATIONS`；先合法持有可提高侵占候選，但返還、拒還或處分等必要事實未齊時，聚合結果維持 `NEED_REVIEW`。
- R4～R6：`ACCEPT`；同意範圍、witness 知識邊界及 fail-closed 校準均納入修正。

### 驗證

- 問句契約、question logic 與 RCQ loader：47 passed。
- E2E套件：2 passed，文件下載測試於整組執行時 timeout；該測試隔離重跑為 1 passed。合計 50 個唯一測試已有通過證據，但不是同一次整組全綠。
- 法務部官方刑法頁面於 2026-10-14 回查成功；本紀錄不取代行為時法與人工法律審查。
- Runtime、題庫接線及下一罪章均未獲授權，也未修改。

### 設計決策

- 建立 8 個 `theft_320_1_movable` 標準，依序涵蓋自由敘述、原持有、同意、先合法持有、遺失狀態、突然力量、暴力脅迫及抗拒能力。
- 使用 canonical exact child route IDs，移除 fraud、damage 及所有 parent／alias route ID。
- 將暴力脅迫與抗拒能力拆成兩個單一事實，避免一題同時回答手段及程度。
- Transfer 的移送來源、既有筆錄及刑事訴訟法第95條權利告知獨立為程序題，不作為犯罪構成要件。

### 驗證

- `tests/test_question_work_item_contract.py`：5 passed。
- 問句 contract、question logic、RCQ loader、E2E：46 passed。
- Markdown相對連結：PASS。
- `git diff --check`：PASS。
- 法律 effects、語意去重、行為時法及接線仍需 Human Gate；runtime未修改。

---

### 獨立審查補強

- 決策：`ACCEPT_WITH_MODIFICATIONS`；題數計算矛盾屬 systemic rule defect，其餘 route、條號、schema 及問句缺陷由新 iteration 修正。
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
- 文件修正完成不等於候選 ruleset 已通過；`theft_320_1_movable`校準與 Human Gate仍為 `NOT_RUN`。

### 影響範圍

- `QUESTION_DESIGN_AND_USE.md`
- `AI_EXECUTION_PROTOCOL.md`
- `OFFENSE_QUESTION_WORK_QUEUE.md`
- `README.md`
- Runtime 程式、題庫與資料 schema：本輪未修改。

---

## 保留且不得改名

- `CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md`、`RCQ_Human REVIEW_WORKSHEET.md`、`SEMANTIC_TEST_SET_REVIEW_WORKSHEET.md`、`LIFECYCLE_RECORD.md`

### 合併與刪除映射

此文件僅用於保留已核准過的參考標準，不涉及刪除或覆蓋其他文件。

### BUILD

- Output：保留一份參考標準 Markdown（本文件）。
- Gate：未修改 runtime邏輯、資料 schema、法律題庫內容、資料庫或部署設定。

### TEST

- `MARKDOWN_LINKS_OK`：PASS。
- `NO_STALE_REFERENCES`：PASS；本文件除外。
- 目標測試首次結果：40 passed、1 failed；唯一失敗為文件下載等待逾時。
- 同一 E2E 案例重跑：1 passed。
- 完整 `pytest`：153 passed。
- Node 前端行為測試：15 passed。
- `node --check app/static/app.js`：PASS。
- `pyflakes app tests`：PASS。
- `data/*.json`解析：5 files PASS。

### Sol Review Decision

- execution_mode：`REVIEWED_PIPELINE`
- routing_triggers：`H2`、`S3`
- runtime_reported_model：`UNVERIFIED`
- R1：`ACCEPT`；保留五份單一責任 canonical 文件。
- R2：`ACCEPT`；保留兩份 RCQ 固定路徑及生命週期紀錄。
- R3：`ACCEPT_WITH_MODIFICATIONS`；保留語意測試人工工作表，其餘逐檔整併後刪除。
- R4：`ACCEPT`；以 runtime code／tests 說明目前行為，法律完整性維持未宣稱。
- R5：`ACCEPT`；以完整檔名、bytes 及 SHA-256留存刪除證據。
- final_status：`COMPLETE / REVIEWED_PIPELINE_UNVERIFIED`
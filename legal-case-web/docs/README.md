# 法律案件工作台文件索引

本目錄只保留目前有效的系統規範、法規維護入口、罪章工作佇列、人工審查資料與生命週期證據。其他 AI 不得從歷史報告或檔名自行推導目前行為。

## 1. 文件權威與閱讀順序

1. 使用者本次指令、適用的 `AGENTS.md` 與安全限制。
2. [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)：元件、runtime 資料來源、文件責任及信任邊界。
3. [QUESTION_DESIGN_AND_USE.md](QUESTION_DESIGN_AND_USE.md)：Gate 1–5、中性事實、候選路由、角色問句、回答重評估及 Human Gate。
4. [LAW_REGISTRY.md](LAW_REGISTRY.md)：穩定法規身分、別名、版本線索及 route 關聯。
5. [LAW_LIFECYCLE.md](LAW_LIFECYCLE.md)：新增法規、更新法規、條文分類與影響分析。
6. [OFFENSE_QUESTION_WORK_QUEUE.md](OFFENSE_QUESTION_WORK_QUEUE.md)：現有 44 個 parent routes 的拆分狀態與逐一製作順序。
7. [AI_EXECUTION_PROTOCOL.md](AI_EXECUTION_PROTOCOL.md)：交給其他 AI 的任務分類、執行提示詞與有限修正 loop。
8. [AI_HANDOFF_PROMPT.md](AI_HANDOFF_PROMPT.md)：下一位 AI 的唯一固定接手提示詞入口。
9. [QUESTION_WORK_ITEM.md](QUESTION_WORK_ITEM.md)：目前唯一罪章問句交付與審核工作檔。
10. 實際程式碼與測試：確認目前 runtime 行為。若與文件衝突，停止寫入並標記 `DOCUMENTATION_DRIFT`。

## 2. 使用者命令如何路由

| 使用者輸入 | 先讀文件 | 結果邊界 |
|---|---|---|
| `新增醫療法的相關罪章` | `LAW_REGISTRY` → `LAW_LIFECYCLE` | 先查重及官方版本，產生法規發現與覆蓋缺口；不直接批次建立罪名 |
| `更新某法` | `LAW_REGISTRY` → `LAW_LIFECYCLE` | 固定舊／新版本，逐條 diff 並列出受影響 route、問句、流程及測試 |
| `製作某罪章問句` | `OFFENSE_QUESTION_WORK_QUEUE` → `QUESTION_DESIGN_AND_USE` | 一次一個 child route，以中性事實與區分問句為核心 |
| `審核上輪結果` | `AI_EXECUTION_PROTOCOL` 與對應 domain 文件 | 同一工作單最多兩輪有界線修正 |

這些命令目前是 AI 維護規約，不是 Web 應用程式已具備的自然語言命令功能。

## 3. 核心法律流程

```text
角色＋自由敘述案情
        ↓
抽取中性事實，未明資訊保持 UNKNOWN
        ↓
產生一個以上候選法律路由
        ↓
依角色選出核心問句與區分問句
        ↓
回答補足構成要件或排除條件
        ↓
重新評估候選路由
        ↓
人工確認，不由系統直接定罪
```

前端採案情優先，避免誘導及過早定性；後端以已核准的法規與罪章覆蓋檢查漏問。兩者由中性事實、`fact_target` 與 `legal_targets` 連接。

## 4. 保留的審查資料

| 文件 | 類型 | Runtime 狀態 | 用途 |
|---|---|---:|---|
| `CRIMINAL_OFFENSE_ROLE_CORE_QUESTIONS_ALL.md` | review-only data | `runtime_enabled: false` | 443 題 RCQ 審查來源；`app/rcq_loader.py` 與測試使用固定路徑 |
| `RCQ_HUMAN_REVIEW_WORKSHEET.md` | human review worksheet | `runtime_enabled: false` | 承辦人逐題審核工作表；loader 使用固定輸出路徑 |
| `SEMANTIC_TEST_SET_REVIEW_WORKSHEET.md` | human review worksheet | 不接入 runtime | 語意測試案例的人工適當性審查 |
| `LIFECYCLE_RECORD.md` | governance evidence | 不接入 runtime | 階段、Gate、驗證、合併與刪除紀錄 |

`runtime_enabled: false` 表示不得注入正式問答流程，不表示檔案可以刪除。

## 5. 來源真實性規則

- `FACT`：由目前檔案、命令輸出、官方來源或測試直接證明。
- `INFERENCE`：由證據推導，但尚未由執行路徑或人工核准直接證明。
- `UNKNOWN`：尚無足夠資料。不得為了選出罪章而補成肯定或否定。
- 法規、版本、生效日與「可以提告」屬外部時效性資料，必須在該次任務以官方來源重新查證。
- 自動測試通過只證明受測程式行為，不證明法律內容完整、逐題適當或 Human Gate 通過。
- 問句製作採逐 route 的 Codex 審核與退修；使用者只在整個已授權 queue 完成後做最終驗收，不需逐章設定規則或核准下一罪章。實際案件的 Human Gate 仍由承辦人負責，不能被 AI 審核取代。
- 候選罪章不是定罪結果。系統不得自動輸出「犯罪成立」或「不成立」。

## 6. AI 修改規約

1. 新增／更新法規一次只處理一部法規；製作問句一次只處理一個明確 child route。
2. 先查既有登錄及 runtime，再查官方來源；不得建立重複 law 或 route。
3. 先建立中性事實與相鄰路由矩陣，再設計問句。
4. 製作問句的 AI 必須採「台灣刑事案件筆錄問句與詢問方法設計專家」角色；先開放敘述，再做單一事實釐清及證據追問。
5. 相鄰路由必須由 `distinction_axis` 選擇，不得只複製 parent route 的 `related` 清單。
6. victim、suspect、transfer 與 witness_review_only 必須依知識範圍分別設計，不得只換稱謂。
7. 保留公司三份通用範本、XLSM 公司罪章題、既有題號及 Human Gate。
8. 不得用新增大量問句掩蓋缺少區分能力的問題。
9. 單一內容錯誤同一根因最多修正兩次；共通規則錯誤改走 `SYSTEMIC_RULE_DEFECT`，停止佇列並重新校準基準 route。
10. 外部 AI 產出一律為 `DESIGN_DRAFT`、`runtime_enabled: false`、`CODEX_REVIEW_REQUIRED`。
11. 未通過下一罪章准入 Gate，不得進入下一個 child route。
12. 未獲明確授權，不得接線、部署、變更資料格式或刪除審查資料。

目前 `question-rules-v2-draft` 只是候選規則集，狀態為 `CODEX_REVIEW_REQUIRED / CALIBRATION_REQUIRED`；runtime 規則沒有因文件修改而自動變更。相鄰 child routes 必須由 canonical 規則與 Codex reviewer 鎖定的 allowlist 限制，規則集也不能藉 `SYSTEMIC_RULE_DEFECT` 無限重設 loop。

## 7. 文件責任與維護規則

| 內容 | 唯一維護位置 |
|---|---|
| 元件、runtime 來源、信任邊界 | `SYSTEM_ARCHITECTURE.md` |
| 案情到候選、問句、回答、重評估、Human Gate | `QUESTION_DESIGN_AND_USE.md` |
| 法規身分、別名、版本線索與 route 關聯 | `LAW_REGISTRY.md` |
| 新增／更新法規與條文分類 | `LAW_LIFECYCLE.md` |
| route 清單、拆分狀態與目前工作單元 | `OFFENSE_QUESTION_WORK_QUEUE.md` |
| AI 任務控制與有限 loop | `AI_EXECUTION_PROTOCOL.md` |
| 給下一位 AI 的固定接手提示詞 | `AI_HANDOFF_PROMPT.md` |
| 標準問句結構與當前罪章完整交付內容 | `QUESTION_WORK_ITEM.md` |
| 歷史證據 | `LIFECYCLE_RECORD.md` |

- 新增 Markdown 前，先確認上述文件無法容納該內容。
- 不在多份文件重複完整 schema 或流程；以連結指向唯一責任文件。
- 歷史輪次提示詞、協作信箱、一次性驗收報告與未核准設計稿不得再放回本目錄。
- 不為每個罪章新增 Markdown；重複使用 `QUESTION_WORK_ITEM.md`，審核前以 SHA-256 與生命週期紀錄保存可追溯證據。
- 每位 AI 停止前更新工作檔的 `last_completed_section`、`resume_from_section`、blockers 與最後驗證；下一位 AI 只從 checkpoint 接續。
- 法規登錄只作人類索引；runtime JSON、程式碼與測試仍需同步驗證。

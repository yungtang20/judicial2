# 法規登錄表

```yaml
document_status: ACTIVE_HUMAN_INDEX
runtime_enabled: false
product_source_of_truth:
  - data/question_bank.json
  - data/legal_route_crosswalk.json
conflict_policy: FAIL_CLOSED_DOCUMENTATION_DRIFT
```

## 1. 使用規則

本表提供穩定法規身分、別名、版本線索與 route 關聯，供新增／更新流程先查重。它不是 runtime 題庫，也不是現行法保證；實際產品行為以 JSON、程式碼與測試為準，法規現況仍須在每次任務中以官方來源重新查證。

`last_local_snapshot` 只表示專案資料所記錄的日期，不表示本次已聯網驗證。未列出的官方代碼、來源、完整條文範圍或生效沿革維持 `UNKNOWN`。

## 2. 必備欄位

每一筆法規至少維護：

```yaml
law_id: <穩定 ASCII id>
official_name: <正式名稱>
aliases: [<別名>]
jurisdiction: TW
issuing_authority: <主管或發布機關；UNKNOWN 可接受>
official_identifier: <官方法規代碼；UNKNOWN 可接受>
official_source: <官方 URL；UNKNOWN 可接受>
source_type: OFFICIAL_LAW_DATABASE|OFFICIAL_AGENCY|LOCAL_SNAPSHOT|UNKNOWN
verification_status: REGISTERED_LOCAL_SNAPSHOT|OFFICIAL_VERIFIED|STALE|UNKNOWN
last_verified_date: <YYYY-MM-DD；未查證為 UNKNOWN>
effective_intervals: [<版本、生效、廢止與未來生效沿革>]
article_scope: [<已登錄條文範圍>]
linked_routes: [<parent route_id>]
linked_question_sets: [<資料檔或問句來源>]
last_diff: <差異工作單或 NONE>
unknowns: [<待補項目>]
```

## 3. 目前登錄

| law_id | 正式名稱與別名 | 關聯 routes | 專案本機版本線索 | 狀態／待補 |
|---|---|---|---|---|
| `tw_criminal_code` | 中華民國刑法；別名：刑法 | `theft`、`aggravated_theft`、`embezzlement`、`fraud`、`injury`、`damage`、`intimidation`、`defamation`、`forgery`、`computer`、`public_danger`、`state_security`、`duty`、`obstruction`、`judicial_integrity`、`voting`、`disorder`、`escape`、`evidence`、`accusation`、`currency`、`securities`、`weights_measures`、`sexual`、`obscenity`、`marriage`、`graves_religion`、`agriculture_commerce`、`opium`、`gambling`、`homicide`、`abortion`、`abandonment`、`liberty`、`privacy`、`robbery` | `2026-07-22` | `REGISTERED_LOCAL_SNAPSHOT`；官方來源、完整版本沿革及行為時法範圍待當次查證 |
| `tw_sexual_harassment_prevention_act` | 性騷擾防治法 | `sexual_harassment` | `2023-08-16` | `REGISTERED_LOCAL_SNAPSHOT`；須區分刑事、行政與保護流程 |
| `tw_stalking_harassment_prevention_act` | 跟蹤騷擾防制法；別名：跟騷法 | `stalking` | `2021-12-01` | `REGISTERED_LOCAL_SNAPSHOT`；保護令與犯罪路由須分層 |
| `tw_narcotics_hazard_prevention_act` | 毒品危害防制條例 | `drugs` | `2022-05-04` | `REGISTERED_LOCAL_SNAPSHOT`；各行為態樣須拆 child route |
| `tw_human_trafficking_prevention_act` | 人口販運防制法 | `trafficking` | `2023-06-14` | `REGISTERED_LOCAL_SNAPSHOT`；犯罪、鑑別及保護流程須分層 |
| `tw_juvenile_justice_act` | 少年事件處理法 | `juvenile` | `2023-06-21` | `REGISTERED_LOCAL_SNAPSHOT`；程序路由，不得當作罪章題組 |
| `tw_domestic_violence_prevention_act` | 家庭暴力防治法；別名：家暴法 | `domestic_violence` | `2023-12-06` | `REGISTERED_LOCAL_SNAPSHOT`；保護、安全與實體罪章分流 |
| `tw_child_youth_welfare_rights_act` | 兒童及少年福利與權益保障法；別名：兒少權法 | `child_protection` | `UNKNOWN` | `REGISTERED_LOCAL_SNAPSHOT`；需核對與性剝削防制條例的範圍 |
| `tw_child_youth_sexual_exploitation_prevention_act` | 兒童及少年性剝削防制條例；別名：兒少性剝削防制條例 | `child_protection` | `2024-08-07` | `REGISTERED_LOCAL_SNAPSHOT`；多法規共同覆蓋，需人工調和 |
| `tw_gender_equality_employment_act` | 性別平等工作法；別名：性工法 | `gender_equality`、`sexual_harassment` | `2023-08-16` | `REGISTERED_LOCAL_SNAPSHOT`；職場行政與救濟流程不得冒充犯罪構成 |
| `tw_gender_equity_education_act` | 性別平等教育法；別名：性平法 | `gender_equality`、`sexual_harassment` | `UNKNOWN` | `REGISTERED_LOCAL_SNAPSHOT`；校園通報、調查與實體犯罪分流 |

`醫療法` 目前不在本表。收到「新增醫療法的相關罪章」時，應依 [LAW_LIFECYCLE.md](LAW_LIFECYCLE.md) 建立 `LAW_DISCOVERY_DRAFT`；不得僅因名稱未出現在本表就直接建立罪名或問句。

## 4. 版本與沿革維護

- 同一法規沿用同一 `law_id`；改名、別名或條號變動不得建立重複身分。
- 修法必須保留歷史版本、生效區間、尚未生效版本及廢止條文。
- 條文改號要保留 `previous_article`／`next_article` 沿革；拆分或合併要保留一對多／多對一關係。
- `FUTURE_EFFECTIVE` 不得覆寫目前有效版本。
- 只有當次官方查證完成時，才能將 `verification_status` 更新為 `OFFICIAL_VERIFIED` 並填入來源與日期。
- 法規新增或版本變動核准後，同步檢查 runtime JSON、問句、測試與 [OFFENSE_QUESTION_WORK_QUEUE.md](OFFENSE_QUESTION_WORK_QUEUE.md)。

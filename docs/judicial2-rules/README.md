# JUDICIAL2 規則手冊版本管理

本目錄保存 `JUDICIAL2_GATES_MANUAL.md` 的不可覆寫版本與相關工作紀錄。

封存狀態：`LOCAL_UNTRACKED_ARCHIVE`。目前以 SHA-256 驗證本機副本，政策上不得覆寫；在未經使用者授權建立 Git commit 前，尚未形成 Git 持久封存或技術上的不可竄改保證。

## 版本規則

1. 每次修改須建立新的版本檔。
2. 既有版本檔不得直接覆寫。
3. 新版本須在正文記錄 `版本` 與 `parent_version_id`。
4. 新版本須在本檔登錄來源、SHA-256 與保存狀態。
5. 法條查證批次不得與架構修正放在同一版本。
6. 缺少原始檔的版本須標記 `MISSING_SOURCE`，不得由後續版本反推重建。

## 版本索引

| 版本 | 父版本 | 保存檔案 | SHA-256 | 狀態 | 來源 |
|---|---|---|---|---|---|
| 2026-10-09-v13 | UNKNOWN | — | — | `MISSING_SOURCE / NOT_ARCHIVED` | 本機附件與 Git 歷史均未找到原文 |
| 2026-10-09-v14 | 2026-10-09-v13 | `versions/JUDICIAL2_GATES_MANUAL_2026-10-09-v14.md` | `01EBC794B2B65B4914B1003DE13AFFC051C71D6BEB50000341AF80AE6792F653` | `ARCHIVED` | 使用者附件原文 |
| 2026-10-09-v15 | 2026-10-09-v14 | `versions/JUDICIAL2_GATES_MANUAL_2026-10-09-v15.md` | `389620ADCDBA8D1007495215252C1DFA8CD5D0C37E8FF6FC6486920177746AA4` | `ARCHIVED` | 使用者附件原文 |
| 2026-10-09-v16 | 2026-10-09-v15 | `versions/JUDICIAL2_GATES_MANUAL_2026-10-09-v16.md` | `E2286406E4CEF91F94323A05C235CBFEEDA4EE8140EED0EAA50C97057D8A2A41` | `ARCHIVED` | 使用者附件原文 |
| 2026-10-09-v17 | 2026-10-09-v16 | `versions/JUDICIAL2_GATES_MANUAL_2026-10-09-v17.md` | `182BBCAA93EF651C0F98B78932B55808D8B3D0BDA5282DAF1449F79FB478A2CD` | `ARCHIVED` | `JUDICIAL2_GATES_MANUAL.md` 經附件正文逐位元組核對 |
| 2026-10-09-v18 | 2026-10-09-v17 | `versions/JUDICIAL2_GATES_MANUAL_2026-10-09-v18.md` | `3BD49B2D6D578D34127BE0A5EB1E1CDFD59796C287EFE968217AE58A63517412` | `ARCHIVED` | 使用者附件原文 |
| 2026-10-09-v19 | 2026-10-09-v18 | `versions/JUDICIAL2_GATES_MANUAL_2026-10-09-v19.md` | `9D4BC4E0B2043FD266BA472195B6B8B56F5DB769D7FA0F6B2E0FA24789B8E6A7` | `ARCHIVED` | 使用者指定之 12 組路由、規則、模板與法條資料修改 |

## 工作紀錄

- `external-data-request.md`：向受理單位索取模板、案號格式與通緝書資料的清單。
- `decision-gates.md`：D-01～D-03 已決定之台帳，以及 D-04～D-07 的 Human Gate。
- `law-verification-batch-01.md`：第一批法條查證的預備範圍與停止條件。
- `test-records/2026-10-09-v17-five-cases.md`：v17 附件所附五件測試摘要。

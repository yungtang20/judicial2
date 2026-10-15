# HG-LR-02 隱私與資安審查

## 審查結果

`CHANGES_REQUIRED_HUMAN_APPROVAL_PENDING`

本輪只審查離線法律檢索 PoC 的 query、adapter、cache、removal audit、batch 與 replay 資料流。沒有執行 live provider 呼叫、使用憑證、傳送案件資料、修改 runtime 或核准 `HG-LR-02`。Machine-readable review 位於 `docs/evidence/hg_lr_02_privacy_security_review.json`。

## 外部資料三格查證卡

1. 問句：2026-10-15 現行公開資料下，這套 PoC 是否足以把 outbound query、cache metadata 與 audit 宣稱為匿名且可安全接線？
2. 證據：本機執行路徑與測試、法務部全國法規資料庫的個資法及施行細則、`HG-LR-01` 已記錄的 provider 第一方政策。
3. 痕跡：法律適用仍取決於實際營運者、特定目的與當時有效版本，因此標記 `REQUIRES_ROLE_PURPOSE_AND_EFFECTIVE_VERSION_REVIEW`；本文件不作個資法合規結論。

## FACT：已證明的控制

- runtime 與 Gate 2 目前不可達，外部 adapter 在 network 前 fail closed。
- query 只接受 allowlisted child route、fact target 與有限 status；validator 會重建完整物件並作 exact equality 比對。
- cache schema 不保存 query text、全文、excerpt、case payload 或明示 personal-data 欄位。
- sync、batch 與 replay report 不輸出 query text、raw provider error、raw locator 或 traceback。
- removal reconciliation 要求 registry 精確命中，cache commit 使用原子替換及 integrity hash。

## FACT：阻擋核准的問題

| ID | 問題 | 現有證據 | 核准前處理 |
|---|---|---|---|
| `P01` | 公開裁判案號仍被持久化 | cache 的 title 含「100年度簡字第5635號」，canonical URL 含編碼 KSDM locator | 明確核准其為可保存公開 metadata，或改為 opaque record 加受控 resolution |
| `P03` | cache 為明文 JSON | 模組未強制 encryption、ACL、retention 或 verified deletion | 選擇 no-cache，或於 `HG-LR-03` 核准儲存控制 |
| `P04` | hosted provider 可能記錄 query | 第一方政策記載完整參數或 query text logging | 核准精確 outbound allowlist、目的、provider 與 retention |
| `P06` | 責任歸屬未定 | 尚無 purpose、retention、access、deletion、incident owner | 指定責任人及程序 |

## FACT：已修正、待審查

| ID | 修正 | 驗證狀態 |
|---|---|---|
| `P02` | route、fact-target 與 status 驗證只回傳穩定錯誤碼與欄位層級訊息，不再插入 caller-controlled value | 負向測試涵蓋未核准 route、任意 fact-target 與任意 status，並確認 exception 不含 sentinel；`REMEDIATED_ENGINEERING_REVIEW_REQUIRED` |

## INFERENCE

- `DEIDENTIFIED_BY_CONSTRUCTION` 只證明 query 沒有自由文字輸入通道，不等於法律或統計意義上的匿名資料。
- route 與 fact-status 組合仍可能揭露承辦人正在研究的罪章與爭點，應視為敏感法律工作 metadata。
- deterministic SHA-256 不能單獨證明匿名化；小型可枚舉輸入可能被反查，且 unkeyed hash 不是簽章。

## 法律來源邊界

- 個資法第 5 條要求不得逾越特定目的必要範圍，並須與蒐集目的具有正當合理關聯。
- 個資法施行細則第 12 條列出範圍界定、風險管理、事故應變、安全管理、稽核軌跡與持續改善等措施。
- 法規頁面同時標示部分修正條文尚未生效。本輪不判定未來營運者屬公務或非公務機關、不選定法律依據，也不宣稱已合規。

## Human Gate 狀態

- [ ] `HG-LR-02` 隱私或資安審查人核准資料邊界。

目前應維持 `PENDING`。`P02` 雖已完成工程修正，仍未取得人工核准；在 `P01`、明文 cache、hosted logging 與責任歸屬完成處理前，不得啟用外部查詢或持久化正式 cache。

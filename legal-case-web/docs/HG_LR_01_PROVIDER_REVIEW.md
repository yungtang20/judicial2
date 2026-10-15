# HG-LR-01 Provider 契約審查

## 審查結果

`PARTIAL_REVIEW_HUMAN_APPROVAL_REQUIRED`

本輪完成 provider 公開契約的證據盤點，但沒有核准 `HG-LR-01`，也沒有執行 live provider 呼叫、使用憑證、傳送案件資料、修改 runtime 或接入 Gate 2。Machine-readable review 位於 `docs/evidence/hg_lr_01_provider_contract_review.json`。

## 外部資料三格查證卡

1. 問句：限定查核台灣法律檢索來源的端點、回應契約、認證、使用條款、隱私、限流與移除規則；查核日為 2026-10-15。
2. 證據：只採 provider 第一方文件、官方機關頁面、官方 API 規格及原始 repository 文件；每個 provider 的 URL 均寫入 machine-readable review。
3. 痕跡：未找到固定 schema、數字限流、SLA、保存期間或自動化授權時明列 `UNKNOWN`／blocking unknown，不以網頁可開啟推定可供正式程式使用。

## Provider 決策矩陣

| Provider | 已確認 FACT | 主要 UNKNOWN | 本輪處置 |
|---|---|---|---|
| 司法院 JDoc | 官方 REST、六小時 Token、JList／JDoc schema、每日 00:00–06:00、同 JID 覆蓋及移除義務 | 帳號責任人、數字限流、SLA、正式刪除 runbook | `CONDITIONAL_OFFICIAL_SOURCE_CANDIDATE` |
| PSUE 公開書類 | 官方公開範圍、第一審判決後 14 日提供、書類正本優先 | 公開 machine endpoint、schema、認證、限流、自動化許可、移除訊號 | `DISCOVERY_ONLY_NOT_A_RUNTIME_PROVIDER` |
| Taiwan Law MCP | 公開測試 endpoint、Streamable HTTP、14 tools、免註冊／key／OAuth、MCP 查詢參數保存 90 日 | version-pinned output schema、數字限流、SLA、獨立 hosted terms、變更通知 | `CONDITIONAL_DISCOVERY_CANDIDATE` |
| TLR hosted | MCP／REST、OAuth dynamic registration、anchor bundle 欄位、hosted terms、可能記錄 query 與 IP-derived metadata | log 保存期、呼叫前數字限流、SLA、版本／變更通知、官方移除事件契約 | `CONDITIONAL_CITATION_RETRIEVAL_CANDIDATE` |
| mcp-taiwan-legal-db | 本機 MCP、可檢視 tool signatures、MIT code、CC0 structured dataset | 核准 release、各上游自動化接受度、local cache/cookie lifecycle、browser-only 相容性 | `SELF_HOST_EVALUATION_ONLY_NOT_BROWSER_DIRECT` |

## FACT

- 五個來源不是等價 fallback。它們分別是官方 API、公開查詢 UI、hosted MCP／REST 及 local MCP scraper。
- 司法院規格要求以帳密換取六小時 Token，服務時段為每日 00:00–06:00；裁判移除時，先前取得內容也必須刪除。
- PSUE 官方頁面說明公開書類範圍及參考性，但本輪未找到公開 machine API contract。
- Taiwan Law MCP 公開頁面列出 endpoint 與 14 個 tools；隱私政策說明完整查詢參數保存 90 日。
- TLR 文件提供 anchor bundle 欄位及 hosted terms；條款不保證可用性或正確性，且 rate limit 只說會在 API response 公告。
- mcp-taiwan-legal-db 是使用者本機發出請求的開源工具；集中式服務及上游規範責任由建置者承擔。

## INFERENCE

- 後續架構應拆成「搜尋／發現」與「官方文件核實」兩層，不可因搜尋命中便視為法律事實或罪章成立。
- PSUE 目前只能當人工 discovery source，不應用未公開的 HTML 行為建 runtime adapter。
- 在公司瀏覽器限制下，local MCP 不是可直接採用的前端方案；若要使用，仍需另行核准後端或地端服務部署。

## UNKNOWN / 核准前必要補件

- 系統負責人尚未選定 discovery provider 與 official verification path。
- 尚未凍結選定 provider 的精確 request／response fixture、版本及 schema drift 行為。
- 尚未指定憑證責任人、secret storage、timeout、retry、rate handling、circuit breaker 與來源移除 runbook。
- hosted provider 的 query 仍須先經 `HG-LR-02` 隱私／資安審查；不得送出案情全文、姓名、地址、識別碼或案號。
- 法律完整性、Gate 2 使用邊界與 runtime／UI 驗收分別屬 `HG-LR-04`、`HG-LR-05`，不在本輪成立。

## Human Gate 狀態

- [ ] `HG-LR-01` 系統負責人核准 provider 契約與連線方式。

本輪建議維持 `PENDING`。只有系統負責人選定來源並接受上述缺口或取得補件後，才可另立核准紀錄；不得直接改寫凍結封包或以本文件代替簽核。

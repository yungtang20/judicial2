# 法律檢索 PoC Human Gate 審查包

## 目前決定

`PENDING_HUMAN_APPROVAL`

本文件與 `docs/evidence/legal_retrieval_human_gate_packet.json` 只凍結目前離線 PoC 的工程證據，不授權外部 provider、runtime、Gate 2、正式案件或部署。

## FACT

- 核心檔案與四個 runtime surface 已列入 SHA-256 凍結清單。
- 固定 corpus 含四個合成情境，標記 `contains_case_data: false`。
- Golden replay 為 4 passed、0 failed。
- runtime surface 預期不得引用 `offense_linkage`、`legal_retrieval` 或 `legal_provider_fixtures`。
- 查詢、cache 與 replay 結果固定保留 `legal_conclusion: false` 及 `HUMAN_REVIEW_REQUIRED`。

## UNKNOWN

- 外部 provider 已完成第一輪公開契約盤點，但各來源仍缺少部分 version-pinned schema、固定限流、SLA、保存期間或自動化使用證據；詳見 `HG_LR_01_PROVIDER_REVIEW.md`。
- 法律內容完整性及正式機關對來源使用方式的接受程度。
- 正式 cache 保存期限、tombstone 解除、監控與事故處理方式。

## Human Gate checklist

- [ ] `HG-LR-01` 系統負責人核准 provider 契約與連線方式。
- [ ] `HG-LR-02` 隱私或資安審查人核准資料邊界。
- [ ] `HG-LR-03` 系統負責人核准正式 cache lifecycle。
- [ ] `HG-LR-04` 法律審查人核准 Gate 2 使用邊界。
- [ ] `HG-LR-05` 產品負責人核准 runtime／UI／稽核／失敗回復。

任一項未核准時，`decision_status` 必須維持 `PENDING_HUMAN_APPROVAL`。任何 frozen file 或 runtime surface hash 改變時，本證據包立即失效，必須重新執行測試與人工審查。

`HG-LR-01` 的公開證據 review 狀態為 `PARTIAL_REVIEW_HUMAN_APPROVAL_REQUIRED`；它不是核准紀錄。Machine-readable review：`docs/evidence/hg_lr_01_provider_contract_review.json`。

`HG-LR-02` 的資料流 review 狀態為 `CHANGES_REQUIRED_HUMAN_APPROVAL_PENDING`。目前已確認 cache 仍保存公開裁判案號線索；原 `P02` 無效輸入回顯已改為穩定錯誤碼並以負向測試鎖定，但尚未取得人工核准。詳見 `HG_LR_02_PRIVACY_SECURITY_REVIEW.md`。這不是核准紀錄。

## Packet integrity

- Machine-readable packet：`docs/evidence/legal_retrieval_human_gate_packet.json`
- Packet SHA-256：`4f8987ddd2ad9c0fdeded492fed78080aa7a288a80178e8468522b98b612065c`
- HG-LR-01 review：`docs/evidence/hg_lr_01_provider_contract_review.json`
- HG-LR-01 review SHA-256：`98c15cdcdaccb4915761ca06bec52412449aee4b1421bfcd22780a29507fe6b4`
- HG-LR-02 review：`docs/evidence/hg_lr_02_privacy_security_review.json`
- HG-LR-02 review SHA-256：`45b3c39f87133078713ad34d53b74010f20931d0b1bed6043cdb270769eeb3af`
- Corpus canonical SHA-256：`ad8e787338e35be3b72badf7588be437cb30a4636fabe8aee5f7e0e2ee6808ed`
- Golden suite evidence SHA-256：`eb7638295f9b9265ade2c9a35791894d9aeafcd49d0a7f7cf02f5db996a50b9b`

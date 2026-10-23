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
- Packet SHA-256：`77790711bd77a72082d13ab683976b42af1fb4e62291f5b542a26c441301369f`
- HG-LR-01 review：`docs/evidence/hg_lr_01_provider_contract_review.json`
- HG-LR-01 review SHA-256：`477b0e361835af91b4694991d33c076bbf824cc8eb0731d6ddae50dd5cf23f0d`
- HG-LR-02 review：`docs/evidence/hg_lr_02_privacy_security_review.json`
- HG-LR-02 review SHA-256：`63d44782d7c8f2fe3c3e91ec45568f25753c1dd1a4f78678a6ae7f8cfa17e984`
- Corpus canonical SHA-256：`ad8e787338e35be3b72badf7588be437cb30a4636fabe8aee5f7e0e2ee6808ed`
- Golden suite evidence SHA-256：`eb7638295f9b9265ade2c9a35791894d9aeafcd49d0a7f7cf02f5db996a50b9b`

上述三個 hash 由測試即時比對，文件若與檔案不一致即視為證據包失效：
`tests/test_hg_lr_01_provider_review.py`、`tests/test_hg_lr_02_privacy_security_review.py`、
`tests/test_legal_retrieval_human_gate_packet.py`。

## 2026-10-23 重新凍結（結論未變）

本輪新增三個**未接線**的候選契約，並已列入 `frozen_files`：

| 檔案 | 角色 | 狀態 |
| --- | --- | --- |
| `app/legal_provider_tlr_pack.py` | `tlr_pack_bundle_contract` | 尚待 `HG-LR-01` 覆核 |
| `app/provider_endpoint_policy.py` | `provider_endpoint_policy` | 尚待 `HG-LR-01`／`HG-LR-02` 覆核 |
| `deploy/providers/taiwan_law_mcp.json` | `provider_endpoint_config` | 尚待 `HG-LR-01`／`HG-LR-02` 覆核 |

- 三個檔案皆未被 `app/server.py`、`app/workflow.py`、`app/rules.py`、`app/static/app.js` 引用，runtime 仍不可達。
- `HG-LR-01`、`HG-LR-02` 的審查結論與 `decision_status` 均未改變，門檻仍為 `PENDING`。
- `V01` 通過數由 456 更新為 543（新增 87 個測試：法源多條號覆蓋、TLR pack 契約、自架端點政策、行為時法）。
- 依序重新綁定：packet → `HG-LR-01`（`packet_sha256`）→ `HG-LR-02`（`packet_sha256`、`provider_review_sha256`）。

行為時法（`app/law_version.py`、`data/law_amendment_history.json`、`data/sources/`）
不屬於本檢索包範圍，另見 `docs/HANDOFF_MANUAL.md` §9。

## 2026-10-23 第二輪重新凍結（檢索結論未變）

本輪把**行為時法**（非檢索功能）接入既有案件流程，因此動到兩個 runtime surface：

| Surface | 變更 | 對檢索的影響 |
| --- | --- | --- |
| `app/workflow.py` | `set_offenses` 逐條寫入 `law_version_audits` / `law_version_summary`；`update_gate1` 清除舊判定 | 無；未引用任何檢索模組 |
| `app/static/app.js` | 顯示逐條行為時法警示；`HINT_ONLY` 罪章標示「待區辨・非認定成立」 | 無；未引用任何檢索模組 |

- 四個 runtime surface 的 `expected_references` 仍為 `0`，`runtime_enabled` 仍為 `false`，`gate2_connected` 仍為 `false`。
- `HG-LR-01`、`HG-LR-02` 的 `decision_status` 與阻擋項均未改變，`approvals_required` 五項仍全為 `PENDING`。
- `V01` 通過數 543 → 563（新增 20 個測試：行為時法接入流程 8 個、`law_version` 輔助函式 12 個）；`V04` 26 → 29（新增逐條警示、查對未完成、`HINT_ONLY` 標示各 1 個）。
- 依序重新綁定：packet → `HG-LR-01`（`packet_sha256`）→ `HG-LR-02`（`packet_sha256`、`provider_review_sha256`）。

此節只記錄雜湊同步，**不是核准紀錄**；`HG-LR-05`（產品負責人核准 runtime／UI／稽核／失敗回復）仍為 `PENDING`。

## 2026-10-23 第三輪重新凍結（檢索結論未變）

本輪只修正**離線規則**（`app/rules.py` 的刑法 §321Ⅰ① 侵入住宅竊盜情境），並新增第五批回歸案例：

| Surface | 變更 | 對檢索的影響 |
| --- | --- | --- |
| `app/rules.py` | 補上「侵入訊號＋進入住宅＋取財」的 §321Ⅰ① 情境（白天自後門侵入不再只給 §320） | 無；純規則字串，未引用任何檢索模組 |

- 四個 runtime surface 的 `expected_references` 仍為 `0`，`runtime_enabled` 仍為 `false`，`gate2_connected` 仍為 `false`。
- `HG-LR-01`、`HG-LR-02` 的 `decision_status` 與阻擋項均未改變，`approvals_required` 五項仍全為 `PENDING`。
- `V01` 通過數 563 → 572（新增第五批 9 個測試：完整／缺事實／主體不明、侵入住宅 `HINT_ONLY` 限制、白天侵入召回、裸「進屋取物」與「夜間經同意入內」反向鎖定）；`V04` 維持 29。
- 依序重新綁定：packet → `HG-LR-01`（`packet_sha256`）→ `HG-LR-02`（`packet_sha256`、`provider_review_sha256`）。

此節同樣只記錄雜湊同步，**不是核准紀錄**；五個 Gate 仍為 `PENDING`。

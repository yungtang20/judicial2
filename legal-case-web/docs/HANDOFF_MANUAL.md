# 案情分析引擎交接手冊

## 0. 交接前提（先讀這一節，再讀本手冊其餘）

本手冊只描述「案情分析引擎」這個子系統的啟動、API 與維護方式，**不是整個專案的入口**。使用本手冊前，先確認下列前提。

### 0.1 本手冊不是專案入口

- 專案固定入口：`docs/AI_HANDOFF_PROMPT.md`（`document_status: ACTIVE_ENTRYPOINT`）。
- 執行控制層：`docs/AI_EXECUTION_PROTOCOL.md`（`document_status: ACTIVE_CONTROLLER`）。
- canonical 閱讀順序：`docs/README.md` §1 第 1–10 項。
- 唯一活躍工作槽位：`docs/QUESTION_WORK_ITEM.md`。
- 固定交棒指令：`請完整閱讀 D:\工作用\judicial1\legal-case-web\docs\AI_HANDOFF_PROMPT.md，並依檔案內容執行。`

若本手冊與上述文件衝突，以 `docs/README.md` §1 的閱讀順序與 canonical 文件為準，並依協定標記 `DOCUMENTATION_DRIFT` 後停止寫入。

### 0.2 本手冊不授權任何寫入

- 唯一允許寫入路徑：`docs/QUESTION_WORK_ITEM.md`。
- 本手冊第 5 節描述的是**規則維護原則與測試要求**，不是修改授權。
- `runtime_enabled: false`、`runtime_auto_advance: false`、`next_route: NOT_AUTHORIZED`。
- 不得批次產生 route；不得自行寫入 Human Gate 核准；不得變更 `legal_targets` allowlist 以外的路由。

### 0.3 禁止範圍

`.omo/quarantine/unauthorized-batch-20261014/` 內的檔案（含 `AGENTS.md.quarantined`、`BATCH_QUESTION_REVIEW.md`、`gen_work_item.py`、`QUESTION_WORK_ITEM.md.bak_orig`）**僅供稽核**：

- 不得讀為有效規則、不得執行、不得計入已完成 route。
- 2026-10-14 曾發生 14 條 route 的未授權批次，已隔離；接手者不得重演。
- 倉庫內目前**不存在**有效的 `AGENTS.md`（已依 MANIFEST 改名為 `.quarantined`）。文件提到「適用的 AGENTS.md」時，指的就是該隔離狀態，不得自建 `AGENTS.md`。

### 0.4 Human Gate 現況（不得自行改寫）

| Gate | 狀態 | 來源 |
|---|---|---|
| HG-LR-01 provider 契約審查 | `PENDING`（`PARTIAL_REVIEW_HUMAN_APPROVAL_REQUIRED`） | `docs/evidence/hg_lr_01_provider_contract_review.json` |
| HG-LR-02 隱私安全審查 | `PENDING`（`CHANGES_REQUIRED_HUMAN_APPROVAL_PENDING`） | `docs/evidence/hg_lr_02_privacy_security_review.json` |
| HG-LR-03／04／05 | `PENDING` | `docs/evidence/legal_retrieval_human_gate_packet.json` |

`decision_status: PENDING_HUMAN_APPROVAL`，且下列項目明確**未**宣稱：
`LEGAL_CORRECTNESS_APPROVED`、`RUNTIME_ENABLED`、`DEPLOYMENT_AUTHORIZED`、`PROVIDER_PRODUCTION_READY`、`GATE2_INTEGRATED`。

任何 AI 或接手者都不得把雜湊同步寫成「已核准」。雜湊一致 ≠ 人工核准。

### 0.5 版本控制相依（提交前必查）

2026-10-22 交接前，下列檔案**未被 git 追蹤，但已被工作樹引用**。漏掉任何一個，HEAD 會直接壞掉。已於 2026-10-22 的交接修復 commit 一併納入版控，但規則仍然有效：

| 檔案 | 若遺漏的破壞方式 |
|---|---|
| `legal-case-web/app/v3_contracts.py` | `app/ai.py`、`app/workflow.py` 皆 `from .v3_contracts import ...` → `ImportError` |
| `lawbank-engine.html`（**倉庫根目錄**） | `app/server.py` 以 `Path(__file__).resolve().parents[2]` 載入 → 獨立頁 404 |
| `legal-case-web/tests/test_case_batch_c001_c030.py` 等 3 檔 | 案例批次基準消失 |
| `legal-case-web/tests/test_v3_contracts.py` 等 | v3 契約無測試 |

`docs/evidence/legal_retrieval_human_gate_packet.json` 的 `runtime_surfaces` 雜湊指向 `app/server.py`、`app/workflow.py`、`app/rules.py`、`app/static/app.js` 的**特定版本**。這四個檔案與 evidence 必須在同一個 commit 內變更，否則乾淨 clone 上的 `tests/test_legal_retrieval_human_gate_packet.py` 會失敗。

不在本專案範圍內的倉庫根目錄項目：`reasoning-flow/`（獨立專案，README 明載與 `legal-case-web` 互不依賴）與 `例子/`（個人截圖）。兩者目前皆未追蹤，**不要**順手 `git add .` 一併提交。

### 0.6 部署與個資邊界

- 本機：`.\start.ps1` → `http://127.0.0.1:8787/`。
- 遠端：Render / Koyeb 部署面另有 invite-only 註冊與 `AUTH_REQUIRED`。
- `web_app/`（Next.js）另有 `llm-proxy`，`app_prototype/`（Streamlit）讀取 `HCNSEC_API_KEY`；兩者都不在本手冊的測試流程內，但同屬本倉庫。
- 真實個資、完整卷證、未去識別化資料一律不得輸入本機測試環境或任何外部模型端點。

## 1. 專案定位

本專案是臺灣刑事案件的候選罪名與證據缺口分析工具。系統只輸出候選方向，不取代承辦人、律師或司法機關的法律判斷。

主要流程：

1. 接收去識別化案情。
2. 從罪名清單產生 1～4 個候選罪名。
3. 判定主體、被害人與案件進度狀態。
4. 以本機規則式 fallback 保留可用結果。
5. 依本機法條快照提供法源與要件缺口。
6. 由前端顯示候選、證據缺口、問句與分析結果。

## 2. 目錄與責任

| 路徑 | 用途 |
|---|---|
| `app/rules.py` | 規則式候選罪名、關鍵詞、要件錨點與安全護欄 |
| `app/ai.py` | Prompt builder 與模型輸出契約（含 v3 契約 envelope） |
| `app/v3_contracts.py` | v3 JSON 結構驗證與 canonical SHA-256 |
| `app/workflow.py` | 案情分析流程、模型失敗時的 fallback |
| `app/server.py` | HTTP API、靜態頁面與 `/api/analyze` |
| `app/static/` | 主要工作台前端 |
| `app/storage.py` | 案件儲存（現況：記憶體 `EphemeralCaseStore`） |
| `app/accounts.py`、`app/security.py` | 帳號、session、登入鎖定與請求防護 |
| `app/documents.py` | 問卷／摘要 docx 生成與頁數驗證 |
| `app/legal_retrieval*.py` | 去識別查詢、metadata cache、batch／replay／sync（離線 POC） |
| `data/` | 本機法規與題庫資料 |
| `tests/` | 單元、語意安全、案例批次與 Human Gate 測試 |
| `docs/evidence/` | 法規來源、Human Gate 與雜湊鏈證據 |
| `docs/AI_HANDOFF_PROMPT.md`、`docs/AI_EXECUTION_PROTOCOL.md`、`docs/QUESTION_WORK_ITEM.md` | **專案 canonical 治理鏈，優先於本手冊** |
| `lawbank-engine.html`（**倉庫根目錄**） | 獨立示範／API 測試頁，由 `app/server.py` 以 `parents[2]` 載入 |

## 3. 啟動方式

在 `D:\工作用\judicial1\legal-case-web` 執行：

```powershell
.\start.ps1
```

啟動腳本會比對 `app/`、`app/static/`、`data/question_bank.json` 的最新 mtime；來源變更時會自動重啟既有服務後再就緒。

啟動後可使用：

- 主要工作台：`http://127.0.0.1:8787/`
- 獨立頁面：`http://127.0.0.1:8787/lawbank-engine.html`

獨立頁面有兩種模式：

- 示範模式：使用固定資料，不呼叫 API。
- 真實 API：呼叫本機 `/api/analyze`。

本機預設 `AUTH_REQUIRED=false`（`app/config.py`），此時 `/api/*` 不需登入；設定 `AUTH_REQUIRED=true` 或部署到遠端時，除 `/api/health`、`/api/auth/status` 外，其餘 `/api/*` 一律需要已登入 session。

## 4. API

### `POST /api/analyze`

請求 JSON：

```json
{
  "case_text": "甲持刀要求乙交付款項。"
}
```

也接受 `summary` 欄位。案情不可為空，此端點長度上限為 5000 字元（`app/server.py` 內硬編）。

回應（實測形狀，勿依記憶引用）：

| 欄位 | 內容 |
|---|---|
| `candidate_result` | 內含 `candidates`（含 `name`、`reason`、`missing`）與 `status` |
| `status` | `subject_identified`、`has_victim`、`is_solved`，值為字串 `"true"`／`"false"`／`"unknown"` |
| `analysis` | `summary`、`per_offence`（`elements`／`similar_crimes_excluded`／`prosecution`／`evidence_hints`／`practical_risk`）、`detailed_analysis`、`conclusion` |
| `laws` | **僅列出本機快取有驗證內容的法條**（`tags: ["VERIFIED_CACHE"]`）；查無者**直接省略**，不會回 `NOT_FOUND` |
| `meta` | 中文鍵：`模式`、`候選罪章`、`法條快取`（**沒有** `meta.mode`） |
| `mode` | 頂層字串，本端點**恆為** `"rules-fallback"` |

重要：`/api/analyze` 走 `app/server.py` 的 `_local_analysis_payload()`，是**本機規則式**分析，沒有模型路徑。`meta.mode` 與「模型／rules-fallback 二選一」的描述不適用於此端點；`NOT_FOUND` 狀態只出現在 `/api/question-bank` 的 `article_content_status`。

### 其他端點

| 端點 | 說明 |
|---|---|
| `GET /api/health` | 存活與 `source_mtime`，免認證 |
| `GET /api/auth/status` | 認證狀態，免認證 |
| `POST /api/auth/register`、`POST /api/auth/login` | 需 invite code；含登入失敗鎖定 |
| `GET/POST /api/cases` | 案件清單／建立。摘要上限 500 字元（`MAX_SUMMARY_LENGTH`） |
| `POST /api/cases/{id}/actions` | 動作套用，需帶 `revision` |
| `GET /api/cases/{id}/documents/{role}/{kind}` | 問卷／摘要 docx（`role`：`victim`／`suspect`／`transfer`；`kind`：`interview`／`brief`） |
| `GET /api/cases/{id}/brief/{role}` | 摘要文字 |
| `GET /api/question-bank` | 題庫與法條快取狀態（`VERIFIED_CACHE`／`NOT_FOUND`） |

案件資料存於記憶體（`EphemeralCaseStore`），重啟即失效；docx 以位元組串流回應，不落地。`data/cases.sqlite3` 為既存檔案且已 gitignore，不是本 API 的預設落地位置。頁數驗證需本機具備 LibreOffice（`soffice.exe`）。

## 5. 規則式 fallback 維護原則

> 本節是維護原則與測試要求，**不是修改授權**；授權邊界見 §0.2。

修改 `app/rules.py` 前，先確認：

1. 是否只根據案情原文，不自行補人物、時間、動機。
2. 是否把「主體不明」放進 `missing`。
3. 是否優先辨識加重條件。
4. 是否避免沒有對人施暴時誤列強盜。
5. 是否保留候選而非輸出犯罪成立結論。
6. 是否加入對應回歸案例與反向安全案例。

目前已涵蓋的主要方向：竊盜、加重竊盜、強盜、詐欺、傷害、恐嚇、誹謗、公然侮辱、妨害公務、侵入住宅、毀損、跟蹤騷擾等。

## 6. 測試流程

完整測試（單次 session 全綠）：

```powershell
py -3 -X utf8 -m pytest -q
```

目前基準：**456 passed**（2026-10-22 單次實測，`py -3 -X utf8 -m pytest -q`）。`-X utf8` 為必要參數，否則中文輸出會亂碼。

前端與靜態檢查：

```powershell
node tests/test_frontend_api_errors.mjs   # 29 passed
node --check app/static/app.js
py -3 -X utf8 -m compileall -q app tests
git diff --check
```

案例批次：

```powershell
py -3 -X utf8 -m pytest -q tests/test_case_batch_c001_c030.py tests/test_case_batch_c031_c060.py tests/test_case_batch_c061_c090.py tests/test_case_batch_c091_c120.py
```

新增規則時，至少同時加入：

- 完整事實案例。
- 缺事實案例。
- 主體不明案例。
- 不應誤列該罪名的反向案例。

**四類缺一不可，且每批都要附允許集合（allowed set）反向檢查。** 既有契約只斷言「預期候選有出現」，多餘候選不會讓測試失敗——2026-10-22 之前因此長期漏掉三種誤列。每批另需一項 `test_*_no_unexpected_extra_candidates`：集合外的候選即為誤列，必須讓測試失敗。

允許集合內的項目是**相鄰競爭假設**（供人工區辨），不是誤列，但每次異動都須人工複核。

### 6.1 證據鏈重算（可重現）

`docs/evidence/` 內的雜湊鏈必須在每次交接或提交前重算。本機預設 `AUTH_REQUIRED=false`，`/api/health` 免認證。

在 `D:\工作用\judicial1\legal-case-web` 執行：

```powershell
$packet = Get-Content docs\evidence\legal_retrieval_human_gate_packet.json -Raw | ConvertFrom-Json
$surfaces = @($packet.frozen_files) + @($packet.runtime_surfaces)
$bad = 0
foreach ($f in $surfaces) {
    $h = (Get-FileHash $f.path -Algorithm SHA256).Hash.ToLower()
    if ($h -ne $f.sha256) { Write-Output "MISMATCH $($f.path)"; $bad++ }
}
$pk = (Get-FileHash docs\evidence\legal_retrieval_human_gate_packet.json -Algorithm SHA256).Hash.ToLower()
$r1 = (Get-FileHash docs\evidence\hg_lr_01_provider_contract_review.json -Algorithm SHA256).Hash.ToLower()
$r2 = Get-Content docs\evidence\hg_lr_02_privacy_security_review.json -Raw | ConvertFrom-Json
if ($r2.packet_sha256 -ne $pk) { Write-Output "MISMATCH hg_lr_02.packet_sha256"; $bad++ }
if ($r2.provider_review_sha256 -ne $r1) { Write-Output "MISMATCH hg_lr_02.provider_review_sha256"; $bad++ }
if ($bad -eq 0) { "EVIDENCE CHAIN OK ($($surfaces.Count) surfaces + 2 review links)" } else { "EVIDENCE CHAIN BROKEN: $bad" }
```

重算後必須同步更新 review 檔內的 `packet_sha256`／`provider_review_sha256`，順序為：packet → `hg_lr_01` → `hg_lr_02`。**只更新雜湊指標，不得改動任何 `decision_status`、`human_gate_status`、`claims_not_made` 或審查內容。**

### 6.2 證據檔行尾

`.gitattributes` 為 `* text=auto eol=lf`，證據 JSON 必須以 **LF** 儲存，雜湊才會在 commit 後與工作樹一致、在新 clone 可重現。若以 CRLF 寫入，工作樹雜湊會與 committed blob 不同，`tests/test_hg_lr_01_provider_review.py`、`tests/test_hg_lr_02_privacy_security_review.py` 會在乾淨 clone 上失敗。

## 7. 法規與 Human Gate

- 法條顯示應以本機已驗證快照為準。
- `NOT_FOUND` 不得憑記憶補法條原文。
- Human Gate 雜湊同步只代表證據鏈一致，不代表人工核准。
- 不得為了讓測試通過而 skip、xfail、刪除 assertion 或繞過 Gate。
- `docs/evidence/legal_retrieval_human_gate_packet.json` 的 `verification` 區段是**已重跑的證據紀錄**；修改 `verification` 數值時，必須同步更新 `tests/test_legal_retrieval_human_gate_packet.py` 內對應的固定值，並重跑完整測試。

相關檔案：

- `docs/evidence/legal_retrieval_human_gate_packet.json`
- `docs/evidence/hg_lr_01_provider_contract_review.json`
- `docs/evidence/hg_lr_02_privacy_security_review.json`
- `docs/HG_LR_01_PROVIDER_REVIEW.md`
- `docs/HG_LR_02_PRIVACY_SECURITY_REVIEW.md`
- `docs/LEGAL_RETRIEVAL_HUMAN_GATE.md`

## 7.1 2026-10-23 新增（行為時法已接入，其餘未接線）

本輪補齊四項缺口。三個檢索相關模組仍未接線：`app/server.py`、`app/workflow.py`、`app/rules.py`、`app/static/app.js` 皆未引用 `offense_linkage`、`legal_retrieval`、`legal_provider_fixtures`，`tests/test_legal_retrieval_human_gate_packet.py` 會持續驗證這件事（`expected_references: 0`）。

**行為時法（`app/law_version.py`）不屬於檢索包，已於本輪接入 `set_offenses` 與前端警示區**；它只讀本機沿革快照，不連外、不含案件資料、不重建歷史條文。詳見下方「行為時法接入位置」。

| 模組／資料 | 用途 | 邊界 |
|---|---|---|
| `app/law_reference.py`（多條號解析）＋ `data/law_reference_cache.json` | 題庫 `article_no` 為「第100條至第119條」「第2條、第25條」時可展開查詢；**全部**條號都在快取才算命中，缺一即 `NOT_FOUND` | 只回快取內容，不生成條文 |
| `app/legal_provider_tlr_pack.py` ＋ `tests/fixtures/tlr_pack_bundle_v1.json` | `twlegalrag pack`（`twlegalrag.bundle/v1`）離線契約：bundle 必須綁定本次去識別查詢、全文未截斷、JID 已登錄，才會產生 hit | 只輸出 citation metadata 與摘錄 hash；判決文字不出模組 |
| `app/provider_endpoint_policy.py` ＋ `deploy/providers/taiwan_law_mcp.json` | Taiwan Law MCP 只允許 loopback 自架端點；hosted 端點記錄為不可選（HG-LR-02 `P04`） | `runtime_ready()` 恆為 false（HG-LR-05 未核准） |
| `app/law_version.py` ＋ `data/law_amendment_history.json` ＋ `data/sources/moj_law_history_C0000001.html` | 行為時法判定：事件日是否早於該條號的增訂／修正／刪除 | 不重建歷史條文；`historical_text_in_repo: false`；已接入案件流程（見下） |

指令：

```powershell
# 法源快取：離線檢查／線上補齊（後者會連外，需先確認可連線）
py -3 -X utf8 scripts\backfill_law_reference_cache.py --check
py -3 -X utf8 scripts\backfill_law_reference_cache.py --fetch --delay 0.3

# 行為時法查對
py -3 -X utf8 scripts\law_version_check.py --article 第320條 --event-date 2010-01-05
py -3 -X utf8 scripts\law_version_check.py --article 185-3 --event-date 2010-01-05 --json

# 沿革快照：離線驗證不可漂移／重新擷取官方頁
py -3 -X utf8 scripts\capture_law_amendment_history.py --check
py -3 -X utf8 scripts\capture_law_amendment_history.py
```

行為時法的判定值：

| 判定 | 意義 |
|---|---|
| `CURRENT_VERSION_APPLIES` | 事件日在該條號最後一次修正生效之後 |
| `HISTORICAL_VERSION_REQUIRED` | 事件日之後仍有修正（含「早於首次修正、適用制定時原文」） |
| `ARTICLE_NOT_YET_IN_FORCE` | 事件日當時該條號尚未增訂 |
| `ARTICLE_NOT_IN_FORCE_AT_EVENT_TIME` | 事件日當時該條號已刪除 |
| `NO_AMENDMENT_RECORDED` | 官方沿革頁無該條號異動紀錄 |
| `VERSION_HISTORY_INCOMPLETE`／`EVENT_DATE_UNKNOWN` | 資料不足；不以推測補值 |

全部結果均帶 `legal_conclusion: false`、`review_status: HUMAN_REVIEW_REQUIRED`。沿革頁只記載條號與日期，**不含**舊條文；`HISTORICAL_VERSION_REQUIRED` 只指出應調閱哪一筆，不提供條文文字。

### 行為時法接入位置

`set_offenses` 會對**已選罪章**的刑法條號（主條文＋`related_articles`，多條號先以 `parse_article_spec` 展開）逐條判定，寫入案件：

| 欄位 | 內容 |
|---|---|
| `law_version_audits[]` | 每筆含 `offense_id`、`article`、`article_no`、`status`、`historical_text_required`、`legal_conclusion: false` |
| `law_version_summary` | `status`（`AUDIT_COMPLETED`／`AUDIT_UNAVAILABLE`）、`by_status`、`historical_text_required_count`、沿革快照來源與 `raw_html_sha256` |

- 只查 `中華民國刑法`／`刑法`（`matches_law`）；其他法規不套用刑法沿革，避免誤判。
- 快照缺失或毀損時寫入 `AUDIT_UNAVAILABLE` 並記 `LAW_VERSION_AUDIT_UNAVAILABLE` 稽核事件，**不中斷** `set_offenses`，也不得解讀為「無須調閱」。
- 單次最多判定 `MAX_VERSION_AUDIT_ARTICLES`（80）筆；超出部分列在 `summary.skipped` 並標 `truncated: true`。
- `update_gate1` 會清空 `temporal_law_warnings`、`law_version_audits`、`law_version_summary`：行為日或罪章變動後不得沿用舊判定。
- 前端 `renderWarnings` 逐條顯示「行為時法（第X條）：…請依官方沿革調閱…並人工覆核」，同一條號同一判定只提示一次；`AUDIT_UNAVAILABLE` 也會顯示，不靜默。

`TlrPackCliClient` 在建構時讀取證據包 `decision_status`；目前為 `PENDING_HUMAN_APPROVAL`，因此 live 呼叫在正式環境一律建構失敗。`--check` 一律離線，重解析 `data/sources` 內的原始頁面並與快照逐欄位比對。

## 8. 已知限制

1. 候選罪名是分類方向，不是正式法律結論。
2. 規則式 fallback 依文字訊號工作，仍需人工審核要件與證據。
3. 外部法規 MCP 尚未接入此 API 路徑。
4. Prompt 2 已提供 lawbank 風格結構，但目前主要流程仍以既有分析流程為主。
5. 真實個資、完整卷證與未去識別化資料不得輸入測試環境。
6. 本手冊只涵蓋案情分析引擎；罪章問句設計流程、`web_app/`、`app_prototype/`、部署面均不在本手冊範圍，見 §0.1 與 `docs/README.md`。
7. 測試通過只證明工程行為符合規格，**不代表法律正確**；法律正確性只能由官方來源與人工 Gate 認定（`AI_EXECUTION_PROTOCOL.md` §4）。
8. `/api/analyze` 目前無模型路徑，恆為規則式輸出。

## 9. 交接後建議順序

1. 先執行完整 pytest，確認基準仍為 572 passed（單次 session）。
2. 執行 §6.1 證據鏈重算，確認 17 個 surface（13 frozen + 4 runtime）與 2 條 review 連結皆一致。
3. 以 `lawbank-engine.html` 測試 API 與前端顯示。
4. 修改規則後先跑對應批次，再跑完整測試。
5. 若修改 `app/rules.py`、`app/server.py` 或 `app/workflow.py`，同步檢查 Human Gate 雜湊並重算 §6.1。
6. 任何法規原文更新都要保留來源、版本、日期與查詢痕跡。
7. 提交前確認 §0.5 的未追蹤相依檔案已一併納入版控，且 evidence 檔為 LF 行尾。

## 10. 交接狀態

- 功能測試：通過。
- 完整測試：572 passed（2026-10-23 單次 session 實測）。
- 案例批次 C001–C090：通過（已補允許集合反向檢查）。
- 案例批次 C091–C125：通過（完整事實／缺事實／主體不明／反向安全四類齊備）。
- 案例批次 C126–C155：通過（10 個方向 × 完整事實／缺事實／主體不明；另含侵入住宅 HINT_ONLY 限制與 §321Ⅰ① 白天侵入的反向鎖定）。
- 前端錯誤處理測試：29 passed。
- Python 編譯檢查：通過。
- 證據鏈重算：17 surfaces（13 frozen + 4 runtime）+ 2 條 review 連結全數一致。
- 證據檔行尾：已正規化為 LF，與 `.gitattributes` 一致。
- Human Gate：維持人工審核邊界，未宣稱已核准（HG-LR-01／02／03／04／05 皆 `PENDING`）。
- 2026-10-22 交接修復：手冊補上 canonical 治理鏈與授權邊界、修正 API 描述、補上可重現的證據重算指令、將未追蹤相依檔案納入版控、對帳 evidence `verification` 基準（V01 289→444→452→455→456、V04 20→26）、evidence 檔正規化為 LF 使乾淨 clone 可重現雜湊鏈。
- 2026-10-22 規則修正（第四批 C091–C120 複審後）：轉述指控護欄放寬到代稱主體（乙／另一方／被害人等）並補上「散布／謠傳／爆料」謂語、引述區間改為自被指控主體起算（不再把「貼文」本身圈入）、弱關鍵詞護欄（稱呼「騙子」不成立詐欺、被指控的「侵占」不成立侵占、被害人發現「遺失」不成立侵占）、否定窗口補上緊接式否定（「未受傷」「未毆打」不成立傷害且不誤傷未成年人條款）、排序時單字關鍵詞命中不再壓過具體行為命中。
- 2026-10-22 規則修正（續二）：否定窗口補上**情境提示層**（關鍵字層先前已套用，提示層未套用，導致「甲未取走任何財物」仍產生竊盜候選）；情境提示層與模型補充項一律改以未被否定的命中為準。
- 2026-10-22 規則修正（續）：強盜方向成立時，竊盜／侵占／恐嚇危害安全降為 `HINT_ONLY` 相鄰競爭假設（以「強盜候選是否成立」為準，避免另立判準）；妨害名譽的散布不實內容情境不再以「名譽受損」未出現為由否定整個方向（該項並非題庫對妨害名譽所追的要素），並補上散佈／發布等異體。
- 2026-10-22 第四批案例標籤更正：C095 由「強盜」更正為「竊盜」（無對人施暴，與既有 C065 鎖定結論一致）、C096 由「加重強盜」更正為「強盜」（刑法無加重強盜此獨立罪名）、C106–C108 由「公然侮辱／誹謗」對應為題庫的妨害名譽。
- 2026-10-23 缺口補齊（四項；當時皆未接線）：① 法源快取多條號解析（`第100條至第119條` 這類 spec 過去被當成單一條號，導致 14 個條目永遠 `NOT_FOUND`）＋ 88 筆回填，快取 105→193 筆；② `twlegalrag pack` 的 `twlegalrag.bundle/v1` 離線契約（綁定去識別查詢、只輸出 citation metadata 與摘錄 hash、截斷全文不得引用、live 客戶端受證據包 `decision_status` 約束）；③ Taiwan Law MCP 自架端點政策（僅 loopback 可選，hosted 端點記錄為不可選，`runtime_ready()` 恆 false）；④ 行為時法判定（官方沿革頁快照、中文數字與條號範圍解析、分段施行留 `null` 不以推測補值）。測試 456 → 469 → 487 → 501 → 543；證據鏈重新凍結（packet → HG-LR-01 → HG-LR-02），三個新檔案列入 `frozen_files`。
- 未追蹤且刻意不提交：`reasoning-flow/`（獨立專案）、`例子/`（個人截圖）。
- 2026-10-23 行為時法接入（第二輪）：`set_offenses` 逐條寫入 `law_version_audits`／`law_version_summary`，前端警示區逐條顯示並提示人工調閱；沿革資料不可用時寫 `AUDIT_UNAVAILABLE`（不靜默、不中斷分析）；`update_gate1` 清除舊判定。`HINT_ONLY` 罪章在選單改標「待區辨・非認定成立」，候選區改用引擎提供的相鄰競爭假設說明。測試 543 → 563、前端 26 → 29；證據鏈再次重新綁定（packet → HG-LR-01 → HG-LR-02），檢索 runtime 仍不可達、五個 Gate 仍 `PENDING`。
- 2026-10-23 第五批案例與召回修正（第三輪）：新增 `tests/test_case_batch_c126_c155.py`（原始需求編號 C121–C150，因 C121–C125 已由第四批使用，順延為 C126–C155）。修正刑法 §321Ⅰ①「侵入住宅」漏接：舊情境把侵入與夜間／工具綁在一起，清晨自未上鎖後門侵入行竊只得到 §320；新分支要求「侵入訊號＋進入住宅＋取財」三者同時成立，避免經同意進入後臨時起意行竊被誤升。侵入住宅（§306）因題庫無獨立項目，仍只以 `HINT_ONLY` 呈現並附保留說明。測試 563 → 572；證據鏈第三輪重新綁定，檢索 runtime 仍不可達、五個 Gate 仍 `PENDING`。

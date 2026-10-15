# 法律案件工作台

本專案是獨立、本機優先的 Gate 1–5 工作台。它不會復原父目錄中已刪除的舊系統檔案，也不會把案件內容送往外部 AI。

## 啟動

需求：Windows、Python 3、LibreOffice，以及 `requirements.txt` 中的套件。

```powershell
cd D:\工作用\judicial1\legal-case-web
py -3 -m pip install -r requirements.txt
.\start.ps1
```

網址固定為 `http://127.0.0.1:8787/`。服務不監聽外部網路介面。

## 已實作流程

1. 首頁只輸入案情摘要；請在摘要內以「發生／查獲時間：」「發生／查獲地點：」「案情經過：」寫明資料（進階欄位收合）。未明示標籤時，時間或地點會保留為 `UNKNOWN`，不自行猜測。
2. Gate 1 先從自由敘述抽取中性事實。沒有證據支持的原持有、同意、保管、取得手段、返還約定及主觀意圖維持 `UNKNOWN`。
3. Gate 2 以規則或 AI（api.iamhc.cn，OpenAI 相容）提出零個或多個候選罪章；候選只代表待區分方向，不代表犯罪成立。
4. 承辦人分別確認候選罪章與 child legal route。兩者原子保存；目前 child route 僅作為法律脈絡，問句覆蓋狀態維持 `PARENT_PACK_ONLY / NONE`。
5. 系統依角色及候選方向選出核心問句與區分問句。每題同時連結 `fact_target` 及 `legal_targets`。
6. 回答的自由文字只保存為陳述。只有操作人員明確選擇的 `YES`、`NO` 或 `UNKNOWN` 事實狀態會觸發候選重評估；衝突資訊維持 `NEED_REVIEW`。
7. Gate 2 同頁填寫受詢問人年籍與詢問起訖時間，問答採逐題呈現（上一題／下一題／進度）。
8. Gate 2.5 依規則顯示證明單、婦幼及 165 案號欄位。
9. Gate 3 產生被害人筆錄及條陳。
10. 同一案件可繼續 Gate 4 的涉嫌人問答及文件。
11. 無被害人案件使用 Gate 5 移送分支。
12. 重新開啟案件時保存舊核准快照，並使後續核准失效。

## 法律與人工核准邊界

- 候選引擎為確定性規則，或外部 AI 分類；兩者都不是法律判斷。
- 系統可以安全回傳零候選。
- 候選初始為 `NEED_REVIEW`；只有具明確 answer mapping 的回答可使其成為 `ACTIVE` 或 `LOWERED`，三種狀態都不代表犯罪成立或排除。
- 題庫維持 `HUMAN_REVIEW_REQUIRED`，並於啟動時載入父目錄 `questions/` 中已核實的全罪章 Markdown 問句（核心／補充／補強／區分／加重分節載入）。
- 公司三份範本（通用被害人、通用涉嫌人、移送涉嫌人）之必問題逐字保留於 `app/company_templates.py`；筆錄輸出含公司表頭、年籍表、應告知事項（刑訴 §95 經 §100-2 準用；移送另含提審法 §1）及簽名區。
- 公司套表罪章題（`新套表.xlsm` 各罪章欄）逐字載入（`app/xlsm_questions.py`），公式插值題跳過由承辦人補實。
- 操作人員必須確認 Gate 1、罪章、問句與回答後才能輸出。
- 法源、程序或必要案號不足時，不得把文件標示為完整。
- 現行公開法規核對入口（2026-10-11 以 twlegalrag 核對現行條文）：
  - 刑事訴訟法 §95、§100-2、§100-3：https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=C0010001
  - 提審法 §1：https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=C0010008
  - 個人資料保護法：https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=I0050021
- 《警察犯罪偵查手冊》現行公開全文仍為 `UNKNOWN`，因此題庫不可宣稱已依該手冊逐條核准。

## 外部 AI 邊界

- 僅 Gate 2 候選罪章分析可送出案情摘要（上限 4000 字）至 `IAMHC_BASE_URL`（預設 https://api.iamhc.cn/v1）。
- 金鑰存於 `legal-case-web/.env`（`IAMHC_API_KEY`），已列入 `.gitignore`。
- 金鑰未設定或服務失敗時自動退回規則候選；重試 4 次後放棄。
- 年籍、問答內容、案號、條陳不送任何外部服務。

## 問句來源與優先序

一般路由載入順序（`docs/QUESTION_DESIGN_AND_USE.md` 第六節）：

1. 公司三份 `.doc` 範本通用必問題（`app/company_templates.py`，逐字）。
2. 通用程序題（`data/question_bank.json` common）。
3. 公司套表罪章題（`data/xlsm_questions.json`，抽取自 `新套表.xlsm` 被害人／涉嫌人／證人筆錄工作表之各罪章欄，公式插值題跳過）。
4. 本庫 Markdown 核心／補充／補強／區分／加重題（`questions/*.md`，分節載入）。
5. JSON 要件題（僅在 md 未涵蓋同一 element 時補入）。

語意相同之題目自動去重（全文比對）。八頁校準總容量為 97 題；被害人固定 company/common 共 19 題，因此 offense 題上限為 78。公司題與核心題優先保留，實際輸出仍以 LibreOffice 頁數檢查 fail closed。

已辨識的財物取走情境不會整批展開 Markdown／JSON 延伸題。執行時保留公司固定題、通用程序題及 XLSM 公司罪章題，再加入 7 題角色化核心／區分問句。完整題庫仍保留作為覆蓋與人工審查來源。

## 文件規則

- 輸出格式為 `.docx`，不修改三份舊式 `.doc`。
- 筆錄 DOCX 依公司範本結構重建：標題列、詢問時間地點、案由、受詢問人年籍表（11 欄＋家庭經濟狀況）、涉嫌人應告知事項、問答、結尾簽名區。
- 版面固定為 A4、標楷體 12pt、1.15 倍行距。
- 下載筆錄前，以本機 LibreOffice 轉成 PDF 並讀取實際頁數。
- 超過 8 頁、LibreOffice 不存在或排版失敗時，系統會阻止筆錄下載。
- 條陳案情摘要最多 500 個 Unicode 字元；超過時阻止寫入，不得靜默截斷。
- 下載的 DOCX 是未加密明文，使用者需自行依機關規定保存。

## 隱私與安全

- 僅綁定 IPv4 `127.0.0.1`。
- CORS 關閉；例外：Gate 2 罪章候選可送案情摘要至外部 AI（見「外部 AI 邊界」）。
- API 驗證記憶體 session token、`Host`、`Origin` 及 body 大小。
- 回應使用 CSP、`no-store`、`nosniff` 與 frame deny。
- 案件 payload 使用 Windows DPAPI current-user scope 加密後存入 SQLite。
- SQLite metadata 只保存隨機案件 ID、revision、Gate 狀態及時間。
- 稽核事件不保存姓名、案號、自由文字或問答內容。
- DPAPI 資料通常不能移到其他 Windows 帳號或電腦解密。密文損壞時系統 fail closed，不會建立空案件取代原資料。

## 語意推理模組（2026-10-15）

| 模組 | 職責 |
|---|---|
| `app/acts.py` | 行為模型與競合分析（不自動定性；竊盜/侵占區辨含經核實裁判錨點） |
| `app/questions.py` | 問句 metadata、動態預算（round-robin）、條件觸發、回答驅動重評估、品質檢核 |
| `app/document_validation.py` | 筆錄/條陳完整性驗證（下載前 fail closed） |
| `app/law_reference.py` | 法源核實（tw-legal-rag REST + 離線快照 `data/law_reference_cache.json`） |
| `app/legal_semantic_corpus.py` | 固定語意測試集（32 案例）+ 差異測試（6 案例） |
| `app/offense_linkage.py` | 驗證離線罪章關聯 PoC；目前只涵蓋普通竊盜、加重竊盜與普通侵占，且不接入 Gate 2 |
| `app/legal_retrieval.py` | 由 route ID、fact target 與有限狀態產生去識別查詢；目前只有離線 adapter，外部 adapter 固定 fail closed |
| `app/legal_retrieval_cache.py` | 將 adapter 結果正規化為公開來源 metadata，驗證兩層完整性 hash，並提供需明示路徑的原子快取 |
| `app/legal_provider_fixtures.py` | 以離線 fixture 驗證已公開的來源契約；不發出網路請求，也不接入 Gate 2 |
| `app/legal_retrieval_reconciliation.py` | 將已驗證的來源移除 locator 精確映射為 `source_id`，原子移除 cache metadata 並留下 tombstone |
| `app/legal_retrieval_sync.py` | 以預設 dry-run 的協調器串接離線 adapter、正規化、明示 cache 與來源移除 reconciliation |
| `app/legal_retrieval_batch.py` | 建立 deterministic 離線 manifest，於記憶體依序套用多 provider 項目並以單次原子交易提交 |
| `app/legal_retrieval_replay.py` | 以嚴格合成 corpus 重播正常、移除、schema 漂移與 stale 回填情境，輸出去識別驗收證據 hash |

`data/offense_linkage_poc.json` 將法條、裁判錨點、child route、區分軸與中性問句以可追溯關聯保存。它固定為 `runtime_enabled: false / HUMAN_REVIEW_REQUIRED`；公開起訴書目前為 `NOT_INGESTED`，不得用此 PoC 宣稱已完成起訴書檢索或法律判斷。

法律檢索 PoC 不接受案情摘要或任意查詢文字，只能使用程式內核准的固定詞彙。`OfflineLinkageAdapter` 不使用網路；`DisabledExternalAdapter` 在沒有獨立 Human Gate 時一律拒絕傳送查詢。

檢索快取不保存全文、節錄、姓名、地址、案號或案件 payload。現有離線來源的 hash scope 是 `REGISTERED_SOURCE_FINGERPRINT_NOT_FULL_DOCUMENT`，不得宣稱為官方文件全文 hash；快取沒有預設正式路徑，也尚未被 runtime 建立或讀取。

來源 fixture adapter 目前只對 `mcp-taiwan-legal-db` 搜尋結果、TLR anchor bundle 與司法院 `JDoc` 的已公開欄位做離線契約測試。司法院全文只在記憶體中計算 `FULL_PUBLIC_DOCUMENT` hash，不進入標準輸出。離線 reconciliation 可把已登錄 JID 的移除訊號精確映射為 `source_id`，在明示 cache 路徑原子移除 metadata，並於同檔保存不含原始 JID 的 tombstone；未知 locator、稽核竄改或舊資料回填一律 fail closed。Taiwan Law MCP 與 PSUE 因缺少本 PoC 可固定的公開 response/API schema，維持 `DISCOVERY_ONLY`。

離線 sync coordinator 預設只回傳不含查詢文字、fixture 摘要或原始 locator 的 `DRY_RUN` 報告，且不建立 cache。只有明示 `commit=True` 才可寫入；移除 commit 另須提供 UTC `observed_at`。adapter 必須宣告 `external_network: false`，且實例、回應及移除事件的 provider 身分必須一致。

離線 batch manifest 只能由 adapter ID 與固定去識別 query 透過 deterministic builder 產生；重複項目或任何欄位竄改都會被拒絕。批次先在記憶體 transaction 依 manifest 順序模擬，後段失敗時不提交前段結果；commit 前若偵測 cache 基線漂移也會拒絕覆寫。全部成功後才以一次原子替換更新明示 cache。

`tests/fixtures/legal_retrieval_replay.json` 是不含案件資料的合成 golden corpus。Replay harness 只允許已驗證的 fixture provider，且只輸出批次狀態、operation 類型、cache／audit／record 計數、錯誤類別與 SHA-256；不輸出 query、原始 locator、fixture 文字、錯誤訊息或 traceback。scratch 目錄必須由呼叫端明示，已有同名 cache 時拒絕覆寫。

`docs/evidence/legal_retrieval_human_gate_packet.json` 凍結 10 個 PoC 核心檔案與 4 個 runtime surface hash，並記錄 golden replay、測試結果、`UNKNOWN` 與五項必要人工核准。封包狀態固定為 `PENDING_HUMAN_APPROVAL`；hash 漂移時封包失效，不得沿用舊證據或把工程 PASS 解讀為接線授權。

`docs/evidence/hg_lr_01_provider_contract_review.json` 將司法院 JDoc、PSUE、Taiwan Law MCP、TLR hosted 與 mcp-taiwan-legal-db 分類盤點。公開證據 review 為 `PARTIAL_REVIEW_HUMAN_APPROVAL_REQUIRED`，`HG-LR-01` 仍是 `PENDING`；本檔不選定 provider、不授權 live call，也不取代 `HG-LR-02` 至 `HG-LR-05`。

`docs/evidence/hg_lr_02_privacy_security_review.json` 追蹤 query、provider boundary、metadata cache、removal audit 及報告資料流。審查確認 query 沒有自由文字通道，但不能因此宣稱匿名：cache 仍保存公開裁判案號線索。原 `P02` 無效輸入回顯已改為穩定錯誤碼並以負向測試鎖定，但仍待工程與人工審查。整體狀態為 `CHANGES_REQUIRED_HUMAN_APPROVAL_PENDING`，不得啟用外部查詢或正式 cache。

### 法源核實

44 個啟用路由均有法源紀錄、明示 crosswalk 狀態及至少一個 child route，共拆出 310 個仍待人工審查的 legal routes。`VERIFIED_CURRENT` 只表示所列主要法源在指定資料版本中可回查，不表示所有罪名、特別法競合、行為時法或問句均已完成人工審查。6 個路由仍標記 `PARTIAL_SCOPE`；其中 `public_danger` 明確只涵蓋酒毒駕與交通事故逃逸，不涵蓋公共危險章其他犯罪。候選輸出依路由型態維持 fail closed；行為時間早於法條修正日時仍會記錄 `temporal_law_warnings`。

### 問句生成管線（docs/QUESTION_DESIGN_AND_USE.md）

公司必問 → 通用題 → 公司罪章題 → md 題 → JSON 要件題 → metadata 豐富化 → 品質檢核（Q1-Q10）。`core` 與 `company_offense` 不得為符合頁數而靜默裁切；必要題超過預算時直接 fail closed，要求承辦人縮小本次路由範圍。

### 品質審查（docs/QUESTION_DESIGN_AND_USE.md）

三層品質關：生成時程式化檢核（Q1-Q10）→ pytest 品質測試集（含誘導/定性語句掃描）→ 承辦人人工審核（題庫變更時）。

## 驗證

```powershell
py -3 -X utf8 -m pytest -q
node --check app\static\app.js
```

**目前基準（2026-10-15）：289 passed**（單一序列完整 pytest）＋ golden replay 4/4 passed ＋ Node 前端行為測試 20 passed ＋ Python compileall／JavaScript syntax PASS。合成案件的本機瀏覽器流程另已實際走完「摘要建案 → 候選罪章 → 37 題被害人問答 → 案號 → 205 字條陳 → 4 頁筆錄 DOCX」；首頁已改為只輸入案情摘要，時間與地點由摘要明示標籤帶入。桌面、768px 與 375px 均無水平溢位；因沒有既有視覺基準圖，視覺回歸仍為 `INCONCLUSIVE`。這些是程式與本機操作證據，不是法律內容完整或 Human Gate 通過證據。

### 前端錯誤恢復說明

- API 非 2xx 回應：安全解析 JSON `message`／`error`（code）；非 JSON 或 HTML 一律使用安全預設訊息，不顯示 raw body。
- `fetch` 失敗（斷線）：顯示繁中「無法連線到本機服務，請確認服務仍在執行。」，不洩漏瀏覽器英文錯誤或 stack。
- 409 `REVISION_CONFLICT`：原 POST 精確 1 次、**不自動重送 mutation**；僅在仍指向同一案件時載入並渲染最新案件，提示「已載入最新版本，請核對後重試」；回載失敗則保留原版本並提示重新選取或重試。
- 永久行為測試：`tests/test_frontend_api_errors.mjs`（20 案例，Node vm 載入實際 app.js）＋ `tests/test_frontend_api_errors.py`（pytest wrapper，UTF-8 fail closed）。

測試涵蓋：零候選、AI 候選解析與失敗退回、關聯候選、問句單一判斷、公司必問逐字輸出、xlsm 公司罪章題載入、權利告知與提審告知、案號條件、500 字摘要、Gate 禁止跳過、年籍儲存、向後修改失效、同案被害人至涉嫌人流程、無被害人分支、DPAPI 明文 sentinel、revision 衝突、密文損壞、DOCX 完整性、LibreOffice 實際頁數、session token、Host、Origin、CSP、CORS 及路徑穿越、前端 409 安全回載。

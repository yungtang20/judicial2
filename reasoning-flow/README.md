# reasoning-flow｜法源推理流程提取與 Web 化

本目錄是專案規劃書 v1.0 的實作區，與既有的 `legal-case-web` **完全分離**，不影響線上服務。

核心原則：**模板與規則都存在 JSON 裡，改資料不改程式碼。**

```
reasoning-flow/
├─ data/
│  ├─ templates.json              ← M1 產出：條陳模板結構
│  ├─ lawbank_reasoning_flow.json ← M2 產出：法源五層推理關聯
│  └─ questions_rules.json        ← M3 產出：問句規則與範本
├─ web/
│  ├─ index.html                   ← M6 產出：完整工作台
│  └─ llm_client.js                ← M7 產出：瀏覽器端 LLM 客戶端
├─ out/                           ← 產出（分析報告／gap_list／問句／條陳／匯出）
├─ prototype/
│  └─ index.html                   ← M1 產出：靜態表單原型（保留）
├─ tools/
│  ├─ validate_templates.py       ← templates.json 驗收腳本（262 項）
│  ├─ validate_reasoning_flow.py  ← lawbank_reasoning_flow.json 驗收腳本（640 項）
│  ├─ validate_questions_rules.py ← questions_rules.json 驗收腳本（446 項）
│  ├─ validate_analyzer.py        ← 分析器驗收腳本（388 項）
│  ├─ validate_generator.py       ← 生成器驗收腳本（1,023 項）
│  ├─ analyzer.js                 ← M4 分析器核心（UMD）
│  ├─ generator.js                ← M5 生成器核心（UMD）
│  ├─ llm_bridge.js               ← M7 LLM 橋接（opencode CLI）
│  ├─ llm_analyzer.js             ← M7 LLM 提示詞與輸出校驗
│  ├─ analyze_case.js             ← 分析器 CLI
│  ├─ generate_output.js          ← 生成器 CLI
│  ├─ build_questions_rules.js    ← questions_rules.json 組裝腳本
│  ├─ apply_field_hints.js        ← templates.json value_hints 套用腳本
│  ├─ lawbank_login.js            ← 法源登入（憑證僅走環境變數）
│  ├─ lawbank_scrape.js           ← 法源擷取器（法條/判解/函釋/論著）
│  ├─ lawbank_job.json            ← 擷取工作設定（改此檔即可擴充罪群）
│  ├─ lawbank_clean.js            ← 擷取結果清洗去噪
│  ├─ lawbank_build_flow.js       ← 組裝 lawbank_reasoning_flow.json
│  ├─ to_umd.js                   ← CommonJS → UMD 轉換
│  ├─ serve.py                    ← 本機伺服器（靜態檔 + /api/llm）
│  ├─ web_e2e.js                  ← M6 瀏覽器端到端測試
│  ├─ web_llm_e2e.js              ← M7 瀏覽器 LLM 測試
│  ├─ llm_e2e.js                  ← M7 LLM 端到端測試
│  ├─ prototype_smoke.js          ← M1 原型煙霧測試
│  ├─ prototype_shot.js           ← M1 原型截圖
│  ├─ web_shot.js                 ← M6 工作台截圖
│  └─ test_facts/                 ← 四個測試案例
├─ raw/                            ← 擷取原始資料與登入 session（已 gitignore）
├─ docs/screenshots/               ← 截圖存證
├─ .gitignore                      ← 排除 raw/
└─ start.ps1                       ← 本機啟動原型
```

---

## 進度總覽

| 里程碑 | 內容 | 狀態 |
|---|---|---|
| M1 | 條陳模板提取 → `templates.json` → 靜態表單原型 | ✅ 完成（262 項驗收通過 + 瀏覽器煙霧測試） |
| M2 | 法源推理流程提取 → `lawbank_reasoning_flow.json` | ✅ 完成（640 項驗收通過） |
| M3 | 問句規則提取 → `questions_rules.json` | ✅ 完成（446 項驗收通過） |
| M4 | 分析器（規劃書 5.1）→ `gap_list` | ✅ 完成（388 項驗收通過） |
| M5 | 生成器（規劃書 5.2）→ 問句清單 + 條陳填充 | ✅ 完成（1,023 項驗收通過） |
| M6 | Web UI 整合（完整工作台） | ✅ 完成（瀏覽器端到端 23 項通過） |
| M7 | 接 LLM 端到端測試 | ✅ 完成（四案例全由 LLM 產出並通過校驗） |

**合計 2,759 項驗收檢查全數通過**（5 份 Python 驗收腳本）＋ 3 個瀏覽器／LLM 端到端測試。

---

## 系統全貌

```text
┌─ web/index.html（完整工作台）───────────────────────────┐
│ ①事實輸入 → ②候選路徑與要件檢核 → ③缺口清單            │
│ ④問句清單 → ⑤條陳填充（可手動覆寫）→ 匯出 .txt        │
└────────────────────────────────────────────────────────┘
        ▲                    ▲                    ▲
        │                    │                    │
  tools/analyzer.js    tools/generator.js    tools/llm_bridge.js
  （規則驅動，UMD）    （規則驅動，UMD）      （M7，語意判讀）
        │                    │                    │
        ▼                    ▼                    ▼
 data/lawbank_       data/templates.json   data/questions_rules.json
 reasoning_flow.json                        （+ LLM 輸出須通過同一套校驗）
```

四份 JSON 為唯一事實來源，**改資料不改程式碼**。

---

## 一、M1 成果

### 1. `data/templates.json`（階段一 4.2 條陳模板提取）

從 `條陳.txt` 提取三種模板：

| template_id | 模板 | 適用條件（有被害人／是否破獲／主體是否特定） |
|---|---|---|
| `victim_report` | 被害人條陳 | 有／未破獲／已特定 |
| `suspect_with_victim` | 涉嫌人條陳，有被害人版 | 有／已破獲／已特定 |
| `suspect_no_victim` | 涉嫌人條陳，無被害人版 | 無／已破獲／已特定 |

每個欄位含 `field_id`、`label`、`type`、`required`、`conditional`、`fixed_text`、`variable_placeholder`、`example`、`note`。

**相較規劃書骨架，另外新增的欄位鍵**（記錄於 JSON 的 `schema_notes.added_field_keys`）：

| 鍵 | 用途 |
|---|---|
| `variable_position` | 變動文字相對於 `fixed_text` 的位置（after / before） |
| `fixed_suffix` | 變動文字之後的固定結尾（例如「。」） |
| `render` | inline（同行）／ below（填在下一行，用於案情摘要） |
| `empty_policy` | todo（未填標「（待補）」）／ keep_placeholder ／ keep_blank |
| `editable` | 是否可由使用者填寫 |
| `slots` | 固定文字中的可填空位（如三個案號），以 `anchor` 標示插入點 |
| `title_text` | 原文第一行標題 |

新增這些鍵的原因：骨架版本不足以讓 L5「按 `fixed_text` 串接」還原出**與原文逐字一致**的文件。例如抬頭是「○○所**報告**」（變動文字在前）、處理員警是「（三）處理員警：警員 **○○○**。」（變動文字在中間有前綴與後綴）、案情摘要在標題的**下一行**。

### 2. `prototype/index.html`（靜態表單原型）

四個區塊，全部由 `templates.json` 驅動：

1. **模板選擇** — 三個下拉（有無被害人／是否破獲／主體是否特定），依 `selection_logic.decision_table` 自動比對，無對應模板時顯示 `result_note`。
2. **表單** — 依 `sections[].fields[]` 動態生成輸入框；固定文字欄位以唯讀框呈現，案號空位以三個可填小框呈現。
3. **條陳預覽** — 即時組裝，輸出規則完全依 JSON 的 `fixed_text` / `render` / `variable_position` / `fixed_suffix` / `empty_policy`；未敘明欄位標「（待補）」；末尾自動附「模擬填充，不構成正式文書。」與「所有罪名均為候選，不認定犯罪成立。」
4. **模板差異對照** — 三種模板的欄位、標籤與佔位差異表。

### 3. 驗收結果

`py -3 tools/validate_templates.py` → **205 項檢查全數通過**，其中最關鍵者：

> 三種模板以 JSON 重建後的文字，與 `條陳.txt` 原文**逐字一致**（含全形冒號、頓號、案號行的半形 `)`、案由佔位的半形 `(受理)`、「警員 」後的半形空格）。

`node tools/prototype_smoke.js` → 瀏覽器煙霧測試通過：無 JS 錯誤、三種模板皆可切換、待補標記與免責註記正確、填值後固定文字與案號空位保持原樣、下載檔含免責註記且有 UTF-8 BOM。

---

## 本機啟動（M1 原型）

```powershell
cd reasoning-flow
.\start.ps1
```

開啟 `http://127.0.0.1:8791/prototype/`。

> 需以 HTTP 伺服器開啟：`file://` 直開會因瀏覽器同源限制而讀不到 `../data/templates.json`。`start.ps1` 已內建 `python -m http.server`。

---

## 二、M2 成果

### `data/lawbank_reasoning_flow.json`（階段一 4.1 法源推理流程提取）

資料來源為**法源法律網 lawbank.com.tw 實際登入擷取**，涵蓋刑法第 30 章、第 33 章之財產犯罪群（§320 竊盜、§321、§325 搶奪、§326、§328 強盜、§329 準強盜、§330、§346 恐嚇取財）。

依規劃書 4.1 的**五層關聯**建構：

| 層 | 內容 | 數量 |
|---|---|---|
| 1. 法條層 | `statute_decomposition` — 法條 → 構成要件 | 9 條法條 / 19 個要件 |
| 2. 要件層 | `element_to_judgment` — 要件 → 判解要旨 | 10 群 / 51 筆判解 |
| 3. 判解層 | `judgment_to_issue` — 判解 → 爭點／法院心證／判斷因素 | 6 組 |
| 4. 爭點層 | `issue_to_scholarship` — 爭點 → 學說正反見解 | 3 組 |
| 5. 推理路徑 | `reasoning_paths` — 事實特徵 → 觸發要件 → 候選法條 | 3 條 |

另含 `search_word_recommendations`（5 組檢索詞建議）與 `extraction_gaps`（3 項已知缺口）。

**核心判準（已從判解原文提取）**

- 「至使不能抗拒」：應依當時具體事實為**客觀判斷**，以一般人置於同一情境時其意思自由是否受壓制為準，**不以被害人主觀上是否覺得害怕為準**，亦不要求完全喪失抗拒能力（最高法院 111 年度台上字第 2060 號、107 年度台上字第 586 號等）。
- 強盜 vs 恐嚇取財：被害人**尚有幾分自由意思**、社會一般通念上僅心生畏怖而未達不能抗拒程度者，屬恐嚇取財（最高法院 86 年度台上字第 5174 號）。
- 搶奪 vs 強盜：乘人不備公然掠取為搶奪；施用強暴脅迫至使不能抗拒而取財者為強盜（最高法院 104 年度台上字第 290 號）。

### 擷取管線（可重跑、可擴充罪群）

```powershell
# 1) 登入（憑證僅由環境變數傳入，不落檔）
$env:LB_USER="<帳號>"; $env:LB_PASS="<密碼>"
node tools/lawbank_login.js

# 2) 擷取（依 tools/lawbank_job.json 的設定；改此 JSON 即可換罪群）
node tools/lawbank_scrape.js

# 3) 清洗去噪 → 4) 組裝五層關聯
node tools/lawbank_clean.js
node tools/lawbank_build_flow.js

# 5) 驗收
py -3 tools/validate_reasoning_flow.py
```

**法源網站存取對照**（供日後擴充時參考）

| 資料 | URL 格式 | 備註 |
|---|---|---|
| 法條 | `FLAWDOC01.aspx?lsid=<法編>&lno=<條號>` | 需由搜尋結果點入，直接訪問回「無此法規資訊」 |
| 判解搜尋 | `FJ/` 首頁填 `#kw` 後按 `#butSubmit` | 分頁 `FJQRY02.aspx?noun=<kw>&sort=1&condition=<hash>&Page=N` |
| 判解要旨 | 結果列表 `table.JudgeNoun-Results-List` 之 `div.summary` | `<em>` 標示者為法源標定之要旨核心 |
| 行政函釋 | `FINT/` 首頁填 `#kw` 後按 `#butSubmit` | 結果列表 `table.Onebar-Results-List` |
| 法學論著 | `treatise/query.aspx` 填 `#ctl00_cphMain_txtKeyword0` 後按 `#ctl00_cphMain_butSubmit` | 需以 `__doPostBack` 提交 |

### M2 已知缺口（記於 `extraction_gaps`）

| gap_id | 狀態 | 說明 |
|---|---|---|
| `g_fyjud` | `needs_external` | 裁判書全文（七段式裁判摘要）需 fyjud 單元之獨立授權，此帳號無閱覽權限。目前判解層僅有要旨欄位文字，`court_reasoning` 係由要旨推得，未經全文核對。 |
| `g_fint` | `needs_external` | 行政函釋以關鍵字檢索，命中多為不相干機關之公告；與本罪群相關之函釋要旨待改以條文關聯路徑擷取。 |
| `g_article_full` | `inferred` | §328 關聯原判例 46 件、精選裁判 355 件，本次僅取符合要件關鍵者，非法源所列全量。 |

另有 `e_motive`（準強盜之動機要件）因關鍵字未涵蓋而無對應判解，已誠實標記 `extraction_status: needs_external` 並附說明，**未放寬條件硬湊**。

### 授權與使用範圍

法源網站頁尾載明其智慧財產權屬法源資訊股份有限公司，未經正式書面授權禁止重製轉載節錄。故本專案的處理原則：

- 原始擷取檔與登入 session 存放於 `raw/`，該目錄已列入 `.gitignore`，**不進版控**。
- `data/lawbank_reasoning_flow.json` 以**條號、判解字號、要旨摘要、原文連結**為主，僅保留建構推理流程所必要的判準要旨段落，不做整庫鏡像。
- 商業或對外散布前，須另行確認法源授權範圍。

---

## 三、M3 成果

### `data/questions_rules.json`（階段一 4.3 問句規則提取）

素材不是外部貼上，而是**既有專案資產的結構化提取**：`questions/review-checklist.md`（每一問的品質門檻）、`questions/common.md`（通用程序問句與禁止事項）、`questions/index.md`（載入順序與代號規則）、`questions/robbery.md`、`questions/threat.md`（要件對照與區分問句）、`rule/interview-page-limit-rule.md`（8 頁限制與問句排程優先序）、`legal-case-web/data/question_bank.json`（既有問句欄位慣例）。

**13 條可程式校驗的規則**，每條含 `check_type` 與 `check_value`：

| rule_id | check_type | 適用 | 嚴重度 | 內容 |
|---|---|---|---|---|
| `open_ended` | required_pattern | 範本 | error | 須含開放式問法或可展開回答之請求；整句是／否命題不合格 |
| `no_leading_answer_presupposition` | forbidden_word | 範本＋既有庫 | error | 禁「你是不是」「對方就是」「是否故意」等暗示答案之問法 |
| `no_legal_conclusion_in_question` | forbidden_word | 範本＋既有庫 | error | 不得要求受詢問者作法律評價；定性用語不得寫入問句 |
| `no_definitive_labeling` | forbidden_word | 範本＋既有庫 | error | 禁「搶匪」「嫌犯」等定性稱呼 |
| `map_to_gap` | mapping_required | 範本 | error | 每句須對應至少一個 gap_id 或 element_id |
| `single_target_only` | mapping_required | 範本 | error | 一題只對一個受詢問者角色 |
| `one_fact_per_question` | tag_constraint | 範本 | warn | 一題一事；列舉型須標「逐項」 |
| `allow_unknown` | required_pattern | 範本 | warn | 須容許不知道／不確定／不願回答 |
| `perception_before_hearsay` | tag_constraint | 範本 | warn | 先問親自見聞，再問轉述 |
| `sensitive_minimum` | tag_constraint | 範本 | warn | 敏感案件最低必要詢問 |
| `page_budget` | tag_constraint | 範本 | error | 每角色每份筆錄最多 8 頁；超出為 `BLOCKED_PAGE_BUDGET` |
| `dedupe_by_meaning` | tag_constraint | 範本 | warn | 依事實目的去重，不只比對文字 |
| `question_id_format` | tag_constraint | 範本 | error | 代號須全庫唯一且符合 `<prefix>-<C\|S\|R\|D\|A\|N\|W>-<number>` |

**23 個問句範本**（相對人 13／行為人 8／證人 2），全部開放式，每句標 `maps_to`（對應 `lawbank_reasoning_flow.json` 的 `element_id` 或事實缺口面向）與 `derived_from`（既有問句來源）。

其中數個範本直接由 M2 的法源判準反推：

- `q_relative_freedom_of_choice`（當時的處境為何？有哪些選項仍能選擇？）→ 對應「被害人尚有幾分自由意思」之區分判準
- `q_relative_coercion_degree`（對方以何種方式、施加於何處？身體或心理感受為何？）→ 對應「依當時具體事實客觀判斷」之判準

### 既有問句庫實測稽核（`existing_library_audit`）

規則不只對新造範本有效——驗收腳本會**實際套用於既有 49 個問句檔**並交叉核對 JSON 記載值（防止資料過期）：

| 指標 | 結果 |
|---|---|
| 掃描檔案 | 49 檔（44 罪章檔＋通用檔） |
| 解析出問句本體 | 1150 句 |
| 硬性違規（暗示答案／法律定性／定性標籤） | **0** |
| 開放式比例 | 67.7% |

**這是 M3 最重要的發現**：既有問句庫**沒有**違規預設答案或法律定性的問題（符合 `review-checklist.md` 標準），但約三分之一是「是否有…？」「你是否…？」式的是／否問法，**不符合專案規劃書 4.3 對問句範本之開放式要求**。

處理方式（未放寬標準）：本檔之 23 個範本已 100% 開放式；既有 44 檔之改寫**記為 `q_existing_bank_open_ended`（`needs_external`），須另行人工確認，不得由系統自動覆寫**。

### M3 已知缺口

| gap_id | 狀態 | 說明 |
|---|---|---|
| `q_company_standard` | `needs_external` | 公司標準筆錄原始問句未納入本規則檔；依 `rule/company-template-role-rule.md`，該類問句須保留原文與原順序，AI 新增問句不得複製其問題 |
| `q_specific_offense_packs` | `extracted` | 各罪章專屬問句仍以 `questions/*.md` 為準，應由 L5 依候選罪章載入 |
| `q_existing_bank_open_ended` | `needs_external` | 既有庫開放式比例 67.7%，改寫須人工確認 |

---

## 四、M4 成果

### `tools/analyzer.js`（分析器核心，規劃書 5.1）

**採規則驅動實作，不依賴 LLM** — 如此輸出可被 `tools/validate_analyzer.py` 逐項校驗，而非黑箱。LLM 的語意理解留待 M7。

輸入 `lawbank_reasoning_flow.json` ＋事實描述，輸出六段 Markdown ＋ 末尾 `gap_list` JSON：

1. **事實解構表** — 主體、交付狀態、人／事／時／地／物／價值／補強／行為／因果九個面向，各標「已敘明／未敘明」
2. **候選罪名群組（未排序）** — 依 `statute_decomposition` 原順序列出，依 `reasoning_paths` 之 `required_triggers` 判斷事實型態
3. **四庫模擬檢索** — 法規／判解／行政函釋／法學論著，每庫標示 `simulated`（資料已登錄）或 `needs_external`（待外部檢索）
4. **要件檢核表** — 已具備／待確認／明顯欠缺／因指代不明無法判斷
5. **缺口清單** — 事實缺口＋要件缺口，每筆具體到「缺哪項事實導致哪個要件無法判斷」，並附建議問法
6. **`gap_list`** JSON — `gap_id`／`type`／`description`／`affects_elements`

### 為支援分析器，M2 資料層補了三個結構性欄位

| 欄位 | 位置 | 用途 |
|---|---|---|
| `fact_patterns` | element | **事實偵測用**情境詞彙（「害怕」「不敢抗拒」「揚言」）。與 `search_tags`（法源檢索用判準詞）用途不同，不可混用 |
| `critical` | element | 是否為基本要件。決定未敘明時屬「明顯欠缺」或「待確認」 |
| `discriminating` | element | 是否為該罪之**區別性**要件。共用要件（如「不法所有之意圖」同屬搶奪／強盜／恐嚇取財）命中不具區別力 |
| `required_triggers` | reasoning_path | 該事實型態成立所需之事實。全部受陳述方視為型態成立 |

前兩項在 M4 開發時才發現必要：`search_tags` 是法源判準詞（「不能抗拒」），拿來比對敘事會全數落空——「因害怕而不敢抗拒」顯然已陳述該要件，但敘事中不會出現「不能抗拒」四個字。

### 測試案例與實測結果

| 案例 | 候選 | 觸發路徑 | 缺口 | 警示 |
|---|---|---|---|---|
| `case_explicit`（明確版） | §328_I、§328_II、§346_I | `p_robbery_vs_threat` | 0 | — |
| `case_partial`（明確但缺漏） | §328_I、§346_I | — | 7 | 【階段不明警示】 |
| `case_ambiguous`（指代不明版） | §328_I、§346_I | —（走 fallback） | 14 | 【主體不明警示】＋【階段不明警示】 |

明確版全要件已具備、零缺口；指代不明版產出 14 筆缺口並同時發出兩項警示。四種要件狀態（已具備／待確認／明顯欠缺／因指代不明無法判斷）皆經案例實測可產生。

### M4 已知限制

- 規則驅動意味著**詞彙式比對**：敘事用同義詞而未收錄於 `fact_patterns` 者，會被誤判為欠缺。目前 `fact_patterns` 為人工建置，收錄 19 個要件之常用情境詞。
- 指代不明之判定採「指代詞出現前文是否已有可辨識主體」之啟發式規則，未做完整篇章分析。
- 候選群組不足兩個時，會取區別性要件命中數最多之路徑之候選法條補足，並於報告中標明「目前尚無完整符合之 reasoning_paths 事實型態」。

---

## 五、M5 成果：生成器（規劃書 5.2）

`tools/generator.js`（UMD，Node 與瀏覽器共用）讀取 `templates.json` ＋ `questions_rules.json` ＋ 分析器 `gap_list`，產出三段：

1. **問句清單** — 分「對相對人／對行為人／對證人」，每句標 `maps_to` 與 `covers_gaps`，並經 `questions_rules.json` 全部 error 級規則校驗（未通過者不納入，另列於「未納入」）
2. **條陳填充表** — 欄位 ID／標籤／填充內容／狀態
3. **匯出用純文字** — 按 `fixed_text` 串接，末尾附免責註記

### 條陳順序不可變（硬性約束）

使用者明確要求「條陳的順序不能改變」。此約束已落實為**可程式驗證的檢查**：

- `templates.json` 之 `fixed_text` 全數照抄 `條陳.txt`，M1 即已驗證重建文字與原文逐字一致
- 匯出時標題行置於最上，其後依 `sections[].fields[]` 原序，**不重排、不增刪**
- `validate_generator.py` 對每個案例，直接以 `條陳.txt` 原文區塊比對匯出文字中各 fixed_text 之**出現位置必須遞增**，且**項數必須相同**

```
匯出（case_explicit）                條陳.txt 原文
被害人條陳                            被害人條陳
○○所報告                            ○○所報告
一、受理案由：114年5月1日…（候選）    一、受理案由：○○○(受理)
二、發生時間：114年5月1日             二、發生時間：年月日時分
三、發生地點：○○市○○區○○路           三、發生地點：
…                                    …
```

### 欄位抽取（`value_hints`，M1 資料層補充）

`templates.json` 的可填欄位新增 `value_hints`，說明「如何自事實描述抽取該欄位值」：`summary`／`datetime`／`location`／`person`／`constant`／`manual`。其中報案時間與破獲時間另設 `context_before`（如「報案」「到案」），避免把發生日期誤填為報案時間。

### 四個測試案例實測

| 案例 | 模板 | 問句 | 缺口 | 警示 |
|---|---|---|---|---|
| `case_explicit`（明確版） | 被害人條陳 | 3（相對人 2／行為人 1） | 1 | — |
| `case_partial`（明確但缺漏） | 被害人條陳 | 6 | 7 | 【階段不明警示】 |
| `case_ambiguous`（指代不明版） | 被害人條陳 | 10 | 15 | 【主體不明警示】＋【階段不明警示】 |
| `case_suspect`（涉嫌人端） | 涉嫌人條陳，有被害人版 | 7 | 5 | — |

**每個 `gap_id` 皆至少對應一句問句**（已驗證）。

---

## 六、M6 成果：Web 整合

`web/index.html` 為完整工作台，模組對應規劃書第六章：

| 模組 | 讀取 | 功能 |
|---|---|---|
| 事實輸入 | — | 自由敘述輸入，載入範例 |
| 分析結果 | `lawbank_reasoning_flow.json` | 候選路徑（未排序）、要件檢核、缺口清單 |
| 模板選擇 | `templates.json` 之 `selection_logic` | 自動比對 + 人工指定 |
| 表單渲染 | `templates.json` 之 `fields[]` | 依規則動態生成，可手動覆寫 |
| 問句清單 | `questions_rules.json` + `gap_list` | 分角色顯示，標示對應缺口 |
| 條陳預覽 | `templates.json` + 填充結果 | 依原文格式串接，順序固定 |
| 匯出 | 全部 | .txt（含 UTF-8 BOM） |

另設「資料與規則」分頁，顯示法源流程、問句規則與模板對照。

`tools/analyzer.js` 與 `tools/generator.js` 經 `tools/to_umd.js` 轉為 UMD，**同一份程式碼**同時供 Node 與瀏覽器使用，故 CLI 與網頁的產出必然一致。

---

## 七、M7 成果：接 LLM

### 架構

`tools/llm_bridge.js` 以 `opencode run --format json --model <model>` 呼叫語意模型，**沿用使用者本機既有認證，金鑰不進 repo**（模型可由 `LB_MODEL` 指定）。瀏覽器端經 `tools/serve.py` 的 `POST /api/llm` 端點呼叫。

### LLM 的角色與邊界

LLM **只判斷「事實是否已受陳述」**，不判斷犯罪是否成立：

- 產出：主體是否特定、交付狀態、各要件狀態（已具備／待確認／明顯欠缺／因指代不明無法判斷）、缺口清單與建議問法
- **不產**：候選罪名（仍由規則依 `lawbank_reasoning_flow.json` 判定，且不排序）、任何成立與否之判斷

### 安全護欄

LLM 輸出**必須通過與規則版相同的校驗**才會採用：`element_id` 須為候選要件且已定義、`status` 值須合法、`gap_id` 格式與唯一性、`affects_elements` 須指向已定義要件、禁語（「成立／構成／該當／應論以」）掃描。任何一項不通過，**自動退回規則版**並於介面明確標示退回原因。

### 實測

四個案例**全由 LLM 產出**並通過全部校驗。LLM 的輸出品質明顯優於規則式比對，例如 `case_explicit` 正確辨識出規則版漏掉的法律爭點：

> 欠缺「被害人基於畏懼將現金交付予行為人」之交付事實：敘事僅載明行為人自行取走被害人包內現金，未載被害人是否親手交出；致 §346_I「使人交付（基於畏懼）」要件無從判斷。

---

## 八、本機啟動

```powershell
cd reasoning-flow
.\start.ps1
```

| 網址 | 內容 |
|---|---|
| `http://127.0.0.1:8797/web/` | 完整工作台（M6，含 LLM 按鈕） |
| `http://127.0.0.1:8797/prototype/` | M1 靜態表單原型 |

`tools/serve.py` 同時提供靜態檔案與 `POST /api/llm` 端點（LLM 版分析所需）。

> 需以 HTTP 伺服器開啟：`file://` 直開會因瀏覽器同源限制而讀不到 `data/*.json`。

---

## 九、驗收與回歸

```powershell
# 五份驗收腳本
py -3 tools/validate_templates.py
py -3 tools/validate_reasoning_flow.py
py -3 tools/validate_questions_rules.py
py -3 tools/validate_analyzer.py
py -3 tools/validate_generator.py

# 端到端測試
node tools/prototype_smoke.js    # M1 原型
node tools/web_e2e.js            # M6 工作台
node tools/llm_e2e.js            # M7 LLM（需 opencode CLI 與網路）
node tools/web_llm_e2e.js        # M7 瀏覽器端 LLM
```

### 環境需求

| 腳本 | 額外需求 |
|---|---|
| `prototype_smoke.js`、`web_e2e.js`、`web_llm_e2e.js` | 環境變數 `PW_PATH`（playwright-core 套件路徑）與 `CHROME_PATH`（Chrome／chrome-headless-shell 可執行檔路徑）。兩者未設定時腳本會以 `TypeError: The "id" argument must be of type string` 失敗，屬環境缺漏而非程式錯誤。 |
| `llm_e2e.js`、`web_llm_e2e.js` | 另需可用的 `opencode` CLI 與網路連線。 |
| `lawbank_login.js` | 環境變數 `LB_USER`、`LB_PASS`；登入後的 session cookie 寫入 `raw/lb_state.json`。`raw/` 已在 `.gitignore` 內，**不得**提交。 |

### 重跑紀錄

- `out/regression_summary.txt`：2026-10-21 16:09，五份驗收腳本與四支端到端腳本全數通過。
- `out/verification_20261022.txt`：2026-10-22 交接前重跑，五份 Python 驗收腳本 exit 皆為 0 且項數與前者一致（262／640／446／388／1023）；四支瀏覽器／LLM 端到端腳本因本機缺 `PW_PATH`、`CHROME_PATH`、opencode CLI 而**未重跑**，沿用 2026-10-21 紀錄。

回歸摘要另存於 `out/regression_summary.txt`。

---

## 十、下一階段

| 項目 | 說明 |
|---|---|
| 擴充罪群 | `tools/lawbank_job.json` 增加條號與關鍵字後重跑擷取，即可涵蓋其他罪章 |
| 8 頁限制 | `rule/interview-page-limit-rule.md` 要求正式輸出時以 PDF 實際頁數判定；目前尚未實作頁數預算與 `BLOCKED_PAGE_BUDGET` 狀態 |
| 行政函釋 | M2 的 `g_fint` 缺口：需改以條文關聯路徑擷取 |
| 既有問句庫改寫 | M3 的 `q_existing_bank_open_ended` 缺口：44 個罪章檔中約三分之一為是／否式問句，改寫須人工確認 |
| 正式筆錄輸出 | 目前產出為模擬用之條陳文字，尚未串接公司標準筆錄（`rule/company-template-role-rule.md`） |

---

## 十一、遵守的規則

- 提取階段**不自行更正**原文錯字：例如「三、查獲地點：年月日時分」的時間格式誤植，保留於 `fixed_text` / `variable_placeholder`，僅於 `note` 標註。
- 全流程禁用斷定語「成立」「構成」「該當」「應論以」。**引述與自撰分流**：判解要旨、條文原文、法院心證等 `quotation_policy.quotation_fields` 所列欄位為法源原文引述，可能含法院原話之斷定語詞；系統自身之判斷（`reasoning_paths[].note`、`extraction_gaps` 等）一律不得出現禁語。驗收腳本會剔除引述欄位後再檢查其餘內容。
- 案由欄位只填「事實描述＋（候選）」，不填具體法條罪名。
- 判解字號若原文無據，一律標 `needs_external`，不得虛構。驗收腳本會檢查 `judgment_to_issue` 與 `reasoning_paths` 所引用的每一個字號，**必須可回溯到 `element_to_judgment` 已登錄者**。
- 對應關係不足時誠實標記 `needs_external` 並附原因，**不得放寬條件硬湊**。

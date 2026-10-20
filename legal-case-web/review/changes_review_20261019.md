# 未提交變更審查草稿（人工 review 用）

日期：2026-10-19 ｜ 狀態：**DRAFT — 未經人工核准，不得視為通過紀錄**
本文件僅整理工作區既有未提交變更，供人工 code review；本身不是核准證據。

> **人工審核集中副本**：本文件、`xlsm_review_draft.md`、`hg_chain_notice.md`、
> `c_class_diff_digest.md`、`rules_sampling_worksheet.md`、`visual_baselines_candidate\`、
> `audit_copy\`（canonical 為工作區根 `.audit\project-qa.tsv`）均已放入 `review\1\` 供人工一次審核。
> canonical 位置不變（工具重跑會更新 canonical），核准動作仍以 canonical 為準：
> 視覺基準核准＝人工把基準照從 `review\visual_baselines_candidate\` 移入
> `review\visual_baselines_approved\`。

---

## 0. 總覽

| 項目 | 狀態 |
|---|---|
| pytest 全套 | 390 passed（2026-10-19 本機實跑） |
| Node 前端行為測試 | test_frontend_api_errors.mjs 22 案例 passed |
| HG hash 鏈（packet → HG-LR-01 → HG-LR-02） | 四節點已隨 rules.py 最新 sha256 (`7d785584…`) 同步並程式驗證一致 |
| git commit | **0** — 全部變更保留未提交 |
| 留痕 | `.audit/project-qa.tsv` 六輪決策紀錄 |

## 1. 變更分類

`git status` 共 30 個修改檔＋untracked。依來源分成三類：

### A. 本 session（探針第 1–6 輪）產出的修改

| 檔案 | 內容 | 依據（探針→修改） |
|---|---|---|
| `app/rules.py` (±339/13) | ① `_PHRASE_HINTS` 白話語句提示（8→9 罪章，含 robbery 雙條件＋`exclude` 欄位排除「新聞／聽說」情境）② `ATTRIBUTED_ALLEGATION_GUARDS` 轉述指控護欄 7 罪章＋`ATTRIBUTION_PREDICATE`（家屬／長官轉述型）③ `_attribution_spans`／`_hits_inside_attributed_spans`／`_has_independent_outside`（引述區間延伸至句末標點、獨立事實只計區間外）④ `_property_taking_values` 加入「持有訊號＋侵占動作」雙條件（保管→拒不返還敘述進屬性事實路徑；引述句不觸發；action 事實值用實際命中詞） | 每條修法先有探針實測失敗輸出；question_bank.json 關鍵字**一律未動** |
| `app/questions.py` (±12/1) | `classify_answer`：`ANSWER_AFFIRMATIVE_YES_OPENERS`（「有，」「有的，」「有,」）＋`ANSWER_AFFIRMATIVE_EXACT_WORDS`（有／有的／是／對）；`build_property_taking_questions` 要求 facts action+object | 「有，不過我沒有…」類混合句維持 negative/矛盾記錄（保守優於覆蓋） |
| `app/documents.py` (±15/1) | `_format_tw_time`＋`_TIME_PASSTHROUGH` 正則：正式文件時間白名單（ISO 可解析或民國樣式照印，其餘自由文字回退 UNKNOWN 交人工補填） | UI 自由文字時間可經 Gate1 編輯寫回 intake， garbage 時間原先直印正式文件 |
| `docs/evidence/legal_retrieval_human_gate_packet.json` | rules.py sha256 更新（d7820e83… → 7d785584…） | hash 鏈節點 1 |
| `docs/evidence/hg_lr_01_provider_contract_review.json` | packet_sha256 更新 | hash 鏈節點 2 |
| `docs/evidence/hg_lr_02_privacy_security_review.json` | packet_sha256＋provider_review_sha256 更新 | hash 鏈節點 3 |
| `tests/test_candidate_phrase_hints.py`（新檔） | PHRASE_HIT_CASES／NEGATION_GUARDED_CASES／FALSE_POSITIVE_CASES（robbery 連案例）＋embezzlement 敘述回归（fact_keys、focused 題數、quote 隔離、舊路徑不變） | 擴增過程中修正過一次探針錯誤預期（動詞前式 object=UNKNOWN 維持原設計） |
| `tests/test_question_logic.py` (±23) | classify_answer 14 案 | |
| `tests/test_documents.py` (±37/1) | 時間門檻 6 案＋端到端 brief 斷言 | |

### B. 本 session 產出的人工覆核工具與 review-only 產物（untracked）

| 檔案／目錄 | 內容 |
|---|---|
| `tools/__init__.py` | 防止本地 `tools` 包被 site-packages 遮蔽 |
| `tools/xlsm_review_diff.py` ＋ `tests/test_xlsm_review_diff.py` | XLSM 差異工具＋測試 |
| `review/xlsm_review_draft.md` | 514 格覆核草稿（工具可重跑）——**待人工覆核** |
| `tools/visual_baseline.py` ＋ `tests/test_visual_baseline.py` | 視覺基準擷取／比對工具＋測試（2026-10-19 審核回饋後修訂：擷取前隱藏暫時性 `#status` toast、新增 Gate 1 合成摘要狀態 `gate1_*.png`、STATUS.json 附 limitations） |
| `review/visual_baselines_candidate/`（home×3＋gate1×3 截圖＋STATUS.json `UNAPPROVED_CANDIDATE`） — **待人工核准**（人工放入 `review/visual_baselines_approved/` 後 `compare` 門檻才生效） |
| `app/static/styles.css`（`.case-branch { margin-top: .75rem; }`） | 審核議題 4 的間距修正（改後已重新擷取基準） |
| `tests/test_generation_stability.py` | 生成穩定性 4 測試（前一 session 已落地，本 session 一併保留） |
| `.audit/` | 各輪決策留痕 TSV（repo 根目錄；`review\1\audit_copy\` 為副本） |

### C. 既有未提交修改（先前 session 產出，本 session 未動、原狀保留）

| 檔案 | 摘要（經 diff 確認） |
|---|---|
| `app/config.py` (1/1) | HOST 預設固定 `127.0.0.1`（移除 Render/PORT 條件暴露） |
| `app/server.py` (1/6) | 移除 RENDER/.onrender.com Host/Origin 旁路；`STORE.save` 回傳值接回 `updated` |
| `app/workflow.py` (±32/13) | auto_prepare fail-closed（「目前不可自動分析」）；單案件記憶體工作區相關流程；Gate1 時間寫回 intake |
| `app/xlsm_questions.py` (±24/2) | `_render_verified_placeholders`：只代入已核對固定專線（1925／1957／412-8518），不認得的占位符原樣保留 fail-closed；`template_text`＋`interpolation_status` 留軌 |
| `app/route_questions.py` (9/0) | 新增 `defamation_309_public_insult` 中性題包（7 題） |
| `app/static/app.js`／`index.html` (±24/7) | 前端 client 對應（409 回載、單案件流程、200 keep 值題目） |
| `README.md` (8/8) | 文件對齊：本機綁定、單案件記憶體、測試基準數字更新 |
| `tests/*`（test_official_case_regressions＋89、test_server_security＋41、test_workflow＋33、test_e2e_flow 5/2、test_line_cases＋9、test_gate2＋1、test_frontend_api_errors.mjs＋20） | 上列行為的回歸測試 |
| `web_app/**`（Next.js 原型：page.js、路由、package.json/lock +3293、eslint.config.mjs 等） | 原型另鏈變更，本 session 未接觸 |

## 2. 探針輪次帳（決策留痕見工作區根 `.audit/project-qa.tsv`）

**基準對照**（審核前檢查第 5b 點修訂）：
- 六輪系列開始前：**368 passed**（goal objective 記錄之 test_generation_stability 落地時點）
- 第 4 輪收尾盤點：**389 passed**
- 現況（2026-10-19，含本日審核回饋修正後）：**390 passed**（pytest 實跑＋collect-only 390 一致）

| 輪 | 主題 | 動作 | 新增回歸測試數＊ |
|---|---|---|---|
| 1 | 白話召回＋覆核工具 | `_PHRASE_HINTS`、XLSM 差異工具、視覺基準工具 | +10 |
| 2 | 轉述指控泛化 | 護欄 7 罪章 `_ATTRIBUTED_ALLEGATION_GUARDS` | +2 |
| 3 | 轉述語義缺口 | 謂詞／span／獨立事實位置／財物擴展設閘 | +3 |
| 4 | 肯定句分類＋robbery＋時間閘 | classify_answer、robbery hint、`_format_tw_time` | +5 |
| 5 | embezzlement focused 題＋storage/前後端驗證 | `_property_taking_values` 雙條件；storage 併發／密文損壞確認已被既有 9 測試覆蓋；前後端錯誤碼契約確認對齊 | +1 |
| 6 | 全域 fail-closed 驗證（純驗證，無修改） | ai.py JSON 抽取、company template fail-loud、save_answers 閘、案號 by-design 自由文字、acts 拒升級、LibreOffice 頁數閘可用性 | 0 |

＊「新增回歸測試數」= 新增 test function 數，非 pass 數差額總帳：368→389→390 間另有
其他 session 批次與本日審核回饋修正（styles.css／visual_baseline 工具修訂）的影響，
逐輪增量不做為通過數會計。

## 2b. 審核前檢查議題處理紀錄（2026-10-19 人工回饋後）

| 議題 | 處理 | 狀態 |
|---|---|---|
| 1 HG hash 鏈 | **人工已選項 A 並回報審閱完成**：機械記帳已落地 `docs/evidence/hg_rules_py_human_review_record.json`（packet schema 凍結故記錄採姊妹檔，packet／HG 檔未再動、hash 不變）；HG-LR-01/02 狀態翻轉仍由人工自行操作 | 記帳完成（HG 翻轉待人工） |
| 2 基準只涵蓋空白首頁 | `capture` 擴充為兩狀態：首頁＋Gate 1（合成摘要、明標非真實案情）→ `gate1_*.png`；`compare` 涵蓋兩組檔案；STATUS.json 加 `limitations` 欄（其他 Gate 畫面仍無基準） | 已修，待人工核准 |
| 3 截圖含暫時提示框 | 擷取前以 CSSOM 隱藏 `#status`（CSP `style-src 'self'` 擋 inline `<style>`，改用 JS 設定 element style）→ 三張舊圖已全部重新擷取 | 已修 |
| 4 案件分支間距偏小 | `styles.css` 加 `.case-branch { margin-top: .75rem; }`；截圖已重擷 | 已修，待人工看圖確認 |
| 5a `.audit` vs `audit` 複本誤差 | 副本資料夾更名 `review/1/audit_copy`；本文 §1-B／§2 註明 canonical 為工作區根 `.audit/project-qa.tsv` | 已修 |
| 5b 測試數無前後基準 | §2 加基準列：368（系列前）→389（第 4 輪盤點）→390（現況），並註明輪次增量為新增 test function 數、非通過數會計 | 已修 |
| 6 未審範圍偏大 | 另立 `review/1/c_class_diff_digest.md`：C 類 30 檔逐檔 diff 濃縮＋審核問題＋建議閱讀順序（web_app 兩個 route.js 排第一梯） | 已備 |
| 7 關鍵字規則需實句抽樣 | 另立 `review/1/rules_sampling_worksheet.md`：16 句合成抽樣，機器行為由 agent 實跑填入、判讀欄留空；並標出 3 個 agent 自查發現的疑點（B1 新聞句 theft/embezzlement 誤觸、B2 object 擷取粗糙、A1 與 A2 輸出相同） | 已備，待人工判讀 |

## 3. 人工關卡現況（agent 不得代做）


| 關卡 | 現況 | 人工動作 |
|---|---|---|
| XLSM 514 格覆核 | `review/xlsm_review_draft.md` 草稿＋`tools/xlsm_review_diff.py` 可重跑 | 依草稿逐格覆核，狀態維持 HUMAN_REVIEW_REQUIRED |
| 視覺基準核准 | `review/visual_baselines_candidate/`（STATUS.json UNAPPROVED_CANDIDATE） | 核准後自行放入 `review/visual_baselines_approved/`，`compare` 門檻生效 |
| PSUE 對照 | 維持 `DISCOVERY_ONLY`／INCONCLUSIVE（需驗證碼、無 API 契約；不繞過） | 無（限制已登記：非判決搜尋引擎） |
| Embezzlement 擴充核定 | 第 5 輪已修「保管→拒不返還」focused 題（rules.py 層） | 覆核該雙條件語義是否符合機關敘述慣例 |
| 已審查資料 | question_bank.json 關鍵字**未動**；review-only 資料未接 runtime | — |

## 4. 驗證重跑指令

```powershell
# Python 全套（workdir: legal-case-web）
py -3 -X utf8 -m pytest -q .
# Node 前端行為測試
node tests/test_frontend_api_errors.mjs
# JS 語法
node --check app/static/app.js
# hash 鏈自檢
py -3 -X utf8 -m pytest -q tests/test_legal_retrieval_human_gate_packet.py
# XLSM 覆核草稿重跑
py -3 -X utf8 tools/xlsm_review_diff.py
```

## 5. 建議的人工 review 重點（風險排序）

1. **`app/rules.py`** — 本輪最大改動面（提示機制、護欄、屬性雙條件）。請覆核：`_property_taking_values` 的「持有訊號＋侵占動作」不會對引述指控句誤建事實（測試已斷言，但語義判斷屬人工）。
2. **`app/questions.py` classify_answer** — 「有，」（肯定開頭）與 exact words 集合是否足夠保守（矛盾續接句仍歸 negative/矛盾）。
3. **`app/documents.py` 時間白名單** — 回退 UNKNOWN 策略是否符合文件作業慣例。
4. **B 類 review-only 產物** — 與 C 類既有修改各自獨立，核准後可分批 commit（建議分組：C 既有修改一組、rules/questions/documents＋對應 tests 一組、tools/review 產物一組）。

---
本文件由 agent 整理生成，僅描述工作區現況；不構成任何法律結論或核准狀態。

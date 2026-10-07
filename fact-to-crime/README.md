# fact-to-crime 事實→元件→罪名 比對引擎

基於「交接手冊 v15」建立的本地規則引擎。
**分工**：LLM 抽取事實與映射元件；本引擎跑全部 **17 層**。**LLM 不直接輸出罪名**（v15 R30）。

## 狀態

| 項目 | 狀態 |
|---|---|
| **17 層覆蓋** | **全部實作** |
| **罪章覆蓋** | **15 個族群** |
| 元件庫 | **167 筆**（**153 verified / 0 partial / 0 unverified**） |
| 罪名庫 | **76 筆** |
| 互斥/競合 | **40 筆** |
| 規則引擎 | `01_規則/rule_engine.js`（12A+12B+13+R18+R30+R43+6C） |
| **前 15 層** | `01_規則/layers.js` |
| **前 15 層細項** | `01_規則/layers_detail.js` |
| **第 7/9 層** | `01_規則/laws_7_9.js` |
| **第 10 層** | `01_規則/criminal_form.js` |
| **第 11 層** | `01_規則/justifications.js` |
| **第 17 層** | `01_規則/s14_contract.js` |
| **整合執行入口** | `01_規則/integration.js`（P1 切分 → 1A 身分 → 2A 分流 → S-14） |
| **驗證腳本** | `03_轉換工具/check.js`（**15/15 PASS**） |
| **伺服器腳本** | `03_轉換工具/serve.sh` |
| **問句引擎** | `01_規則/question_engine.js` + `question_library.js`（15 章全覆蓋） |
| **R33 審計** | `01_規則/audit.js`（71 題，0 法律用語） |
| **LLM 骨架** | `01_規則/llm_generator.js` + `llm_config.json` |
| **法規查證** | `00_資料/法規查證/criminal_code_general.json`（14 條 verified）+ 元件庫 **153 verified / 0 待查證** |
| 測試 | `02_評測/test.js`（**21/21 PASS**）+ S-14 整合測試 |

## 罪章清單（15 個族群）

| 族群目錄 | 條號 | 元件 | 罪名 | 測試 |
|---|---|---|---|---|
| `criminal_221` | §221、§222、§226、§227、§229-1 | 24 | 5 | POS/NEG/AGG |
| `criminal_fraud` | §339、§339-1、§339-4、詐防條例§43/§44、§341 未遂 | 11 | 6 | POS/NEG |
| `criminal_theft_embezzle` | §320、§321、§335、§337 | 15 | 5 | POS/LOST |
| `criminal_harm_dv` | §277、§284、§287 + 家暴法§3/§50/§61 | 16 | 9 | POS/DV |
| `criminal_defame` | §309、§310 | 7 | 2 | POS |
| `criminal_public_danger` | §185-3 | 7 | 3 | POS |
| `criminal_traffic` | 道交法§35 + §185-4、§185-6 | 10 | 4 | POS |
| `criminal_drugs` | 毒條§4-13 | 13 | 10 | POS |
| `criminal_sexual_harassment` | 性騷法§25 + 性工法§12 + 性別平等教育法 | 7 | 4 | POS |
| `criminal_forgery` | §210、§214、§216、§217、§218 | 8 | 5 | POS |
| `criminal_gambling` | §266、§268 | 7 | 2 | POS |
| `criminal_intimidation` | §302、§304、§305、§346 | 6 | 4 | POS |
| `criminal_computer` | §358-362 | 6 | 4 | POS |
| `criminal_obscenity` | §231、§235 + 兒少性剝削 | 6 | 3 | POS |
| `criminal_robbery` | §325、§328、§329、§330、§347 | 9 | 5 | POS |

## 快速啟動

```bash
cd D:/工作用/judicial1/fact-to-crime

# 1. 驗證資料完整性（15 章 schema/id/cross_reference）
node 03_轉換工具/check.js

# 2. 跑全部測試（21 個案例）
node 02_評測/test.js

# 3. R33 審計
node 01_規則/audit.js

# 4. 全 17 層整合執行入口（P1 切分 → 1A 身分 → 2A 分流 → S-14）
node 01_規則/integration.js 02_評測/cases/S14-INPUT-TE-001.json

# 5. S-14 契約
node 01_規則/s14_contract.js 02_評測/cases/S14-INPUT-TE-001.json

# 6. 罪名比對
node 01_規則/rule_engine.js 00_資料/罪章/criminal_221 02_評測/cases/TC-221-POS-001.json

# 7. 前 15 層細項
node 01_規則/layers_detail.js <input.json>

# 8. 問句生成
node 01_規則/question_engine.js criminal_221 02_評測/cases/TC-221-POS-001.json 被害人

# 9. LLM 生成（需配置 llm_config.json）
node 01_規則/llm_generator.js

# 10. 本機伺服器（解決 file:// fetch 限制）
bash 03_轉換工具/serve.sh 8000
```

## 整合執行入口（`01_規則/integration.js`）

從陳報檔（LINE 文本或 CSV）到 S-14 契約的完整流程：

```text
LINE 陳報文本
  ↓ P1 案件切分（R41）
  ↓ 欄位抽取（案由/時間/地點/金額/年次）
  ↓ P2 日期正規化（R42：推定值標「推定」）
  ↓ 1A 身分判定（R23/R38/代理）
  ↓ 2A 分流（行政/刑罰/非刑案/程序案，R40）
  ↓（程序案/非刑案不進元件比對）
  ↓ S-14 契約（全 17 層）
  ↓ 輸出 JSON
```

## 17 層覆蓋

| 層 | 模組 | 狀態 |
|---|---|---|
| P1/P2 | `layers.js` + `integration.js` | ✅ |
| 1A~1I | `layers.js` + `layers_detail.js` | ✅ |
| 2A~2I | `layers.js` + `layers_detail.js` | ✅ |
| 3A~3F | `layers_detail.js` | ✅ |
| 4A~4C | `layers.js` + `layers_detail.js` | ✅ |
| 5A~5F | `layers.js` + `layers_detail.js` | ✅ |
| 6A~6C | `layers_detail.js` + `rule_engine.js` | ✅ |
| 7 | `laws_7_9.js` | ✅ |
| 8A~8G | `rule_engine.js` + `layers_detail.js` | ✅ |
| 9 | `laws_7_9.js` | ✅ |
| 10A~10F | `criminal_form.js` | ✅ |
| 11A/11B | `justifications.js` | ✅ |
| 12A~12D | `rule_engine.js` | ✅ |
| 13 | `rule_engine.js` | ✅ |
| 14A~14D | `layers.js` + `layers_detail.js` | ✅ |
| 15A~15D | `layers.js` + `layers_detail.js` | ✅ |
| 16 | `question_engine.js` + `question_library.js` | ✅ |
| 17 | `s14_contract.js` | ✅ |
| R18/R30/R33/R43/6C | `rule_engine.js` + `audit.js` | ✅ |

## 法規查證（115.07.22 最新版）

`00_資料/法規查證/criminal_code_general.json` 已查證 14 條：

| 條號 | 內容 | 狀態 |
|---|---|---|
| 刑§2 | 從舊從輕 | ✅ |
| 刑§16 | 法律之不知與減刑 | ✅ |
| 刑§17 | 加重結果犯（不能預見不適用） | ✅ |
| 刑§18 | 未成年人、滿 80 歲人之責任能力 | ✅ |
| 刑§19 | 責任能力－精神狀態 | ✅ |
| 刑§23 | 正當防衛 | ✅ |
| 刑§24 | 緊急避難 | ✅ |
| 刑§26 | 不能犯不罰 | ✅ |
| 刑§27 | 中止犯 | ✅ |
| 刑§28 | 共同正犯 | ✅ |
| 刑§29 | 教唆犯 | ✅ |
| 刑§30 | 幫助犯 | ✅ |
| 刑§214 | 使公務員登載不實 | ✅ |
| 刑§330 | **加重強盜罪**（非法條常業竊盜；常業竊盜 2006 年已併入§321） | ✅ |

## 測試結果（21/21 PASS）

| Case | 族群 | 類型 |
|---|---|---|
| TC-221-POS/NEG/AGG | §221 | 正/反/加重 |
| TC-FR-POS/NEG | §339 | 正/反 |
| TC-TE-POS/LOST | §320 | 正/互斥 |
| TC-HD-POS/DV | §277 | 正/家暴 |
| TC-PD-POS | §185-3 | 正 |
| TC-DF-POS | §309 | 正 |
| TC-FG-POS | §210 | 正 |
| TC-GB-POS | §266 | 正 |
| TC-IN-POS/R18 | §346 | 正/12B |
| TC-CP-POS | §358-362 | 正 |
| TC-TR-POS | 道交法§35 | 正 |
| TC-DR2-POS | 毒條§12 | 正 |
| TC-SH2-POS | 性騷法§25 | 正 |
| TC-OB-POS | §235 | 正 |
| TC-RB-POS | §325 | 正 |
| S14-INPUT-TE-001 | §320 | S-14 整合 |

## 修復記錄

### Round 9（本次）— 全罪章交叉驗證完成

**question_engine 15 章全測試**（0 dups 全部通過）：

| 族群 | 問句 | rule_library | llm 缺口 | dups |
|---|---|---|---|---|
| criminal_221 | 27 | 12 | 15 | 0 |
| criminal_fraud | 18 | 13 | 5 | 0 |
| criminal_theft_embezzle | 18 | 9 | 9 | 0 |
| criminal_harm_dv | 19 | 11 | 8 | 0 |
| criminal_defame | 15 | 11 | 4 | 0 |
| criminal_public_danger | 12 | 7 | 5 | 0 |
| criminal_traffic | 11 | 8 | 3 | 0 |
| criminal_drugs | 17 | 6 | 11 | 0 |
| criminal_sexual_harassment | 15 | 8 | 7 | 0 |
| criminal_forgery | 12 | 6 | 6 | 0 |
| criminal_gambling | 11 | 8 | 3 | 0 |
| criminal_intimidation | 13 | 10 | 3 | 0 |
| criminal_computer | 14 | 9 | 5 | 0 |
| criminal_obscenity | 11 | 7 | 4 | 0 |
| criminal_robbery | 15 | 9 | 6 | 0 |
| **合計** | **218** | **133** | **92** | **0** |

**S-14 契約 9 章整合測試**（27 layer key 全通過）：criminal_221、fraud、theft_embezzle、harm_dv、defame、intimidation、computer、forgery、gambling，每章 candidates 正確浮現、問句 11~19 題。

**rule_library 問句統計**：63 題（不含 common 8 題）；**R33 審計 71 題 0 洩漏**。

### Round 8 — 最後 2 個 partial 查證完成，0 待查證

1. **§339-3 查證完成**：正確為「**違法製作財產權紀錄**」——以不正方法將虛偽資料或不正指令輸入電腦，製作財產權之得喪、變更紀錄，而取得他人之財產。**非「三人以上共同」**（三人以上共同是§339-4①②）。7 年以下有期徒刑+70 萬以下罰金；未遂犯罰之；**不需證明對方陷於錯誤**（電腦無法被騙）。E-FR-005、charge_fraud_special 已更正。
2. **兒少性剝削條例查證完成**：§2 定義四款行為（使為有對價之性交猥褻、利用供人觀覽、拍攝製造重製持有散布播送交付公然陳列販賣性影像、使坐檯陪酒伴遊），113.08.07 修正；前身為兒童及少年性交易防制條例（2017 年改名、106.01.01 施行）。新增 §36① 拍攝製造兒少性影像（1年以上7年以下+10萬以上100萬以下罰金）。E-OB-005 已查證、E-OB-007 新增、charge_minor_sex_trade 更新為§36。
3. **元件庫狀態**：**153 verified / 0 partial / 0 unverified**。

### Round 7 — §221 條文結構重大更正

查證發現**原 §221 元件庫有結構性錯誤**，已全面重寫：

1. **條號錯誤更正**：原用「§221-1」「§221-1之2」**不存在**。正確條號：§222（加重強制性交）、§226（加重結果犯）、§227（與幼年性交）、§229-1（告訴乃論）。
2. **§221 法定刑錯誤更正**：原寫「五年以上二十年以下」→ 正確「**三年以上十年以下有期徒刑**」。
3. **§221 方法重構**：原 3 方法（強暴/脅迫/其他）→ 正確 4 方法（**強暴/脅迫/恐嚇/催眠術或其他違反意願之方法**）。
4. **新增核心要件「違反被害人意願」**（E-221-006）：§221 為核心，§227 不需要。
5. **§222 九款加重要件補全**：二人以上共同、未滿14歲、精神身體障礙、藥劑、凌虐、駕駛交通工具、侵入住宅、攜帶兇器、照相錄音錄影散布。
6. **§226 加重結果犯重構**：致於死（無期或10年↑）、致重傷（10年↑）、致羞忿自殺（10年↑）。
7. **§227 兩個新罪名**：未滿14歲（3~10年）、14~16歲（7年↓），均不需要「違反意願」要件。
8. **§229-1 告訴乃論**：對配偶犯§221/§224、未滿18犯§227 須告訴乃論。
9. **§339-4 重構**：加重詐欺四款（冒用政府名義、三人以上共同、傳播工具散布、電腦合成不實影像）。
10. **詐防條例§43 三級化重懲查證**：100萬↑（3~10年+3000萬罰金）、1000萬↑（5~12年+3億罰金）、1億↑（7年↑或無期+5億罰金），115.01.23 施行。
11. **§44 複合型態加重查證**：加重二分之一，最高度及最低度同加。
12. **§214 查證完成**：明知為不實之事項，使公務員登載於職務上所掌之公文書。
13. **§330 更正**：為「加重強盜罪」（非「常業犯」）；常業竊盜 2006 年修法已併入§321。
14. **兒少性交易→兒少性剝削**：兒童及少年性交易防制條例已於 2017 年改名為「兒童及少年性剝削防制條例」。
15. **測試案例對齊**：TC-221-POS/NEG/AGG 更新為新元件 ID 與新預期結果。

### Round 6

1. **`03_轉換工具/check.js`**：驗證腳本（schema/必填/id 唯一/cross_reference），發現 5 章 intra_chapter exclusions 缺 `between_charges` → 已修
2. **`03_轉換工具/serve.sh`**：本機伺服器啟動腳本
3. **`01_規則/integration.js`**：全 17 層整合執行入口（P1 → 1A → 2A → S-14）
4. **刑法條號查證**：14 條 verified（via LawPlayer 115.07.22）；`criminal_robbery` 元件 verification 更新
5. **`00_資料/法規查證/criminal_code_general.json`**：查證結果寫入

### Round 5

6. **問句庫 15 章全覆蓋**、**6 個未測罪章測試**、**1B~1I 整合到 S-14**

### Round 4

7. **前 15 層細項**：`layers_detail.js`
8. **criminal_robbery**、**llm_config.json**

### Round 3

9. **第 7/9/10/11/17 層**、**§321/§339-1/§341/§230/家暴法細項**

### Round 2

10. **R18/R30/R43/layers.js 補建**

### Round 1

11. **rule_engine 硬編碼**、**determineState 漏 any_result**、**EX-HD-005**

## 已知限制（依 v15 第十三節）

- **R30 LLM 不直接輸出罪名**：`llm_guard` 欄位明示，但倉庫無強制防堵機制。
- **R18**：`warnings` 仍列出。
- **4A 正式抽取**：由 LLM 責任，需 `llm_config.json` 注入真實 LLM。
- **問句生成（S-11）**：非核心缺口標 `generated_by: llm`，實際 LLM 生成需注入。
- **待查證**：**0**（Round 8 全部查證完成；153 verified / 0 partial / 0 unverified）

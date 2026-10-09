# 警詢筆錄 AI 輔助產出系統

## JUDICIAL2 本機 Gate Pipeline

案件資料預設只在本機處理。啟動方式：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web.ps1
```

網頁位址：`http://127.0.0.1:8787/`。Gate 1 可選擇連接本機
OpenAI-compatible 模型，但 `JUDICIAL2_LOCAL_LLM_ENDPOINT` 只接受 loopback
位址。非本機模型端點會被拒絕。

公開法條資料可用 `twlegalrag` 建置：

```powershell
python law\import_laws.py
python law\sync_twlegalrag.py
```

同步查詢只包含法規名稱與條次，不包含案件摘要、姓名、案號或其他偵查資料。
同步取得的是現行整編版本，行為時法仍須另查。Gate 2 的所有候選維持
`NEED_REVIEW`，不得視為犯罪成立或正式法律意見。

**🌐 正式站（線上使用）：https://judicial-prod.onrender.com/**

事實→元件→罪名比對引擎（v15，17 層）。LLM 抽取事實與映射元件；罪名由規則引擎計算；問句由缺口產生。**LLM 不直接輸出罪名**（R30）。輸出僅供偵查參考，最終認定屬檢察官與法官。

## 🚀 快速開始

### 線上使用（推薦）

直接打開 **https://judicial-prod.onrender.com/**：

1. **選受詢問人身分**：被害人／被告／證人／關係人
2. **選罪章族群**：15 個族群（強制性交、詐欺、竊盜侵占、傷害家暴、妨害名譽、公共危險、交通、毒品、性騷擾、偽造文書、賭博、恐嚇妨害自由、妨害電腦、妨害風化、搶奪強盜）
3. **輸入案情**：貼上 LINE 陳報檔文本或輸入案情摘要
4. **產出問句**：三段結構（自由陳述 → 證據保全 → 缺口聚焦 → 結尾開放）＋ 罪名浮現表 ＋ 開放構成要件 ＋ R43 警告
5. **複製／匯出 .txt／列印**

### 本機使用

```bash
git clone https://github.com/yungtang20/judicial1.git
cd judicial1
bash fact-to-crime/03_轉換工具/serve.sh 8000
# 開啟 http://localhost:8000/index.html
```

### CLI（全 17 層 S-14 契約）

```bash
cd fact-to-crime
node 02_評測/test.js                          # 21/21 PASS
node 03_轉換工具/check.js                     # 15/15 PASS（schema/id/cross_reference）
node 01_規則/audit.js                         # R33 審計（0 法律用語）
node 01_規則/integration.js 02_評測/cases/S14-INPUT-TE-001.json  # 全 17 層
node 01_規則/question_engine.js criminal_221 02_評測/cases/TC-221-POS-001.json 被害人
```

## 📁 目錄結構

```text
judicial1/
├── README.md                       # 本檔（仓库首頁）
├── index.html                      # 線上站入口（render static 用）
├── fact-to-crime/                  # 主系統（v15，17 層）
│   ├── README.md                   # 系統詳細說明（含 8+ 輪修復記錄、法規查證狀態）
│   ├── llm_config.json             # LLM 配置（Agnes API，R30 guard）
│   ├── 00_資料/
│   │   ├── 法規查證/                # 14 條刑法 + 全部特別法 verified
│   │   └── 罪章/{15 個族群}/        # {elements,charges,exclusions}.json
│   ├── 01_規則/
│   │   ├── integration.js          # 全 17 層入口（P1→1A→2A→S-14）
│   │   ├── rule_engine.js          # 12A+12B+13+R18+R30+R43+6C
│   │   ├── layers.js               # 前 15 層框架
│   │   ├── layers_detail.js        # 前 15 層細項（1B~1I、2B~2I、3A~3F、5A~5F、6A~6C、8D/8E/8G、14A~14D、15A~15D）
│   │   ├── laws_7_9.js             # 第 7/9 層（映射、三段論）
│   │   ├── criminal_form.js        # 第 10 層（共犯、錯誤、未遂、加重結果）
│   │   ├── justifications.js       # 第 11 層（阻卻事由）
│   │   ├── s14_contract.js         # 第 17 層（S-14 契約整合）
│   │   ├── question_engine.js      # 第 16 層（S-11 問句引擎）
│   │   ├── question_library.js     # 15 章全覆蓋（218 題，R33 審校）
│   │   └── audit.js                # R33 審計
│   ├── 02_網站/index.html          # 本機網頁版
│   ├── 02_評測/test.js + cases/    # 21 個測試案例
│   └── 03_轉換工具/check.js + serve.sh
└── 警詢筆錄AI輔助系統/              # 早期手冊版（rules JSON：roles/case_types/questions_general/schema）
```

## 📊 系統規模

| 項目 | 數量 |
|---|---|
| 罪章族群 | **15** |
| 元件庫 | **153**（100% verified） |
| 罪名庫 | **71** |
| 互斥/競合 | **36** |
| 問句 | **218**（0 重複、R33 審校 0 法律用語） |
| 處理層 | **17**（v15 全實作） |
| 測試 | **21/21 PASS** + check 15/15 PASS + audit 0 泄漏 |
| 核心規則 | R1~R45 全實作 |

## ⚖️ 4 層架構

```text
┌──────────────────────────────┐
│ UI / Human                   │
│ 看問題、回答、查看候選法條     │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ Workflow / State Engine      │
│ 控制流程、Queue、Revision     │
└───────┬──────────────┬───────┘
        ↓              ↓
┌──────────────┐ ┌──────────────┐
│ LLM Engine   │ │ Legal Engine │
│ 理解/推理/問句 │ │ 法源/要件/排序 │
└──────────────┘ └──────────────┘
        ↓              ↓
┌──────────────────────────────┐
│ Fact Graph / Evidence / DB   │
│ 保存狀態與歷史               │
└──────────────────────────────┘
```

**規則：**
- Workflow Engine 才能決定下一步。
- LLM 不能自行決定流程。
- LLM 不得直接修改 Candidate Status。
- Legal Engine 不得自行產生自然語言 Question。
- DB 保存狀態與歷史。
- Human 是輸入與審查來源之一。

## 🚀 8 個 Stage Pipeline

```text
S1 INGEST
原始案情 → Claims/Facts/Evidence

S2 ANALYZE
Fact → Behavior → LegalNorm → Element → Candidate

S3 PLAN
Candidate → UNKNOWN → CoreIssue → Question Queue

S4 ASK
Queue → Question → Human

S5 ANSWER
Human Answer → LLM Extraction → Claims/Facts

S6 UPDATE
Fact Graph → 找受影響 Behavior/Element/Candidate

S7 DECIDE
State Engine 判斷：
├─ 已解決 → 下一題
├─ 新 UNKNOWN → Question
├─ Evidence Required → Evidence Request
├─ Legal Review → NEED_REVIEW
└─ 無重大變化 → 不重跑

S8 OUTPUT
Current State → Summary / 條陳 / Full Transcript
```

**唯一允許重新進行完整 Analysis 的情況：**

```text
1. 新增重大 Behavior
2. 新增可能適用的法律領域
3. 法律版本發生變化
4. 原 Candidate 被新事實根本推翻
5. 人工要求重新分析
```

其他答案只做局部更新。

## ⚡ 核心變更

### Module Capability Boundaries

| 模組 | 可以 | 不可以 |
|---|---|---|
| LLM Extraction | 抽取 Claim/Fact | 判定真偽 |
| LLM Legal | 提出法律分析 | 自創法條 |
| LLM Question | 產生中立問題 | 決定犯罪成立 |
| State Engine | 更新狀態/Queue | 自己解釋法律 |
| Legal Validator | 驗證法源 | 自創法源 |
| Candidate Engine | 計算排序 | 用 keyword 決定罪名 |
| Human | 回答/審查 | 不應被系統偽造為 Evidence |
| DB | 保存狀態 | 不執行 LLM 推理 |

### Question Queue System

建立：

```text
Question Queue
```

每個 Question：

```text
questionId
coreIssueId
elementIds
candidateIds
priority
status
```

狀態：

```text
PENDING
ASKED
ANSWERED
OBSOLETE
NEED_REVIEW
```

Answer 後，如果該問題已解決：

```text
Q1 → ANSWERED
```

如果其他問題因此失效：

```text
Q2 → OBSOLETE
```

**禁止重複詢問已經取得且沒有矛盾的資訊。**

### Incremental Updates via Event Triggers

```text
FactChanged
     ↓
Impact Analyzer
     ↓
哪些 Element 受影響？
     ↓
哪些 Candidate 受影響？
     ↓
只更新那些項目
```

例如：

```text
sk6619 = 被害人帳號
```

只影響：

```text
Account Ownership
Identifiability
相關 Candidate Elements
```

不需要重新分析整份案件。

### Runtime Guards

```text
MAX_ANALYSIS_ROUNDS
MAX_LLM_CALLS
MAX_CASE_TOKENS
MAX_LATENCY
```

任何一項超過：

```text
→ STOP
→ BUDGET_EXCEEDED
→ NEED_REVIEW
```

**不能讓 Agent 自己無限 Loop。**

## ⚖️ 17 層處理流程（僅適用於 Full Re-analysis）

```text
前處理：P1 案件切分（R41）、P2 日期正規化（R42）
第 1 層 程序：1A 身分判定（R23/R38）→ 1B~1I 權利告知/告訴期間/夜間詢問/錄音/不正方法/通譯/陪同/筆錄
第 2 層 分流：2A 行政/刑罰/非刑案/程序案（R40）→ 2B~2I 性別事件/特別法/告訴乃論/管轄/時際法/階段/模式
第 3 層 保護：3A~3F 弱勢被害人/代號/地址保密/隔離訊問/轉介/社工（有法源才觸發）
第 4 層 事實：4A 結構化（LLM）→ 4B 欄位一致性（R36）→ 4C 來源盤點
第 5 層 證據：5A~5F 證據能力（R24；自白任意性/傳聞法則/違法取證）
第 6 層 解釋：6A~6C 文義體系目的/罪刑法定（R26）/學說分歧（重要見解欄）
第 7 層 映射：五類法律要件（R13 人事時地物不進法律要件）
第 8 層 比對：8A~8G 四態判定/推論降級/互斥/因果/主觀/數額門檻
第 9 層 三段論：大前提＋小前提→結論（R25 無罪推定）
第 10 層 形態：10A~10F 錯誤/保證人/共犯/未遂/加重結果/客觀處罰條件
第 11 層 阻卻：11A 阻卻違法 → 11B 阻卻減免罪責（R20 不得跳過）
第 12 層 罪名：12A 規則計算（R30 LLM 不輸出）→ 12B 反證自檢（R18）
第 13 層 競合：互斥對/想像競合/法條競合/吸收/跨章跨法
第 14 層 門檻：14A~14D 階段門檻/無罪推定/舉證責任/追訴權時效（刑§80）
第 15 層 量刑：15A~15D 量刑事由（刑§57）/累犯自首/緩刑/沒收
第 16 層 問句：S-11 三段結構 + 缺口聚焦 + 證據保全 + 補充問句（R33/R34/R35）
第 17 層 輸出：S-14 契約 JSON
```

## 🔒 核心保障

- **R30**：LLM 不直接輸出罪名（`llm_guard` 欄位明示 LLM 可以做/不可以做）
- **R18**：未通過反證自檢的候選罪名不得輸出為「可能涉及」
- **R33/R34/R35**：問句措辭中立、追問引用原話、目的為取得準確資訊
- **R25/R26**：無罪推定、罪刑法定為硬規則
- **API key 安全**：不寫死在配置檔，由環境變數 `AGNES_API_KEY` 注入

## 📚 法規查證狀態

元件庫 **153 verified / 0 待查證**（來源：全國法規資料庫 115.07.22）：

- **刑法**：§2、§10、§13、§14、§16~§30、§47①、§57、§62、§80、§210、§214、§221、§222、§224、§226、§227、§229-1、§266、§268、§277、§284、§287、§302、§304、§305、§309、§310、§320、§321、§325、§328、§329、§330、§335、§337、§339 系列、§346、§358~362
- **特別法**：詐欺犯罪危害防制條例§2/§43/§44（115.01.23 施行）、兒童及少年性剝削防制條例§2/§36（113.08.07）、家庭暴力防治法§3/§50/§61、性騷擾防治法§2/§3/§25、性別平等工作法§12、性別平等教育法、毒品危害防制條例§4~13、道交法§35/§36、洗錢防制法
- **憲法法庭**：113 年憲判字第 3 號（公然侮辱限縮適用）
- **刑訴**：§95、§98、§100-1/2/3、§154、§155、§156①、§158-4、§159、§159-2、§161、§237、§238①、§303③

## 🛠️ 部署

- **正式站**：https://judicial-prod.onrender.com/ （render static，連本仓库 main 分支）
- **render 設定**：Publish Directory `.`、無 build command；根目錄 `index.html` 為入口
- **推 git 即部署**：`git push origin main` → render 自動 deploy

## 📝 詳細文件

系統架構、17 層細節、8+ 輪修復記錄、法規查證完整清單：見 [`fact-to-crime/README.md`](fact-to-crime/README.md)

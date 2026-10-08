# JUDICIAL2 Architecture Design (ASD-STE100 規格格式)

## 0. 目的

本文件以 ASD-STE100 風格描述 JUDICIAL2 的架構、流程、角色模型與品質護欄，讓後續實作能以**結構化規格**方式持續驗證。

---

## 1. 第一原則

### 1.1 Standard

```text
UI
 ↓
Workflow / State Engine
 ├→ Rule Engine
 ├→ Legal Engine / Validator
 ├→ Fact Graph / DB
 └→ LLM Provider
```

- LLM 不得作為 Workflow Controller。
- LLM 只能在明確指定的 Stage 被呼叫。

### 1.2 Example

```text
UI answers "該貼文是由何人發布？"
  ↓
State Engine 判斷這是角色問句
  ↓
if actor UNRESOLVED -> 產生問句
if actor RESOLVED -> 進入下一階段
```

### 1.3 Dependencies

- Rule Engine
- Legal Engine / Validator
- Fact Graph / DB
- LLM Provider

### 1.4 Criteria

- LLM output 不得直接改變 State Machine 狀態。
- 每個 LLM call 必須有 schema 驗證。
- 每個 LLM call 必須記錄 modelVersion / promptVersion。

---

## 2. LLM 與 Rule 的責任

### 2.1 Standard

LLM 可做：
1. Fact Extraction：Raw Case / Answer → Claim / Fact candidates
2. Behavior Interpretation：Rule 無法可靠解析自然語言時，提出 Behavior candidate
3. Legal Reasoning：Behavior → possible LegalNorm → Element mapping → reasoning（結果必須經 Validator）
4. Question Generation：UNKNOWN → CoreIssue → Element → Candidate → 中立問題
5. Answer Interpretation：Answer → Claim / Fact candidates

Rule / Engine 優先處理：
- Fact 狀態保存 / Fact ID / Evidence 關聯 / Revision / Event Log
- Question Queue / Question status
- Candidate status transition / Element status calculation / Candidate ranking
- Conflict detection / Duplicate detection
- Question 已回答判斷 / Question obsolete 判斷
- Loop control / Budget control / Trace 建立
- LegalNorm version validation / Schema validation

### 2.2 Example

```text
案情：帳號 A 發布針對被害人 B 的侮辱文字。
LLM Extraction:
  claim: "A 發布文字"
  fact: "文字發表於某平台"
Rule Engine:
  map claim to Behavior B1
LLM Question:
  if victim slot UNRESOLVED -> "該行為的對象是誰？"
```

### 2.3 Dependencies

- llm_provider.js
- question_engine.js
- impact_analyzer.js

### 2.4 Criteria

- LLM 不可直接判定 IsVictim / IsActor。
- 所有角色槽位由 State Engine 維護狀態。
- 所有 candidate 必須 trace 到 element / fact / evidence。

---

## 3. 三槽位角色模型

### 3.1 Standard

對每個 Behavior `B_i`，**一律**建立三個角色槽位：

```json
{
  "behaviorId": "B1",
  "action": "...",
  "actor":   { "entityId": null, "entityType": null, "resolvedTo": null, "status": "UNRESOLVED" },
  "victim":  { "entityId": null, "entityType": null, "resolvedTo": null, "status": "UNRESOLVED" },
  "witnesses": []
}
```

槽位狀態：

| 狀態 | 意義 |
|------|------|
| `RESOLVED` | 已填入具體 Entity |
| `UNRESOLVED` | 案情未提供，但行為邏輯上可能存在 |
| `NOT_APPLICABLE` | 該行為本質上不存在該角色 |

### 3.2 Example

```json
{
  "behaviorId": "B1",
  "action": "公開發布文字",
  "actor": {
    "entityId": "A2",
    "entityType": "ACCOUNT",
    "resolvedTo": null,
    "status": "RESOLVED"
  },
  "victim": {
    "entityId": "A1",
    "entityType": "ACCOUNT",
    "resolvedTo": "P1",
    "status": "RESOLVED"
  },
  "witnesses": []
}
```

### 3.3 Dependencies

- Step 2 behavior extraction
- Entity registry
- Rule Engine

### 3.4 Criteria

- 三槽位必定存在，不可省略。
- `UNRESOLVED` 與 `NOT_APPLICABLE` 必須能區分。
- 角色分類不因槽位狀態被跳過。

---

## 4. 填入規則

### 4.1 Standard

| 槽位 | 填入條件 | 填不進去時 |
|------|----------|------------------|
| actor | 動作發出者 | `UNRESOLVED` |
| victim | 動作承受者 | `UNRESOLVED` |
| witnesses | 感知但未參與者 | `[]` |

填入方法：
- actor：主動語態主語 → actor；被動語態 by 之後 → actor。
- victim：主動語態受詞 → victim；被動語態主語 → victim。
- witness：有「看到」「聽到」「在場」等感知動詞者。

### 4.2 Example

```text
"帳號 A 在直播間指責 B"
→ actor = A
→ victim = B
→ witnesses = []（案情未提及觀眾）
```

### 4.3 Dependencies

- LLM / Rule NLP parser

### 4.4 Criteria

- 填入必須有 source raw text 作證。
- 無明確主語/受詞 → `UNRESOLVED`，不強制猜測。

---

## 5. 後續階段如何使用槽位

### 5.1 Standard

| Element.targetRole | 對應槽位 | 若該槽位 UNRESOLVED |
|--------------------|----------|-------------------|
| ACTOR | behavior.actor | 產生問句：行為人是誰？ |
| VICTIM | behavior.victim | 產生問句：被害人為誰？ |
| WITNESS | behavior.witnesses | 產生問句：有哪些證人？ |
| OBJECT | 不綁人 | 正常檢驗 |

### 5.2 Example

```text
Element targetRole = VICTIM
behavior.victim.status = UNRESOLVED
→ 問句：該行為的承受對象為何？
```

### 5.3 Dependencies

- question_engine.js
- layers_detail.js

### 5.4 Criteria

- 角色問句必須在進入三階層前被處理。
- 若 actor UNRESOLVED，罪名標記 `SUBJECT_UNRESOLVED`，不列入最終輸出。

---

## 6. Pipeline（8 Stage）

### 6.1 Standard

```text
S1 INGEST     原始案情 → Claims/Facts/Evidence
S2 ANALYZE    Fact → Behavior → LegalNorm → Element → Candidate
S3 PLAN       Candidate → UNKNOWN → CoreIssue → Question Queue
S4 ASK        Queue → Question → Human
S5 ANSWER     Human Answer → LLM Extraction → Claims/Facts
S6 UPDATE     Fact Graph → 找受影響 Behavior/Element/Candidate
S7 DECIDE     State Engine 判斷：已解決 / 新 UNKNOWN / Evidence Required / Legal Review / 無重大變化
S8 OUTPUT     Current State → Summary / 條陳 / Full Transcript
```

### 6.2 Example

同現行 `integration.js` 的 `runIntegration()` 流程。

### 6.3 Dependencies

- integration.js
- s14_contract.js
- render_brief.js

### 6.4 Criteria

- 每個 Stage 必須驗證 schema。
- Answer 後禁止全鏈重跑，僅做增量。

---

## 7. Answer 後禁止全鏈重跑

### 7.1 Standard

```text
Answer
→ LLM Answer Extraction
→ Fact Graph Update
→ Impact Analysis
→ 只找受影響的 Behavior/Element/Candidate
→ Rule Engine 更新
→ 判斷是否需要 LLM
```

若沒有 Material Change：`NO RE-ANALYSIS`。

### 7.2 Example

```text
使用者回答：「該貼文由 sky6619 發布」
→ 更新 actor slot → 若有新罪名浮現才跑規則
→ 不重跑全部 NLP / Law 模型
```

### 7.3 Dependencies

- impact_analyzer.js
- runtime_guard.js

### 7.4 Criteria

- 未受影響的 Behavior / Element / Candidate 不得重算。
- 每次更新必須有 revision event log。

---

## 8. Full Re-analysis 條件

### 8.1 Standard

僅以下情況允許：
1. 新增重大 Behavior
2. 新增法律適用範圍
3. 法律版本需要重新判定
4. 新 Fact 根本推翻既有分析
5. 人工明確要求重新分析

### 8.2 Example

```text
使用者補充：這個行為涉及多個被害人，且發生在不同時間。
→ 認定為新增重大 Behavior → 全案重新分析
```

### 8.3 Dependencies

- Impact Analyzer

### 8.4 Criteria

- 非全案情況，不可呼叫 `runS14`。

---

## 9. Trace 要求

### 9.1 Standard

每個正式 Candidate 必須能追溯：

```text
Candidate → Element → Fact → Evidence/Answer → Revision
```

若 Fact 是 LLM inference，另外記錄：
- model
- modelVersion
- promptVersion
- inputReferences

### 9.2 Example

```json
{
  "candidateId": "C1",
  "elements": ["E-TE-001", "E-TE-002"],
  "facts": ["F-202", "F-203"],
  "evidence": ["EV-001"],
  "revisionId": "R-004",
  "llmInference": {
    "model": "agnes-2.5-flash",
    "modelVersion": "agnes-2.5-flash-2026-07-22",
    "promptVersion": "v15",
    "inputReferences": ["F-202", "F-203"]
  }
}
```

### 9.3 Dependencies

- LLM Provider
- Audit

### 9.4 Criteria

- 不可把 LLM 推論偽裝成 Evidence。
- Trace 必須可讀取。

---

## 10. 效能要求

### 10.1 Standard

```text
Material Change Detection
Incremental Update
Question Batch
Cache
LLM Call Budget:
  maxAnalysisRounds
  maxLLMCalls
  maxTokens
  maxLatency
```

超過限制：`BUDGET_EXCEEDED → STOP → NEED_REVIEW`。

### 10.2 Example

```text
若同一案件已被問 5 題但狀態未改，則停止重複問句。
```

### 10.3 Dependencies

- runtime_guard.js

### 10.4 Criteria

- 不得無限 Loop。
- 必須有明確 STOP 條件。

---

## 11. 護欄（更新）

### 11.1 Standard

- G. 三槽位永遠生成：不因「看起來沒有」而省略。
- H. `UNRESOLVED` ≠ `NOT_APPLICABLE`：待查 vs 本質不存在。
- I. 三階層僅對 RESOLVED 的 actor 檢驗。
- J. 一人多角色支援：同一 Entity 可在 B1 是 actor、B2 是 victim。
- K. 罪名 subject 必須為 RESOLVED actor。

### 11.2 Example

```text
行為持有毒品：
  victim: NOT_APPLICABLE
  actor: UNRESOLVED -> 產生問句

公然侮辱：
  actor: A
  victim: B
  witnesses: [] -> 不產生證人問句
```

### 11.3 Dependencies

- rule_engine.js
- question_engine.js
- layer_detail.js

### 11.4 Criteria

- 無 actor 的 Behavior 不進三階層。
- 無 victim 的 Behavior 不必產生 victim 問句，除非規定需確認。

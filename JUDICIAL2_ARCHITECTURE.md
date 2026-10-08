# JUDICIAL2 Architecture

## 第一原則

```text
UI
 ↓
Workflow / State Engine
 ├→ Rule Engine
 ├→ Legal Engine / Validator
 ├→ Fact Graph / DB
 └→ LLM Provider
```

LLM 不得成為 Workflow Controller。LLM 只能在明確指定的 Stage 被呼叫。

## LLM 與 Rule 的責任

### LLM 可以做
1. Fact Extraction：Raw Case / Answer → Claim / Fact candidates
2. Behavior Interpretation：Rule 無法可靠解析自然語言時，提出 Behavior candidate
3. Legal Reasoning：Behavior → possible LegalNorm → Element mapping → reasoning，但結果必須經 Validator
4. Question Generation：UNKNOWN → CoreIssue → Element → Candidate → 中立問題
5. Answer Interpretation：Answer → Claim / Fact candidates

### Rule / Engine 優先處理
以下不得每次交給 LLM：
- Fact 狀態保存 / Fact ID / Evidence 關聯 / Revision / Event Log
- Question Queue / Question status
- Candidate status transition / Element status calculation / Candidate ranking
- Conflict detection / Duplicate detection
- Question 已回答判斷 / Question obsolete 判斷
- Loop control / Budget control / Trace 建立
- LegalNorm version validation / Schema validation

## Pipeline（8 Stage）

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

## Answer 後禁止全鏈重跑

改為：

```text
Answer
→ LLM Answer Extraction
→ Fact Graph Update
→ Impact Analysis
→ 只找受影響的 Behavior/Element/Candidate
→ Rule Engine 更新
→ 判斷是否需要 LLM
```

若沒有 Material Change：NO RE-ANALYSIS。

## Full Re-analysis 條件（僅以下情況）

1. 新增重大 Behavior
2. 新增法律適用範圍
3. 法律版本需要重新判定
4. 新 Fact 根本推翻既有分析
5. 人工明確要求重新分析

## Trace 要求

每個正式 Candidate 必須能追溯：
Candidate → Element → Fact → Evidence/Answer → Revision

若 Fact 是 LLM inference，另外記錄：model / modelVersion / promptVersion / inputReferences。
不能把 LLM 推論偽裝成 Evidence。

## 效能要求

- Material Change Detection
- Incremental Update
- Question Batch
- Cache
- LLM Call Budget（maxAnalysisRounds / maxLLMCalls / maxTokens / maxLatency）

超過限制：BUDGET_EXCEEDED → STOP → NEED_REVIEW。不得無限 Loop。

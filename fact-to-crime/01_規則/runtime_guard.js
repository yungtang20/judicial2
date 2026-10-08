// runtime_guard.js
// Runtime Guard：超限即 STOP → BUDGET_EXCEEDED → NEED_REVIEW，不得無限 Loop。
// State Engine 邊界：僅計算資源消耗、判斷是否停止；不解釋法律、不產生問句、不執行 LLM。

const DEFAULT_LIMITS = {
  maxAnalysisRounds: 10,
  maxLLMCalls: 20,
  maxTokens: 8000,
  maxLatencyMs: 30000,
};

function createGuard(limits = {}) {
  return {
    limits: { ...DEFAULT_LIMITS, ...limits },
    analysisRounds: 0,
    llmCalls: 0,
    tokens: 0,
    startTime: Date.now(),
  };
}

function checkGuard(guard) {
  if (guard.analysisRounds > guard.limits.maxAnalysisRounds) return 'BUDGET_EXCEEDED';
  if (guard.llmCalls > guard.limits.maxLLMCalls) return 'BUDGET_EXCEEDED';
  if (guard.tokens > guard.limits.maxTokens) return 'BUDGET_EXCEEDED';
  if (Date.now() - guard.startTime > guard.limits.maxLatencyMs) return 'BUDGET_EXCEEDED';
  return null;
}

module.exports = { createGuard, checkGuard, DEFAULT_LIMITS };

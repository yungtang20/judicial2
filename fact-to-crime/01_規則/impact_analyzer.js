// impact_analyzer.js
// Impact Analyzer：Answer 產生新 Fact 後，找出受影響的 Behavior / Element / Candidate。
// State Engine 邊界：僅計算影響範圍；不解釋法律、不產生問句、不執行 LLM、也不刪除既有節點。

function findAffectedElements(newFact, elementIndex) {
  const affected = new Set();
  for (const [eid, el] of Object.entries(elementIndex)) {
    const sources = el.source_types || [];
    const text = `${el.name || ''} ${el.semantic || ''}`;
    const factText = `${newFact.description || ''} ${newFact.source || ''}`;
    if (sources.some(s => factText.includes(s)) || text.includes(factText.split(' ')[0])) {
      affected.add(eid);
    }
  }
  return [...affected];
}

function findAffectedCandidates(affectedElements, chargeStates) {
  const affectedCharges = new Set();
  for (const [chargeId, state] of Object.entries(chargeStates || {})) {
    if (affectedElements.some(eid => JSON.stringify(state).includes(eid))) {
      affectedCharges.add(chargeId);
    }
  }
  return [...affectedCharges];
}

function analyzeImpact(newFact, elementIndex, chargeStates) {
  const affectedElements = findAffectedElements(newFact, elementIndex);
  const affectedCandidates = findAffectedCandidates(affectedElements, chargeStates);
  return { affectedElements, affectedCandidates, needsFullReanalysis: false };
}

module.exports = { analyzeImpact, findAffectedElements, findAffectedCandidates };

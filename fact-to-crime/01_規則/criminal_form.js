// criminal_form.js
// v15 第 10 層：犯罪形態審查
// 10A 構成要件錯誤／禁止錯誤
// 10B 不作為犯保證人地位
// 10C 共犯（正犯、共同正犯、教唆、幫助）
// 10D 未遂／中止／不能犯（未遂減輕：刑§25② ✓）
// 10E 加重結果犯（需可預見，刑§17 ⚠️）
// 10F 客觀處罰條件 ⚠️

// ============================================================
// 10A 構成要件錯誤／禁止錯誤
// ============================================================
function checkMistake(stateMap, elements) {
  const warnings = [];
  // 構成要件錯誤：對客觀事實認知錯誤（例如把他人之物當自己的）
  // 禁止錯誤：對違法性認知錯誤
  for (const el of elements.elements || []) {
    if (el.type !== '主觀') continue;
    const st = stateMap[el.id];
    if (!st) continue;
    if (st.status === '不符合' && st.source_raw && st.source_raw.some(s => /誤以為|誤認|不知情/.test(s))) {
      warnings.push({
        element: el.id,
        name: el.name,
        type: '構成要件錯誤',
        message: '10A：構成要件錯誤（對客觀事實認知錯誤）',
        note: '構成要件錯誤可阻卻故意，可能降為過失或不罰',
      });
    }
    if (st.status === '不符合' && st.source_raw && st.source_raw.some(s => /不知道違法|不知是違法/.test(s))) {
      warnings.push({
        element: el.id,
        name: el.name,
        type: '禁止錯誤',
        message: '10A：禁止錯誤（對違法性認知錯誤）',
        note: '依刑法第16條：禁止錯誤可減輕或免除其刑 ⚠️ 條文需查證',
      });
    }
  }
  return warnings;
}

// ============================================================
// 10B 不作為犯保證人地位
// ============================================================
function checkOmission(stateMap, elements) {
  const warnings = [];
  const hasOmissionElement = (elements.elements || []).some(e =>
    /不作為|保證人|未.*阻止|未.*防止/.test(e.name) || /不作為/.test(e.semantic || '')
  );
  if (hasOmissionElement) {
    warnings.push({
      type: '不作為犯',
      message: '10B：不作為犯需審查保證人地位（依法令、契約、危險前行為等）',
      note: '保證人地位需查證 ⚠️',
    });
  }
  return warnings;
}

// ============================================================
// 10C 共犯（正犯、共同正犯、教唆、幫助）
// ============================================================
function checkAccomplice(stateMap, elements, rawText = '') {
  const warnings = [];
  const patterns = [
    { kw: /共犯|共同正犯|二人以上/, type: '共同正犯', basis: '刑法第28條' },
    { kw: /教唆|唆使/, type: '教唆犯', basis: '刑法第29條' },
    { kw: /幫助|協助|提供工具|提供帳戶/, type: '幫助犯', basis: '刑法第30條' },
  ];
  for (const p of patterns) {
    if (p.kw.test(rawText)) {
      warnings.push({
        type: p.type,
        message: `10C：${p.type}（${p.basis}）`,
        note: '共犯型態需依個案判定',
      });
    }
  }
  return warnings;
}

// ============================================================
// 10D 未遂／中止／不能犯（刑§25② ✓）
// ============================================================
function checkAttempt(stateMap, elements) {
  const warnings = [];
  for (const el of elements.elements || []) {
    if (el.type !== '形態') continue;
    const st = stateMap[el.id];
    if (!st || !['符合', '推論符合'].includes(st.status)) continue;
    warnings.push({
      element: el.id,
      name: el.name,
      type: '未遂',
      message: '10D：未遂（刑§25② ✓ 未遂減輕）',
      note: '未遂不列獨立罪名（v15 12D），附註走刑之加減',
    });
  }
  // 中止：自行防止結果發生
  if (/中止|自動防止/.test(JSON.stringify(stateMap))) {
    warnings.push({
      type: '中止犯',
      message: '10D：中止犯（刑§27）',
      note: '中止犯減輕或免除其刑 ⚠️ 條文需查證',
    });
  }
  // 不能犯：行為不能發生犯罪之結果
  if (/不能犯|不能發生/.test(JSON.stringify(stateMap))) {
    warnings.push({
      type: '不能犯',
      message: '10D：不能犯（刑§26）',
      note: '不能犯減輕或免除其刑 ⚠️ 條文需查證',
    });
  }
  return warnings;
}

// ============================================================
// 10E 加重結果犯（需可預見，刑§17 ⚠️）
// ============================================================
function checkAggravatedResult(stateMap, elements) {
  const warnings = [];
  for (const el of elements.elements || []) {
    if (!el.aggravated_result) continue;
    const st = stateMap[el.id];
    if (!st || !['符合', '推論符合'].includes(st.status)) continue;
    warnings.push({
      element: el.id,
      name: el.name,
      type: '加重結果犯',
      message: '10E：加重結果犯（刑§17 ⚠️ 需可預見）',
      note: '加重結果犯需行為人對加重結果具過失或可預見性（刑§17 ⚠️ 條文需查證）',
    });
  }
  return warnings;
}

// ============================================================
// 10F 客觀處罰條件 ⚠️
// ============================================================
function checkObjectivePenaltyCondition(stateMap, elements) {
  const warnings = [];
  for (const el of elements.elements || []) {
    if (!el.objective_penalty_condition) continue;
    const st = stateMap[el.id];
    if (!st || !['符合', '推論符合'].includes(st.status)) continue;
    warnings.push({
      element: el.id,
      name: el.name,
      type: '客觀處罰條件',
      message: '10F：客觀處罰條件 ⚠️',
      note: '客觀處罰條件與加重結果分開標註（v15 R22）',
    });
  }
  return warnings;
}

// ============================================================
// 主入口
// ============================================================
function runCriminalForm(stateMap, elements, rawText = '') {
  return {
    spec_version: 'v15',
    layer: 10,
    checks: {
      '10A 構成要件錯誤／禁止錯誤': checkMistake(stateMap, elements),
      '10B 不作為犯保證人地位': checkOmission(stateMap, elements),
      '10C 共犯': checkAccomplice(stateMap, elements, rawText),
      '10D 未遂／中止／不能犯': checkAttempt(stateMap, elements),
      '10E 加重結果犯': checkAggravatedResult(stateMap, elements),
      '10F 客觀處罰條件': checkObjectivePenaltyCondition(stateMap, elements),
    },
  };
}

module.exports = {
  runCriminalForm,
  checkMistake,
  checkOmission,
  checkAccomplice,
  checkAttempt,
  checkAggravatedResult,
  checkObjectivePenaltyCondition,
};

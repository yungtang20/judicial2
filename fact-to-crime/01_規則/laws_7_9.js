// laws_7_9.js
// v15 第 7 層：映射五類法律要件（行為、客體、結果、主觀、狀態）
// v15 第 9 層：三段論法（大前提 + 小前提 → 結論）
// R13：人事時地物不進法律要件
// R14：因果併入元件比對

// ============================================================
// 第 7 層：映射五類法律要件
// 把元件庫的 type（行為/客體/結果/主觀/狀態/形態）映射到五類法律要件
// ============================================================
const LEGAL_REQUIREMENT_TYPES = {
  '行為': '行為',
  '客體': '客體',
  '結果': '結果',
  '主觀': '主觀',
  '狀態': '狀態',
  '形態': '形態',
};

// 把元件按五類要件分組
function mapToLegalRequirements(elements) {
  const grouped = { 行為: [], 客體: [], 結果: [], 主觀: [], 狀態: [], 形態: [] };
  for (const el of elements.elements || []) {
    const type = LEGAL_REQUIREMENT_TYPES[el.type] || '狀態';
    if (grouped[type]) grouped[type].push(el);
  }
  return grouped;
}

// 把 stateMap 按五類要件分組（含狀態）
function groupStateByRequirement(stateMap, elements) {
  const grouped = { 行為: {}, 客體: {}, 結果: {}, 主觀: {}, 狀態: {}, 形態: {} };
  for (const el of elements.elements || []) {
    const type = LEGAL_REQUIREMENT_TYPES[el.type] || '狀態';
    if (stateMap[el.id]) grouped[type][el.id] = stateMap[el.id];
  }
  return grouped;
}

// ============================================================
// 第 9 層：三段論法
// 大前提（法條元件）＋小前提（事實）→結論
// ============================================================
// 大前提：罪名 requires_elements / requires_one_of / requires_any_result
// 小前提：stateMap 中各元件的四態
// 結論：罪名成立 / 不成立 / 資料不足

function syllogism(charge, stateMap, elements) {
  const majorPremise = {
    article: charge.article,
    requires_elements: charge.requires_elements || [],
    requires_one_of: charge.requires_one_of || {},
    requires_any_result: charge.requires_any_result || [],
    requires_all_optional: charge.requires_all_optional || [],
  };

  // 小前提：各元件狀態 + 語意
  const minorPremise = {};
  const allRequired = [
    ...majorPremise.requires_elements,
    ...Object.values(majorPremise.requires_one_of).flat(),
    ...majorPremise.requires_any_result,
    ...majorPremise.requires_all_optional,
  ];
  for (const eid of allRequired) {
    const el = (elements.elements || []).find(e => e.id === eid);
    if (!el) continue;
    minorPremise[eid] = {
      semantic: el.semantic,
      type: el.type,
      status: (stateMap[eid] && stateMap[eid].status) || '資料不足',
      source_raw: stateMap[eid]?.source_raw || [],
    };
  }

  // 結論（依 R25：無罪推定為硬規則；罪疑唯輕僅適用審判階段）
  const allPositive = (eids) => eids.every(eid => {
    const st = minorPremise[eid]?.status;
    return st === '符合' || st === '推論符合';
  });
  const anyPositive = (eids) => eids.some(eid => {
    const st = minorPremise[eid]?.status;
    return st === '符合' || st === '推論符合';
  });
  const anyNegative = (eids) => eids.some(eid => minorPremise[eid]?.status === '不符合');

  let conclusion = 'not_charged';
  if (majorPremise.requires_elements.length > 0 && !allPositive(majorPremise.requires_elements)) {
    conclusion = anyNegative(majorPremise.requires_elements) ? 'not_charged' : '資料不足';
  } else if (!Object.values(majorPremise.requires_one_of).every(anyPositive)) {
    conclusion = '資料不足';
  } else if (majorPremise.requires_any_result.length > 0 && !anyPositive(majorPremise.requires_any_result)) {
    conclusion = '資料不足';
  } else {
    conclusion = '可能涉及';
  }

  return {
    major_premise: majorPremise,
    minor_premise: minorPremise,
    conclusion,
    notes: [
      'R25：無罪推定為硬規則；罪疑唯輕僅適用審判階段',
      'R13：人事時地物不進法律要件',
      'R14：因果併入元件比對',
    ],
  };
}

module.exports = {
  mapToLegalRequirements,
  groupStateByRequirement,
  syllogism,
  LEGAL_REQUIREMENT_TYPES,
};

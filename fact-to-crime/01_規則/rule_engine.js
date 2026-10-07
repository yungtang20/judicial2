// rule_engine.js
// Implements v14 layers 12 (12A rule calc + 12B counter-evidence) and 13 (exclusions).
// Pure data + rules, no LLM.

const fs = require('fs');
const path = require('path');

// Status constants
const S = {
  FIT: '符合',
  INFERRED: '推論符合',
  NOT_FIT: '不符合',
  INSUFFICIENT: '資料不足',
};

// 8A rule: 推論符合 needs source_raw; else downgrade to 資料不足
function normalizeStatus(state) {
  if (!state) return S.INSUFFICIENT;
  if (state.status === S.INFERRED && (!state.source_raw || state.source_raw.length === 0)) {
    return S.INSUFFICIENT;
  }
  return state.status || S.INSUFFICIENT;
}

function isPositive(status) {
  return status === S.FIT || status === S.INFERRED;
}

// Evaluate one charge against a state map (returns true if charge holds)
function chargeHolds(charge, stateMap) {
  // requires_elements: all must be positive
  for (const eid of (charge.requires_elements || [])) {
    if (!isPositive(normalizeStatus(stateMap[eid]))) return false;
  }
  // requires_one_of: each group must have >=1 positive
  const oneOf = charge.requires_one_of || {};
  for (const groupId of Object.keys(oneOf)) {
    const candidates = oneOf[groupId];
    const anyPositive = candidates.some(eid => isPositive(normalizeStatus(stateMap[eid])));
    if (!anyPositive) return false;
  }
  // requires_any_result: at least one of the listed result elements must be positive
  const anyResult = charge.requires_any_result || [];
  if (anyResult.length > 0) {
    const anyPositive = anyResult.some(eid => isPositive(normalizeStatus(stateMap[eid])));
    if (!anyPositive) return false;
  }
  // requires_all_optional: all listed must be positive (attacker variant etc.)
  for (const eid of (charge.requires_all_optional || [])) {
    if (!isPositive(normalizeStatus(stateMap[eid]))) return false;
  }
  // requires_not_all: at least one of these must NOT be positive (attempt charge: no completed act)
  const notAll = charge.requires_not_all || [];
  if (notAll.length > 0) {
    const anyPositive = notAll.some(eid => isPositive(normalizeStatus(stateMap[eid])));
    if (anyPositive) return false;
  }
  // not_applicable_if: if any positive → charge blocked
  for (const eid of (charge.not_applicable_if || [])) {
    if (isPositive(normalizeStatus(stateMap[eid]))) return false;
  }
  return true;
}

// 12B counter-evidence: for each necessary element of the charge, force it to NOT_FIT
// and recompute; charge must downgrade. If still holds → ⚠️ 判定疑義
function counterEvidenceCheck(charge, stateMap) {
  const necessary = [
    ...(charge.requires_elements || []),
    ...(charge.requires_all_optional || []),
  ];
  // For one_of groups, each candidate is individually necessary? No.
  // "necessary" here = an element whose removal should break the charge.
  // For a one_of group, removing ONE candidate does NOT break the group (others remain).
  // So only requires_elements and requires_all_optional are true "necessary" elements.
  const failures = [];
  for (const eid of necessary) {
    const mutated = { ...stateMap, [eid]: { status: S.NOT_FIT } };
    if (chargeHolds(charge, mutated)) {
      failures.push(eid);
    }
  }
  return failures; // empty = pass; non-empty = 判定疑義
}

// 13 exclusions
function applyExclusions(candidateCharges, charges, exclusions, stateMap) {
  const byId = {};
  for (const c of charges) byId[c.id] = c;
  let final = [...candidateCharges];
  for (const ex of exclusions) {
    if (ex.type === 'statute_competition_special_general') {
      const special = ex.special_over_general;
      const generals = ex.between_charges.filter(id => id !== special);
      const specialHolds = final.includes(special);
      if (specialHolds) {
        // remove all generals that this exclusion targets
        final = final.filter(id => !generals.includes(id));
      }
    }
  }
  return final;
}

// Determine charge state: 可能涉及 / 資料不足 / not_charged
function determineState(charge, stateMap) {
  // If the charge would hold, it's 可能涉及 (pending 12B)
  if (chargeHolds(charge, stateMap)) return '可能涉及';
  // If not, check why:
  // - If a requires_element is 資料不足 → 資料不足
  // - If a requires_element is 不符合 → not_charged
  const required = [
    ...(charge.requires_elements || []),
    ...(charge.requires_all_optional || []),
  ];
  for (const eid of required) {
    const st = normalizeStatus(stateMap[eid]);
    if (st === S.INSUFFICIENT) return '資料不足';
  }
  const oneOf = charge.requires_one_of || {};
  for (const gid of Object.keys(oneOf)) {
    const anyFit = oneOf[gid].some(eid => {
      const st = normalizeStatus(stateMap[eid]);
      return st === S.FIT || st === S.NOT_FIT; // at least answered
    });
    const anyPositive = oneOf[gid].some(eid => isPositive(normalizeStatus(stateMap[eid])));
    if (!anyPositive) {
      // Check if any in group is INSUFFICIENT
      if (oneOf[gid].some(eid => normalizeStatus(stateMap[eid]) === S.INSUFFICIENT)) {
        return '資料不足';
      }
    }
  }
  // requires_any_result: at least one must be positive
  const anyResult = charge.requires_any_result || [];
  if (anyResult.length > 0) {
    const anyPositive = anyResult.some(eid => isPositive(normalizeStatus(stateMap[eid])));
    if (!anyPositive) {
      if (anyResult.some(eid => normalizeStatus(stateMap[eid]) === S.INSUFFICIENT)) return '資料不足';
    }
  }
  return 'not_charged';
}

// Main entry
// stateMap: { "E-221-001": { status, source_raw, source_type, source_count }, ... }
function run(chapterDir, stateMap) {
  const chapter = JSON.parse(fs.readFileSync(path.join(chapterDir, 'charges.json'), 'utf-8'));
  const elements = JSON.parse(fs.readFileSync(path.join(chapterDir, 'elements.json'), 'utf-8'));
  const exclusionsData = JSON.parse(fs.readFileSync(path.join(chapterDir, 'exclusions.json'), 'utf-8'));
  const exclusions = Array.isArray(exclusionsData) ? exclusionsData : (exclusionsData.exclusions || []);

  // Candidate charges (12A)
  // 1) Base candidates: non-variant charges whose elements hold.
  const baseCandidates = chapter.charges
    .filter(c => !c.is_variant_of)
    .filter(c => chargeHolds(c, stateMap))
    .map(c => c.id);

  // 2) Variant candidates: attempt (or other variant) holds AND parent does NOT.
  //    Variant is reported only when it adds information beyond parent.
  const variantCandidates = [];
  for (const c of chapter.charges) {
    if (!c.is_variant_of) continue;
    if (!chargeHolds(c, stateMap)) continue;
    const parentHolds = baseCandidates.includes(c.is_variant_of);
    if (!parentHolds) variantCandidates.push(c.id);
  }

  // 3) Apply 13 exclusions (special_over_general etc.)
  const finalCandidates = applyExclusions(baseCandidates.concat(variantCandidates), chapter.charges, exclusions, stateMap);

  // 12B counter-evidence (R18: 未通過反證自檢者不得輸出為可能涉及)
  const counterEvidence = {};
  const doubtingCandidates = [];
  for (const cid of finalCandidates) {
    const charge = chapter.charges.find(c => c.id === cid);
    const failures = counterEvidenceCheck(charge, stateMap);
    counterEvidence[cid] = {
      necessary_elements: [
        ...(charge.requires_elements || []),
        ...(charge.requires_all_optional || []),
      ],
      failures,
      has_doubt: failures.length > 0,
    };
    if (failures.length > 0) doubtingCandidates.push(cid);
  }
  // R18: 未通過反證自檢的候選罪名移出 finalCandidates
  const verifiedCandidates = finalCandidates.filter(cid => !doubtingCandidates.includes(cid));

  // States
  const chargeStates = {};
  for (const c of chapter.charges) {
    if (c.is_variant_of) continue; // handled under parent
    chargeStates[c.id] = determineState(c, stateMap);
  }

  // R43: 法人不得作為行為人元件（依 stateMap 檢查法人被告）
  const actorWarnings = [];
  for (const charge of chapter.charges) {
    if (!charge.actor_subject_type_required) continue;
    for (const eid of (charge.requires_elements || [])) {
      const el = elements.elements.find(e => e.id === eid);
      if (!el) continue;
      // 依 stateMap 檢查該元件的 actor_subject_type（若 LLM 有提供）
      const stateEntry = stateMap[eid];
      const stateActorType = stateEntry?.actor_subject_type || el.actor_subject_type;
      if (stateActorType === '法人' && charge.actor_subject_type_required === '自然人') {
        actorWarnings.push({
          charge: charge.id,
          element: eid,
          message: '⚠️ R43：法人不得作為行為人元件，需追問實際行為之自然人',
          actor_subject_type: stateActorType,
        });
      }
    }
  }

  // 6C: 開放構成要件標「待法官補充」
  const openConstitution = elements.elements
    .filter(e => e.constitution_type === '開放')
    .map(e => ({
      element_id: e.id,
      element_name: e.name,
      key_doctrines: e.key_doctrines || [],
      message: '待法官補充（開放構成要件）',
    }));

  return {
    s14_output: {
      spec_version: 'v15',
      chapter_id: elements.chapter_id,
      generated_by: 'rule_engine.js (12A+12B+13+R43+6C)',
      llm_output_charges: false, // R30: LLM 不得直接輸出罪名
      llm_guard: {
        rule: 'R30: LLM 不得直接輸出罪名；罪名由本引擎規則計算',
        enforcement: '本引擎為唯一罪名輸出來源；LLM 讀取此 JSON 時，只能引用 candidate_charges，不得自行新增或修改',
        llm_must_do: [
          '抽取事實（第 4 層）',
          '映射元件（第 7 層）',
          '依缺口生成問句（第 16 層）',
        ],
        llm_must_not_do: [
          '直接輸出罪名（R30）',
          '修改 candidate_charges（R30）',
          '在對話中下判定「構成 XX 罪」',
        ],
      },
      candidate_charges: verifiedCandidates, // R18: 未通過反證自檢者移出
      charge_states: chargeStates,
      counter_evidence: counterEvidence,
      actor_warnings: actorWarnings,
      open_constitution: openConstitution,
      warnings: Object.values(counterEvidence)
        .filter(c => c.has_doubt)
        .map(c => ({
          charge: Object.keys(counterEvidence)[Object.values(counterEvidence).indexOf(c)],
          message: '⚠️ 判定疑義：移除必要元件未降級',
          failed_elements: c.failures,
        })),
    },
  };
}

module.exports = { run, S, isPositive, normalizeStatus, chargeHolds };

// CLI: node rule_engine.js <chapter_dir> <state_map.json>
if (require.main === module) {
  const [chapterDir, stateFile] = process.argv.slice(2);
  if (!chapterDir || !stateFile) {
    console.error('Usage: node rule_engine.js <chapter_dir> <state_map.json>');
    process.exit(1);
  }
  const raw = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
  // Support both raw state map and test-case wrapper ({state_map: ...})
  const stateMap = (raw && typeof raw === 'object' && raw.state_map) ? raw.state_map : raw;
  const result = run(chapterDir, stateMap);
  console.log(JSON.stringify(result, null, 2));
}

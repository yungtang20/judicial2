// question_engine.js
// 混合問句方案（C）：引擎依 rule_engine 的缺口 + question_library 查表產出問句
// 核心要件（necessary + requires_one_of 群組）→ 查表
// 其他缺口 → 標 `generated_by: llm`，由 LLM 依 v15 第九節措儀規則生成
// 
// ===== MODULE: LLM Question (rule-driven template) =====
// 可以 (Can):
// - 依 rule_engine 的缺口找出缺失元件
// - 依 question_library 查表產出標準問句
// - 標記非核心缺口由 LLM 生成
// - 去重（v15 第九節 14）
//
// 不可以 (Cannot):
// - 自行決定犯罪成立（僅標記缺口）
// - 自創法條（僅引用既有元件/罪名）
// - 產生非中立問題（須遵循 R33）
// - 修改 Fact Graph 或 Candidate 狀態
// - 決定流程（由 State Engine 控制）
//
// 必須由 State Engine 在 S3 PLAN / S16 階段呼叫
// =================================


const fs = require('fs');
const path = require('path');
const QLIB = require('./question_library.js');

function loadChapters() {
  const chapterDirs = fs.readdirSync(path.join(__dirname, '..', '00_資料', '罪章'))
    .filter(d => fs.statSync(path.join(__dirname, '..', '00_資料', '罪章', d)).isDirectory());
  const out = {};
  for (const d of chapterDirs) {
    const dir = path.join(__dirname, '..', '00_資料', '罪章', d);
    out[d] = {
      elements: JSON.parse(fs.readFileSync(path.join(dir, 'elements.json'), 'utf-8')),
      charges: JSON.parse(fs.readFileSync(path.join(dir, 'charges.json'), 'utf-8')),
      exclusions: JSON.parse(fs.readFileSync(path.join(dir, 'exclusions.json'), 'utf-8')),
    };
  }
  return out;
}

function normalizeStatus(state) {
  if (!state) return '資料不足';
  if (state.status === '推論符合' && (!state.source_raw || state.source_raw.length === 0)) return '資料不足';
  return state.status || '資料不足';
}
function isPositive(st) { return st === '符合' || st === '推論符合'; }

// 依 question_library 查表：給定 chapter_id / charge_id / element_id，回傳問句
function lookupQuestions(chapterId, chargeId, elementId) {
  const ch = QLIB.chapters[chapterId];
  if (!ch) return [];
  const charge = ch[chargeId];
  if (!charge) return [];
  const questions = charge.element_questions?.[elementId] || [];
  return questions;
}

// 依缺口產生問句
// stateMap: 元件狀態
// charges: 該罪章的 charges
// elements: 該罪章的 elements
// chapterId: 罪章 id
// inquiredIdentity: 受詢問人身分（被害人/證人/被告/關係人）
function generateQuestions(chapterId, stateMap, charges, elements, inquiredIdentity = '被害人') {
  const out = [];
  const seen = new Set(); // 去重（v15 第九節 14）

  // 通用 A 自由陳述段
  for (const q of QLIB.common.free_statement) {
    if (!q.identity_sensitive.includes(inquiredIdentity)) continue;
    const key = `A:${q.text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ ...q, generated_by: 'rule_library', bound_element: null });
  }

  // 通用 E 證據保全段
  for (const q of QLIB.common.evidence_preservation) {
    if (!q.identity_sensitive.includes(inquiredIdentity)) continue;
    const key = `E:${q.text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ ...q, generated_by: 'rule_library', bound_element: null });
  }

  // 缺口聚焦段（B）：查表核心要件
  const processedElements = new Set();
  const processedGroups = new Set();
  for (const charge of charges.charges) {
    const chargeId = charge.id;

    // 1) requires_elements 缺口
    for (const eid of (charge.requires_elements || [])) {
      if (processedElements.has(eid)) continue; // 跨罪名去重
      processedElements.add(eid);
      const st = normalizeStatus(stateMap[eid]);
      if (isPositive(st)) continue; // 已符合，不問
      const qs = lookupQuestions(chapterId, chargeId, eid);
      for (const q of qs) {
        if (!q.identity_sensitive.includes(inquiredIdentity)) continue;
        const key = `B:${q.text}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ ...q, generated_by: 'rule_library', bound_element: eid, bound_charge: chargeId });
      }
      // 查表無對應問句 → 標 LLM
      if (qs.length === 0) {
        out.push({
          stage: 'B', priority: 5, type: '開放',
          text: `（LLM 依 v15 措辭規則生成，針對元件 ${eid}）`,
          generated_by: 'llm', bound_element: eid, bound_charge: chargeId,
          identity_sensitive: [inquiredIdentity], neutral: true
        });
      }
    }

    // 2) requires_one_of 群組缺口
    for (const [groupId, candidates] of Object.entries(charge.requires_one_of || {})) {
      const anyPositive = candidates.some(eid => isPositive(normalizeStatus(stateMap[eid])));
      if (anyPositive) continue;
      if (processedGroups.has(groupId)) continue;
      processedGroups.add(groupId);
      for (const eid of candidates) {
        const qs = lookupQuestions(chapterId, chargeId, eid);
        for (const q of qs) {
          if (!q.identity_sensitive.includes(inquiredIdentity)) continue;
          const key = `B:${q.text}`;
          if (seen.has(key)) continue;
          seen.add(key);
          out.push({ ...q, generated_by: 'rule_library', bound_element: eid, bound_charge: chargeId, bound_group: groupId });
        }
        if (qs.length === 0) {
          out.push({
            stage: 'B', priority: 4, type: '開放',
            text: `（LLM 依 v15 措辭規則生成，針對群組 ${groupId} / 元件 ${eid}）`,
            generated_by: 'llm', bound_element: eid, bound_charge: chargeId, bound_group: groupId,
            identity_sensitive: [inquiredIdentity], neutral: true
          });
        }
      }
    }

    // 3) requires_all_optional / requires_any_result 缺口
    const extras = [
      ...(charge.requires_all_optional || []),
      ...(charge.requires_any_result || []),
    ];
    for (const eid of extras) {
      const st = normalizeStatus(stateMap[eid]);
      if (isPositive(st)) continue;
      const qs = lookupQuestions(chapterId, chargeId, eid);
      for (const q of qs) {
        if (!q.identity_sensitive.includes(inquiredIdentity)) continue;
        const key = `B:${q.text}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ ...q, generated_by: 'rule_library', bound_element: eid, bound_charge: chargeId });
      }
    }
  }

  // C 結尾開放段
  for (const q of QLIB.common.open_ending) {
    if (!q.identity_sensitive.includes(inquiredIdentity)) continue;
    const key = `C:${q.text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ ...q, generated_by: 'rule_library', bound_element: null });
  }

  // 依 priority 排序（v15 第九節 3：身分與程序 > 證據保全 > 證據能力 > 主觀 > 阻卻 > 其他 > 量刑）
  out.sort((a, b) => {
    const stageOrder = { A: 0, E: 1, B: 2, C: 3 };
    if (stageOrder[a.stage] !== stageOrder[b.stage]) return stageOrder[a.stage] - stageOrder[b.stage];
    return (a.priority || 5) - (b.priority || 5);
  });

  return out;
}

module.exports = { generateQuestions, lookupQuestions, loadChapters, buildQuestionQueue, updateQuestionStatus };

const QUESTION_STATUS = ['PENDING', 'ASKED', 'ANSWERED', 'OBSOLETE', 'NEED_REVIEW'];

function buildQuestionQueue(questions) {
  return questions.map((q, idx) => ({
    questionId: `Q${String(idx + 1).padStart(3, '0')}`,
    coreIssueId: q.bound_element || q.bound_charge || null,
    elementIds: q.bound_element ? [q.bound_element] : [],
    candidateIds: q.bound_charge ? [q.bound_charge] : [],
    priority: q.priority != null ? q.priority : 5,
    status: 'PENDING',
    text: q.text,
    stage: q.stage,
    generated_by: q.generated_by,
    identity_sensitive: q.identity_sensitive,
    neutral: q.neutral,
  }));
}

function updateQuestionStatus(queue, questionId, newStatus) {
  const q = queue.find(item => item.questionId === questionId);
  if (!q) return false;
  if (!QUESTION_STATUS.includes(newStatus)) return false;
  q.status = newStatus;
  return true;
}

// CLI: node question_engine.js <chapter_id> <state_map.json> [identity]
if (require.main === module) {
  const [chapterId, stateFile, identity] = process.argv.slice(2);
  if (!chapterId || !stateFile) {
    console.error('Usage: node question_engine.js <chapter_id> <state_map.json> [identity]');
    process.exit(1);
  }
  const chapters = loadChapters();
  if (!chapters[chapterId]) {
    console.error(`Chapter not found: ${chapterId}`);
    process.exit(1);
  }
  const stateMap = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
  const questions = generateQuestions(
    chapterId, stateMap,
    chapters[chapterId].charges,
    chapters[chapterId].elements,
    identity || '被害人'
  );
  console.log(JSON.stringify({ s11_output: { spec_version: 'v15', chapter_id: chapterId, questions } }, null, 2));
}

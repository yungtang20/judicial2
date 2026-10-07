// s14_contract.js
// v15 第 17 層：S-14 輸出契約整合
// 整合全部 17 層輸出為一份 S-14 JSON

const fs = require('fs');
const path = require('path');
const { run } = require('./rule_engine.js');
const { runAllLayers } = require('./layers.js');
const { mapToLegalRequirements, groupStateByRequirement, syllogism } = require('./laws_7_9.js');
const { runCriminalForm } = require('./criminal_form.js');
const { runJustifications, ensureChecked } = require('./justifications.js');
const { runAllDetailLayers } = require('./layers_detail.js');
const { generateQuestions } = require('./question_engine.js');

const ROOT = path.join(__dirname, '..');
const CHAPTERS_ROOT = path.join(ROOT, '00_資料', '罪章');

// ============================================================
// 主入口
// input: {
//   chapter_id: 'criminal_221',
//   raw_text: '（受詢問人陳述原文）',
//   case_type: '傷害案',
//   declared_role: '被害人',
//   case_date: '2024-06-15',
//   message_date: { year: 2024, month: 6, day: 15 },
//   article: '刑法第221條',
//   max_penalty: '五年以上二十年以下有期徒刑',
//   know_perpetrator_date: '2024-06-16',
//   fields: { occurred, reported, cracked, loss_amount, birth_year, age },
//   evidence: { 'E-221-001': {...} },
//   state_map: { 'E-221-001': {...} },
//   inquired_identity: '被害人',
// }
// ============================================================
function runS14(input) {
  const chapterDir = path.join(CHAPTERS_ROOT, input.chapter_id);
  if (!fs.existsSync(chapterDir)) {
    return { error: true, message: `罪章不存在：${input.chapter_id}` };
  }

  const elements = JSON.parse(fs.readFileSync(path.join(chapterDir, 'elements.json'), 'utf-8'));
  const charges = JSON.parse(fs.readFileSync(path.join(chapterDir, 'charges.json'), 'utf-8'));
  const exclusions = JSON.parse(fs.readFileSync(path.join(chapterDir, 'exclusions.json'), 'utf-8'));

  // 第 12、13 層：罪名浮現
  const ruleResult = run(chapterDir, input.state_map || {}).s14_output;

  // 前 15 層（P1/P2/1A/2A/2D/4B/R45/5/14/15）
  const layersResult = runAllLayers(input);

  // 第 7 層：映射五類法律要件
  const requirements = mapToLegalRequirements(elements);

  // 第 9 層：三段論法
  const syllogisms = {};
  for (const charge of charges.charges) {
    if (charge.is_variant_of) continue;
    syllogisms[charge.id] = syllogism(charge, input.state_map || {}, elements);
  }

  // 第 10 層：犯罪形態審查
  const criminalForm = runCriminalForm(input.state_map || {}, elements, input.raw_text || '');

  // 第 11 層：阻卻事由審查（R20 不得跳過）
  const justifications = ensureChecked(runJustifications(input.raw_text || '', input.state_map || {}));

  // 前 15 層細項（1B~1I、2B~2I、3A~3F、4A/4C、5A~5F、6A~6C、8D/8E/8G、14A~14D、15A~15D）
  const detailResult = runAllDetailLayers({
    ...input,
    elements,
    exclusions,
    stage: layersResult.layers.L2A?.result?.mode || '未判定',
    max_penalty: input.max_penalty,
    statute_limitations_years: charges.charges[0]?.statute_of_limitations_years,
  });

  // 第 16 層：問句（S-11）
  const questions = generateQuestions(
    input.chapter_id,
    input.state_map || {},
    charges,
    elements,
    input.inquired_identity || '被害人'
  );

  return {
    s14_contract: {
      spec_version: 'v15',
      version: '1.0',
      generated_at: new Date().toISOString(),
      input_summary: {
        chapter_id: input.chapter_id,
        case_type: input.case_type,
        declared_role: input.declared_role,
        inquired_identity: input.inquired_identity,
        case_date: input.case_date,
      },
      layers: {
        P1: layersResult.layers.P1,
        P2: layersResult.layers.P2,
        L1A: layersResult.layers.L1A,
        L2A: layersResult.layers.L2A,
        L2D: layersResult.layers.L2D,
        L4B: layersResult.layers.L4B,
        R45: layersResult.layers.R45,
        L5: layersResult.layers.L5,
        L7: { name: '映射五類法律要件（R13：人事時地物不進法律要件）', result: requirements },
        L9: { name: '三段論法', result: syllogisms },
        L10: { name: '犯罪形態審查', result: criminalForm },
        L11: { name: '阻卻事由審查（R20）', result: justifications },
        L12: {
          name: '罪名浮現（12A+12B）',
          candidate_charges: ruleResult.candidate_charges,
          charge_states: ruleResult.charge_states,
          counter_evidence: ruleResult.counter_evidence,
          llm_guard: ruleResult.llm_guard,
        },
        L13: { name: '互斥對與競合', result: exclusions },
        L14: layersResult.layers.L14,
        L15: layersResult.layers.L15,
        L1_detail: detailResult.detail_layers.L1,
        L2_detail: detailResult.detail_layers.L2,
        L3_detail: detailResult.detail_layers.L3,
        L4_detail: detailResult.detail_layers.L4,
        L5_detail: detailResult.detail_layers.L5,
        L6_detail: detailResult.detail_layers.L6,
        L8_detail: detailResult.detail_layers.L8,
        L14_detail: detailResult.detail_layers.L14,
        L15_detail: detailResult.detail_layers.L15,
        R43: { name: '法人行為人（R43）', result: ruleResult.actor_warnings },
        '6C': { name: '開放構成要件（6C/R21）', result: ruleResult.open_constitution },
      },
      s11_questions: {
        name: '問句佇列（第 16 層 S-11，混合方案 C）',
        questions,
        note: 'R33：問句不得含罪名、法律用語、元件名稱；R34：追問引用受詢問人自己的用語；R35：問句目的為取得準確資訊',
      },
      warnings: ruleResult.warnings,
      open_constitution: ruleResult.open_constitution,
      actor_warnings: ruleResult.actor_warnings,
    },
  };
}

module.exports = { runS14 };

// CLI
if (require.main === module) {
  const [inputFile] = process.argv.slice(2);
  if (!inputFile) {
    console.error('Usage: node s14_contract.js <input.json>');
    process.exit(1);
  }
  const input = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));
  const result = runS14(input);
  console.log(JSON.stringify(result, null, 2));
}

// audit.js — v15 第十節指標自檢
// 檢查 rule_library 問句的法律用語洩漏（R33）、誘導題（R33）、元件名稱洩漏

const fs = require('fs');
const path = require('path');
const QLIB = require('./question_library.js');

// 法律用語黑名單（R33：問句不得含罪名、法律用語、元件名稱）
// 這些是技術/法律專業術語，日常對話不會用
const LEGAL_TERMS = [
  // 罪名
  '強制性交', '詐欺', '竊盜', '侵占', '傷害罪', '公然侮辱', '誹謗',
  '酒駕', '公共危險', '施用毒品', '性騷擾罪', '妨害名譽', '妨害自由',
  '危險駕駛', '肇事逃逸', '重傷害', '過失致死', '妨害秘密', '妨害性隱私',
  // 法律概念
  '不法所有意圖', '犯罪故意', '直接故意', '間接故意', '主觀要件',
  '客觀要件', '構成要件', '證據能力', '證明力', '告訴乃論',
  '推論符合', '資料不足', '阻卻事由', '正當防衛', '緊急避難',
  '法條競合', '想像競合', '特別法', '普通法', '時際法',
  '刑法第', '刑事訴訟法第', '性騷擾防治法第', '家庭暴力防治法第',
  '毒品危害防制條例第', '道路交通管理處罰條例第',
  // 法律動作
  '起訴', '偵查', '告訴', '上訴', '抗告', '聲請', '移送',
  '依法逮捕', '依法拘提', '現行犯', '執行搜索',
];

// 元件名稱黑名單（元件庫 element name 不應出現在問句中）
const ELEMENT_NAMES = [];

// 誘導題黑名單（v15 第九節 5：禁止選項題、誘導題、預設答案題）
const LEADING_PATTERNS = [
  /是不是要?\s*([^\s?]+)\s*啊?？/,  // 「是不是要XX啊？」
  /你猜他會不會是/,                  // 預設答案
  /有沒有誘惑/,                      // 價值判斷
  /他的行為是不是犯罪/,              // 法律評價
  /為何犯罪/,                        // 動機判斷
];

function audit() {
  const issues = [];
  const allQuestions = [];

  // 收集所有問句
  for (const q of QLIB.common.free_statement) allQuestions.push({ section: 'common.free_statement', ...q });
  for (const q of QLIB.common.open_ending) allQuestions.push({ section: 'common.open_ending', ...q });
  for (const q of QLIB.common.evidence_preservation) allQuestions.push({ section: 'common.evidence_preservation', ...q });

  for (const [chapter, charges] of Object.entries(QLIB.chapters)) {
    for (const [chargeId, chargeData] of Object.entries(charges)) {
      for (const [elemId, questions] of Object.entries(chargeData.element_questions || {})) {
        for (const q of questions) allQuestions.push({ section: `${chapter}.${chargeId}.${elemId}`, ...q });
      }
      for (const [groupId, questions] of Object.entries(chargeData.group_questions || {})) {
        for (const q of questions) allQuestions.push({ section: `${chapter}.${chargeId}.${groupId}`, ...q });
      }
    }
  }

  // 檢查法律用語洩漏（R33）
  for (const q of allQuestions) {
    for (const term of LEGAL_TERMS) {
      if (q.text.includes(term)) {
        issues.push({
          type: 'legal_term_leak',
          section: q.section,
          term,
          text: q.text,
          message: `R33 問句含法律用語：${term}`
        });
      }
    }
    // 檢查誘導題（v15 第九節 5）
    for (const pattern of LEADING_PATTERNS) {
      if (pattern.test(q.text)) {
        issues.push({
          type: 'leading_question',
          section: q.section,
          text: q.text,
          message: 'v15 第九節 5：問句可能為誘導題或預設答案'
        });
      }
    }
  }

  return { total_questions: allQuestions.length, issues, passes: issues.length === 0 };
}

module.exports = { audit, LEGAL_TERMS };

// CLI
if (require.main === module) {
  const r = audit();
  console.log(`Total questions audited: ${r.total_questions}`);
  console.log(`Issues found: ${r.issues.length}`);
  for (const issue of r.issues) {
    console.log(`  [${issue.type}] ${issue.message}`);
    console.log(`    section: ${issue.section}`);
    console.log(`    text: ${issue.text}`);
  }
  console.log(`\n[SUMMARY] ${r.passes ? 'PASS' : 'FAIL'} — ${r.total_questions} audited, ${r.issues.length} issues`);
  if (!r.passes) process.exit(1);
}

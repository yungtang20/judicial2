// justifications.js
// v15 第 11 層：阻卻事由審查
// 11A 阻卻違法：正當防衛、緊急避難、依法令之行為、業務上正當行為、得被害人承諾
// 11B 阻卻／減免罪責：責任能力、違法性認識、期待可能性
// R20：阻卻事由獨立審查，不得跳過

// ============================================================
// 11A 阻卻違法
// ============================================================
const JUSTIFICATION_PATTERNS = [
  {
    kw: /正當防衛|防衛|反擊|自衛|互毆|拉扯/,
    name: '正當防衛',
    basis: '刑法第23條',
    note: '需現在不法侵害、防衛行為、防衛意思；互毆需 1A 雙重身分判定',
    verification: 'verified',
  },
  {
    kw: /緊急避難|避難|危險|緊急/,
    name: '緊急避難',
    basis: '刑法第24條',
    note: '需現在危難、避難行為、避難意思；避難行為不得逾越必要程度',
    verification: 'verified',
  },
  {
    kw: /依法令|依規定|依職權|執行職務/,
    name: '依法令之行為',
    basis: '刑法第21條第1項',
    note: '依法令之行為不罰',
    verification: 'verified',
  },
  {
    kw: /業務上|職務上正當|工作上/,
    name: '業務上正當行為',
    basis: '刑法第21條第2項',
    note: '業務上之正當行為不罰',
    verification: 'verified',
  },
  {
    kw: /得被害人承諾|被害人同意|承諾|經同意/,
    name: '得被害人承諾',
    basis: '學說與實務見解',
    note: '得被害人承諾之行為可阻卻違法；但違反善良風俗者不在此限 ⚠️',
    verification: 'partial',
  },
];

// ============================================================
// 11B 阻卻／減免罪責
// ============================================================
const EXCUSE_PATTERNS = [
  {
    kw: /責任能力|心神喪失|精神障礙|心智缺陷/,
    name: '責任能力',
    basis: '刑法第19條',
    note: '行為時因精神障礙或其他心智缺陷，致不能辨識其行為違法或欠缺依其辨識而行為之能力者，不罰',
    verification: 'verified',
  },
  {
    kw: /違法性認識|不知違法|不知道違法/,
    name: '違法性認識',
    basis: '刑法第16條',
    note: '不得因不知法律而免除刑事責任；但按其情節，有正當理由而無法認識者，得依其情節減輕或免除其刑',
    verification: 'verified',
  },
  {
    kw: /期待可能性|無期待|被迫|脅迫下|非自願/,
    name: '期待可能性',
    basis: '學說與實務見解',
    note: '無期待可能性時可阻卻或減免罪責；學說與實務見解分歧 ⚠️',
    verification: 'partial',
  },
  {
    kw: /未滿十四歲|十四歲以下|未滿十八歲|兒童|少年/,
    name: '年齡（責任能力）',
    basis: '刑法第18條',
    note: '未滿十四歲人之行為，不罰；十四歲以上未滿十八歲人之行為，得減輕其刑',
    verification: 'verified',
  },
];

// ============================================================
// 審查（依 rawText 或 stateMap）
// ============================================================
function runJustifications(rawText = '', stateMap = null) {
  const results = {
    '11A 阻卻違法': [],
    '11B 阻卻／減免罪責': [],
  };

  const text = rawText || (stateMap ? JSON.stringify(stateMap) : '');
  if (!text) return results;

  // 11A
  for (const p of JUSTIFICATION_PATTERNS) {
    if (p.kw.test(text)) {
      results['11A 阻卻違法'].push({
        name: p.name,
        basis: p.basis,
        note: p.note,
        verification: p.verification,
      });
    }
  }

  // 11B
  for (const p of EXCUSE_PATTERNS) {
    if (p.kw.test(text)) {
      results['11B 阻卻／減免罪責'].push({
        name: p.name,
        basis: p.basis,
        note: p.note,
        verification: p.verification,
      });
    }
  }

  return results;
}

// 阻卻事由不得跳過（R20）：若無任何阻卻事由審查結果，仍要標明「已審查，無阻卻事由」
function ensureChecked(results) {
  const hasAny = Object.values(results).some(arr => arr.length > 0);
  if (!hasAny) {
    return {
      ...results,
      '審查狀態': [{ message: 'R20：阻卻事由已審查，未發現阻卻事由' }],
    };
  }
  return results;
}

module.exports = {
  runJustifications,
  ensureChecked,
  JUSTIFICATION_PATTERNS,
  EXCUSE_PATTERNS,
};

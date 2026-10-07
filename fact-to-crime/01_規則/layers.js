// layers.js
// v15 前 15 層（除第 12、13、16 層已在 rule_engine/question_engine 實作）
// P1 案件切分、P2 日期正規化、1A 身分判定、2A 分流、2D 告訴乃論、
// 4B 欄位一致性、5 證據能力、14 門檻時效、15 量刑、S-14 契約

const fs = require('fs');
const path = require('path');

// ============================================================
// P1 案件切分（R41）
// 一則訊息含多件報告時，先切成獨立案件
// 依「一、案由：」等標題切分
// ============================================================
function splitCases(rawText) {
  if (!rawText || typeof rawText !== 'string') return [];
  // 切分標題：一、案由、二、時間 等編號開頭
  const caseStartPattern = /^[一二三四五六七八九十]+[、．.]\s*(案由|查獲)/m;
  const lines = rawText.split(/\r?\n/);
  const cases = [];
  let current = null;
  for (const line of lines) {
    if (caseStartPattern.test(line.trim()) && current) {
      // 新案件開始
      cases.push(current);
      current = null;
    }
    if (!current) {
      // 檢查是否為新案件的開頭（時間戳 + 案由）
      const tsMatch = line.match(/^\d{1,2}:\d{2}\s/);
      if (tsMatch && caseStartPattern.test(rawText.slice(rawText.indexOf(line)))) {
        current = { timestamp: tsMatch[0].trim(), text: line };
        continue;
      }
    }
    if (current) current.text += '\n' + line;
  }
  if (current) cases.push(current);
  return cases;
}

// ============================================================
// P2 日期正規化（R42）
// 處理缺年（0128/0955）、民國七碼（1141009）、民國年月日
// 推定值標「推定」，不得自動採用（R42）
// ============================================================
function normalizeDate(input, messageDate = null) {
  if (!input || typeof input !== 'string') return { raw: input, status: '資料不足' };

  const trimmed = input.trim();

  // 民國七碼：1141009 → 2025-10-09
  let m = trimmed.match(/^(\d{3})(\d{2})(\d{2})$/);
  if (m) {
    return {
      raw: input,
      year: 1911 + parseInt(m[1]),
      month: parseInt(m[2]),
      day: parseInt(m[3]),
      iso: `${1911 + parseInt(m[1])}-${m[2]}-${m[3]}`,
      status: '推定',
      note: 'R42：民國七碼格式，推定值須由人員確認',
    };
  }

  // 民國年月日：115年06月06日07時20分
  m = trimmed.match(/^(\d{2,3})年(\d{1,2})月(\d{1,2})日(\d{1,2})時(\d{1,2})分?/);
  if (m) {
    return {
      raw: input,
      year: 1911 + parseInt(m[1]),
      month: parseInt(m[2]),
      day: parseInt(m[3]),
      hour: parseInt(m[4]),
      minute: m[5] ? parseInt(m[5]) : 0,
      iso: `${1911 + parseInt(m[1])}-${String(m[2]).padStart(2, '0')}-${String(m[3]).padStart(2, '0')}T${String(m[4]).padStart(2, '0')}:${String(m[5] || 0).padStart(2, '0')}`,
      status: '推定',
      note: 'R42：民國年月日格式，推定值須由人員確認',
    };
  }

  // 缺年：0128/0955（月日/時分）
  m = trimmed.match(/^(\d{2})(\d{2})\/(\d{2})(\d{2})$/);
  if (m) {
    const year = messageDate ? messageDate.year : null;
    return {
      raw: input,
      month: parseInt(m[1]),
      day: parseInt(m[2]),
      hour: parseInt(m[3]),
      minute: parseInt(m[4]),
      year,
      iso: year ? `${year}-${m[1]}-${m[2]}T${m[3]}:${m[4]}` : null,
      status: year ? '推定' : '資料不足',
      note: year
        ? 'R42：缺年，年份由訊息日期推定，不得自動採用'
        : 'R42：缺年且無訊息日期可推定',
    };
  }

  // 西元年：2024-06-15
  m = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) {
    return {
      raw: input, year: parseInt(m[1]), month: parseInt(m[2]), day: parseInt(m[3]),
      iso: trimmed, status: '推定', note: 'R42：西元年格式',
    };
  }

  return { raw: input, status: '資料不足', note: 'P2：無法辨識的日期格式' };
}

// ============================================================
// 1A 受詢問人身分判定（R23、R38）
// 被告／證人／被害人／關係人，可兼具
// 陳述顯示本人有涉案行為時重判
// ============================================================
function determineIdentity(rawText, declaredRole = null) {
  if (!rawText) return { identities: [], primary: null, warnings: [] };

  const warnings = [];
  const identities = new Set();

  // 依宣告身分
  if (declaredRole) identities.add(declaredRole);

  // 依陳述關鍵詞判定
  const patterns = [
    { kw: /報案人|被害人|遭[我渠他]|受害/, role: '被害人' },
    { kw: /涉嫌|被告|嫌犯|犯嫌|嫌疑人/, role: '被告' },
    { kw: /證人|目擊|見聞/, role: '證人' },
    { kw: /告訴代理人|告發人|關係人/, role: '關係人' },
    { kw: /報案代理人|代為報案/, role: '關係人', note: '代理報案（v15 1A）' },
  ];
  for (const p of patterns) {
    if (p.kw.test(rawText)) {
      identities.add(p.role);
      if (p.note) warnings.push(p.note);
    }
  }

  // R38：陳述顯示本人有涉案行為時重判
  if (/本人.{0,10}(涉嫌|涉案|逮捕|拘提)/.test(rawText)) {
    if (!identities.has('被告')) {
      identities.add('被告');
      warnings.push('R38：陳述顯示本人有涉案行為，重新判定身分並補權利告知');
    }
  }

  const arr = [...identities];
  // 1A 主角色：被害人 > 被告 > 證人 > 關係人（筆錄模式優先）
  const priority = ['被害人', '被告', '證人', '關係人'];
  const primary = priority.find(r => arr.includes(r)) || null;

  return { identities: arr, primary, warnings };
}

// ============================================================
// 2A 分流（行政/刑罰/非刑案/程序案）（R12、R40）
// ============================================================
const NON_CRIME_CATEGORIES = [
  '相驗', '死亡案', '火災', '疾病救護', '失蹤', '為民服務', '自殺',
  '備案', '申請報案證明', '調閱監視器', '申請調閱', '災害事件',
  '糾紛', '其他', '其他案類', '兒少通報', '家庭暴力通報',
];

const ADMIN_CATEGORIES = [
  '社會秩序維護法', '社維', '性騷擾防治法',
];

const PROCEDURAL_CATEGORIES = [
  '通緝', '查獲.*通緝', '逮捕',
];

function classifyCase(caseType) {
  if (!caseType) return { mode: '未判定', warnings: ['填空區未填（v15 限制 6）'] };

  for (const p of PROCEDURAL_CATEGORIES) {
    if (new RegExp(p).test(caseType)) {
      return { mode: '程序案', warnings: ['v15 2I：程序案模式，只跑第 1、2 層與逮捕程序，不做第 7~13 層'] };
    }
  }
  for (const c of NON_CRIME_CATEGORIES) {
    if (caseType.includes(c)) {
      return { mode: '非刑案', warnings: ['v15 2A：非刑案類走行政流程，不進元件比對（R40）'] };
    }
  }
  for (const c of ADMIN_CATEGORIES) {
    if (caseType.includes(c)) {
      return { mode: '行政', warnings: ['v15 2A：行政罰分流；涉刑案時雙軌'] };
    }
  }
  return { mode: '刑罰', warnings: [] };
}

// ============================================================
// 2D 告訴乃論（v15 2D）
// ============================================================
// 告訴乃論清單（v15 附錄 B；⚠️ 需查證）
const PRIVATE_PROSECUTION_LIST = [
  '§277 傷害（基本）', '§284 過失傷害', '§287 過失致死',
  '§309 公然侮辱', '§310 誹謗', '§305 恐嚇危害安全', '§304 強制罪',
  '§358 無故入侵', '§359 取得刪除變更', '§360 干擾系統', '§362 製作病毒',
  '§221 強制性交（告訴乃論，§221-1 加重為非告訴乃論）',
  '§320 竊盜（非告訴乃論）',
  '§335 侵占（非告訴乃論）',
  '§339 詐欺（非告訴乃論）',
];

function isPrivateProsecution(article) {
  if (!article) return { result: '資料不足', warning: '⚠️ 告訴乃論清單需查證（v15 附錄 B）' };
  const hit = PRIVATE_PROSECUTION_LIST.find(p => article.includes(p.split(' ')[0]));
  return { result: hit ? '是' : '非', warning: hit ? '' : '⚠️ 需查證' };
}

// ============================================================
// 4B 欄位一致性檢查（R36）
// 時間先後、金額與案情、管轄單位、年次與年齡
// 矛盾者標「⚠️ 欄位矛盾」，不自動更正
// ============================================================
function fieldConsistencyCheck(fields, rawText = '') {
  const warnings = [];
  if (!fields || typeof fields !== 'object') return warnings;

  // 時間先後：發生 vs 報案 vs 破獲
  if (fields.occurred && fields.reported && fields.cracked) {
    if (new Date(fields.cracked) < new Date(fields.reported)) {
      warnings.push({
        type: 'time_order', field: 'cracked',
        message: '⚠️ 欄位矛盾：破獲時間早於報案時間',
      });
    }
  }
  if (fields.occurred && fields.reported) {
    if (new Date(fields.reported) < new Date(fields.occurred)) {
      warnings.push({
        type: 'time_order', field: 'reported',
        message: '⚠️ 欄位矛盾：報案時間早於發生時間',
      });
    }
  }

  // 金額與案情（v15 4B）
  if (fields.loss_amount !== undefined && fields.loss_amount !== null) {
    const hasMoneyContext = /匯款|轉帳|損失|遭詐|交付|款項|元/.test(rawText);
    if (!hasMoneyContext) {
      warnings.push({
        type: 'amount_vs_facts', field: 'loss_amount',
        message: '⚠️ 欄位矛盾：損失金額欄位無案情支持（v15 4B）',
      });
    }
  }

  // 年次與年齡
  if (fields.birth_year && fields.age !== undefined && fields.age !== null) {
    const currentYear = new Date().getFullYear() - 1911;
    const calcAge = currentYear - fields.birth_year;
    if (Math.abs(calcAge - fields.age) > 1) {
      warnings.push({
        type: 'year_vs_age', field: 'age',
        message: `⚠️ 欄位矛盾：年次 ${fields.birth_year} 與年齡 ${fields.age} 不符（推算 ${calcAge}）`,
      });
    }
  }

  return warnings;
}

// 事發至報案時間差（R45）
function timeGapBetween(occurred, reported) {
  if (!occurred || !reported) return { gap: null, high_priority_evidence: false };
  const diffMs = new Date(reported) - new Date(occurred);
  const days = diffMs / (1000 * 60 * 60 * 24);
  return {
    gap_days: days,
    high_priority_evidence: days >= 30, // R45：差距大者提高證據保全優先（門檻待你決定）
    note: days >= 30 ? 'R45：事發至報案差距大（≥30 日），證據保全問句提高優先' : '',
  };
}

// ============================================================
// 5 證據能力審查（R24、R5）
// ============================================================
function evidenceAdmissibilityCheck(evidence) {
  const warnings = [];
  if (!evidence) return warnings;

  for (const [eid, ev] of Object.entries(evidence)) {
    const adm = ev.evidence_admissibility;
    if (!adm) {
      warnings.push({
        element: eid,
        message: '⚠️ 5F：證據能力未審查，該證據不得進入元件比對（R24）',
      });
    } else if (adm === '排除') {
      warnings.push({
        element: eid,
        message: '⚠️ 5F：證據能力被排除，不得進入元件比對',
      });
    } else if (ev.note && ev.note.includes('見解分歧')) {
      warnings.push({
        element: eid,
        message: '⚠️ 5E：未全程錄音之筆錄，學說與實務見解分歧',
      });
    }
  }
  return warnings;
}

// ============================================================
// 14 階段門檻與追訴權時效（R25、R28）
// ============================================================
// 追訴權時效（刑§80，依最重本刑分級）⚠️ 條文需查證
const STATUTE_OF_LIMITATIONS_TIERS = [
  { max_penalty: '死刑、無期徒刑或十年以上有期徒刑', years: 20, tier: 1 },
  { max_penalty: '三年以上十年未滿有期徒刑', years: 10, tier: 2 },
  { max_penalty: '一年以上三年未滿有期徒刑', years: 5, tier: 3 },
  { max_penalty: '一年未滿有期徒刑', years: 3, tier: 4 },
];

function statuteOfLimitations(maxPenalty) {
  if (!maxPenalty) return { years: null, warning: '⚠️ 資料不足' };
  for (const tier of STATUTE_OF_LIMITATIONS_TIERS) {
    if (maxPenalty.includes(tier.max_penalty.split('或')[0]) || maxPenalty.includes(tier.max_penalty)) {
      return { years: tier.years, tier: tier.tier, warning: '' };
    }
  }
  return { years: null, warning: '⚠️ 刑度級距未對應（刑§80 ⚠️ 需查證）' };
}

// 告訴期間（刑訴§237：知悉犯人時起六個月）✓
function complaintPeriod(knowPerpetratorDate, caseDate = null) {
  if (!knowPerpetratorDate) return { expired: null, warning: '知悉犯人時點空白（v15 填空區）' };
  const sixMonthsLater = new Date(knowPerpetratorDate);
  sixMonthsLater.setMonth(sixMonthsLater.getMonth() + 6);
  const now = caseDate ? new Date(caseDate) : new Date();
  return {
    deadline: sixMonthsLater.toISOString().split('T')[0],
    expired: now > sixMonthsLater,
    warning: '',
  };
}

// ============================================================
// 15 量刑層（R11）
// ============================================================
function sentencingFactors(rawText = '') {
  const factors = [];
  // 15A 量刑事由（刑§57）✓
  if (/累犯/.test(rawText)) factors.push({ factor: '累犯', basis: '刑§47① ✓' });
  if (/自首/.test(rawText)) factors.push({ factor: '自首', basis: '刑§62 ✓' });
  if (/緩刑/.test(rawText)) factors.push({ factor: '緩刑', basis: '刑§74' });
  if (/易科罰金/.test(rawText)) factors.push({ factor: '易科罰金', basis: '刑§41' });
  if (/沒收/.test(rawText)) factors.push({ factor: '沒收', basis: '刑§38' });
  return factors;
}

// ============================================================
// 主入口：跑全部層
// ============================================================
function runAllLayers(input) {
  const out = {
    spec_version: 'v15',
    layers: {},
  };

  // P1 案件切分
  out.layers.P1 = {
    name: '案件切分（R41）',
    result: input.raw_text ? splitCases(input.raw_text).length : 0,
    warnings: [],
  };

  // P2 日期正規化
  out.layers.P2 = {
    name: '日期正規化（R42）',
    result: input.case_date ? normalizeDate(input.case_date, input.message_date) : null,
    warnings: [],
  };

  // 1A 身分判定
  out.layers.L1A = {
    name: '受詢問人身分判定（R23、R38）',
    result: determineIdentity(input.raw_text, input.declared_role),
    warnings: [],
  };

  // 2A 分流
  out.layers.L2A = {
    name: '分流（行政/刑罰/非刑案/程序案）',
    result: classifyCase(input.case_type),
    warnings: [],
  };

  // 2D 告訴乃論
  out.layers.L2D = {
    name: '告訴乃論',
    result: isPrivateProsecution(input.article),
    warnings: [],
  };

  // 4B 欄位一致性
  out.layers.L4B = {
    name: '欄位一致性檢查（R36）',
    result: fieldConsistencyCheck(input.fields, input.raw_text),
    warnings: [],
  };

  // R45 時間差
  out.layers.R45 = {
    name: '事發至報案時間差',
    result: timeGapBetween(input.fields?.occurred, input.fields?.reported),
    warnings: [],
  };

  // 5 證據能力
  out.layers.L5 = {
    name: '證據能力審查（R24）',
    result: evidenceAdmissibilityCheck(input.evidence),
    warnings: [],
  };

  // 14 階段門檻與時效
  out.layers.L14 = {
    name: '階段門檻與追訴權時效（刑§80 ⚠️）',
    result: statuteOfLimitations(input.max_penalty),
    complaint_period: complaintPeriod(input.know_perpetrator_date, input.case_date),
    warnings: [],
  };

  // 15 量刑
  out.layers.L15 = {
    name: '量刑層（R11）',
    result: sentencingFactors(input.raw_text),
    warnings: [],
  };

  return out;
}

module.exports = {
  runAllLayers,
  splitCases,
  normalizeDate,
  determineIdentity,
  classifyCase,
  isPrivateProsecution,
  fieldConsistencyCheck,
  timeGapBetween,
  evidenceAdmissibilityCheck,
  statuteOfLimitations,
  complaintPeriod,
  sentencingFactors,
};

// CLI
if (require.main === module) {
  const [inputFile] = process.argv.slice(2);
  if (!inputFile) {
    console.error('Usage: node layers.js <input.json>');
    process.exit(1);
  }
  const input = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));
  const result = runAllLayers(input);
  console.log(JSON.stringify(result, null, 2));
}

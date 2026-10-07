// layers_detail.js
// v15 第 1~6 層細項 + 第 8、14、15 層細項
// 補足 layers.js 未涵蓋的細項檢查

const fs = require('fs');
const path = require('path');

// ============================================================
// 第 1 層細項：1B~1I
// ============================================================
// 1B 權利告知（刑訴§95 ✓）
const RIGHTS_NOTIFIED_ITEMS = [
  { item: '犯罪嫌疑', law: '刑訴§95①①' },
  { item: '得保持緘默', law: '刑訴§95①②' },
  { item: '得選任辯護人', law: '刑訴§95①③' },
  { item: '得請求調查有利之證據', law: '刑訴§95①④' },
];

function checkRightsNotified(rawText = '') {
  const results = [];
  for (const item of RIGHTS_NOTIFIED_ITEMS) {
    const kw = item.item.replace(/[犯罪嫌疑]/g, '');
    const found = rawText.includes(item.item) || rawText.includes(kw);
    results.push({
      item: item.item,
      law: item.law,
      notified: found,
      warning: found ? '' : '⚠️ 1B：權利告知未確認（刑訴§95 ✓）',
    });
  }
  return results;
}

// 1C 告訴期間告知（刑訴§237 ✓，知悉犯人時起六個月）
function checkComplaintPeriodNotified(rawText = '') {
  const found = /六個月|6個月|告訴期間|告訴乃論/.test(rawText);
  return {
    notified: found,
    warning: found ? '' : '⚠️ 1C：告訴期間告知未確認（刑訴§237 ✓）',
  };
}

// 1D 夜間詢問限制（刑訴§100-3 ✓）
// 例外：明示同意／夜間逮捕僅查驗人別／檢察官或法官許可／急迫情形
// 「夜間」以氣象局日沒時間為準
function checkNightInterrogation(rawText = '', interrogationTime = null, sunsetTime = null) {
  const result = {
    is_night: false,
    exception: null,
    warning: '',
  };

  // 判定是否夜間
  if (interrogationTime && sunsetTime) {
    const it = interrogationTime.match(/(\d{1,2}):(\d{2})/);
    const st = sunsetTime.match(/(\d{1,2}):(\d{2})/);
    if (it && st) {
      const itMin = parseInt(it[1]) * 60 + parseInt(it[2]);
      const stMin = parseInt(st[1]) * 60 + parseInt(st[2]);
      result.is_night = itMin >= stMin; // 日沒後為夜間
    }
  } else {
    // 備援：傳統夜間定義（18:00~06:00）⚠️ 需查證
    result.is_night = /夜間|晚上|凌晨/.test(rawText);
    result.warning = '⚠️ 1D：日沒時間需查證（以氣象局為準）';
  }

  if (result.is_night) {
    // 檢查例外
    const exceptions = [
      { kw: /明示同意|同意製作/, text: '明示同意' },
      { kw: /夜間逮捕.{0,10}查驗人別|僅查驗人別/, text: '夜間逮捕僅查驗人別' },
      { kw: /檢察官.{0,5}許可|法官.{0,5}許可/, text: '檢察官或法官許可' },
      { kw: /急迫|緊急/, text: '急迫情形' },
    ];
    for (const ex of exceptions) {
      if (ex.kw.test(rawText)) {
        result.exception = ex.text;
        break;
      }
    }
    if (!result.exception) {
      result.warning = '⚠️ 1D：夜間詢問需確認例外情形（刑訴§100-3 ✓）';
    }
  }

  return result;
}

// 1E 全程連續錄音，必要時錄影（刑訴§100-1、§100-2）
function checkContinuousRecording(rawText = '') {
  const found = /錄音|錄影|全程連續錄音/.test(rawText);
  return {
    recorded: found,
    warning: found ? '' : '⚠️ 1E：全程連續錄音未確認（刑訴§100-1、§100-2）',
  };
}

// 1F 禁止強暴、脅迫、利誘、詐欺、疲勞訊問及其他不正方法（刑訴§98 ✓）
function checkImproperMethods(rawText = '') {
  const improperPatterns = [
    { kw: /強暴|暴力/, text: '強暴' },
    { kw: /脅迫|威脅/, text: '脅迫' },
    { kw: /利誘|利誘/.test ? /利誘/ : null, text: '利誘' },
    { kw: /詐欺|欺騙/, text: '詐欺' },
    { kw: /疲勞訊問|疲勞/, text: '疲勞訊問' },
    { kw: /不正方法/, text: '不正方法' },
  ];
  const found = [];
  for (const p of improperPatterns) {
    if (p.kw && p.kw.test(rawText)) found.push(p.text);
  }
  return {
    improper_methods: found,
    warning: found.length > 0
      ? `⚠️ 1F：偵測到可能的不正方法（刑訴§98 ✓）：${found.join('、')}`
      : '',
  };
}

// 1G 通譯、辯護人在場 ⚠️
function checkInterpreterAndCounsel(rawText = '') {
  const results = {
    interpreter: { present: false, warning: '' },
    counsel: { present: false, warning: '' },
  };
  // 通譯
  if (/通譯|翻譯|外語/.test(rawText)) {
    results.interpreter.present = true;
  } else if (/外籍|外國人|美國人|日籍|韓籍/.test(rawText)) {
    results.interpreter.warning = '⚠️ 1G：受詢問人可能需通譯，需確認（刑訴§95 以外條文 ⚠️）';
  }
  // 辯護人
  if (/辯護人|律師/.test(rawText)) {
    results.counsel.present = true;
  } else if (/被告|嫌疑人|犯嫌/.test(rawText)) {
    results.counsel.warning = '⚠️ 1G：辯護人在場未確認 ⚠️';
  }
  return results;
}

// 1H 陪同、送達地址、自由意識、實在性、簽名捺印
function checkAccompanyingAndOther(rawText = '') {
  const results = {
    accompanying: { present: false, warning: '' },
    service_address: { present: false, warning: '' },
    free_will: { confirmed: false, warning: '' },
    truthfulness: { confirmed: false, warning: '' },
    signature: { confirmed: false, warning: '' },
  };
  if (/陪同|家屬|社工|監護人/.test(rawText)) results.accompanying.present = true;
  else results.accompanying.warning = '⚠️ 1H：陪同人未確認';

  if (/送達地址|送達處所|文書送達/.test(rawText)) results.service_address.present = true;
  else results.service_address.warning = '⚠️ 1H：送達地址未確認';

  if (/自由意識|自由陳述|自由意願/.test(rawText)) results.free_will.confirmed = true;
  else results.free_will.warning = '⚠️ 1H：自由意識未確認';

  if (/實在性|是否實在|真實/.test(rawText)) results.truthfulness.confirmed = true;
  else results.truthfulness.warning = '⚠️ 1H：實在性未確認';

  if (/簽名|捺印/.test(rawText)) results.signature.confirmed = true;
  else results.signature.warning = '⚠️ 1H：簽名捺印未確認';

  return results;
}

// 1I 筆錄時間、地點、案由、案號
function checkRecordMeta(fields = {}) {
  const results = [];
  const meta = [
    { key: 'record_time', name: '筆錄時間' },
    { key: 'record_place', name: '筆錄地點' },
    { key: 'case_reason', name: '案由' },
    { key: 'case_number', name: '案號' },
  ];
  for (const m of meta) {
    const found = fields[m.key];
    if (!found) {
      results.push({ field: m.name, warning: `⚠️ 1I：${m.name}未填` });
    }
  }
  return results;
}

// ============================================================
// 第 2 層細項：2B~2I
// ============================================================
// 2B 性別事件（是→性平三法；否→跳過）
function checkGenderEvent(rawText = '') {
  const isGenderEvent = /性騷擾|性別|性平|性侵害|性霸凌/.test(rawText);
  return {
    is_gender_event: isGenderEvent,
    law: isGenderEvent ? '性別平等工作法、性別平等教育法、性騷擾防治法' : null,
    warning: isGenderEvent ? '2B：性別事件觸發性平三法' : '',
  };
}

// 2C 特別法分流細項
function checkSpecialLaws(rawText = '') {
  const results = [];
  const laws = [
    { kw: /兒少|兒童及少年/, name: '兒少性剝削防制條例' },
    { kw: /家暴|家庭暴力/, name: '家庭暴力防治法' },
    { kw: /性侵|性侵害/, name: '性侵害犯罪防治法' },
    { kw: /跟蹤|跟騷/, name: '跟蹤騷擾防制法' },
    { kw: /人口販運/, name: '人口販運防制法' },
    { kw: /詐欺|洗錢/, name: '詐欺犯罪危害防制條例、洗錢防制法' },
  ];
  for (const l of laws) {
    if (l.kw.test(rawText)) {
      results.push({ law: l.name, triggered: true });
    }
  }
  return results;
}

// 2E 管轄（含他轄案件）
function checkJurisdiction(fields = {}, rawText = '') {
  const warnings = [];
  if (fields.jurisdiction && fields.receiving_unit && fields.jurisdiction !== fields.receiving_unit) {
    warnings.push({
      type: 'cross_jurisdiction',
      message: `2E：他轄案件（受理：${fields.receiving_unit}，管轄：${fields.jurisdiction}）`,
    });
  }
  if (/他轄|非本轄/.test(rawText)) {
    warnings.push({ type: 'cross_jurisdiction', message: '2E：他轄案件（依陳報判斷）' });
  }
  return warnings;
}

// 2F 空白罪狀補充規範查證
function checkBlankStatute(rawText = '', elements = null) {
  if (!elements) return [];
  const blank = (elements.elements || []).filter(e =>
    /空白罪狀|補充規範/.test(e.semantic || '') || e.constitution_type === '開放'
  );
  return blank.map(e => ({
    element: e.id,
    name: e.name,
    message: `2F：空白罪狀/開放構成要件，補充規範需查證：${e.source_basis}`,
  }));
}

// 2G 時際法：行為時法與從舊從輕（刑§2 ⚠️）
function checkTemporalLaw(caseDate = null, lawChangeDate = null, lawName = '') {
  if (!caseDate || !lawChangeDate) {
    return { changed: false, warning: lawName ? `2G：${lawName} 修正日期未確認（刑§2 ⚠️）` : '' };
  }
  const cd = new Date(caseDate);
  const ld = new Date(lawChangeDate);
  const changed = cd < ld;
  return {
    changed,
    law: lawName,
    old_law_applies: changed,
    warning: changed
      ? `2G：行為時法與裁判時法不同，依刑§2 從舊從輕 ⚠️（刑§2 條文需查證）`
      : '',
  };
}

// 2H 階段判定（警詢／偵查／審判）
function determineStage(rawText = '') {
  if (/警詢|派出所|分駐所/.test(rawText)) return '警詢';
  if (/偵查|地檢署|檢察官/.test(rawText)) return '偵查';
  if (/審判|法院|法官/.test(rawText)) return '審判';
  return '未判定';
}

// 2I 處理模式判定（筆錄／陳報／程序案）
function determineProcessingMode(rawText = '') {
  if (/查獲.*通緝|逮捕|拘提/.test(rawText)) return '程序案';
  if (/筆錄|詢問|訊問/.test(rawText)) return '筆錄';
  if (/陳報|報告|摘要/.test(rawText)) return '陳報';
  return '未判定';
}

// ============================================================
// 第 3 層細項：3A~3F
// ============================================================
function checkProtectionMeasures(rawText = '', caseType = '') {
  const results = {
    '3A 弱勢被害人': false,
    '3B 代號、真實姓名對照表': false,
    '3C 地址保密': false,
    '3D 隔離訊問': false,
    '3E 轉介服務': false,
    '3F 社工、監護人': false,
    warnings: [],
  };

  const isSensitive = /性侵|性騷擾|跟蹤|家暴|兒少|人口販運/.test(rawText) || /性侵|性騷擾|跟蹤|家暴|兒少/.test(caseType);

  if (isSensitive) {
    results['3A 弱勢被害人'] = /弱勢|未成年|身心障礙|精神/.test(rawText);
    results['3B 代號、真實姓名對照表'] = /代號|對照表|真實姓名/.test(rawText);
    results['3C 地址保密'] = /地址保密|隱匿地址/.test(rawText);
    results['3D 隔離訊問'] = /隔離訊問/.test(rawText);
    results['3E 轉介服務'] = /轉介/.test(rawText);
    results['3F 社工、監護人'] = /社工|監護人/.test(rawText);

    if (!results['3B 代號、真實姓名對照表']) {
      results.warnings.push('⚠️ 3B：敏感案件需建立真實姓名對照表');
    }
  }
  return results;
}

// ============================================================
// 第 4 層細項：4A 事實結構化、4C 來源盤點
// ============================================================
function structureFacts(rawText = '') {
  if (!rawText) return { people: [], events: [], times: [], places: [], objects: [], warnings: ['4A：無原始文本可抽取'] };

  // 這裡由 LLM 責任抽取；本函數僅檢查是否有 source_raw
  const people = [];
  const times = [];
  const places = [];
  const objects = [];

  // 簡易抽取（僅供檢核，正式抽取由 LLM）
  const timeMatches = rawText.match(/\d{1,2}:\d{2}|\d{2,3}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}/g) || [];
  times.push(...timeMatches);

  const placeMatches = rawText.match(/臺北市?[^\s，。]{0,20}(街|路|巷|弄|號)/g) || [];
  places.push(...placeMatches);

  return {
    people,
    times,
    places,
    objects,
    warnings: times.length === 0 ? ['⚠️ 4A：時間未抽取'] : [],
    note: '正式抽取由 LLM 責任（R1、R13）',
  };
}

// 4C 來源盤點：被害人陳述、監視器、物證、書證各幾筆
function inventorySources(stateMap = {}) {
  const counts = {
    被害人陳述: 0, 行為人陳述: 0, 證人陳述: 0,
    監視器: 0, 物證: 0, 書證: 0, 電磁紀錄: 0, 醫療紀錄: 0,
  };
  for (const [eid, ev] of Object.entries(stateMap)) {
    const st = ev.source_type;
    if (st && counts[st] !== undefined) counts[st]++;
  }
  return counts;
}

// ============================================================
// 第 5 層細項：5A~5F
// ============================================================
function detailedEvidenceCheck(stateMap = {}, rawText = '') {
  const results = {
    '5A 證據能力先於證明力': [],
    '5B 自白任意性': [],
    '5C 傳聞法則與例外': [],
    '5D 違法取證排除': [],
    '5E 未全程錄音': [],
    '5F 審查結果': [],
  };

  for (const [eid, ev] of Object.entries(stateMap)) {
    // 5A 證據能力
    const adm = ev.evidence_admissibility;
    if (!adm) {
      results['5A 證據能力先於證明力'].push({ element: eid, message: '⚠️ 證據能力未標註' });
    } else if (adm === '排除') {
      results['5F 審查結果'].push({ element: eid, message: '證據能力被排除，不得進入元件比對' });
    }

    // 5B 自白任意性（僅行為人陳述）
    if (ev.source_type === '行為人陳述') {
      const hasImproper = /強暴|脅迫|利誘|詐欺|疲勞/.test(ev.source_raw?.join(' ') || '');
      if (hasImproper) {
        results['5B 自白任意性'].push({
          element: eid,
          message: '⚠️ 5B：自白可能有不正方法（刑訴§98、§156①）',
        });
      }
    }

    // 5C 傳聞法則（僅證人陳述且非現場）
    if (ev.source_type === '證人陳述' && ev.source_raw?.some(s => /聽說|轉述|據稱/.test(s))) {
      results['5C 傳聞法則與例外'].push({
        element: eid,
        message: '⚠️ 5C：傳聞法則適用（刑訴§159）',
      });
    }

    // 5D 違法取證
    if (ev.source_raw?.some(s => /未經同意搜索|非法搜索|違法搜索/.test(s))) {
      results['5D 違法取證排除'].push({
        element: eid,
        message: '⚠️ 5D：違法取證（刑訴§158-4）',
      });
    }
  }

  // 5E 未全程錄音
  if (!/全程連續錄音/.test(rawText) && /筆錄|詢問/.test(rawText)) {
    results['5E 未全程錄音'].push({
      message: '⚠️ 5E：未全程錄音之筆錄，學說與實務見解分歧',
    });
  }

  return results;
}

// ============================================================
// 第 6 層細項：6A 解釋、6B 罪刑法定與類推禁止
// ============================================================
function legalInterpretation(elements = null, rawText = '') {
  const results = {
    '6A 文義、體系、歷史、目的解釋': [],
    '6B 罪刑法定與類推禁止': [],
    '6C 學說與實務分歧': [],
  };

  if (elements) {
    // 6A
    for (const el of elements.elements || []) {
      if (el.constitution_type === '開放') {
        results['6A 文義、體系、歷史、目的解釋'].push({
          element: el.id,
          name: el.name,
          message: '6A：開放構成要件，需文義、體系、歷史、目的解釋',
        });
      }
    }
    // 6B 罪刑法定與類推禁止（R26 硬規則）
    results['6B 罪刑法定與類推禁止'].push({
      message: 'R26：罪刑法定與類推禁止為硬規則；禁止類推適用',
    });
    // 6C
    for (const el of elements.elements || []) {
      if (el.key_doctrines && el.key_doctrines.length > 0) {
        results['6C 學說與實務分歧'].push({
          element: el.id,
          name: el.name,
          doctrines: el.key_doctrines,
        });
      }
    }
  }

  return results;
}

// ============================================================
// 第 8 層細項：8D 互斥標註、8E 因果、8G 數額門檻
// ============================================================
function checkMutuallyExclusive(stateMap = {}, elements = null, exclusions = null) {
  const warnings = [];
  if (!elements || !exclusions) return warnings;

  for (const ex of exclusions.exclusions || []) {
    if (ex.type !== 'intra_chapter_mutual_exclusion') continue;
    const positives = ex.elements.filter(eid => {
      const st = stateMap[eid]?.status;
      return st === '符合' || st === '推論符合';
    });
    if (positives.length > 1) {
      warnings.push({
        exclusion: ex.id,
        elements: positives,
        message: `⚠️ 8D：互斥元件同時符合（${ex.note || ''}）`,
      });
    }
  }
  return warnings;
}

// 8E 因果要件：行為與結果間因果、客觀歸責、因果中斷
function checkCausality(stateMap = {}, elements = null, rawText = '') {
  const warnings = [];
  if (!elements) return warnings;

  const hasResult = (elements.elements || []).some(e => e.type === '結果');
  const hasConduct = (elements.elements || []).some(e => e.type === '行為');
  if (!hasResult || !hasConduct) return warnings;

  // 檢查因果關鍵詞
  const causalKeywords = ['因而', '導致', '造成', '致使', '以致'];
  const hasCausal = causalKeywords.some(kw => rawText.includes(kw));
  if (!hasCausal && /符合|推論符合/.test(JSON.stringify(stateMap))) {
    warnings.push({
      message: '⚠️ 8E：行為與結果間因果關係未明確（R14 因果併入元件比對）',
    });
  }

  // 客觀歸責
  if (/客觀歸責|歸責/.test(rawText)) {
    warnings.push({ message: '8E：客觀歸責需依風險實現理論檢查' });
  }

  // 因果中斷
  if (/因果中斷|介入因素|第三人行為/.test(rawText)) {
    warnings.push({
      message: '⚠️ 8E：可能存在因果中斷（介入因素）',
    });
  }

  return warnings;
}

// 8G 數額門檻（量的元件）
function checkAmountThreshold(stateMap = {}, elements = null) {
  const warnings = [];
  if (!elements) return warnings;

  for (const el of elements.elements || []) {
    if (!el.amount_threshold) continue;
    const st = stateMap[el.id];
    if (!st) continue;
    if (st.status === '符合' || st.status === '推論符合') {
      const th = el.amount_threshold;
      if (th.status === 'unverified') {
        warnings.push({
          element: el.id,
          name: el.name,
          message: `⚠️ 8G：數額門檻未查證（${th.basis}）`,
        });
      }
    }
  }
  return warnings;
}

// ============================================================
// 第 14 層細項：14A~14D
// ============================================================
function detailedStageThreshold(stage = '', maxPenalty = '', statuteLimitationsYears = null, caseDate = null) {
  const results = {
    '14A 階段門檻': { stage, warning: stage === '未判定' ? '⚠️ 14A：階段未判定前不得判斷門檻（R28）' : '' },
    '14B 無罪推定與證據裁判': { message: 'R25：無罪推定與證據裁判為硬規則（刑訴§154 ✓）；罪疑唯輕僅適用審判階段 ⚠️' },
    '14C 檢察官舉證責任': { message: '刑訴§161 ✓' },
    '14D 追訴權時效': statuteOfLimitationsCheck(maxPenalty, statuteLimitationsYears, caseDate),
  };
  return results;
}

function statuteOfLimitationsCheck(maxPenalty = '', years = null, caseDate = null) {
  if (years === null || years === undefined) {
    return { years: null, warning: '⚠️ 14D：追訴權時效未定（刑§80 ⚠️ 需查證）' };
  }
  if (!caseDate) {
    return { years, warning: '⚠️ 14D：案發日期未填，無法計算時效' };
  }
  const deadline = new Date(caseDate);
  deadline.setFullYear(deadline.getFullYear() + years);
  const now = new Date();
  return {
    years,
    deadline: deadline.toISOString().split('T')[0],
    expired: now > deadline,
    warning: '',
  };
}

// ============================================================
// 第 15 層細項：15A~15D
// ============================================================
function detailedSentencing(rawText = '', stateMap = {}) {
  const results = {
    '15A 量刑事由': { message: '刑§57 ✓（量刑事由需查證細節）', factors: [] },
    '15B 累犯、自首': { recidivist: false, voluntary_surrender: false },
    '15C 緩刑、易科罰金': { probation: false, fine_instead: false },
    '15D 沒收': { confiscated: false, items: [] },
  };

  // 15A
  const factors = [];
  const factorPatterns = [
    { kw: /動機|目的/, text: '犯罪動機與目的' },
    { kw: /受教育|知識|品行/, text: '教育程度與品行' },
    { kw: /生活狀況/, text: '生活狀況' },
    { kw: /智識程度/, text: '智識程度' },
    { kw: /與被害人.{0,5}關係/, text: '與被害人關係' },
    { kw: /犯罪所生之危險|所生損害/, text: '犯罪所生之危險或損害' },
    { kw: /犯後態度|態度/.test ? /犯後態度|悔意/.test ? /犯後態度|悔意|道歉/ : null : null, text: '犯後態度' },
  ];
  for (const p of factorPatterns) {
    if (p.kw && p.kw.test(rawText)) factors.push(p.text);
  }
  results['15A 量刑事由'].factors = factors;

  // 15B
  if (/累犯/.test(rawText)) results['15B 累犯、自首'].recidivist = true;
  if (/自首/.test(rawText)) results['15B 累犯、自首'].voluntary_surrender = true;

  // 15C
  if (/緩刑/.test(rawText)) results['15C 緩刑、易科罰金'].probation = true;
  if (/易科罰金/.test(rawText)) results['15C 緩刑、易科罰金'].fine_instead = true;

  // 15D
  if (/沒收|扣押/.test(rawText)) {
    results['15D 沒收'].confiscated = true;
    const items = rawText.match(/扣押[^\s，。]{0,20}/g) || [];
    results['15D 沒收'].items = items;
  }

  return results;
}

// ============================================================
// 主入口
// ============================================================
function runAllDetailLayers(input) {
  return {
    spec_version: 'v15',
    detail_layers: {
      L1: {
        name: '程序細項（1B~1I）',
        '1B 權利告知': checkRightsNotified(input.raw_text || ''),
        '1C 告訴期間告知': checkComplaintPeriodNotified(input.raw_text || ''),
        '1D 夜間詢問': checkNightInterrogation(input.raw_text || '', input.interrogation_time, input.sunset_time),
        '1E 全程錄音': checkContinuousRecording(input.raw_text || ''),
        '1F 不正方法': checkImproperMethods(input.raw_text || ''),
        '1G 通譯辯護人': checkInterpreterAndCounsel(input.raw_text || ''),
        '1H 陪同送達': checkAccompanyingAndOther(input.raw_text || ''),
        '1I 筆錄資訊': checkRecordMeta(input.fields || {}),
      },
      L2: {
        name: '分流細項（2B~2I）',
        '2B 性別事件': checkGenderEvent(input.raw_text || ''),
        '2C 特別法分流': checkSpecialLaws(input.raw_text || ''),
        '2E 管轄': checkJurisdiction(input.fields || {}, input.raw_text || ''),
        '2G 時際法': checkTemporalLaw(input.case_date, input.law_change_date, input.law_name),
        '2H 階段': determineStage(input.raw_text || ''),
        '2I 處理模式': determineProcessingMode(input.raw_text || ''),
      },
      L3: {
        name: '保護細項（3A~3F）',
        result: checkProtectionMeasures(input.raw_text || '', input.case_type || ''),
      },
      L4: {
        name: '事實結構化細項（4A、4C）',
        '4A 結構化': structureFacts(input.raw_text || ''),
        '4C 來源盤點': inventorySources(input.state_map || {}),
      },
      L5: {
        name: '證據能力細項（5A~5F）',
        result: detailedEvidenceCheck(input.state_map || {}, input.raw_text || ''),
      },
      L6: {
        name: '法律解釋細項（6A~6C）',
        result: legalInterpretation(input.elements, input.raw_text || ''),
      },
      L8: {
        name: '元件比對細項（8D、8E、8G）',
        '8D 互斥': checkMutuallyExclusive(input.state_map || {}, input.elements, input.exclusions),
        '8E 因果': checkCausality(input.state_map || {}, input.elements, input.raw_text || ''),
        '8G 數額': checkAmountThreshold(input.state_map || {}, input.elements),
      },
      L14: {
        name: '階段門檻細項（14A~14D）',
        result: detailedStageThreshold(input.stage, input.max_penalty, input.statute_limitations_years, input.case_date),
      },
      L15: {
        name: '量刑細項（15A~15D）',
        result: detailedSentencing(input.raw_text || '', input.state_map || {}),
      },
    },
  };
}

module.exports = {
  runAllDetailLayers,
  checkRightsNotified,
  checkNightInterrogation,
  checkImproperMethods,
  determineStage,
  determineProcessingMode,
  checkProtectionMeasures,
  structureFacts,
  inventorySources,
  detailedEvidenceCheck,
  legalInterpretation,
  checkMutuallyExclusive,
  checkCausality,
  checkAmountThreshold,
  detailedStageThreshold,
  detailedSentencing,
};

// CLI
if (require.main === module) {
  const [inputFile] = process.argv.slice(2);
  if (!inputFile) {
    console.error('Usage: node layers_detail.js <input.json>');
    process.exit(1);
  }
  const input = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));
  const result = runAllDetailLayers(input);
  console.log(JSON.stringify(result, null, 2));
}

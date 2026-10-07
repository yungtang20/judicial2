// integration.js — 全 17 層整合執行入口
// 讀取陳報檔（LINE 文本或 CSV）→ 跑全部 17 層 → 輸出 S-14 契約 JSON
// 用法：node 01_規則/integration.js <input.json>

const fs = require('fs');
const path = require('path');
const { runS14 } = require('./s14_contract.js');
const { splitCases, normalizeDate, determineIdentity, classifyCase } = require('./layers.js');

const ROOT = path.resolve(__dirname, '..');

// ============================================================
// 從陳報檔文本抽取欄位（LLM 責任，本函數為骨架）
// 依吳興所/三張所陳報格式：一、案由 二、時間 三、地點 四、狀況 五、...
// ============================================================
function extractFields(rawText) {
  const fields = {};
  if (!rawText) return fields;

  // 案由
  const m1 = rawText.match(/[一二三]、\s*案由[：:]\s*([^\n]+)/);
  if (m1) fields.case_reason = m1[1].trim();

  // 發生時間
  const m2 = rawText.match(/(?:發生時間|時間)[：:]\s*([^\n]+)/);
  if (m2) fields.occurred_raw = m2[1].trim();

  // 報案時間
  const m3 = rawText.match(/報案時間[：:]\s*([^\n]+)/);
  if (m3) fields.reported_raw = m3[1].trim();

  // 地點
  const m4 = rawText.match(/(?:發生地點|地點|案發地點)[：:]\s*([^\n]+)/);
  if (m4) fields.place = m4[1].trim();

  // 損失金額
  const m5 = rawText.match(/(?:損失金額|遭詐欺金額)[：:]\s*([^\n]+)/);
  if (m5) fields.loss_amount_raw = m5[1].trim();

  // 年次
  const m6 = rawText.match(/(\d{2,3})年次/);
  if (m6) fields.birth_year = 1911 + parseInt(m6[1]);

  return fields;
}

// ============================================================
// 主入口
// input: {
//   raw_text: '（LINE 陳報文本，可含多件）',
//   chapter_id: 'criminal_theft_embezzle',
//   declared_role: '被害人',
//   case_type: '竊盜案',
//   article: '刑法第320條',
//   max_penalty: '五年以下有期徒刑',
//   state_map: { ... },  // 可由 LLM 提供，或留空讓引擎預設
//   evidence: { ... },
//   fields: { ... },     // 可由 LLM 提供，或由本函數抽取
// }
// ============================================================
function runIntegration(input) {
  const warnings = [];

  // P1 案件切分
  const cases = splitCases(input.raw_text || '');
  if (cases.length > 1) {
    warnings.push(`R41：一則訊息含 ${cases.length} 件報告，已切分；每件各自處理`);
  }

  // 抽取欄位（若未由 LLM 提供）
  const extractedFields = input.fields || extractFields(input.raw_text || '');

  // P2 日期正規化
  if (extractedFields.occurred_raw && !extractedFields.occurred) {
    extractedFields.occurred = normalizeDate(extractedFields.occurred_raw, input.message_date);
    if (extractedFields.occurred.status === '推定') {
      warnings.push(`R42：發生時間為推定值，不得自動採用：${extractedFields.occurred.raw}`);
    }
  }
  if (extractedFields.reported_raw && !extractedFields.reported) {
    extractedFields.reported = normalizeDate(extractedFields.reported_raw, input.message_date);
    if (extractedFields.reported.status === '推定') {
      warnings.push(`R42：報案時間為推定值，不得自動採用：${extractedFields.reported.raw}`);
    }
  }

  // 1A 身分判定
  const identity = determineIdentity(input.raw_text || '', input.declared_role);
  if (identity.warnings.length > 0) {
    warnings.push(...identity.warnings);
  }

  // 2A 分流
  const mode = classifyCase(input.case_type || '');
  if (mode.warnings.length > 0) {
    warnings.push(...mode.warnings);
  }

  // 程序案/非刑案不進元件比對（R40）
  if (mode.mode === '程序案' || mode.mode === '非刑案') {
    return {
      integration: {
        spec_version: 'v15',
        mode: mode.mode,
        cases_split: cases.length,
        warnings,
        message: `R40：${mode.mode}不進元件比對`,
      },
    };
  }

  // 跑 S-14 契約（全 17 層）
  const s14 = runS14({
    ...input,
    fields: extractedFields,
    inquired_identity: identity.primary || input.inquired_identity || '被害人',
  });

  return {
    integration: {
      spec_version: 'v15',
      cases_split: cases.length,
      identity: identity,
      mode: mode.mode,
      warnings: [...warnings, ...(s14.s14_contract?.warnings || [])],
      s14_contract: s14.s14_contract,
    },
  };
}

module.exports = { runIntegration, extractFields };

// CLI
if (require.main === module) {
  const [inputFile] = process.argv.slice(2);
  if (!inputFile) {
    console.error('Usage: node integration.js <input.json>');
    process.exit(1);
  }
  const input = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));
  const result = runIntegration(input);
  console.log(JSON.stringify(result, null, 2));
}

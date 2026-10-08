// render_brief.js
// 產出指定條陳（可供筆錄/陳報使用的純文字格式）。
// 不解釋法律、不產生問句、不執行 LLM；僅格式化 S-14 contract 已有資料。

const fs = require('fs');

function renderBrief(s14Contract, inputInfo = null) {
  const c = s14Contract;
  if (!c) return '（無 S-14 契約資料）';
  const inp = inputInfo || c.input || {};

  const lines = [];
  lines.push('========================================');
  lines.push('警詢筆錄 指定條陳');
  lines.push('========================================');
  lines.push(`案由：${c.input_summary?.case_type || '未填'}`);
  lines.push(`受詢問人身分：${c.input_summary?.inquired_identity || '未定'}`);
  lines.push(`聲明角色：${c.input_summary?.declared_role || '未填'}`);
  lines.push(`案件日期：${c.input_summary?.case_date || '未填'}`);
  lines.push(`產出時間：${c.generated_at || new Date().toISOString()}`);
  lines.push('');

  lines.push('【候選罪章】');
  const candidates = c.layers?.L12?.candidate_charges || [];
  if (candidates.length === 0) {
    lines.push('  （資料不足，未浮現候選罪章）');
  } else {
    candidates.forEach(id => lines.push(`  - ${id}`));
  }
  lines.push('');

  lines.push('【罪名狀態】');
  const states = c.layers?.L12?.charge_states || {};
  Object.entries(states).forEach(([id, st]) => lines.push(`  ${id}：${st}`));
  lines.push('');

  lines.push('【核心問句】');
  const questions = c.s11_questions?.questions || [];
  const core = questions.filter(q => q.stage === 'B');
  const free = questions.filter(q => q.stage === 'A');
  const evidence = questions.filter(q => q.stage === 'E');
  const ending = questions.filter(q => q.stage === 'C');

  if (free.length > 0) {
    lines.push('  〔自由陳述〕');
    free.forEach(q => lines.push(`   ${q.text}`));
  }
  if (evidence.length > 0) {
    lines.push('  〔證據保全〕');
    evidence.forEach(q => lines.push(`   ${q.text}`));
  }
  if (core.length > 0) {
    lines.push('  〔缺口聚焦〕');
    core.forEach(q => lines.push(`   ${q.text}`));
  }
  if (ending.length > 0) {
    lines.push('  〔結尾開放〕');
    ending.forEach(q => lines.push(`   ${q.text}`));
  }
  lines.push('');

  lines.push('【開放構成要件】');
  const openItems = c.open_constitution || [];
  if (openItems.length === 0) {
    lines.push('  （無）');
  } else {
    openItems.forEach(item => lines.push(`  - ${item}`));
  }
  lines.push('');

  lines.push('【警告提示】');
  const warns = c.layers?.L12?.llm_guard?.llm_must_not_do || [];
  if (warns.length > 0) {
    warns.forEach(w => lines.push(`  ⚠️ ${w}`));
  }
  if (c.actor_warnings && c.actor_warnings.length > 0) {
    c.actor_warnings.forEach(w => lines.push(`  ⚠️ ${w}`));
  }
  if (c.warnings && c.warnings.length > 0) {
    c.warnings.forEach(w => lines.push(`  ⚠️ ${w}`));
  }
  lines.push('');
  lines.push('========================================');
  lines.push('正式條陳（案件基本資料）');
  lines.push('========================================');
  lines.push(`一、案由：${c.input_summary?.case_type || '未填'}`);
  lines.push(`二、發生時間：${c.input_summary?.case_date || '未填'}`);
  lines.push(`三、受詢問人身分：${c.input_summary?.inquired_identity || '未定'}`);
  lines.push(`四、聲明角色：${c.input_summary?.declared_role || '未填'}`);
  lines.push('');
  lines.push('【案情摘要】');
  const rawText = (typeof inp.raw_text === 'string' && inp.raw_text.trim().length > 0) ? inp.raw_text : '（未提供）';

  function parseSections(text) {
    const out = {};
    let current = null;
    const parts = text.split(/\r?\n/);
    for (const line of parts) {
      const m = line.match(/^([一二三四五六七八九十]+)、(.*)$/);
      if (m) {
        current = m[1];
        out[current] = (m[2] || '').trim();
      } else if (current && line.trim().length > 0) {
        out[current] += '\n' + line.trim();
      }
    }
    return out;
  }

  const sections = parseSections(rawText);
  lines.push('【案情摘要】');
  lines.push(rawText);
  lines.push('');
  lines.push('【正式條陳】');
  const order = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'];
  for (const key of order) {
    if (sections[key]) {
      lines.push(`${key}、${sections[key]}`);
    }
  }
  lines.push('');
  lines.push('========================================');
  return lines.join('\n');
}

// CLI
if (require.main === module) {
  const inputFile = process.argv[2];
  if (!inputFile) {
    console.error('Usage: node render_brief.js <s14_contract.json>');
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));
  const s14 = data.s14_contract || data.integration?.s14_contract || data;
  const inputInfo = data.integration?.input || data.input || null;
  console.log(renderBrief(s14, inputInfo));
}

module.exports = { renderBrief };

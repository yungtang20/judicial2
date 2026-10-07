// check.js — 驗證腳本
// 檢查 00_資料/罪章/ 全部 JSON：
// 1. JSON 合法性（UTF-8、無註解、無尾隨逗號）
// 2. 必填欄位
// 3. id 唯一性
// 4. cross_reference（charges 引用 elements、exclusions 引用 charges）
// 5. locked/verification 欄位完整性

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const CHAPTERS = path.join(ROOT, '00_資料', '罪章');

function checkJson(path_str) {
  try {
    JSON.parse(fs.readFileSync(path_str, 'utf-8'));
    return { ok: true };
  } catch (e) {
    return { ok: false, message: e.message };
  }
}

function checkChapter(dir) {
  const issues = [];
  const files = ['elements.json', 'charges.json', 'exclusions.json'];

  // 1. JSON 合法性
  for (const f of files) {
    const p = path.join(dir, f);
    if (!fs.existsSync(p)) {
      issues.push(`[FAIL] ${f}: 檔案不存在`);
      continue;
    }
    const r = checkJson(p);
    if (!r.ok) issues.push(`[FAIL] ${f}: JSON 不合法（${r.message}）`);
  }
  if (issues.length > 0) return issues;

  const els = JSON.parse(fs.readFileSync(path.join(dir, 'elements.json'), 'utf-8'));
  const chs = JSON.parse(fs.readFileSync(path.join(dir, 'charges.json'), 'utf-8'));
  const exs = JSON.parse(fs.readFileSync(path.join(dir, 'exclusions.json'), 'utf-8'));

  // 2. 必填欄位 + 3. id 唯一性
  const elemIds = new Set();
  for (const el of els.elements || []) {
    for (const req of ['id', 'name', 'type', 'semantic', 'source_basis', 'law_category', 'verification', 'actor_subject_type', 'necessary']) {
      if (!(req in el)) issues.push(`[FAIL] elements.json ${el.id || '?'}: 缺欄位 ${req}`);
    }
    if (elemIds.has(el.id)) issues.push(`[FAIL] elements.json: id 重複 ${el.id}`);
    elemIds.add(el.id);
  }

  const chargeIds = new Set();
  for (const c of chs.charges || []) {
    for (const req of ['id', 'name', 'article', 'base_penalty', 'statute_of_limitations_years', 'private_prosecution', 'actor_subject_type_required', 'verification']) {
      if (!(req in c)) issues.push(`[FAIL] charges.json ${c.id || '?'}: 缺欄位 ${req}`);
    }
    if (chargeIds.has(c.id)) issues.push(`[FAIL] charges.json: id 重複 ${c.id}`);
    chargeIds.add(c.id);
  }

  const exclIds = new Set();
  for (const ex of exs.exclusions || []) {
    for (const req of ['id', 'type', 'between_charges', 'verification']) {
      if (!(req in ex)) issues.push(`[FAIL] exclusions.json ${ex.id || '?'}: 缺欄位 ${req}`);
    }
    if (exclIds.has(ex.id)) issues.push(`[FAIL] exclusions.json: id 重複 ${ex.id}`);
    exclIds.add(ex.id);
  }

  // 4. cross_reference
  for (const c of chs.charges || []) {
    for (const eid of (c.requires_elements || [])) {
      if (!elemIds.has(eid)) issues.push(`[FAIL] charges.json ${c.id}: 引用不存在元件 ${eid}`);
    }
    for (const eid of (c.requires_all_optional || [])) {
      if (!elemIds.has(eid)) issues.push(`[FAIL] charges.json ${c.id}: 引用不存在元件 ${eid}`);
    }
    for (const eid of (c.requires_not_all || [])) {
      if (!elemIds.has(eid)) issues.push(`[FAIL] charges.json ${c.id}: 引用不存在元件 ${eid}`);
    }
    for (const eid of (c.requires_any_result || [])) {
      if (!elemIds.has(eid)) issues.push(`[FAIL] charges.json ${c.id}: 引用不存在元件 ${eid}`);
    }
    for (const gid of Object.keys(c.requires_one_of || {})) {
      for (const eid of (c.requires_one_of[gid] || [])) {
        if (!elemIds.has(eid)) issues.push(`[FAIL] charges.json ${c.id}: 群組 ${gid} 引用不存在元件 ${eid}`);
      }
    }
    for (const sid of (c.supersedes || [])) {
      if (!chargeIds.has(sid)) issues.push(`[FAIL] charges.json ${c.id}: supersedes 不存在罪名 ${sid}`);
    }
  }

  for (const ex of exs.exclusions || []) {
    for (const cid of (ex.between_charges || [])) {
      if (cid.startsWith('外法:') || cid.startsWith('外章:')) continue; // 跨法/跨章允許
      if (!chargeIds.has(cid)) issues.push(`[FAIL] exclusions.json ${ex.id}: 引用不存在罪名 ${cid}`);
    }
    if (ex.special_over_general && !chargeIds.has(ex.special_over_general)) {
      issues.push(`[FAIL] exclusions.json ${ex.id}: special_over_general 不存在 ${ex.special_over_general}`);
    }
  }

  return issues;
}

function main() {
  const dirs = fs.readdirSync(CHAPTERS).filter(d => fs.statSync(path.join(CHAPTERS, d)).isDirectory()).sort();
  let pass = 0, fail = 0;
  for (const d of dirs) {
    const issues = checkChapter(path.join(CHAPTERS, d));
    if (issues.length === 0) {
      pass++;
      console.log(`[PASS] ${d}`);
    } else {
      fail++;
      console.log(`[FAIL] ${d}`);
      for (const i of issues) console.log(`  ${i}`);
    }
  }
  console.log(`\n[SUMMARY] ${pass} passed, ${fail} failed out of ${dirs.length} chapters`);
  if (fail > 0) process.exit(1);
}

main();

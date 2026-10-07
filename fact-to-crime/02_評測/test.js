// test.js — run rule_engine against test cases and compare with expected
// v15 test runner for fact-to-crime

const fs = require('fs');
const path = require('path');
const { run } = require('../01_規則/rule_engine.js');

const ROOT = path.resolve(__dirname, '..');
const CHAPTERS_ROOT = path.join(ROOT, '00_資料', '罪章');
const CASES_DIR = path.join(__dirname, 'cases');

function inferChapter(caseId) {
  // TC-221-* → criminal_221
  // TC-FR-* → criminal_fraud
  // TC-TE-* → criminal_theft_embezzle
  // TC-HD-* → criminal_harm_dv
  // TC-PD-* → criminal_public_danger
  // TC-DF-* → criminal_defame
  const m = caseId.match(/^TC-([A-Z0-9]+)-/);
  if (!m) return null;
  const prefix = m[1];
  const map = {
    '221': 'criminal_221',
    'FR': 'criminal_fraud',
    'TE': 'criminal_theft_embezzle',
    'HD': 'criminal_harm_dv',
    'DF': 'criminal_defame',
    'PD': 'criminal_public_danger',
    'FG': 'criminal_forgery',
    'GB': 'criminal_gambling',
    'IN': 'criminal_intimidation',
    'CP': 'criminal_computer',
    'TR': 'criminal_traffic',
    'DR2': 'criminal_drugs',
    'SH2': 'criminal_sexual_harassment',
    'OB': 'criminal_obscenity',
    'RB': 'criminal_robbery',
  };
  return map[prefix] || null;
}

function assertEq(actual, expected, label, path_so_far = '') {
  const got = JSON.stringify(actual);
  const exp = JSON.stringify(expected);
  if (got === exp) return { ok: true };
  return { ok: false, label, path: path_so_far, expected: exp, actual: got };
}

function runCase(casePath) {
  const tc = JSON.parse(fs.readFileSync(casePath, 'utf-8'));
  if (!tc.case_id) return null; // skip S14 input files
  const chapterName = inferChapter(tc.case_id);
  if (!chapterName) {
    return { case_id: tc.case_id, error: 'cannot infer chapter from case_id' };
  }
  const chapterDir = path.join(CHAPTERS_ROOT, chapterName);
  if (!fs.existsSync(chapterDir)) {
    return { case_id: tc.case_id, error: `chapter dir not found: ${chapterName}` };
  }
  const result = run(chapterDir, tc.state_map);
  const out = result.s14_output;
  const checks = [];

  if (tc.expected.charge_states) {
    for (const [cid, expState] of Object.entries(tc.expected.charge_states)) {
      const actual = out.charge_states[cid];
      checks.push(assertEq(actual, expState, `charge_states[${cid}]`, `s14_output.charge_states.${cid}`));
    }
  }
  if (tc.expected.candidate_charges) {
    const actual = [...out.candidate_charges].sort();
    const expected = [...tc.expected.candidate_charges].sort();
    checks.push(assertEq(actual, expected, 'candidate_charges (sorted)', 's14_output.candidate_charges'));
  }
  if (tc.expected.counter_evidence_all_pass !== undefined) {
    const allPass = Object.values(out.counter_evidence).every(c => !c.has_doubt);
    checks.push(assertEq(allPass, tc.expected.counter_evidence_all_pass, 'counter_evidence_all_pass', 's14_output.counter_evidence.*.has_doubt'));
  }
  return { case_id: tc.case_id, case_type: tc.case_type, chapter: chapterName, checks, out };
}

function main() {
  const caseFiles = fs.readdirSync(CASES_DIR).filter(f => f.endsWith('.json')).sort();
  let pass = 0, fail = 0;
  const failures = [];
  for (const f of caseFiles) {
    const r = runCase(path.join(CASES_DIR, f));
    if (!r) continue; // skip S14 input files
    if (r.error) {
      fail++;
      failures.push(r);
      console.log(`[FAIL] ${r.case_id}: ${r.error}`);
      continue;
    }
    const bad = r.checks.filter(c => !c.ok);
    if (bad.length === 0) {
      pass++;
      console.log(`[PASS] ${r.case_id} (${r.case_type}, ${r.chapter})`);
    } else {
      fail++;
      failures.push(r);
      console.log(`[FAIL] ${r.case_id} (${r.case_type}, ${r.chapter})`);
      for (const c of bad) {
        console.log(`  ✗ ${c.label} @ ${c.path}`);
        console.log(`    expected: ${c.expected}`);
        console.log(`    actual:   ${c.actual}`);
      }
    }
  }
  console.log(`\n[SUMMARY] ${pass} passed, ${fail} failed out of ${caseFiles.length} cases`);
  if (fail > 0) process.exit(1);
}

main();

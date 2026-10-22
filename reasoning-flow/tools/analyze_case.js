// M4 分析器 CLI：讀事實 JSON + lawbank_reasoning_flow.json，輸出 Markdown 報告與 gap_list。
// 用法：
//   node tools/analyze_case.js tools/test_facts/case_explicit.json
//   node tools/analyze_case.js --all      （批次處理 test_facts/ 全部案例）
const fs = require("fs");
const path = require("path");
const { analyze } = require("./analyzer");

const FLOW_FILE = process.env.FLOW_FILE || path.join(__dirname, "..", "data", "lawbank_reasoning_flow.json");
const OUT_DIR = process.env.OUT_DIR || path.join(__dirname, "..", "out");

function run(factsFile) {
  const flow = JSON.parse(fs.readFileSync(FLOW_FILE, "utf8"));
  const facts = JSON.parse(fs.readFileSync(factsFile, "utf8"));
  const result = analyze(facts, flow);

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const base = path.basename(factsFile, ".json");
  const mdFile = path.join(OUT_DIR, base + ".md");
  const gapFile = path.join(OUT_DIR, base + ".gap_list.json");
  const metaFile = path.join(OUT_DIR, base + ".meta.json");

  fs.writeFileSync(mdFile, result.markdown, "utf8");
  fs.writeFileSync(gapFile, JSON.stringify(result.gap_list, null, 2), "utf8");
  fs.writeFileSync(metaFile, JSON.stringify(result.meta, null, 2), "utf8");

  console.log("[" + base + "]");
  console.log("  md   : " + mdFile);
  console.log("  gap  : " + gapFile);
  console.log("  候選 : " + result.meta.candidate_statutes.join(", "));
  console.log("  主體 : " + (result.meta.subject_identified ? "已確認" : "不明"));
  console.log("  交付 : " + result.meta.delivery_status);
  console.log("  缺口 : " + result.meta.gap_count + " 筆");
  return result;
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("用法：node tools/analyze_case.js <facts.json> | --all");
  process.exit(2);
}
if (args[0] === "--all") {
  const dir = path.join(__dirname, "test_facts");
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
    run(path.join(dir, f));
  }
} else {
  run(args[0]);
}

// M5 生成器 CLI：gap_list → 問句清單 + 條陳填充 + 匯出純文字
// 用法：
//   node tools/generate_output.js tools/test_facts/case_explicit.json
//   node tools/generate_output.js --all
const fs = require("fs");
const path = require("path");
const { analyze } = require("./analyzer");
const { generate } = require("./generator");

const PKG = path.join(__dirname, "..");
const FLOW_FILE = process.env.FLOW_FILE || path.join(PKG, "data", "lawbank_reasoning_flow.json");
const TEMPLATES_FILE = process.env.TEMPLATES_FILE || path.join(PKG, "data", "templates.json");
const RULES_FILE = process.env.RULES_FILE || path.join(PKG, "data", "questions_rules.json");
const OUT_DIR = process.env.OUT_DIR || path.join(PKG, "out");

function mdEscape(s) {
  return String(s == null ? "" : s).replace(/\|/g, "\\|");
}

function buildReport(facts, analysis, gen) {
  const L = [];
  L.push("# 條陳與問句產出：" + (facts.case_id || "(未命名案件)"));
  L.push("");
  L.push("> 本文件為模擬產出，內容待承辦人核實。所有罪名均為候選，不認定犯罪成立。");
  L.push("");

  L.push("## 一、模板選擇");
  L.push("");
  L.push("| 項目 | 內容 |");
  L.push("|---|---|");
  L.push("| 模板 | " + mdEscape(gen.template_name) + "（" + mdEscape(gen.template_id) + "） |");
  L.push("| 選擇依據 | " + mdEscape(gen.template_selection.note || "—") + " |");
  L.push("| 有無被害人 | " + (gen.template_selection.answers.has_victim === null ? "未敘明（暫依有被害人處理）" : gen.template_selection.answers.has_victim ? "有" : "無") + " |");
  L.push("| 是否已破獲 | " + (gen.template_selection.answers.is_solved ? "是" : "否") + " |");
  L.push("| 主體是否特定 | " + (gen.template_selection.answers.subject_identified === null ? "未敘明" : gen.template_selection.answers.subject_identified ? "是" : "否") + " |");
  L.push("");

  L.push("## 二、問句清單");
  L.push("");
  const groupOrder = gen.questions_by_target
    ? Object.keys(gen.questions_by_target)
    : ["relative", "suspect", "witness"];
  const labels = { relative: "對相對人（被害人）", suspect: "對行為人（涉嫌人）", witness: "對證人" };
  for (const g of groupOrder) {
    const list = gen.questions_by_target[g] || [];
    L.push("### " + (labels[g] || g) + "（" + list.length + " 句）");
    L.push("");
    if (!list.length) {
      L.push("（本角色無缺口對應之問句）");
      L.push("");
      continue;
    }
    L.push("| id | question | maps_to | note |");
    L.push("|---|---|---|---|");
    for (const q of list) {
      L.push(
        "| " +
          mdEscape(q.id) +
          " | " +
          mdEscape(q.question) +
          " | " +
          mdEscape((q.maps_to || []).join("、")) +
          " | " +
          mdEscape(q.note || "") +
          " |"
      );
    }
    L.push("");
  }
  if (gen.rejected_questions && gen.rejected_questions.length) {
    L.push("### 未納入之問句（未通過規則校驗）");
    L.push("");
    for (const r of gen.rejected_questions) {
      L.push("- " + mdEscape(r.gap_id) + "：" + mdEscape(r.question) + " —— " + mdEscape(r.violations.map((v) => v.rule_id).join("、")));
    }
    L.push("");
  }

  L.push("## 三、條陳填充表");
  L.push("");
  L.push("| 欄位 ID | 標籤 | 填充內容 | 狀態 |");
  L.push("|---|---|---|---|");
  for (const r of gen.statement_fill) {
    L.push(
      "| " +
        mdEscape(r.field_id) +
        " | " +
        mdEscape(r.label) +
        " | " +
        mdEscape(r.value) +
        " | " +
        mdEscape(r.status) +
        " |"
    );
  }
  L.push("");

  L.push("## 四、匯出用純文字");
  L.push("");
  L.push("```text");
  L.push(gen.export_text);
  L.push("```");
  L.push("");
  return L.join("\n");
}

function run(factsFile) {
  const flow = JSON.parse(fs.readFileSync(FLOW_FILE, "utf8"));
  const templates = JSON.parse(fs.readFileSync(TEMPLATES_FILE, "utf8"));
  const rulesDoc = JSON.parse(fs.readFileSync(RULES_FILE, "utf8"));
  const facts = JSON.parse(fs.readFileSync(factsFile, "utf8"));

  const analysis = analyze(facts, flow);
  const gen = generate({
    templates,
    rulesDoc,
    gapList: analysis.gap_list,
    meta: analysis.meta,
    factsText: facts.facts_text || "",
    templateOverride: facts.template_override || null,
  });

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const base = path.basename(factsFile, ".json");
  const files = {
    report: path.join(OUT_DIR, base + ".generated.md"),
    questions: path.join(OUT_DIR, base + ".questions.json"),
    fill: path.join(OUT_DIR, base + ".statement_fill.json"),
    export: path.join(OUT_DIR, base + ".export.txt"),
  };
  fs.writeFileSync(files.report, buildReport(facts, analysis, gen), "utf8");
  fs.writeFileSync(files.questions, JSON.stringify(gen.questions, null, 2), "utf8");
  fs.writeFileSync(files.fill, JSON.stringify(gen.statement_fill, null, 2), "utf8");
  fs.writeFileSync(files.export, "\ufeff" + gen.export_text, "utf8");

  console.log("[" + base + "]");
  console.log("  模板  : " + gen.template_name);
  console.log("  問句  : " + gen.meta.question_count + " 句（未納入 " + gen.meta.rejected_count + " 句）");
  console.log("  覆蓋缺口: " + gen.meta.covered_gaps.join(", "));
  console.log("  輸出  : " + files.report);
  return { analysis, gen };
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("用法：node tools/generate_output.js <facts.json> | --all");
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

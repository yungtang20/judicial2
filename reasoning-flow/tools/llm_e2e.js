// M7 端到端測試：規則版與 LLM 版並行產出，並驗證 LLM 輸出之品質與安全性。
// 用法：node tools/llm_e2e.js
const fs = require("fs");
const path = require("path");
const { analyze } = require("./analyzer");
const { generate } = require("./generator");
const { analyzeWithLLM, validateLLMOutput } = require("./llm_analyzer");

const PKG = path.join(__dirname, "..");
const OUT_DIR = path.join(PKG, "out");
const FORBIDDEN_WORDS = ["成立", "構成", "該當", "應論以"];
const ALLOWED = [
  "不認定犯罪成立",
  "不構成",
  "未構成",
  "構成要件之判準",
  "成立與否",
  "所有罪名均為候選，不認定犯罪成立。",
  "模擬填充，不構成正式文書。",
];

const results = [];
function check(ok, name, detail = "") {
  results.push({ ok: !!ok, name, detail });
  console.log((ok ? "  [OK] " : "  [FAIL] ") + name + (ok ? "" : "  → " + detail));
}

function hasForbidden(text) {
  const scan = String(text || "");
  for (const w of FORBIDDEN_WORDS) {
    let i = scan.indexOf(w);
    while (i !== -1) {
      const seg = scan.slice(Math.max(0, i - 25), i + 25);
      if (!ALLOWED.some((a) => seg.includes(a))) return w;
      i = scan.indexOf(w, i + w.length);
    }
  }
  return null;
}

(async () => {
  const flow = JSON.parse(fs.readFileSync(path.join(PKG, "data", "lawbank_reasoning_flow.json"), "utf8"));
  const templates = JSON.parse(fs.readFileSync(path.join(PKG, "data", "templates.json"), "utf8"));
  const rulesDoc = JSON.parse(fs.readFileSync(path.join(PKG, "data", "questions_rules.json"), "utf8"));

  const cases = fs
    .readdirSync(path.join(__dirname, "test_facts"))
    .filter((f) => f.endsWith(".json"))
    .sort();

  const llmOutputs = {};

  for (const f of cases) {
    const base = path.basename(f, ".json");
    const facts = JSON.parse(fs.readFileSync(path.join(__dirname, "test_facts", f), "utf8"));
    console.log(`\n[${base}]`);

    // ---- 規則版（基準）----
    const rule = analyze(facts, flow);
    check(rule.gap_list.length > 0 || base === "case_explicit", `${base}：規則版產出缺口清單`);
    check(!hasForbidden(rule.markdown), `${base}：規則版報告無禁語`);

    // ---- LLM 版 ----
    const r = await analyzeWithLLM(facts.facts_text || "", flow, rule);
    console.log(`  來源=${r.source}  耗時=${r.elapsedMs}ms`);
    if (r.source === "llm") {
      check(true, `${base}：LLM 輸出通過全部校驗`);
      const o = r.llm;
      check(typeof o.subject.identified === "boolean", `${base}：LLM 給出主體判定`);
      check(Array.isArray(o.elements) && o.elements.length > 0, `${base}：LLM 給出要件判定`);
      check(Array.isArray(o.gaps), `${base}：LLM 給出缺口陣列`);
      check(!hasForbidden(JSON.stringify(o)), `${base}：LLM 輸出無禁語`);

      // LLM 缺口須可對應既有要件
      const validIds = new Set();
      for (const st of flow.statute_decomposition) {
        if (!rule.meta.candidate_statutes.includes(st.statute_id)) continue;
        for (const el of st.elements) validIds.add(el.element_id);
      }
      const bad = (o.gaps || []).flatMap((g) =>
        (g.affects_elements || []).filter((e) => !validIds.has(e)).map((e) => g.gap_id + "→" + e)
      );
      check(bad.length === 0, `${base}：LLM 缺口之 affects_elements 皆指向候選要件`, bad.join(","));

      // 依 LLM 結果產生缺口清單並送入生成器
      const llmGapList = (o.gaps || []).map((g) => ({
        gap_id: g.gap_id,
        type: g.type,
        description: g.description,
        affects_elements: g.affects_elements || [],
        question_hint: g.question_hint || "請補充說明本項事實之具體內容。",
      }));
      const gen = generate({
        templates,
        rulesDoc,
        gapList: llmGapList,
        meta: Object.assign({}, rule.meta, { subject_identified: o.subject.identified }),
        factsText: facts.facts_text || "",
      });
      check(gen.questions.length > 0, `${base}：LLM 缺口可產生問句（${gen.questions.length} 句）`);
      const covered = new Set(gen.questions.flatMap((q) => q.covers_gaps || []));
      const missing = llmGapList.map((g) => g.gap_id).filter((id) => !covered.has(id));
      check(missing.length === 0, `${base}：LLM 缺口全數有對應問句`, missing.join(","));
      check(!hasForbidden(gen.export_text), `${base}：LLM 版匯出文字無禁語`);
      check(
        gen.export_text.includes("模擬填充，不構成正式文書。"),
        `${base}：LLM 版匯出文字含免責註記`
      );
      check(
        gen.export_text.trim().endsWith("所有罪名均為候選，不認定犯罪成立。"),
        `${base}：LLM 版匯出文字末尾為候選聲明`
      );
      llmOutputs[base] = { llm: o, gen, rule_meta: rule.meta };
    } else {
      // 退回規則版：此為系統設計之正確行為（非失敗）。驗證退回後產出仍完整且合法。
      check(!!r.rule, `${base}：LLM 失敗時已退回規則版`);
      check(r.violations.length > 0, `${base}：退回原因已記錄`);
      const gen = generate({
        templates,
        rulesDoc,
        gapList: rule.gap_list,
        meta: rule.meta,
        factsText: facts.facts_text || "",
      });
      check(gen.questions.length > 0, `${base}：退回版仍產出問句（${gen.questions.length} 句）`);
      check(!hasForbidden(gen.export_text), `${base}：退回版匯出文字無禁語`);
      check(
        gen.export_text.trim().endsWith("所有罪名均為候選，不認定犯罪成立。"),
        `${base}：退回版匯出文字末尾為候選聲明`
      );
      check(
        gen.export_text.split("\n").length > 5,
        `${base}：退回版匯出文字完整`,
        String(gen.export_text.split("\n").length)
      );
      llmOutputs[base] = { fallback: r.violations, rule_meta: rule.meta, gen };
    }
  }

  // 產出報告
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(path.join(OUT_DIR, "llm_e2e.json"), JSON.stringify(llmOutputs, null, 2), "utf8");

  const failed = results.filter((r) => !r.ok);
  const usedLLM = Object.values(llmOutputs).filter((e) => e.llm).length;
  const usedFallback = Object.keys(llmOutputs).length - usedLLM;
  console.log("\n" + "-".repeat(60));
  console.log(`LLM 產出：${usedLLM} 例；退回規則版：${usedFallback} 例`);
  console.log(`檢查項目：${results.length}　通過：${results.length - failed.length}　失敗：${failed.length}`);
  process.exit(failed.length ? 1 : 0);
})();

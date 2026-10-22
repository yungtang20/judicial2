// M7 LLM 分析層：以語意模型補足規則式比對之不足（主體辨識、要件受陳述與否、缺口敘述）。
//
// 設計原則：
//   1. LLM 僅判斷「事實是否已受陳述」，不判斷「犯罪是否成立」——系統全程不認定犯罪成立。
//   2. LLM 輸出須通過與規則版相同之校驗（element_id 須存在、狀態值須合法、禁語檢查）。
//   3. 任一校驗不通過或呼叫失敗，即退回規則版 analyzer，並於輸出標明 fallback。
//   4. 候選罪名不由 LLM 產生，仍依 lawbank_reasoning_flow.json 之規則判定，且不排序。
const { callLLM, extractJSON } = require("./llm_bridge");

const VALID_STATUS = ["已具備", "待確認", "明顯欠缺", "因指代不明無法判斷"];
const VALID_GAP_TYPE = ["fact", "element"];
const FORBIDDEN_WORDS = ["成立", "構成", "該當", "應論以"];
const ALLOWED_PHRASES = [
  "不認定犯罪成立",
  "不構成",
  "未構成",
  "構成要件之判準",
  "成立與否",
];

/** 建立提示詞：只給該判斷所需之要件清單與事實，避免模型自由發揮 */
function buildPrompt(factsText, flow, candidateStatutes) {
  const elements = [];
  for (const st of flow.statute_decomposition) {
    if (candidateStatutes && candidateStatutes.length && !candidateStatutes.includes(st.statute_id)) continue;
    for (const el of st.elements) {
      elements.push({
        element_id: el.element_id,
        statute_id: st.statute_id,
        element_name: el.element_name,
        definition: el.definition,
        fact_patterns: el.fact_patterns || [],
        critical: el.critical !== false,
        discriminating: el.discriminating === true,
      });
    }
  }
  const schema = {
    subject: { identified: "boolean", detail: "string" },
    delivery_status: "string（已交付／已取走／僅有要求或脅迫，交付與否未敘明／未敘明）",
    elements: [
      {
        element_id: "string（須為清單中既有 id）",
        status: "string（已具備／待確認／明顯欠缺／因指代不明無法判斷）",
        reason: "string（一句話說明理由）",
      },
    ],
    gaps: [
      {
        gap_id: "string（g1 起依序編號）",
        type: "string（fact 或 element）",
        description: "string（具體指出缺哪項事實、致哪個要件無法判斷）",
        affects_elements: "string 陣列（既有 element_id）",
        question_hint: "string（開放式建議問法，不得為是／否問句）",
      },
    ],
  };

  return [
    "你是刑事案件承辦人助手。請依下列規定分析事實，僅輸出 JSON。",
    "",
    "【絕對禁止】",
    "- 不得輸出「成立」「構成」「該當」「應論以」等斷定語。",
    "- 不得判斷犯罪是否成立；你只判斷「事實是否已受陳述」。",
    "- 不得新增不在清單中的 element_id。",
    "- 不得輸出 Markdown 圍欄、前言或結語，只輸出 JSON 物件。",
    "",
    "【判斷基準】",
    "- status=已具備：敘事中已出現該要件對應之事實。",
    "- status=明顯欠缺：基本要件（critical=true）之對應事實完全未出現。",
    "- status=待確認：非基本要件，敘事未提及，尚待確認。",
    "- status=因指代不明無法判斷：敘事中出現相關內容，但所指之人未明。",
    "- subject.identified=false：敘事中當事人未明確或出現未解析之指代。",
    "- 每個缺口須具體指出「缺哪項事實、致哪個要件無法判斷」。",
    "",
    "【事實描述】",
    factsText,
    "",
    "【待判斷之要件】",
    JSON.stringify(elements, null, 1),
    "",
    "【輸出 JSON 結構】",
    JSON.stringify(schema, null, 1),
    "",
    "只輸出 JSON。",
  ].join("\n");
}

/** 校驗 LLM 輸出是否符合規則；回傳 {ok, violations} */
function validateLLMOutput(obj, flow, candidateStatutes) {
  const violations = [];
  if (!obj || typeof obj !== "object") {
    return { ok: false, violations: ["輸出非 JSON 物件"] };
  }
  const validElementIds = new Set();
  for (const st of flow.statute_decomposition) {
    if (candidateStatutes && candidateStatutes.length && !candidateStatutes.includes(st.statute_id)) continue;
    for (const el of st.elements) validElementIds.add(el.element_id);
  }
  if (typeof obj.subject !== "object" || typeof obj.subject.identified !== "boolean") {
    violations.push("subject.identified 須為布林值");
  }
  if (!Array.isArray(obj.elements) || !obj.elements.length) {
    violations.push("elements 須為非空陣列");
  }
  for (const e of obj.elements || []) {
    if (!validElementIds.has(e.element_id)) {
      violations.push("element_id 不存在或非候選要件：" + e.element_id);
    }
    if (!VALID_STATUS.includes(e.status)) {
      violations.push("status 值不合法：" + e.element_id + " → " + e.status);
    }
    if (!e.reason || String(e.reason).length < 2) {
      violations.push("reason 為空：" + e.element_id);
    }
  }
  if (!Array.isArray(obj.gaps)) {
    violations.push("gaps 須為陣列");
  }
  const seenGap = new Set();
  for (const g of obj.gaps || []) {
    if (!/^g\d+$/.test(g.gap_id || "")) violations.push("gap_id 格式不合法：" + g.gap_id);
    if (seenGap.has(g.gap_id)) violations.push("gap_id 重複：" + g.gap_id);
    seenGap.add(g.gap_id);
    if (!VALID_GAP_TYPE.includes(g.type)) violations.push("gap type 不合法：" + g.gap_id);
    if (!g.description || String(g.description).length < 4) violations.push("gap description 為空：" + g.gap_id);
    for (const eid of g.affects_elements || []) {
      if (!validElementIds.has(eid)) violations.push("affects_elements 指向未定義要件：" + eid);
    }
    if (g.question_hint) {
      const bad = FORBIDDEN_WORDS.find(
        (w) => g.question_hint.includes(w) && !ALLOWED_PHRASES.some((a) => g.question_hint.includes(a))
      );
      if (bad) violations.push("question_hint 含禁語：" + bad + "（" + g.gap_id + "）");
    }
  }
  // 禁語：整體掃描（排除允許片語）
  const raw = JSON.stringify(obj);
  for (const w of FORBIDDEN_WORDS) {
    let idx = raw.indexOf(w);
    while (idx !== -1) {
      const seg = raw.slice(Math.max(0, idx - 25), idx + 25);
      if (!ALLOWED_PHRASES.some((a) => seg.includes(a))) {
        violations.push("輸出含禁語：" + w + " → …" + seg + "…");
        break;
      }
      idx = raw.indexOf(w, idx + w.length);
    }
  }
  return { ok: violations.length === 0, violations };
}

/**
 * 以 LLM 執行分析；失敗則退回規則版。
 * @returns {Promise<{source:'llm'|'fallback', violations:string[], llm?:object, rule?:object}>}
 */
async function analyzeWithLLM(factsText, flow, ruleAnalysis) {
  const candidateStatutes = ruleAnalysis.meta.candidate_statutes;
  const prompt = buildPrompt(factsText, flow, candidateStatutes);
  const res = await callLLM(prompt);
  if (!res.ok) {
    return { source: "fallback", violations: ["LLM 呼叫失敗：" + res.error], rule: ruleAnalysis, elapsedMs: res.elapsedMs };
  }
  const obj = extractJSON(res.text);
  if (!obj) {
    return { source: "fallback", violations: ["LLM 回傳內容無法解析為 JSON"], rule: ruleAnalysis, elapsedMs: res.elapsedMs };
  }
  const v = validateLLMOutput(obj, flow, candidateStatutes);
  if (!v.ok) {
    return { source: "fallback", violations: v.violations, rule: ruleAnalysis, elapsedMs: res.elapsedMs, llm: obj };
  }
  return { source: "llm", violations: [], llm: obj, elapsedMs: res.elapsedMs };
}

module.exports = { buildPrompt, validateLLMOutput, analyzeWithLLM, VALID_STATUS, FORBIDDEN_WORDS };

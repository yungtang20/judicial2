// M7 瀏覽器端 LLM 客戶端：呼叫本機 /api/llm 端點，套用與 tools/llm_analyzer.js 相同之校驗。
// 可同時於 Node 與瀏覽器載入。
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.RF = root.RF || {};
    root.RF.llm = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STATUS = ["已具備", "待確認", "明顯欠缺", "因指代不明無法判斷"];
  const FORBIDDEN = ["成立", "構成", "該當", "應論以"];
  const ALLOWED = ["不認定犯罪成立", "不構成", "未構成", "構成要件之判準", "成立與否"];

  function buildPrompt(factsText, flow, cands) {
    const elements = [];
    for (const st of flow.statute_decomposition) {
      if (cands && cands.length && !cands.includes(st.statute_id)) continue;
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
      JSON.stringify(
        {
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
        },
        null,
        1
      ),
      "",
      "只輸出 JSON。",
    ].join("\n");
  }

  function extractJSON(text) {
    let s = String(text || "").trim();
    const f = s.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (f) s = f[1].trim();
    const a = s.indexOf("{");
    const b = s.lastIndexOf("}");
    if (a < 0 || b <= a) return null;
    try {
      return JSON.parse(s.slice(a, b + 1));
    } catch (e) {
      return null;
    }
  }

  function validate(obj, flow, cands) {
    const V = [];
    const ids = new Set();
    for (const st of flow.statute_decomposition) {
      if (cands && cands.length && !cands.includes(st.statute_id)) continue;
      for (const el of st.elements) ids.add(el.element_id);
    }
    if (!obj || typeof obj !== "object" || typeof obj.subject !== "object" ||
        typeof obj.subject.identified !== "boolean") {
      V.push("subject.identified 須為布林值");
    }
    if (!Array.isArray(obj.elements) || !obj.elements.length) V.push("elements 須為非空陣列");
    for (const e of obj.elements || []) {
      if (!ids.has(e.element_id)) V.push("element_id 不存在或非候選要件：" + e.element_id);
      if (STATUS.indexOf(e.status) < 0) V.push("status 值不合法：" + e.element_id);
      if (!e.reason) V.push("reason 為空：" + e.element_id);
    }
    if (!Array.isArray(obj.gaps)) V.push("gaps 須為陣列");
    const seen = new Set();
    for (const g of obj.gaps || []) {
      if (!/^g\d+$/.test(g.gap_id || "")) V.push("gap_id 格式不合法：" + g.gap_id);
      if (seen.has(g.gap_id)) V.push("gap_id 重複：" + g.gap_id);
      seen.add(g.gap_id);
      if (["fact", "element"].indexOf(g.type) < 0) V.push("gap type 不合法：" + g.gap_id);
      for (const x of g.affects_elements || []) {
        if (!ids.has(x)) V.push("affects_elements 指向未定義要件：" + x);
      }
    }
    const raw = JSON.stringify(obj);
    for (const w of FORBIDDEN) {
      let i = raw.indexOf(w);
      while (i !== -1) {
        const seg = raw.slice(Math.max(0, i - 25), i + 25);
        if (!ALLOWED.some((a) => seg.includes(a))) {
          V.push("輸出含禁語：" + w);
          break;
        }
        i = raw.indexOf(w, i + w.length);
      }
    }
    return { violations: V };
  }

  /** 呼叫本機端點取得 LLM 輸出並校驗。失敗時回傳 {ok:false, error}。 */
  async function analyzeWithLLM(factsText, flow, cands, endpoint) {
    const url = endpoint || "/api/llm";
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: buildPrompt(factsText, flow, cands) }),
    });
    const j = await res.json();
    if (!j.ok) return { ok: false, error: j.error || "LLM 呼叫失敗" };
    const obj = extractJSON(j.text);
    if (!obj) return { ok: false, error: "LLM 回傳內容無法解析為 JSON" };
    const v = validate(obj, flow, cands);
    if (v.violations.length) return { ok: false, error: "LLM 輸出未通過校驗", violations: v.violations };
    return { ok: true, obj: obj, model: j.model };
  }

  return { buildPrompt, extractJSON, validate, analyzeWithLLM, STATUS, FORBIDDEN };
});

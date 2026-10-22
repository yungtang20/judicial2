// 可同時於 Node（CommonJS）與瀏覽器（掛載至 window.RF.<Name>）載入。
//
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.RF = root.RF || {};
    root.RF.generator = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
"use strict";

/* ============================================================
   規則執行器（與 questions_rules.json 之 check_type 對應）
   ============================================================ */
function checkRule(rule, question, item) {
  const ctype = rule.check_type;
  if (ctype === "required_pattern") {
    const cv = rule.check_value;
    const markers = Array.isArray(cv) ? cv : cv.open_markers || [];
    const hit = markers.filter((m) => question.includes(m));
    if (!hit.length) return { ok: false, msg: "未含開放式標記" };
    if (!Array.isArray(cv)) {
      const allowed = cv.allowed_programmatic || [];
      if (allowed.some((a) => question.includes(a))) return { ok: true, msg: "例外句（權益選擇）" };
    }
    return { ok: true, msg: "命中：" + hit.slice(0, 3).join("、") };
  }
  if (ctype === "forbidden_word") {
    const words = Array.isArray(rule.check_value) ? rule.check_value : [];
    for (const w of words) {
      if (question.includes(w)) return { ok: false, msg: "含禁用字：" + w };
    }
    return { ok: true, msg: "" };
  }
  if (ctype === "mapping_required") {
    const targets = Array.isArray(rule.check_value) ? rule.check_value : [rule.check_value];
    const maps = (item && item.maps_to) || [];
    for (const t of targets) {
      // gap_id    → 該問句須標明所對應之缺口或事實面向
      if (t === "gap_id") {
        if (item && item.gap_id) return { ok: true, msg: "" };
        if (item && item.covers_gaps && item.covers_gaps.length) return { ok: true, msg: "" };
        if (maps.some((m) => String(m).startsWith("gap_category:"))) return { ok: true, msg: "" };
        continue;
      }
      // element_id → maps_to 須含構成要件
      if (t === "element_id") {
        if (maps.some((m) => String(m).startsWith("e_"))) return { ok: true, msg: "" };
        continue;
      }
      // target    → 該問句須標明受詢問者角色
      if (t === "target") {
        if (item && item.target) return { ok: true, msg: "" };
        continue;
      }
      if (maps.some((m) => String(m).includes(t))) return { ok: true, msg: "" };
    }
    return { ok: false, msg: "未對應 " + targets.join("/") };
  }
  if (ctype === "tag_constraint") {
    const cv = rule.check_value;
    if (!cv || typeof cv !== "object") return { ok: true, msg: "" };
    if (cv.id_pattern && item && item.id && !new RegExp(cv.id_pattern).test(item.id)) {
      return { ok: false, msg: "代號格式不符：" + item.id };
    }
    if (cv.max_question_marks) {
      const n = (question.match(/[？?]/g) || []).length;
      if (n > cv.max_question_marks) return { ok: false, msg: `問號數 ${n} > ${cv.max_question_marks}` };
    }
    return { ok: true, msg: "" };
  }
  return { ok: true, msg: "" };
}

/** 依規則集檢驗問句；回傳 {ok, violations[]} */
function validateQuestion(rules, question, item) {
  const violations = [];
  for (const r of rules) {
    if (r.severity !== "error") continue;
    if (r.applies_to && !r.applies_to.includes("templates")) continue;
    const res = checkRule(r, question, item);
    if (!res.ok) violations.push({ rule_id: r.rule_id, msg: res.msg });
  }
  return { ok: violations.length === 0, violations };
}

/* ============================================================
   要件 → 受詢問者角色
   ============================================================ */
const ELEMENT_TARGET = {
  e_coercion: "relative",
  e_irresistible: "relative",
  e_taking_or_delivery: "relative",
  e_threat: "relative",
  e_delivery_by_fear: "relative",
  e_robbery_intent: "relative",
  e_theft_taking: "relative",
  e_theft_object: "relative",
  e_robbery_snatch: "relative",
  e_agg_circumstance: "suspect",
  e_preceding_offense: "suspect",
  e_motive: "suspect",
  e_ond_the_spot: "suspect",
  e_illegal_benefit: "relative",
};

/* ============================================================
   模板選擇（templates.json 的 selection_logic）
   ============================================================ */
function selectTemplate(templates, answers, overrideId) {
  if (overrideId) {
    const t = (templates.templates || []).find((x) => x.template_id === overrideId);
    if (t) return { template: t, note: "人工指定模板：" + t.template_name };
  }
  const table = templates.selection_logic.decision_table || [];
  for (const row of table) {
    let ok = true;
    for (const key of ["has_victim", "is_solved", "subject_identified"]) {
      const cond = row[key];
      if (cond === null || cond === undefined) continue;
      const ans = answers[key];
      if (ans === null || ans === undefined) { ok = false; break; }
      if (cond !== ans) { ok = false; break; }
    }
    if (!ok) continue;
    if (row.template_id) {
      const t = templates.templates.find((x) => x.template_id === row.template_id);
      return { template: t, note: row.result_note || "" };
    }
    // 無對應模板：退回最一般之模板並註明
    const fallback = templates.templates[0];
    return {
      template: fallback,
      note: (row.result_note || "無對應模板") + "；已暫用最一般之模板，請承辦人確認後調整。",
      noExactMatch: true,
    };
  }
  const fallback = templates.templates[0];
  return { template: fallback, note: "無相符之選擇列，暫用最一般之模板。", noExactMatch: true };
}

/* ============================================================
   條陳欄位填充
   ============================================================ */
function extractValue(hints, factsText) {
  if (!hints) return null;
  switch (hints.type) {
    case "summary": {
      const t = String(factsText || "").trim();
      if (!t) return null;
      let s = t.length > (hints.max_length || 200) ? t.slice(0, hints.max_length || 200) : t;
      if (hints.max_length && t.length > hints.max_length) s += "…";
      return s + (hints.suffix || "");
    }
    case "constant":
      return hints.value || null;
    case "manual":
      return null;
    case "datetime":
    case "location":
    case "person": {
      // 若指定 context_before，僅在該脈絡詞之後的視窗內擷取，
      // 避免把「發生時間」誤填為「報案時間」或「破獲時間」。
      const scopes = [];
      if (hints.context_before && hints.context_before.length) {
        const win = hints.context_window || 30;
        for (const ctx of hints.context_before) {
          let idx = (factsText || "").indexOf(ctx);
          while (idx !== -1) {
            scopes.push((factsText || "").slice(idx, idx + ctx.length + win));
            idx = (factsText || "").indexOf(ctx, idx + ctx.length);
          }
        }
        if (!scopes.length) return null;
      } else {
        scopes.push(factsText || "");
      }
      for (const scope of scopes) {
        for (const p of hints.patterns || []) {
          const re = new RegExp(p);
          const m = re.exec(scope);
          if (m) {
            const v = (m[1] !== undefined ? m[1] : m[0]).trim();
            if (v) return v;
          }
        }
      }
      return null;
    }
    default:
      return null;
  }
}

/** 組裝條陳填充表 */
function fillStatement(templates, template, factsText, meta) {
  const subjectUnknown = meta && meta.subject_identified === false;
  const rows = [];
  for (const sec of template.sections || []) {
    for (const f of sec.fields || []) {
      const row = {
        template_id: template.template_id,
        section_id: sec.section_id,
        section_title: sec.section_title,
        field_id: f.field_id,
        label: f.label,
        fixed_text: f.fixed_text,
        type: f.type,
        editable: f.editable !== false,
        render: f.render || "inline",
        variable_position: f.variable_position || "after",
        fixed_suffix: f.fixed_suffix || "",
        value: "",
        status: "",
      };

      if (f.type === "static") {
        row.value = f.fixed_text;
        row.status = "固定文字";
        rows.push(row);
        continue;
      }
      if (f.type === "composite") {
        row.value = f.fixed_text;
        row.status = "固定文字（案號空位保留原樣）";
        row.slots = (f.slots || []).map((s) => ({ slot_id: s.slot_id, label: s.label, value: "" }));
        rows.push(row);
        continue;
      }

      const extracted = extractValue(f.value_hints, factsText);
      // 主體不明時，與當事人有關之欄位一律標「（主體待確認）」，不填入含指代之敘事
      const subjectRelated = ["case_reason", "case_summary", "jurisdiction"].includes(f.field_id);
      if (subjectUnknown && subjectRelated) {
        row.value = "（主體待確認）";
        row.status = "主體待確認";
      } else if (extracted) {
        row.value = extracted;
        row.status = "已填";
      } else {
        // 依 empty_policy 決定未填之標記
        if (f.empty_policy === "keep_placeholder") {
          row.value = f.variable_placeholder || "";
          row.status = "保留原文佔位";
        } else if (f.empty_policy === "keep_blank") {
          row.value = "";
          row.status = "保留原樣";
        } else {
          row.value = "（待補）";
          row.status = "未敘明，待補";
        }
      }
      rows.push(row);
    }
  }
  return rows;
}

/** 依 fixed_text 規則串接為條陳文字（與 M1 原型之組裝規則一致）
 *  順序規則：標題行置於最上，其後依 template.sections[].fields[] 之原序，
 *  不得重排、不得增刪欄位。此一約束由 tools/validate_generator.py 對照 條陳.txt 驗證。
 */
function renderStatement(rows, template) {
  const lines = [];
  if (template && template.title_text) lines.push(template.title_text);
  for (const r of rows) {
    if (r.type === "static" || r.type === "composite") { lines.push(r.value); continue; }
    if (r.render === "below") {
      lines.push(r.fixed_text + "\n" + r.value);
    } else if (r.variable_position === "before") {
      lines.push(r.value + r.fixed_text + r.fixed_suffix);
    } else {
      lines.push(r.fixed_text + r.value + r.fixed_suffix);
    }
  }
  return lines.join("\n");
}

/* ============================================================
   問句清單生成
   ============================================================ */
function buildQuestions(rulesDoc, gapList, meta) {
  const rules = rulesDoc.rules || [];
  const templates = rulesDoc.question_templates || [];
  const questions = [];
  const rejected = [];
  const usedTemplateIds = new Set();

  for (const gap of gapList) {
    // 1) 依缺口判定受詢問者角色
    let target = null;
    for (const eid of gap.affects_elements || []) {
      if (ELEMENT_TARGET[eid]) { target = ELEMENT_TARGET[eid]; break; }
    }
    if (!target) {
      // 主體／交付／事實面向類缺口 → 相對人（其為事實陳述者）
      target = "relative";
    }

    // 2) 找出對應之問句範本
    const matched = [];
    for (const t of templates) {
      if (t.target !== target) continue;
      const maps = t.maps_to || [];
      const hit = maps.some((m) => {
        if (gap.affects_elements && gap.affects_elements.some((e) => m === e)) return true;
        if (m.startsWith("gap_category:")) {
          const cat = m.slice("gap_category:".length);
          if (gap.type === "fact" && gap.description.includes("「" + cat + "」")) return true;
          // 主體／交付類缺口以關鍵面向對應
          if (cat === "人" && /主體|指代|當事人/.test(gap.description)) return true;
          if (cat === "物" && /交付|取走|財物/.test(gap.description)) return true;
          if (cat === "補強" && /佐證|補強/.test(gap.description)) return true;
        }
        return false;
      });
      if (hit) matched.push(t);
    }

    // 3) 優先使用專屬範本；無則用缺口附帶之建議問法
    const candidates = matched.length
      ? matched
      : [{ template_id: null, template: gap.question_hint, target, maps_to: gap.affects_elements || [], fact_categories: [] }];

    let added = 0;
    for (const c of candidates) {
      const text = c.template;
      if (!text) continue;
      const item = {
        id: "",
        target: c.target,
        question: text,
        maps_to: (c.maps_to || []).concat(gap.affects_elements || []).filter((v, i, a) => a.indexOf(v) === i),
        gap_id: gap.gap_id,
        note: "對應缺口 " + gap.gap_id + (c.template_id ? "；範本 " + c.template_id : "；依缺口建議問法"),
        source_template_id: c.template_id || null,
      };
      // maps_to 不得為空：事實面向缺口以「gap:<gap_id>」標示其對應之缺口
      if (!item.maps_to.length) item.maps_to = ["gap:" + gap.gap_id];
      const v = validateQuestion(rules, item.question, item);
      if (!v.ok) {
        rejected.push({ gap_id: gap.gap_id, question: text.slice(0, 60), violations: v.violations });
        continue;
      }
      // 去重：同 target 且 question 相同者，併入該問句所覆蓋之缺口
      const dup = questions.find((q) => q.target === item.target && q.question === item.question);
      if (dup) {
        if (!dup.covers_gaps.includes(gap.gap_id)) {
          dup.covers_gaps.push(gap.gap_id);
          dup.note += "；並對應缺口 " + gap.gap_id;
        }
        added++;
        break;
      }
      item.id = makeQuestionId(rulesDoc, item);
      item.covers_gaps = [gap.gap_id];
      questions.push(item);
      if (c.template_id) usedTemplateIds.add(c.template_id);
      added++;
      break; // 每個缺口取第一個合適範本即可
    }
    if (added === 0) {
      // 最後手段：以缺口描述之面向產生開放式問句
      const fallbackText = gap.question_hint || "請補充說明本項事實之具體內容。";
      const item = {
        id: "",
        target,
        question: fallbackText,
        maps_to: gap.affects_elements || [],
        gap_id: gap.gap_id,
        note: "對應缺口 " + gap.gap_id + "；無合適範本，採缺口建議問法",
        source_template_id: null,
      };
      const v = validateQuestion(rules, item.question, item);
      if (v.ok) {
        item.id = makeQuestionId(rulesDoc, item);
        item.covers_gaps = [gap.gap_id];
        questions.push(item);
      } else {
        rejected.push({ gap_id: gap.gap_id, question: fallbackText.slice(0, 60), violations: v.violations });
      }
    }
  }

  // 4) 角色基礎問句：每個角色之最低必問（自由敘述與依序敘述），
  //    避免於無缺口時完全未向某一方詢問。依 questions_rules 之 question_templates 取出。
  const BASELINE = [
    { target: "relative", template_id: "q_relative_free_account", condition: () => true },
    {
      target: "suspect",
      template_id: "q_suspect_sequence",
      condition: (m) => m && m.has_victim !== false && m.subject_identified !== false,
    },
  ];
  for (const b of BASELINE) {
    if (!b.condition(meta)) continue;
    const t = templates.find((x) => x.template_id === b.template_id);
    if (!t) continue;
    const item = {
      id: "",
      target: t.target,
      question: t.template,
      maps_to: t.maps_to || [],
      gap_id: null,
      covers_gaps: [],
      note: "角色基礎問句（每次詢問必問）",
      source_template_id: t.template_id,
      is_baseline: true,
    };
    const v = validateQuestion(rules, item.question, item);
    if (!v.ok) {
      rejected.push({ gap_id: "(baseline)", question: t.template.slice(0, 60), violations: v.violations });
      continue;
    }
    if (questions.some((q) => q.target === item.target && q.question === item.question)) continue;
    item.id = makeQuestionId(rulesDoc, item);
    questions.push(item);
  }

  // 5) 依 rules 之 priority_order 分組排序
  const order = (rules.find((r) => r.rule_id === "page_budget") || {}).check_value?.priority_order || [];
  const groupOrder = rulesDoc.output_format?.group_order || ["relative", "suspect", "witness"];

  return { questions, rejected, usedTemplateIds: [...usedTemplateIds], priorityOrder: order, groupOrder };
}

/** 產生符合 <prefix>-<C|S|R|D|A|N|W>-<number> 格式且不重複之代號 */
function makeQuestionId(rulesDoc, item) {
  const prefix = item.target === "suspect" ? "N" : item.target === "witness" ? "W" : "C";
  const used = rulesDoc._usedIds || (rulesDoc._usedIds = new Set());
  let n = 1;
  let id;
  do {
    id = "GEN-" + prefix + "-" + String(n).padStart(2, "0");
    n++;
  } while (used.has(id));
  used.add(id);
  return id;
}

/* ============================================================
   主入口
   ============================================================ */
function generate(input) {
  const { templates, rulesDoc, gapList, meta, factsText, templateOverride } = input;

  // 模板選擇
  const answers = {
    has_victim: meta && meta.has_victim !== null && meta.has_victim !== undefined ? meta.has_victim : true,
    is_solved: meta && meta.is_solved === true,
    subject_identified: meta ? meta.subject_identified : null,
  };
  const sel = selectTemplate(templates, answers, templateOverride);
  const template = sel.template;

  // 條陳填充
  const fillRows = fillStatement(templates, template, factsText, meta);

  // 問句清單
  const q = buildQuestions(rulesDoc, gapList, meta);

  // 匯出文字（標題行 + 依原序之欄位）
  const exportText =
    renderStatement(fillRows, template) + "\n\n" + (templates.export_rules?.footer || []).join("\n");

  return {
    template_id: template.template_id,
    template_name: template.template_name,
    template_selection: { answers, note: sel.note, no_exact_match: !!sel.noExactMatch },
    questions: q.questions,
    questions_by_target: groupBy(q.questions, "target"),
    rejected_questions: q.rejected,
    statement_fill: fillRows,
    export_text: exportText,
    meta: {
      question_count: q.questions.length,
      rejected_count: q.rejected.length,
      gap_count: gapList.length,
      covered_gaps: [...new Set(q.questions.flatMap((x) => x.covers_gaps || []))].sort(),
      fill_status: fillRows.reduce((a, r) => { a[r.status] = (a[r.status] || 0) + 1; return a; }, {}),
    },
  };
}

function groupBy(arr, key) {
  const out = {};
  for (const x of arr) {
    const k = x[key];
    if (!out[k]) out[k] = [];
    out[k].push(x);
  }
  return out;
}

return {
  generate,
  validateQuestion,
  checkRule,
  selectTemplate,
  fillStatement,
  extractValue,
  buildQuestions,
  renderStatement,
  ELEMENT_TARGET,
};
});

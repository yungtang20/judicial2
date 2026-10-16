"use strict";

const token = document.querySelector('meta[name="session-token"]').content;
const state = { current: null, bank: null, questionIndex: 0, gate2Step: "offense" };
const $ = (selector) => document.querySelector(selector);

function announce(message, isError = false) {
  const node = $("#status");
  node.textContent = message;
  node.style.background = isError ? "#7e1f1f" : "#10241c";
}

class ApiError extends Error {
  constructor(message, status, code, cause) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    if (cause !== undefined) this.cause = cause;
  }
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-Session-Token", token);
  if (options.body) headers.set("Content-Type", "application/json");
  let response;
  try {
    response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  } catch (cause) {
    // 本機服務停止或一般網路錯誤：不暴露瀏覽器英文錯誤或 stack
    throw new ApiError("無法連線到本機服務，請確認服務仍在執行。", 0, "NETWORK_ERROR", cause);
  }
  if (!response.ok) {
    let message = `操作失敗（${response.status}）`;
    let code = null;
    try {
      const body = await response.json();
      if (typeof body.message === "string" && body.message) message = body.message;
      if (typeof body.error === "string" && body.error) code = body.error;
      else if (typeof body.code === "string" && body.code) code = body.code;
    } catch (_) {
      // JSON 無效或回應是 HTML：維持安全預設訊息
    }
    throw new ApiError(message, response.status, code);
  }
  return response;
}

async function jsonApi(path, options = {}) {
  return (await api(path, options)).json();
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function profilePayload(raw, role) {
  const profile = {};
  for (const key of [
    "name", "alias", "gender", "birth_date", "birth_place", "occupation",
    "national_id", "registered_address", "current_address", "education", "phone",
  ]) profile[key] = raw[key] || "";
  return {
    role,
    profile,
    session: {
      start_time: raw.session_start || "",
      end_time: raw.session_end || "",
      location: raw.session_location || "",
    },
  };
}

function lines(value) {
  if (!value) return [];
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function setVisible(id, visible) {
  $(id).hidden = !visible;
}

function activeInterview() {
  if (!state.current) return null;
  return state.current.interviews[`${state.current.question_role}:default`] || null;
}

const KIND_LABELS = {
  company: "公司必問",
  common: "通用必要問句",
  company_offense: "公司套表題",
  core: "核心問句",
  supplemental: "補充問句",
  reinforce: "補強問句",
  distinguishing: "區分問句",
  aggravating: "加重問句",
};

// 題目分組順序：同罪章、同類型的題目連續排列
const KIND_ORDER = ["company", "common", "company_offense", "core", "supplemental", "reinforce", "distinguishing", "aggravating"];

function kindMeta(question) {
  if (question.kind === "company") return "公司範本必問題（逐字保留）";
  if (question.kind === "common") return "通用必要問句";
  const parts = [KIND_LABELS[question.kind] || question.kind];
  if (question.offense_name) parts.push(question.offense_name);
  return parts.join(" · ") + " · 待本案人工確認";
}

function questionMethod(question) {
  if (question.kind === "company") {
    return "提問方式：依公司範本文字逐字詢問，讓受詢問人自行回答，不代答或提示答案。";
  }
  const purpose = String(question.meta?.purpose || "").trim();
  const purposeText = purpose ? `本題用於「${purpose}」。` : "";
  const phase = question.meta?.question_phase;
  const guidance = {
    narrative: "先請受詢問人用自己的話完整敘述，再就不清楚處追問。",
    single_fact: "一次只確認一項事實，並容許回答不知道、不確定或不記得。",
    evidence_followup: "只追問資料來源、時間、位置與可查證方式。",
  }[phase] || "依題目原文中立提問，並容許回答不知道、不確定或不記得。";
  return `提問方式：${purposeText}${guidance}不得把候選罪章當成已成立。`;
}

// 把問句依「罪章 → 類型」排序，並回傳分段資訊供總覽使用
function groupQuestions(questions) {
  const groups = [];
  let currentKey = null;
  const sorted = [...questions].sort((a, b) => {
    const offA = a.offense_name || "";
    const offB = b.offense_name || "";
    if (offA !== offB) {
      // 公司必問、通用題排最前
      const rankA = a.kind === "company" ? -2 : a.kind === "common" ? -1 : 0;
      const rankB = b.kind === "company" ? -2 : b.kind === "common" ? -1 : 0;
      if (rankA !== rankB) return rankA - rankB;
      return offA.localeCompare(offB, "zh-Hant");
    }
    return KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind);
  });
  for (const question of sorted) {
    const key = `${question.offense_name || "通用"}|${question.kind}`;
    if (key !== currentKey) {
      groups.push({ key, label: groupLabel(question), questions: [] });
      currentKey = key;
    }
    groups[groups.length - 1].questions.push(question);
  }
  return { sorted, groups };
}

function groupLabel(question) {
  const kind = KIND_LABELS[question.kind] || question.kind;
  return question.offense_name ? `${question.offense_name} · ${kind}` : kind;
}

function renderProgress(caseState) {
  const order = ["GATE1_REVIEW", "GATE2_QA", "CASE_NUMBERS", "OUTPUT_READY"];
  const currentIndex = order.indexOf(caseState);
  document.querySelectorAll("#gate-progress li").forEach((item, index) => {
    item.classList.toggle("current", index === currentIndex);
    item.classList.toggle("done", index < currentIndex);
  });
}

// 警示顯示（docs/QUESTION_DESIGN_AND_USE.md §6、§8）：承辦人必須可見
function renderWarnings(caseData) {
  const box = $("#case-warnings");
  if (!box) return;
  box.textContent = "";
  const items = [];
  // 問句裁切（8 頁預算）
  for (const w of caseData.question_budget_warnings || []) {
    if (w.level === "BUDGET_PRUNED" && w.pruned_count > 0) {
      const detail = (w.pruned_questions || [])
        .map((q) => `　· ${q.text || q.id}（${q.kind || "?"}）`)
        .join("\n");
      items.push(`⚠ 問句超出 8 頁預算，已裁 ${w.pruned_count} 題（承辦人可視案情自行補問）：\n${detail}`);
    }
  }
  // 候選矛盾（回答驅動重評估，spec §7.4）
  for (const contradiction of caseData.candidate_contradictions || []) {
    items.push(`⚠ 構成要件「${contradiction.element}」的回答同時含肯定與否認陳述，請核對（題號：${(contradiction.question_ids || []).join("、")}）`);
  }
  // 行為時法警示（spec §5.5）
  for (const w of caseData.temporal_law_warnings || []) {
    items.push(`⚠ ${w.message}`);
  }
  if (items.length === 0) {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  for (const text of items) {
    const p = document.createElement("p");
    p.textContent = text;
    box.appendChild(p);
  }
}

function fillGate1(caseData) {
  const form = $("#gate1-form");
  for (const key of ["people", "events", "times", "places", "objects", "behaviors", "unknowns"]) {
    form.elements[key].value = (caseData.gate1[key] || []).join("\n");
  }
  form.elements.causation.value = caseData.gate1.causation || "UNKNOWN";
  renderStructuredFacts(caseData.gate1);
}

// 結構化事實檢視（spec §0 目標 2：可追溯、承辦人逐筆確認）
function renderStructuredFacts(gate1) {
  const box = $("#structured-facts");
  if (!box) return;
  const facts = (gate1 && gate1.facts) || [];
  if (facts.length === 0) { box.hidden = true; return; }
  box.hidden = false;
  const tbody = box.querySelector("tbody");
  tbody.textContent = "";
  for (const fact of facts) {
    const row = document.createElement("tr");
    const idCell = document.createElement("td");
    idCell.className = "fact-id";
    idCell.textContent = (fact.fact_id || "").slice(0, 8);
    const excerptCell = document.createElement("td");
    excerptCell.textContent = fact.source_excerpt || fact.normalized_text || "";
    const statusCell = document.createElement("td");
    statusCell.textContent = `${fact.machine_status || "UNKNOWN"}｜${fact.fact_status || "UNKNOWN"}`;
    row.append(idCell, excerptCell, statusCell);
    tbody.appendChild(row);
  }
}

function choice(id, name, suggested, selected, candidateState = "") {
  const label = document.createElement("label");
  label.className = "choice";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.name = "offense";
  input.value = id;
  input.checked = selected;
  const span = document.createElement("span");
  span.textContent = suggested ? `${name}（候選：${candidateState || "NEED_REVIEW"}）` : name;
  label.append(input, span);
  return label;
}

function legalRoutesForOffenses(bank, offenseIds) {
  const selected = new Set(offenseIds);
  return (bank?.offenses || []).flatMap((offense) => {
    if (!selected.has(offense.id)) return [];
    return (offense.legal_routes || []).map((route) => ({
      id: route.id,
      name: route.name,
      parent_offense_id: offense.id,
    }));
  });
}

function renderLegalRoutes() {
  const container = $("#legal-route-list");
  if (!container || !state.bank) return;
  const offenseIds = Array.from(document.querySelectorAll('input[name="offense"]:checked')).map((item) => item.value);
  const routes = legalRoutesForOffenses(state.bank, offenseIds);
  const selected = new Set((state.current?.selected_legal_routes || []).map((item) => item.route_id));
  const nodes = routes.map((route) => {
    const label = document.createElement("label");
    label.className = "choice";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "legal_route";
    input.value = route.id;
    input.checked = selected.has(route.id);
    const span = document.createElement("span");
    span.textContent = route.name;
    label.append(input, span);
    return label;
  });
  if (!nodes.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "請先選擇候選罪章，再檢視其法律路由。";
    nodes.push(empty);
  }
  container.replaceChildren(...nodes);
}

function renderOffenses(caseData) {
  const suggested = new Map(caseData.candidates.map((item) => [item.id, item]));
  const selected = new Set(caseData.selected_offenses);
  const container = $("#offense-list");
  const nodes = state.bank.offenses.map((item) => choice(
    item.id,
    item.name,
    suggested.has(item.id),
    selected.has(item.id),
    suggested.get(item.id)?.candidate_state,
  ));
  container.replaceChildren(...nodes);
  container.querySelectorAll('input[name="offense"]').forEach((input) => {
    input.addEventListener("change", () => {
      $("#route-review-confirmed").checked = false;
      renderLegalRoutes();
    });
  });
  renderLegalRoutes();
  const routeReview = $("#route-review-confirmed");
  routeReview.checked = ["SELECTED", "REVIEWED_NONE_SELECTED"].includes(caseData.route_selection_status);
  const alternativeBox = $("#alternative-route-list");
  const alternatives = caseData.alternative_routes || [];
  if (alternativeBox) {
    alternativeBox.hidden = alternatives.length === 0;
    alternativeBox.textContent = alternatives.length
      ? `另須人工檢查的非刑事方向：${alternatives.map((item) => item.name).join("、")}。這不是法律結論。`
      : "";
  }
  $("#question-role").value = caseData.question_role;
  const sourceNote = caseData.candidates_source === "ai" ? "AI 分析" : "規則比對";
  $("#ai-analyze").textContent = `AI 分析候選罪章（目前：${sourceNote}）`;
}

function fillProfileForm(caseData) {
  const form = $("#profile-form");
  const role = caseData.question_role;
  const profile = (caseData.profiles || {})[`${role}:default`] || {};
  const session = (caseData.interview_sessions || {})[`${role}:default`] || {};
  const fieldMap = {
    name: "profile-name", alias: "profile-alias", gender: "profile-gender",
    birth_date: "profile-birth-date", birth_place: "profile-birth-place",
    occupation: "profile-occupation", national_id: "profile-national-id",
    registered_address: "profile-registered-address", current_address: "profile-current-address",
    education: "profile-education", phone: "profile-phone",
  };
  for (const [key, id] of Object.entries(fieldMap)) {
    form.elements[id].value = profile[key] || "";
  }
  form.elements["session-start"].value = session.start_time || "";
  form.elements["session-end"].value = session.end_time || "";
  form.elements["session-location"].value = session.location || "";
}

function clampQuestionIndex(caseData) {
  const count = caseData.questions.length;
  if (state.questionIndex >= count) state.questionIndex = Math.max(0, count - 1);
  if (state.questionIndex < 0) state.questionIndex = 0;
}

function setGate2Step(step) {
  state.gate2Step = step;
  const tabs = {
    offense: "#step-tab-offense",
    profile: "#step-tab-profile",
    qa: "#step-tab-qa",
  };
  for (const [name, tabId] of Object.entries(tabs)) {
    $(tabId).classList.toggle("current", name === step);
  }
  setVisible("#gate2-step-offense", step === "offense");
  setVisible("#gate2-step-profile", step === "profile");
  setVisible("#gate2-step-qa", step === "qa");
}

function renderCurrentQuestion(caseData) {
  clampQuestionIndex(caseData);
  const container = $("#question-current");
  const progress = $("#qa-progress");
  const count = caseData.questions.length;
  if (!count) {
    progress.textContent = "尚未建立問句；請先選擇候選罪章。";
    container.replaceChildren();
    $("#question-outline").replaceChildren();
    return;
  }
  const index = state.questionIndex;
  const question = caseData.questions[index];
  const answered = caseData.questions.filter((item) => (item.answer || "").trim()).length;
  progress.textContent = `第 ${index + 1} / ${count} 題 · 已作答 ${answered} 題`;

  const label = document.createElement("label");
  label.htmlFor = "current-answer";
  label.textContent = question.text;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = kindMeta(question);
  if (question.meta?.legacy_fixed) {
    const legacy = document.createElement("div");
    legacy.className = "meta warning-inline";
    legacy.textContent = question.meta.legacy_compound
      ? "公司核定固定題：複合問句，逐字詢問；回答只作敘事記錄，不自動更新事實或路由。"
      : "公司核定固定題：逐字保留；回答只作敘事記錄，不自動更新事實或路由。";
    meta.append(legacy);
  }
  const method = document.createElement("div");
  method.className = "meta question-method";
  method.textContent = questionMethod(question);
  const textarea = document.createElement("textarea");
  textarea.id = "current-answer";
  textarea.rows = 4;
  textarea.maxLength = 20000;
  textarea.value = question.answer || "";
  textarea.placeholder = "不清楚、不記得或不願回答時，請明確填寫（例如 UNKNOWN）。";
  textarea.addEventListener("input", () => {
    question.answer = textarea.value;
    question.status = textarea.value.trim() ? "ANSWERED" : "PENDING";
    refreshOutline();
  });
  const nodes = [label, meta, method];
  if (question.meta?.answer_map) {
    const codeLabel = document.createElement("label");
    codeLabel.htmlFor = "current-answer-code";
    codeLabel.textContent = "中性事實狀態";
    const select = document.createElement("select");
    select.id = "current-answer-code";
    const fallbackLabels = { UNKNOWN: "UNKNOWN／無法確認", YES: "有", NO: "沒有" };
    const answerLabels = question.meta.answer_labels || {};
    for (const value of Object.keys(question.meta.answer_map)) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = answerLabels[value] || fallbackLabels[value] || value;
      select.append(option);
    }
    select.value = question.answer_code || "UNKNOWN";
    select.addEventListener("change", () => { question.answer_code = select.value; });
    nodes.push(codeLabel, select);
  }
  nodes.push(textarea);
  container.replaceChildren(...nodes);
  $("#prev-question").disabled = index === 0;
  $("#next-question").disabled = index === count - 1;
  highlightOutline(index);
}

function highlightOutline(index) {
  document.querySelectorAll("#question-outline .outline-item").forEach((node, i) => {
    node.classList.toggle("current", i === index);
    node.classList.toggle("answered", Boolean(state.current?.questions[i]?.answer?.trim()));
  });
}

function refreshOutline() {
  if (!state.current) return;
  highlightOutline(state.questionIndex);
}

function renderQuestionOutline(caseData) {
  const container = $("#question-outline");
  const { groups } = groupQuestions(caseData.questions);
  const nodes = [];
  let flatIndex = 0;
  for (const group of groups) {
    const heading = document.createElement("div");
    heading.className = "outline-group";
    heading.textContent = group.label;
    nodes.push(heading);
    for (const question of group.questions) {
      const itemIndex = flatIndex; // closure：flatIndex 會繼續遞增，必須先固定
      const item = document.createElement("button");
      item.type = "button";
      item.className = "outline-item";
      item.textContent = `${itemIndex + 1}. ${question.text.slice(0, 24)}${question.text.length > 24 ? "…" : ""}`;
      item.addEventListener("click", () => {
        state.questionIndex = itemIndex;
        renderCurrentQuestion(state.current);
      });
      nodes.push(item);
      flatIndex += 1;
    }
  }
  container.replaceChildren(...nodes);
}

function stepQuestion(delta) {
  if (!state.current) return;
  state.questionIndex = Math.max(0, Math.min(state.current.questions.length - 1, state.questionIndex + delta));
  renderCurrentQuestion(state.current);
}

function renderNumbers(caseData) {
  $("#brief-preview").textContent = `500 字內摘要：${caseData.brief_summary}`;
  $("#proof-number").value = caseData.case_numbers.proof || "";
  $("#women-child-number").value = caseData.case_numbers.women_child || "";
  $("#case165-number").value = caseData.case_numbers.case_165 || "";
  const needsWomenChild = caseData.intake.victim_is_code || /^[A-Za-z]{1,8}\d{3,20}$/.test(caseData.intake.victim_identifier || "");
  const offenseSet = new Set(caseData.selected_offenses);
  Object.values(caseData.interviews).forEach((item) => item.selected_offenses.forEach((id) => offenseSet.add(id)));
  setVisible("#women-child-field", needsWomenChild);
  $("#women-child-number").required = needsWomenChild;
  setVisible("#case165-field", offenseSet.has("fraud"));
  $("#case165-number").required = offenseSet.has("fraud");
}

function renderOutputRoles(caseData) {
  const select = $("#output-role");
  Array.from(select.options).forEach((option) => {
    option.disabled = !caseData.interviews[`${option.value}:default`];
  });
  const first = Array.from(select.options).find((option) => !option.disabled);
  if (first && select.selectedOptions[0]?.disabled) select.value = first.value;
  $("#start-suspect").hidden = !caseData.intake.has_victim || Boolean(caseData.interviews["suspect:default"]);
  loadBrief().catch((error) => {
    $("#brief-output").value = "";
    announce(error.message, true);
  });
}

function renderCase(caseData) {
  state.current = caseData;
  state.questionIndex = 0;
  $("#home").hidden = true;
  $("#workspace").hidden = false;
  $("#case-heading").textContent = `案件 ${caseData.case_id.slice(0, 8)} · revision ${caseData.revision}`;
  renderProgress(caseData.state);
  renderWarnings(caseData);
  fillGate1(caseData);
  renderOffenses(caseData);
  fillProfileForm(caseData);
  if (caseData.questions.length) {
    // 讓資料順序與總覽顯示順序一致（罪章分組、類型排序）
    caseData.questions.sort((a, b) => {
      const offA = a.offense_name || "";
      const offB = b.offense_name || "";
      if (offA !== offB) {
        const rankA = a.kind === "company" ? -2 : a.kind === "common" ? -1 : 0;
        const rankB = b.kind === "company" ? -2 : b.kind === "common" ? -1 : 0;
        if (rankA !== rankB) return rankA - rankB;
        return offA.localeCompare(offB, "zh-Hant");
      }
      return KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind);
    });
    renderQuestionOutline(caseData);
  }
  renderCurrentQuestion(caseData);
  renderNumbers(caseData);
  setVisible("#gate1-panel", caseData.state === "GATE1_REVIEW");
  setVisible("#gate2-panel", caseData.state === "GATE2_QA");
  setVisible("#numbers-panel", caseData.state === "CASE_NUMBERS");
  setVisible("#output-panel", caseData.state === "OUTPUT_READY");
  if (caseData.state === "GATE2_QA") {
    // 有罪章與問句時直接停在問答；否則從選罪章開始
    setGate2Step(caseData.questions.length ? "qa" : "offense");
  }
  if (caseData.state === "OUTPUT_READY") renderOutputRoles(caseData);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function refreshCases() {
  const result = await jsonApi("/api/cases");
  const nodes = result.cases.map((item) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    const offenseNote = (item.state === "GATE2_QA" && !item.has_offenses) ? "（未選罪章）" : "";
    // 密文損壞：不得誤導為「未選罪章」（spec §8.4 fail closed）
    const damageNote = item.damaged ? "⚠ 資料損壞" : "";
    button.textContent = `${item.case_id.slice(0, 8)} · ${stateLabel(item.state)}${damageNote}${offenseNote} · r${item.revision}`;
    button.addEventListener("click", async () => {
      try { renderCase(await jsonApi(`/api/cases/${item.case_id}`)); }
      catch (error) { announce(error.message, true); }
    });
    li.append(button);
    return li;
  });
  $("#case-list").replaceChildren(...nodes);
}

function stateLabel(state) {
  return {
    GATE1_REVIEW: "1 事實",
    GATE2_QA: "2 問答",
    CASE_NUMBERS: "2.5 案號",
    OUTPUT_READY: "3-5 輸出",
  }[state] || state;
}

async function reloadLatestCaseAfterConflict(caseId) {
  try {
    const latest = await jsonApi(`/api/cases/${caseId}`);
    if (state.current?.case_id === caseId) {
      renderCase(latest);
      try {
        await refreshCases();
      } catch (listError) {
        return { ok: true, latest, listFailed: true };
      }
      return { ok: true, latest };
    }
    return { ok: true, latest, switched: true };
  } catch (error) {
    return { ok: false, error };
  }
}

async function action(name, payload = {}) {
  if (!state.current) throw new Error("尚未選擇案件");
  const caseId = state.current.case_id;
  const sentRevision = state.current.revision;
  let updated;
  try {
    updated = await jsonApi(`/api/cases/${caseId}/actions`, {
      method: "POST",
      body: JSON.stringify({ action: name, revision: sentRevision, payload }),
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 409 && error.code === "REVISION_CONFLICT") {
      const result = await reloadLatestCaseAfterConflict(caseId);
      if (result.ok && !result.switched) {
        if (result.listFailed) {
          announce("已載入最新案件，但案件清單暫時未更新，請核對後重試。");
        } else {
          announce("案件已由其他分頁更新，已載入最新版本，請核對後重試。");
        }
        throw new ApiError("案件已由其他分頁更新，已載入最新版本，請核對後重試。", 409, "REVISION_CONFLICT");
      }
      if (result.ok && result.switched) {
        throw new ApiError("案件已由其他更新，且目前已切換至其他案件。", 409, "REVISION_CONFLICT_SWITCHED");
      }
      announce("偵測到案件版本衝突，但無法載入最新版本。請重新選取案件或重新整理後再試。");
      throw new ApiError("偵測到案件版本衝突，但無法載入最新版本。請重新選取案件或重新整理後再試。", 409, "REVISION_CONFLICT");
    }
    throw error;
  }
  renderCase(updated);
  await refreshCases();
  return updated;
}

async function loadBrief() {
  if (!state.current || state.current.state !== "OUTPUT_READY") return;
  const role = $("#output-role").value;
  if ($("#output-role").selectedOptions[0]?.disabled) return;
  const result = await jsonApi(`/api/cases/${state.current.case_id}/brief/${role}`);
  $("#brief-output").value = result.text;
}

async function download(kind) {
  const role = $("#output-role").value;
  const response = await api(`/api/cases/${state.current.case_id}/documents/${role}/${kind}`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `case-${state.current.case_id.slice(0, 8)}-${role}-${kind}.docx`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  const pages = response.headers.get("X-Document-Pages");
  announce(kind === "interview" ? `筆錄已下載，實際排版 ${pages} 頁` : "條陳已下載");
}

$("#intake-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = formObject(event.currentTarget);
  raw.has_victim = $("#has-victim").checked;
  raw.victim_is_code = $("#victim-is-code").checked;
  try {
    const created = await jsonApi("/api/cases", { method: "POST", body: JSON.stringify(raw) });
    renderCase(created);
    await refreshCases();
    announce("案件已建立。請核對 Gate 1。 ");
  } catch (error) { announce(error.message, true); }
});

$("#gate1-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = formObject(event.currentTarget);
  const gate1 = {};
  for (const key of ["people", "events", "times", "places", "objects", "behaviors", "unknowns"]) gate1[key] = lines(raw[key]);
  gate1.causation = raw.causation;
  try { await action("update_gate1", { gate1 }); announce("Gate 1 已儲存，後續核准已失效。 "); }
  catch (error) { announce(error.message, true); }
});

$("#approve-gate1").addEventListener("click", async () => {
  try { await action("approve_gate1", { confirmed: true }); announce("Gate 1 已確認。請選擇候選罪章。 "); }
  catch (error) { announce(error.message, true); }
});

$("#ai-analyze").addEventListener("click", async () => {
  const button = $("#ai-analyze");
  button.disabled = true;
  button.textContent = "AI 分析中…（約 30 秒）";
  try {
    await action("analyze_candidates", { external_ai_consent: true });
    announce("AI 分析完成。候選僅供人工選擇，不代表犯罪成立。 ");
  } catch (error) { announce(error.message, true); }
  finally {
    button.textContent = "AI 分析候選罪章";
    refreshAiConsent();
  }
});

function refreshAiConsent() {
  const consent = $("#ai-consent");
  const button = $("#ai-analyze");
  const enabled = Boolean(state.bank?.external_ai_enabled);
  button.disabled = !enabled || !consent.checked;
  $("#ai-consent-status").textContent = enabled
    ? (consent.checked ? "已明確同意。本次只送出案情摘要，請確認摘要不含不必要的個資。" : "服務已設定，但仍須勾選明示同意後才能送出摘要。")
    : "外部 AI 尚未啟用。僅設定 API key 不會自動外送資料。";
}

$("#ai-consent").addEventListener("change", refreshAiConsent);

$("#offense-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const offenseIds = Array.from(document.querySelectorAll('input[name="offense"]:checked')).map((item) => item.value);
  if (!offenseIds.length) { announce("請至少選擇一個罪章。", true); return; }
  const legalRouteIds = Array.from(document.querySelectorAll('input[name="legal_route"]:checked')).map((item) => item.value);
  if (!$("#route-review-confirmed").checked) { announce("請先完成法律路由人工檢視。", true); return; }
  try {
    await action("set_offenses", {
      offense_ids: offenseIds,
      legal_route_ids: legalRouteIds,
      route_review_confirmed: true,
      role: $("#question-role").value,
    });
    setGate2Step("profile");
    announce("問句已建立。請填寫年籍與詢問時間。 ");
  } catch (error) { announce(error.message, true); }
});

$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = formObject(event.currentTarget);
  try {
    await action("save_profile", profilePayload(raw, state.current.question_role));
    announce("年籍與詢問時間已加密保存。 ");
  } catch (error) { announce(error.message, true); }
});

$("#profile-to-qa").addEventListener("click", () => setGate2Step("qa"));

$("#step-tab-offense").addEventListener("click", () => setGate2Step("offense"));
$("#step-tab-profile").addEventListener("click", () => setGate2Step("profile"));
$("#step-tab-qa").addEventListener("click", () => setGate2Step("qa"));

$("#question-role").addEventListener("change", () => {
  $("#route-review-confirmed").checked = false;
});

$("#prev-question").addEventListener("click", () => stepQuestion(-1));
$("#next-question").addEventListener("click", () => stepQuestion(1));

$("#answers-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const answers = {};
  const answerCodes = {};
  for (const question of state.current.questions) {
    answers[question.id] = question.answer || "";
    if (question.meta?.answer_map) answerCodes[question.id] = question.answer_code || "UNKNOWN";
  }
  try {
    await action("save_answers", { answers, answer_codes: answerCodes });
    announce("回答已加密保存。 ");
  } catch (error) { announce(error.message, true); }
});

$("#approve-gate2").addEventListener("click", async () => {
  const unanswered = state.current.questions.filter((q) => !(q.answer || "").trim());
  if (unanswered.length) {
    const goFirst = window.confirm(`尚有 ${unanswered.length} 題未作答（不清楚可填 UNKNOWN）。要跳到第一個未作答的題目嗎？`);
    if (goFirst) {
      const firstIndex = state.current.questions.findIndex((q) => !(q.answer || "").trim());
      state.questionIndex = Math.max(0, firstIndex);
      setGate2Step("qa");
      renderCurrentQuestion(state.current);
      return;
    }
  }
  const answers = {};
  const answerCodes = {};
  for (const question of state.current.questions) {
    answers[question.id] = question.answer || "";
    if (question.meta?.answer_map) answerCodes[question.id] = question.answer_code || "UNKNOWN";
  }
  try {
    await action("save_answers", { answers, answer_codes: answerCodes });
    await action("approve_gate2", { confirmed: true });
    announce("Gate 2 已確認。 ");
  } catch (error) { announce(error.message, true); }
});

$("#numbers-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try { await action("save_case_numbers", { case_numbers: formObject(event.currentTarget) }); announce("案號已確認，可以輸出文件。 "); }
  catch (error) { announce(error.message, true); }
});

$("#output-role").addEventListener("change", () => loadBrief().catch((error) => announce(error.message, true)));
$("#download-interview").addEventListener("click", () => download("interview").catch((error) => announce(error.message, true)));
$("#download-brief").addEventListener("click", () => download("brief").catch((error) => announce(error.message, true)));
$("#copy-brief").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText($("#brief-output").value); announce("條陳已複製。 "); }
  catch (_) { announce("瀏覽器拒絕剪貼簿操作，請手動選取複製。", true); }
});
$("#start-suspect").addEventListener("click", async () => {
  try { await action("start_interview", { role: "suspect" }); announce("已進入涉嫌人問答。既有被害人輸出仍保留。 "); }
  catch (error) { announce(error.message, true); }
});
$("#reopen-case").addEventListener("click", async () => {
  if (!window.confirm("重新開啟會使下游核准失效。是否繼續？")) return;
  try { await action("reopen", {}); announce("案件已重新開啟，請重新核對 Gate 1。 "); }
  catch (error) { announce(error.message, true); }
});
$("#new-case").addEventListener("click", () => {
  state.current = null;
  state.questionIndex = 0;
  $("#workspace").hidden = true;
  $("#home").hidden = false;
  $("#intake-form").reset();
  $("#has-victim").checked = true;
  announce("可以建立新案件。 ");
});

async function initialize() {
  try {
    state.bank = await jsonApi("/api/question-bank");
    refreshAiConsent();
    await refreshCases();
    announce("準備就緒。Gate 1 只在本機處理；外部 AI 必須由承辦人明示同意後才可分析候選。 ");
  } catch (error) { announce(error.message, true); }
}

initialize();

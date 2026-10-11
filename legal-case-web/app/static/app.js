"use strict";

const token = document.querySelector('meta[name="session-token"]').content;
const state = { current: null, bank: null, questionIndex: 0, gate2Step: "offense" };
const $ = (selector) => document.querySelector(selector);

function announce(message, isError = false) {
  const node = $("#status");
  node.textContent = message;
  node.style.background = isError ? "#7e1f1f" : "#10241c";
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-Session-Token", token);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  if (!response.ok) {
    let message = `操作失敗（${response.status}）`;
    try { message = (await response.json()).message || message; } catch (_) { /* safe fallback */ }
    throw new Error(message);
  }
  return response;
}

async function jsonApi(path, options = {}) {
  return (await api(path, options)).json();
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function lines(value) {
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

function fillGate1(caseData) {
  const form = $("#gate1-form");
  for (const key of ["people", "events", "times", "places", "objects", "behaviors", "unknowns"]) {
    form.elements[key].value = (caseData.gate1[key] || []).join("\n");
  }
  form.elements.causation.value = caseData.gate1.causation || "UNKNOWN";
}

function choice(id, name, suggested, selected) {
  const label = document.createElement("label");
  label.className = "choice";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.name = "offense";
  input.value = id;
  input.checked = selected;
  const span = document.createElement("span");
  span.textContent = suggested ? `${name}（候選）` : name;
  label.append(input, span);
  return label;
}

function renderOffenses(caseData) {
  const suggested = new Set(caseData.candidates.map((item) => item.id));
  const selected = new Set(caseData.selected_offenses);
  const container = $("#offense-list");
  const nodes = state.bank.offenses.map((item) => choice(item.id, item.name, suggested.has(item.id), selected.has(item.id)));
  container.replaceChildren(...nodes);
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
  container.replaceChildren(label, meta, textarea);
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
  $("#brief-preview").textContent = `100 字內摘要：${caseData.brief_summary}`;
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
    button.textContent = `${item.case_id.slice(0, 8)} · ${stateLabel(item.state)} · r${item.revision}`;
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

async function action(name, payload = {}) {
  if (!state.current) throw new Error("尚未選擇案件");
  const updated = await jsonApi(`/api/cases/${state.current.case_id}/actions`, {
    method: "POST",
    body: JSON.stringify({ action: name, revision: state.current.revision, payload }),
  });
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
    await action("analyze_candidates", {});
    announce("AI 分析完成。候選僅供人工選擇，不代表犯罪成立。 ");
  } catch (error) { announce(error.message, true); }
  finally {
    button.disabled = false;
    button.textContent = "AI 分析候選罪章";
  }
});

$("#offense-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const offenseIds = Array.from(document.querySelectorAll('input[name="offense"]:checked')).map((item) => item.value);
  if (!offenseIds.length) { announce("請至少選擇一個罪章。", true); return; }
  try {
    await action("set_offenses", { offense_ids: offenseIds, role: $("#question-role").value });
    setGate2Step("profile");
    announce("問句已建立。請填寫年籍與詢問時間。 ");
  } catch (error) { announce(error.message, true); }
});

$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = formObject(event.currentTarget);
  const fieldMap = {
    "profile-name": "name", "profile-alias": "alias", "profile-gender": "gender",
    "profile-birth-date": "birth_date", "profile-birth-place": "birth_place",
    "profile-occupation": "occupation", "profile-national-id": "national_id",
    "profile-registered-address": "registered_address", "profile-current-address": "current_address",
    "profile-education": "education", "profile-phone": "phone",
  };
  const profile = {};
  for (const [input, key] of Object.entries(fieldMap)) profile[key] = raw[input] || "";
  const session = {
    start_time: raw["session-start"] || "",
    end_time: raw["session-end"] || "",
    location: raw["session-location"] || "",
  };
  try {
    await action("save_profile", { role: state.current.question_role, profile, session });
    announce("年籍與詢問時間已加密保存。 ");
  } catch (error) { announce(error.message, true); }
});

$("#profile-to-qa").addEventListener("click", () => setGate2Step("qa"));

$("#step-tab-offense").addEventListener("click", () => setGate2Step("offense"));
$("#step-tab-profile").addEventListener("click", () => setGate2Step("profile"));
$("#step-tab-qa").addEventListener("click", () => setGate2Step("qa"));

$("#prev-question").addEventListener("click", () => stepQuestion(-1));
$("#next-question").addEventListener("click", () => stepQuestion(1));

$("#answers-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const answers = {};
  for (const question of state.current.questions) {
    answers[question.id] = question.answer || "";
  }
  try {
    await action("save_answers", { answers });
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
  for (const question of state.current.questions) answers[question.id] = question.answer || "";
  try {
    await action("save_answers", { answers });
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
    await refreshCases();
    announce("準備就緒。案件內容僅在 AI 罪章候選時送出摘要；問答內容不外傳。 ");
  } catch (error) { announce(error.message, true); }
}

initialize();

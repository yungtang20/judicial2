import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const appPath = join(__dirname, "..", "app", "static", "app.js");
const rawSource = readFileSync(appPath, "utf8");
const BOOTSTRAP_CALL = "initialize();";
if (!rawSource.includes(BOOTSTRAP_CALL)) {
  throw new Error(`找不到檔尾 bootstrap「${BOOTSTRAP_CALL}」，測試隔離失敗`);
}
const appSource = rawSource.replace(BOOTSTRAP_CALL, "/* initialize() disabled for test isolation */");

function createHarness({ fetchImpl }) {
  const fetchLog = [];
  const spyFetch = async (path, options = {}) => {
    const entry = { path, method: options.method || "GET", body: options.body || null };
    fetchLog.push(entry);
    return fetchImpl(path, options);
  };
  const elements = new Map();
  const makeElement = (id) => ({
    id,
    textContent: "",
    style: {},
    hidden: false,
    value: "",
    className: "",
    children: [],
    classList: { toggle() {}, add() {}, remove() {} },
    _handlers: {},
    addEventListener(type, handler) { this._handlers[type] = handler; },
    appendChild(node) { this.children.push(node); },
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children = [...nodes]; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
  });
  // Fill in the form.elements collection for gate1/profile forms
  const gate1FormFields = ["people", "events", "times", "places", "objects", "behaviors", "results", "evidence", "unknowns", "causation"];
  const profileFormFields = ["profile-name", "profile-alias", "profile-gender", "profile-birth-date", "profile-birth-place", "profile-occupation", "profile-national-id", "profile-registered-address", "profile-current-address", "profile-education", "profile-phone", "session-start", "session-end", "session-location"];
  const makeFormElements = (ids) => {
    const map = {};
    for (const id of ids) map[id] = makeElement(id);
    return map;
  };
  const formElements = {
    "gate1-form": makeFormElements(gate1FormFields),
    "profile-form": makeFormElements(profileFormFields),
  };
  const document = {
    querySelector(selector) {
      const id = selector.replace(/^#/, "");
      if (!elements.has(id)) {
        const el = makeElement(id);
        if (formElements[id]) el.elements = formElements[id];
        elements.set(id, el);
      }
      return elements.get(id);
    },
    querySelectorAll() { return []; },
    createElement(tag) { return makeElement(tag); },
    body: makeElement("body"),
  };
  const window = { scrollTo() {}, confirm: () => true };
  const context = vm.createContext({
    document,
    window,
    fetch: spyFetch,
    Headers,
    AbortController,
    URL,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    FormData: class { constructor() { this.entries = () => []; } },
    navigator: { clipboard: { writeText: async () => {} } },
    console,
  });
  vm.runInContext(appSource, context, { filename: "app.js" });
  return { context, elements, fetchLog };
}

function createConflictHarness({ postStatus = 409, postBody = {}, getImpl, listImpl, caseId = "case-abc-123", sentRevision = 1, latestRevision = 2 }) {
  const { context, elements, fetchLog } = createHarness({
    fetchImpl: async (path, options = {}) => {
      const method = options.method || "GET";
      if (method === "POST" && path === `/api/cases/${caseId}/actions`) {
        return {
          ok: false,
          status: postStatus,
          json: async () => postBody,
          headers: new Headers(),
        };
      }
      if (method === "GET" && path === `/api/cases/${caseId}` && getImpl) {
        return getImpl();
      }
      if (method === "GET" && path === "/api/cases" && listImpl) {
        return listImpl();
      }
      if (method === "GET" && path === "/api/cases") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ cases: [{ case_id: caseId, state: "GATE1_REVIEW", revision: latestRevision, has_offenses: false }] }),
          headers: new Headers(),
        };
      }
      if (method === "GET" && path === "/api/question-bank") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ offenses: [] }),
          headers: new Headers(),
        };
      }
      return { ok: true, status: 200, json: async () => ({}), headers: new Headers() };
    },
  });
  const stateRef = vm.runInContext("state", context);
  // 409 recovery flow goes through renderCase which requires state.bank.offenses
  stateRef.bank = { offenses: [] };
  stateRef.current = { case_id: caseId, revision: sentRevision, state: "GATE1_REVIEW", interviews: {}, profiles: {}, question_role: "victim", questions: [] };
  return { context, elements, fetchLog, caseId, sentRevision, latestRevision, stateRef };
}

test("逐題流程只包含追加問句並另列摘要已知內容", () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  const caseData = {
    questions: [
      { id: "known", text: "已知題", answer: "摘要答案", meta: { known_from_summary: true, known_answer: "摘要答案" } },
      { id: "additional", text: "追加題", answer: "", meta: {} },
    ],
  };
  const additional = context.additionalQuestions(caseData);
  assert.equal(additional.length, 1);
  assert.equal(additional[0].id, "additional");

  context.renderKnownQuestions(caseData);
  const summary = elements.get("known-question-summary");
  assert.equal(summary.hidden, false);
  assert.equal(summary.children.length, 2);
  assert.match(summary.children[0].textContent, /1 題已自動帶入/);
});

test("profile and answer saves describe the actual in-memory retention", async () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  vm.runInContext("state", context).current = {
    case_id: "case-id",
    revision: 1,
    question_role: "victim",
    questions: [],
  };
  vm.runInContext("renderCase = () => {};", context);

  const profileForm = elements.get("profile-form");
  await profileForm._handlers.submit({ preventDefault() {}, currentTarget: profileForm });
  assert.equal(elements.get("status").textContent, "年籍與詢問時間已暫存於本機服務記憶體。 ");

  await elements.get("answers-form")._handlers.submit({ preventDefault() {} });
  assert.equal(elements.get("status").textContent, "回答已暫存於本機服務記憶體。 ");
});

test("年籍 payload 使用 HTML name 欄位並保留詢問時間", () => {
  const { context } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  const payload = context.profilePayload({
    name: "測試受詢問人",
    national_id: "A123456789",
    education: "大學",
    session_start: "2026-10-14T14:00",
    session_end: "2026-10-14T15:00",
    session_location: "測試派出所",
  }, "victim");

  assert.equal(payload.role, "victim");
  assert.equal(payload.profile.name, "測試受詢問人");
  assert.equal(payload.profile.national_id, "A123456789");
  assert.equal(payload.profile.education, "大學");
  assert.deepEqual(
    JSON.parse(JSON.stringify(payload.session)),
    { start_time: "2026-10-14T14:00", end_time: "2026-10-14T15:00", location: "測試派出所" },
  );
});

test("500 JSON 安全訊息：UI 顯示 server message 而非 raw body", async () => {
  const { context, elements, fetchLog } = createHarness({
    fetchImpl: async () => ({
      ok: false,
      status: 500,
      json: async () => ({ error: "INTERNAL_ERROR", message: "本機服務無法完成操作" }),
      headers: new Headers(),
    }),
  });
  const api = context.api;
  let caught;
  try { await api("/api/test"); } catch (error) { caught = error; }
  assert.ok(caught, "api() 應拋出錯誤");
  assert.equal(caught.message, "本機服務無法完成操作");
  assert.equal(caught.status, 500);
  assert.equal(caught.code, "INTERNAL_ERROR");
  assert.equal(fetchLog.length, 1);
  assert.equal(fetchLog[0].path, "/api/test");
  context.announce(caught.message, true);
  assert.equal(elements.get("status").textContent, "本機服務無法完成操作");
});

test("500 非 JSON 含敏感 sentinel：UI 不出現 sentinel，只顯示安全預設訊息", async () => {
  const sentinel = "SECRET_CASE_DATA_12345";
  const { context, elements, fetchLog } = createHarness({
    fetchImpl: async () => ({
      ok: false,
      status: 500,
      json: async () => { throw new Error(sentinel); },
      headers: new Headers(),
    }),
  });
  const api = context.api;
  let caught;
  try { await api("/api/test"); } catch (error) { caught = error; }
  assert.ok(caught, "api() 應拋出錯誤");
  assert.equal(caught.message, "操作失敗（500）");
  assert.ok(!caught.message.includes(sentinel), "錯誤訊息不得包含 sentinel");
  assert.equal(fetchLog.length, 1);
  context.announce(caught.message, true);
  const uiText = elements.get("status").textContent;
  assert.equal(uiText, "操作失敗（500）");
  assert.ok(!uiText.includes(sentinel), "UI 不得出現 sentinel");
});

test("fetch reject：UI 顯示繁中斷線提示，不顯示瀏覽器英文錯誤或 stack", async () => {
  const { context, elements, fetchLog } = createHarness({
    fetchImpl: async () => { throw new TypeError("Failed to fetch"); },
  });
  const api = context.api;
  let caught;
  try { await api("/api/test"); } catch (error) { caught = error; }
  assert.ok(caught, "api() 應拋出錯誤");
  assert.equal(caught.code, "NETWORK_ERROR");
  assert.equal(caught.status, 0);
  assert.equal(caught.message, "無法連線到本機服務，請確認服務仍在執行。");
  assert.equal(fetchLog.length, 1);
  context.announce(caught.message, true);
  const uiText = elements.get("status").textContent;
  assert.equal(uiText, "無法連線到本機服務，請確認服務仍在執行。");
  assert.ok(!uiText.includes("Failed to fetch"), "UI 不得出現瀏覽器英文錯誤");
  assert.ok(!uiText.includes("TypeError"), "UI 不得出現 stack 類型");
});

test("409 JSON：保留 status 與 code，不實作 reload", async () => {
  const { context, fetchLog } = createHarness({
    fetchImpl: async () => ({
      ok: false,
      status: 409,
      json: async () => ({ error: "REVISION_CONFLICT", message: "案件已被其他操作修改" }),
      headers: new Headers(),
    }),
  });
  const api = context.api;
  let caught;
  try { await api("/api/test"); } catch (error) { caught = error; }
  assert.ok(caught, "api() 應拋出錯誤");
  assert.equal(caught.status, 409);
  assert.equal(caught.code, "REVISION_CONFLICT");
  assert.equal(caught.message, "案件已被其他操作修改");
  assert.equal(fetchLog.length, 1);
});

test("非字串 message/error 型別：使用安全預設訊息", async () => {
  const { context, fetchLog } = createHarness({
    fetchImpl: async () => ({
      ok: false,
      status: 400,
      json: async () => ({ error: 12345, message: null }),
      headers: new Headers(),
    }),
  });
  const api = context.api;
  let caught;
  try { await api("/api/test"); } catch (error) { caught = error; }
  assert.ok(caught, "api() 應拋出錯誤");
  assert.equal(caught.message, "操作失敗（400）");
  assert.equal(caught.code, null);
  assert.equal(fetchLog.length, 1);
});

test("409 → 單案 GET 成功：POST=1, GET=1, revision 更新, 顯示安全訊息", async () => {
  const fullCase = { case_id: "case-abc-123", revision: 2, state: "GATE1_REVIEW", interviews: {}, interview_sessions: {}, profiles: {}, question_role: "victim", gate1: { people: [], events: [], times: [], places: [], objects: [], behaviors: [], unknowns: [], causation: "UNKNOWN" }, candidates: [], selected_offenses: [], questions: [], case_numbers: { proof: "", women_child: "", case_165: "" }, brief_summary: "", intake: { has_victim: true, victim_is_code: false, victim_identifier: "" }, question_budget_warnings: [], candidate_contradictions: [], temporal_law_warnings: [] };
  const { context, elements, fetchLog, caseId, latestRevision, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => fullCase,
      headers: new Headers(),
    }),
  });
  let caught;
  try { await context.action("update_gate1", { gate1: {} }); } catch (e) { caught = e; }
  assert.ok(caught, "action() 應拋出 ApiError");
  assert.equal(caught.status, 409);
  assert.equal(stateRef.current.revision, latestRevision);
  const postCalls = fetchLog.filter((e) => e.method === "POST");
  const getCaseCalls = fetchLog.filter((e) => e.method === "GET" && e.path === `/api/cases/${caseId}`);
  assert.equal(postCalls.length, 1, "POST 次數必須為 1");
  assert.equal(getCaseCalls.length, 1, "單案 GET 次數必須為 1");
  assert.equal(elements.get("status").textContent, "案件已由其他分頁更新，已載入最新版本，請核對後重試。");
  const caseHeading = elements.get("case-heading");
  assert.ok(caseHeading, "case-heading 元素必須存在");
  assert.ok(caseHeading.textContent.includes(`revision ${latestRevision}`), "case-heading 必須顯示最新修訂版本");
});

test("409 → 單案 GET 500：POST=1, state 不變, 顯示無法回載訊息", async () => {
  const { context, elements, fetchLog, caseId, sentRevision, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: false,
      status: 500,
      json: async () => ({ error: "INTERNAL_ERROR", message: "SECRET_SERVER_ERROR_99999" }),
      headers: new Headers(),
    }),
  });
  let caught;
  try { await context.action("update_gate1", { gate1: {} }); } catch (e) { caught = e; }
  assert.ok(caught, "action() 應拋出 ApiError");
  assert.equal(stateRef.current.revision, sentRevision, "state.current 不得被部分資料覆寫");
  const postCalls = fetchLog.filter((e) => e.method === "POST");
  assert.equal(postCalls.length, 1, "POST 次數必須為 1");
  const uiText = elements.get("status").textContent;
  assert.equal(uiText, "偵測到案件版本衝突，但無法載入最新版本。請重新選取案件或重新整理後再試。");
  assert.ok(!uiText.includes("SECRET_SERVER_ERROR_99999"), "UI 不得出現 raw body sentinel");
});

test("409 → 單案 GET network error：POST=1, state 不變, 顯示無法回載訊息", async () => {
  const { context, elements, fetchLog, caseId, sentRevision, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => { throw new TypeError("Failed to fetch"); },
  });
  let caught;
  try { await context.action("update_gate1", { gate1: {} }); } catch (e) { caught = e; }
  assert.ok(caught, "action() 應拋出 ApiError");
  assert.equal(stateRef.current.revision, sentRevision, "state.current 不得被部分資料覆寫");
  const postCalls = fetchLog.filter((e) => e.method === "POST");
  assert.equal(postCalls.length, 1, "POST 次數必須為 1");
  const uiText = elements.get("status").textContent;
  assert.equal(uiText, "偵測到案件版本衝突，但無法載入最新版本。請重新選取案件或重新整理後再試。");
  assert.ok(!uiText.includes("Failed to fetch"), "UI 不得出現瀏覽器英文錯誤");
  assert.ok(!uiText.includes("TypeError"), "UI 不得出現 stack 類型");
});

test("409 回載期間切換案件：原案件不得覆蓋目前畫面", async () => {
  const { context, elements, fetchLog, caseId, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ case_id: caseId, revision: 99, state: "GATE1_REVIEW", interviews: {}, profiles: {}, question_role: "victim" }),
      headers: new Headers(),
    }),
  });
  const actionPromise = context.action("update_gate1", { gate1: {} });
  stateRef.current = { case_id: "other-case-xyz", revision: 5, state: "GATE2_QA", interviews: {}, profiles: {}, question_role: "suspect" };
  let caught;
  try { await actionPromise; } catch (e) { caught = e; }
  assert.ok(caught, "action() 應拋出 ApiError");
  assert.equal(stateRef.current.case_id, "other-case-xyz", "state.current 不得被舊案件覆蓋");
  assert.equal(stateRef.current.revision, 5, "state.current revision 不得被舊案件覆蓋");
  const caseHeading = elements.get("case-heading");
  if (caseHeading) {
    assert.ok(!caseHeading.textContent.includes("revision 99"), "原案件不得被 render 回目前畫面");
  } else {
    assert.ok(true, "當案件切換時 case-heading 不存在，原案件未被 render 回目前畫面");
  }
});

test("409 後使用者第二次明確操作：POST 總數為 1, 第二次使用新 revision", async () => {
  const { context, fetchLog, caseId, latestRevision } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ case_id: caseId, revision: latestRevision, state: "GATE1_REVIEW", interviews: {}, profiles: {}, question_role: "victim" }),
      headers: new Headers(),
    }),
  });
  try { await context.action("update_gate1", { gate1: {} }); } catch (e) { /* expected */ }
  const postCallsAfterFirst = fetchLog.filter((e) => e.method === "POST");
  assert.equal(postCallsAfterFirst.length, 1, "第一次 409 後 POST 總數必須為 1");
  const secondAction = context.action("approve_gate1", { confirmed: true });
  try { await secondAction; } catch (e) { /* expected */ }
  const postCallsAfterSecond = fetchLog.filter((e) => e.method === "POST");
  assert.equal(postCallsAfterSecond.length, 2, "第二次明確操作後 POST 總數為 2");
  const secondPost = postCallsAfterSecond[1];
  const secondBody = JSON.parse(secondPost.body);
  assert.equal(secondBody.revision, latestRevision, "第二次 POST 必須使用回載後的新 revision");
});

test("無案件清單模式：409 單案 GET 成功後保留最新案件", async () => {
  const fullCase = { case_id: "case-abc-123", revision: 2, state: "GATE1_REVIEW", interviews: {}, profiles: {}, question_role: "victim", gate1: { people: [], events: [], times: [], places: [], objects: [], behaviors: [], unknowns: [], causation: "UNKNOWN" }, candidates: [], selected_offenses: [], questions: [], case_numbers: { proof: "", women_child: "", case_165: "" }, brief_summary: "", intake: { has_victim: true, victim_is_code: false, victim_identifier: "" }, question_budget_warnings: [], candidate_contradictions: [], temporal_law_warnings: [] };
  const { context, elements, fetchLog, caseId, latestRevision, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => fullCase,
      headers: new Headers(),
    }),
    listImpl: async () => { throw new Error("list failed"); },
  });
  let caught;
  try { await context.action("update_gate1", { gate1: {} }); } catch (e) { caught = e; }
  assert.ok(caught, "action() 應拋出 ApiError");
  assert.equal(stateRef.current.revision, latestRevision, "最新案件必須保留");
  assert.equal(elements.get("status").textContent, "案件已由其他分頁更新，已載入最新版本，請核對後重試。");
  assert.equal(fetchLog.filter((entry) => entry.path === "/api/cases").length, 0, "不得讀取案件清單");
});

test("H: gate1-form submit handler 409 後不得顯示「Gate 1 已儲存」", async () => {
  const fullCase = { case_id: "case-abc-123", revision: 2, state: "GATE1_REVIEW", interviews: {}, interview_sessions: {}, profiles: {}, question_role: "victim", gate1: { people: [], events: [], times: [], places: [], objects: [], behaviors: [], unknowns: [], causation: "UNKNOWN" }, candidates: [], selected_offenses: [], questions: [], case_numbers: { proof: "", women_child: "", case_165: "" }, brief_summary: "", intake: { has_victim: true, victim_is_code: false, victim_identifier: "" }, question_budget_warnings: [], candidate_contradictions: [], temporal_law_warnings: [] };
  const { context, elements, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => fullCase,
      headers: new Headers(),
    }),
  });
  const form = elements.get("gate1-form");
  const handler = form._handlers["submit"];
  assert.ok(handler, "gate1-form 必須有 submit handler");
  await handler({ preventDefault() {} });
  const statusText = elements.get("status").textContent;
  assert.ok(!statusText.includes("Gate 1 已儲存"), "409 後不得顯示成功訊息");
  assert.ok(statusText.includes("已載入最新版本"), "應顯示安全訊息");
});

test("I: approve-gate1 click handler 409 後不得顯示「Gate 1 已確認」", async () => {
  const fullCase = { case_id: "case-abc-123", revision: 2, state: "GATE1_REVIEW", interviews: {}, interview_sessions: {}, profiles: {}, question_role: "victim", gate1: { people: [], events: [], times: [], places: [], objects: [], behaviors: [], unknowns: [], causation: "UNKNOWN" }, candidates: [], selected_offenses: [], questions: [], case_numbers: { proof: "", women_child: "", case_165: "" }, brief_summary: "", intake: { has_victim: true, victim_is_code: false, victim_identifier: "" }, question_budget_warnings: [], candidate_contradictions: [], temporal_law_warnings: [] };
  const { context, elements, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => fullCase,
      headers: new Headers(),
    }),
  });
  const button = elements.get("approve-gate1");
  const handler = button._handlers["click"];
  assert.ok(handler, "approve-gate1 必須有 click handler");
  await handler();
  const statusText = elements.get("status").textContent;
  assert.ok(!statusText.includes("Gate 1 已確認"), "409 後不得顯示成功訊息");
  assert.ok(statusText.includes("已載入最新版本"), "應顯示安全訊息");
});

test("J: 409 recovery 後 state.current.revision 更新為最新值", async () => {
  const { context, elements, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ case_id: "case-abc-123", revision: 2, state: "GATE1_REVIEW", interviews: {}, profiles: {}, question_role: "victim" }),
      headers: new Headers(),
    }),
  });
  try { await context.action("update_gate1", { gate1: {} }); } catch (e) { /* expected */ }
  assert.equal(stateRef.current.revision, 2, "state.current.revision 應更新為 2");
});

test("K: action() 在 409 recovery 後拋出 ApiError", async () => {
  const { context, elements, stateRef } = createConflictHarness({
    postStatus: 409,
    postBody: { error: "REVISION_CONFLICT", message: "案件版本衝突" },
    getImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => ({ case_id: "case-abc-123", revision: 2, state: "GATE1_REVIEW", interviews: {}, profiles: {}, question_role: "victim" }),
      headers: new Headers(),
    }),
  });
  let caught;
  try { await context.action("update_gate1", { gate1: {} }); } catch (e) { caught = e; }
  assert.ok(caught, "action() 應拋出錯誤");
  assert.equal(caught.status, 409, "錯誤狀態應為 409");
  assert.equal(caught.code, "REVISION_CONFLICT", "錯誤碼應為 REVISION_CONFLICT");
});

test("L: 條陳摘要標示 500 字且複製完整內容", async () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  const summary = "字".repeat(500);
  assert.ok(rawSource.includes("500 字內摘要"));
  context.document.querySelector("#brief-output").value = summary;
  let copied = "";
  context.navigator.clipboard.writeText = async (value) => { copied = value; };
  await elements.get("copy-brief")._handlers.click();
  assert.equal(copied, summary);
});

test("M: 法律路由選項只來自目前選取的罪章", () => {
  const { context } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  const bank = { offenses: [
    { id: "theft", legal_routes: [{ id: "theft_320_1_movable", name: "普通動產竊盜" }] },
    { id: "fraud", legal_routes: [{ id: "fraud_339_general", name: "普通詐欺" }] },
  ] };
  assert.deepEqual(
    JSON.parse(JSON.stringify(context.legalRoutesForOffenses(bank, ["theft"]))),
    [{ id: "theft_320_1_movable", name: "普通動產竊盜", parent_offense_id: "theft" }],
  );
});

test("N: Gate 2 依題目快照動態顯示 enum 選項", () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  const stateRef = vm.runInContext("state", context);
  const question = {
    id: "THF3201MOV-C02-V",
    text: "請說明物品原由何人控制。",
    kind: "distinguishing",
    answer: "",
    answer_code: "UNKNOWN",
    meta: {
      answer_map: {
        OTHER_PERSON_CONTROL: "OTHER_PERSON_CONTROL",
        SUSPECT_PREEXISTING_CONTROL: "SUSPECT_PREEXISTING_CONTROL",
        UNKNOWN: "UNKNOWN",
      },
      answer_labels: {
        OTHER_PERSON_CONTROL: "由他人控制",
        SUSPECT_PREEXISTING_CONTROL: "行為人原已控制",
        UNKNOWN: "UNKNOWN／無法確認",
      },
    },
  };
  const caseData = { questions: [question] };
  stateRef.current = caseData;
  context.renderCurrentQuestion(caseData);
  const select = elements.get("question-current").children.find((node) => node.id === "current-answer-code");
  assert.ok(select, "應建立中性事實狀態選單");
  assert.deepEqual(
    select.children.map((option) => [option.value, option.textContent]),
    [
      ["OTHER_PERSON_CONTROL", "由他人控制"],
      ["SUSPECT_PREEXISTING_CONTROL", "行為人原已控制"],
      ["UNKNOWN", "UNKNOWN／無法確認"],
    ],
  );
});

test("O: 問句畫面顯示中立提問方式與人工確認邊界", () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  const stateRef = vm.runInContext("state", context);
  const question = {
    id: "THF3201MOV-C02-V",
    text: "物品被移動前，你最後看見它由誰保管或使用？",
    kind: "distinguishing",
    answer: "",
    answer_code: "UNKNOWN",
    meta: {
      purpose: "區分競爭假設",
      question_phase: "single_fact",
      answer_map: { YES: "YES", NO: "NO", UNKNOWN: "UNKNOWN" },
    },
  };
  const caseData = { questions: [question] };
  stateRef.current = caseData;
  context.renderCurrentQuestion(caseData);
  const method = elements.get("question-current").children.find((node) => node.className === "meta question-method");
  assert.ok(method, "應顯示提問方式");
  assert.match(method.textContent, /區分競爭假設/);
  assert.match(method.textContent, /一次只確認一項事實/);
  assert.match(method.textContent, /不得把候選罪章當成已成立/);
});

test("P: Gate 2 候選分析顯示列入原因、欠缺要件、來源與三層級", () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}), headers: new Headers() }),
  });
  const stateRef = vm.runInContext("state", context);
  stateRef.bank = {
    offenses: [
      { id: "robbery", name: "搶奪／強盜／海盜" },
      { id: "theft", name: "竊盜" },
    ],
  };
  const candidate = {
    id: "robbery",
    name: "搶奪／強盜／海盜",
    selection_origin: "keyword_hint",
    candidate_eligibility: "ELIGIBLE_CANDIDATE",
    inclusion_reason: "案情摘要含有本罪章的關鍵詞：脅迫、搶走",
    source: { status: "VERIFIED_CURRENT", law_name: "中華民國刑法", article_no: "第328條" },
    route_element_matrix: [
      {
        route_id: "robbery_328_1_violence",
        route_name: "強盜（強暴脅迫至使不能抗拒）",
        supported_count: 2,
        total_count: 4,
        not_checkable_count: 1,
        elements: [
          { element: "強暴脅迫", status: "SOURCE_SUPPORTED", source_excerpts: ["甲持刀脅迫乙"] },
          { element: "至使不能抗拒", status: "ABSENT", source_excerpts: [] },
          { element: "不法所有意圖", status: "NOT_CHECKABLE", source_excerpts: [] },
        ],
      },
      {
        route_id: "robbery_330_1_aggravated",
        route_name: "加重強盜（兇器）",
        supported_count: 3,
        total_count: 4,
        not_checkable_count: 0,
        elements: [
          { element: "兇器", status: "SOURCE_SUPPORTED", source_excerpts: ["甲持刀"] },
        ],
      },
    ],
    unknown_elements: ["不法所有意圖"],
    contradicting_fact_refs: [],
  };
  const caseData = {
    candidates: [candidate],
    selected_offenses: ["robbery"],
    alternative_routes: [],
    question_role: "victim",
    candidates_source: "rules",
  };
  stateRef.current = caseData;
  context.renderOffenses(caseData);
  const analysis = elements.get("candidate-element-analysis");
  assert.ok(analysis, "應有候選分析區塊");
  assert.equal(analysis.hidden, false, "候選分析應顯示");
  const getText = (node) => {
    if (!node) return "";
    let text = node.textContent || "";
    for (const child of node.children || []) {
      text += "\n" + getText(child);
    }
    return text;
  };
  const text = analysis.children.map(getText).join("\n");
  assert.match(text, /主要候選/, "應標示主要候選");
  assert.match(text, /列入原因：案情摘要含有本罪章的關鍵詞：脅迫、搶走/, "應顯示列入原因");
  assert.match(text, /規則比對（法條已核實）/, "應顯示來源");
  assert.match(text, /中華民國刑法 第328條/, "應顯示法條名稱與條號");
  assert.match(text, /欠缺要件：不法所有意圖/, "應顯示欠缺要件");
  assert.match(text, /路由：強盜（強暴脅迫至使不能抗拒）/, "應顯示所有路由");
  assert.match(text, /路由：加重強盜（兇器）/, "應顯示第二條路由");
  assert.match(text, /候選不代表犯罪成立/, "應保留候選聲明");
});

test("Q: AI 分析逾時：顯示降級訊息並可重試一次，第二次逾時則禁用", async () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => {
      const err = new Error("aborted");
      err.name = "AbortError";
      throw err;
    },
  });
  const stateRef = vm.runInContext("state", context);
  stateRef.current = { case_id: "case-abc-123", revision: 1, state: "GATE2_QA" };
  stateRef.bank = { external_ai_enabled: true };

  const button = elements.get("ai-analyze");
  const handler = button._handlers["click"];
  assert.ok(handler, "應有 ai-analyze click handler");

  // 第一次點擊：逾時
  await handler();
  assert.match(elements.get("status").textContent, /外部 AI 分析逾時/);
  assert.match(button.textContent, /重試，尚剩 1 次/);

  // 第二次點擊：再次逾時，應禁用
  await handler();
  assert.match(button.textContent, /重試次數已用完/);
});

test("R: AI 分析成功：顯示請求 ID", async () => {
  const { context, elements } = createHarness({
    fetchImpl: async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        case_id: "case-abc-123",
        revision: 2,
        state: "GATE2_QA",
        candidates: [],
        selected_offenses: [],
        bank: { offenses: [] },
        gate1: {
          people: [], events: [], times: [], places: [], objects: [],
          behaviors: [], results: [], evidence: [], unknowns: [],
          causation: "UNKNOWN", facts: [],
        },
        intake: {},
        interviews: {},
        questions: [],
        preparation_mode: "MANUAL",
        case_numbers: { proof: "", women_child: "", case_165: "" },
      }),
      headers: new Headers({ "X-Request-ID": "req-abc123" }),
    }),
  });
  const stateRef = vm.runInContext("state", context);
  stateRef.current = { case_id: "case-abc-123", revision: 1, state: "GATE2_QA" };
  stateRef.bank = { external_ai_enabled: true, offenses: [] };

  const button = elements.get("ai-analyze");
  const handler = button._handlers["click"];
  await handler();
  assert.match(elements.get("status").textContent, /req-abc123/);
  assert.match(elements.get("status").textContent, /不代表犯罪成立/);
});

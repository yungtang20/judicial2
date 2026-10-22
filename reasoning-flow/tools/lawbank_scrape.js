// 法源抓取器 v2（M2）：法條 / 判解要旨 / 行政函釋要旨 / 論著
// 憑證與 session 由環境變數提供，不落檔。
const { chromium } = require(process.env.PW_PATH);
const fs = require("fs");
const RAW_DIR = process.env.RAW_DIR || require("path").join(__dirname, "..", "raw");
const STATE_FILE = process.env.LB_STATE || require("path").join(RAW_DIR, "lb_state.json");
const RAW_FILE = process.env.LB_RAW || require("path").join(RAW_DIR, "lb_raw.json");
const JOB_FILE = process.env.LB_JOB || require("path").join(__dirname, "lawbank_job.json");
fs.mkdirSync(RAW_DIR, { recursive: true });

const DB = "https://db.lawbank.com.tw";
const DELAY = 1400;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------- 法條 ---------- */
async function fetchStatute(page, lsid, lno) {
  await page.goto(DB + "/FLAW/FLAWDOC01.aspx?lsid=" + lsid + "&lno=" + lno, {
    waitUntil: "domcontentloaded", timeout: 60000,
  });
  await page.waitForTimeout(1500);
  return page.evaluate(() => {
    // 條文正文：單段條文用 div.law-article；多段條文用多個 div.line-* / div.show-number
    let paras = Array.from(document.querySelectorAll("div.show-number"))
      .map((d) => d.innerText.replace(/\s+/g, " ").trim())
      .filter((t) => t && t.length > 4 && !/^\d+\/\d+$/.test(t));
    if (!paras.length) {
      const single = document.querySelector("div.law-article");
      if (single) {
        const t = single.innerText.replace(/\s+/g, " ").trim();
        if (t && t.length > 4) paras = [t];
      }
    }
    const meta = {};
    document.querySelectorAll("td,span,div").forEach((el) => {
      const t = (el.innerText || "").trim();
      if (/^法規名稱：/.test(t)) meta.law_name = t.replace(/^法規名稱：/, "").trim();
      if (/^修正日期：/.test(t)) meta.amended = t.replace(/^修正日期：/, "").trim();
      if (/^主管機關：/.test(t)) meta.authority = t.replace(/^主管機關：/, "").trim();
    });
    const relCounts = {};
    document.querySelectorAll("input[name='cbType']").forEach((cb) => {
      const v = cb.value || "";
      const m = v.match(/^([A-Z])(\d*)`(\d+)`(.+)$/);
      if (m) relCounts[m[4].trim()] = parseInt(m[3], 10);
    });
    return {
      url: location.href,
      title: document.title,
      meta,
      article_paragraphs: paras,
      article_text: paras.join(""),
      related_counts: relCounts,
    };
  });
}

/* ---------- 判解 ---------- */
function extractFjRows() {
  const tbl = document.querySelector("table.JudgeNoun-Results-List");
  const rows = [];
  if (!tbl) return { rows, count: null };
  tbl.querySelectorAll("tr.line").forEach((tr) => {
    const tds = tr.querySelectorAll("td");
    if (tds.length < 2) return;
    const cell = tds[1];
    const a = cell.querySelector("a[href*='judcontent']");
    const summary = cell.querySelector("div.summary");
    const mark = cell.querySelector(".markarea");
    // 要旨關鍵段：<em> 標記者為法源標示之要旨核心
    const keyParts = summary
      ? Array.from(summary.querySelectorAll("em")).map((e) => e.innerText.trim()).filter(Boolean)
      : [];
    const raw = summary ? summary.innerText.trim() : null;
    // 去掉尾端截斷記號
    const clean = raw ? raw.replace(/…+$/, "").replace(/\.\.\.$/, "") : null;
    // 引用數
    let cited = null;
    cell.querySelectorAll("div").forEach((d) => {
      const t = d.innerText || "";
      const m = t.match(/被引用數：\s*(\d+)\s*次/);
      if (m) cited = parseInt(m[1], 10);
    });
    rows.push({
      case_ref: a ? a.getAttribute("data-title") : null,
      case_ref_text: a ? a.innerText.replace(/\s+/g, " ").trim() : null,
      case_link: a ? a.href : null,
      status: mark ? mark.innerText.replace(/\s+/g, " ").trim() : null,
      holding_snippet: clean,
      holding_key: keyParts,
      cited_count: cited,
    });
  });
  return { rows, count: tbl.innerText.split("\n")[0].trim() };
}

async function fjSearch(page, kw, maxPages = 1) {
  await page.goto(DB + "/FJ/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1200);
  await page.fill("#kw", kw);
  await page.waitForTimeout(250);
  await Promise.all([
    page.waitForLoadState("domcontentloaded", { timeout: 60000 }).catch(() => {}),
    page.click("#butSubmit"),
  ]);
  await page.waitForTimeout(2200);

  const first = await page.evaluate(extractFjRows);
  const out = { keyword: kw, count_text: first.count, rows: first.rows };
  if (!first.rows.length) {
    // 關鍵字無結果：改試單詞
    out.note = "no_result";
  }

  const nextHref = await page.evaluate(() => {
    const a = Array.from(document.querySelectorAll("a")).find((x) => (x.innerText || "").trim() === "下一頁");
    return a ? a.getAttribute("href") : null;
  });

  let href = nextHref;
  for (let p = 2; p <= maxPages && href; p++) {
    await page.goto(new URL(href, DB + "/FJ/").href, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1500);
    const part = await page.evaluate(extractFjRows);
    out.rows = out.rows.concat(part.rows);
    href = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll("a")).find((x) => (x.innerText || "").trim() === "下一頁");
      return a ? a.getAttribute("href") : null;
    });
    await sleep(DELAY);
  }
  return out;
}

/* ---------- 行政函釋 ---------- */
function extractFintRows() {
  const rows = [];
  const trs = Array.from(document.querySelectorAll("table.Onebar-Results-List tr"));
  for (let i = 0; i < trs.length; i++) {
    const tr = trs[i];
    if (!/line/.test(tr.className || "")) continue;
    const cells = tr.querySelectorAll("td");
    const docNo = (cells[2] ? cells[2].innerText : tr.innerText).replace(/\s+/g, " ").trim();
    const a = tr.querySelector("a[href]");
    // 後續列：發文日期列、要旨列（id=trData）
    let docDate = null, holding = null, link = a ? a.href : null;
    for (let j = i + 1; j < Math.min(i + 4, trs.length); j++) {
      const c = trs[j].querySelectorAll("td");
      const t = (trs[j].innerText || "").replace(/\s+/g, " ").trim();
      if (/^發文日期/.test(t) && c.length >= 3) docDate = c[2].innerText.replace(/\s+/g, " ").trim();
      if (/^要\s*旨/.test(t) && c.length >= 3) {
        holding = c[2].innerText.replace(/\s+/g, " ").trim();
        if (!link) { const a2 = trs[j].querySelector("a[href]"); if (a2) link = a2.href; }
        break;
      }
    }
    rows.push({ doc_no: docNo, doc_date: docDate, holding: holding, link: link });
  }
  return rows;
}

async function fintSearch(page, kw, maxPages = 1) {
  await page.goto(DB + "/FINT/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1200);
  await page.fill("#kw", kw);
  await page.waitForTimeout(250);
  await Promise.all([
    page.waitForLoadState("domcontentloaded", { timeout: 60000 }).catch(() => {}),
    page.click("#butSubmit"),
  ]);
  await page.waitForTimeout(2200);
  const first = await page.evaluate(extractFintRows);
  const out = { keyword: kw, rows: first };
  const nextHref = await page.evaluate(() => {
    const a = Array.from(document.querySelectorAll("a")).find((x) => (x.innerText || "").trim() === "下一頁");
    return a ? a.getAttribute("href") : null;
  });
  let href = nextHref;
  for (let p = 2; p <= maxPages && href; p++) {
    await page.goto(new URL(href, DB + "/FINT/").href, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1500);
    const part = await page.evaluate(extractFintRows);
    out.rows = out.rows.concat(part);
    href = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll("a")).find((x) => (x.innerText || "").trim() === "下一頁");
      return a ? a.getAttribute("href") : null;
    });
    await sleep(DELAY);
  }
  return out;
}

/* ---------- 論著 ---------- */
async function treatiseSearch(page, kw, maxPages = 1) {
  await page.goto("https://www.lawbank.com.tw/treatise/query.aspx", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1600);
  await page.fill("#ctl00_cphMain_txtKeyword0", kw);
  await page.waitForTimeout(250);
  // 以 ASP.NET __doPostBack 提交（<a> 元素觸發 WebForm_DoPostBackWithOptions）
  const navPromise = page.waitForNavigation({ timeout: 45000, waitUntil: "domcontentloaded" }).catch(() => null);
  await page.evaluate(() => {
    const a = document.querySelector("#ctl00_cphMain_butSubmit");
    if (!a) return;
    const oc = a.getAttribute("onclick") || "";
    const m = oc.match(/__doPostBack\('([^']+)'/);
    if (m && typeof window.__doPostBack === "function") {
      window.__doPostBack(m[1], "");
    } else {
      a.click();
    }
  });
  await navPromise;
  await page.waitForLoadState("domcontentloaded").catch(() => {});
  await page.waitForTimeout(3000);

  const parse = () => {
    const rows = [];
    // 結果列表：每筆為一個 li/div，含標題連結、作者譯者、出版日期
    const anchors = Array.from(document.querySelectorAll("a[href*='pl_article'],a[href*='dt_article']"));
    const seen = new Set();
    anchors.forEach((a) => {
      const title = (a.innerText || "").replace(/\s+/g, " ").trim();
      if (!title || seen.has(a.href)) return;
      seen.add(a.href);
      // 往上找包含作者/日期的父容器
      let container = a;
      for (let k = 0; k < 4 && container.parentElement; k++) {
        container = container.parentElement;
        const t = container.innerText || "";
        if (/作者譯者|出版日期/.test(t)) break;
      }
      const txt = (container.innerText || "").replace(/\s+/g, " ");
      const author = (txt.match(/作者譯者：\s*([^\s]+(?:\s+[^\s]+)?)/) || [])[1] || null;
      const pubdate = (txt.match(/出版日期：\s*([\d.]+)/) || [])[1] || null;
      const hasFull = /有全文/.test(txt) ? /^\s*\d+\.\s*有全文/.test(txt) : null;
      rows.push({ title, author, pub_date: pubdate, has_full: hasFull, link: a.href });
    });
    const count = (document.body.innerText || "").match(/共\s*([\d,]+)\s*筆/);
    return { rows, count: count ? parseInt(count[1].replace(/,/g, ""), 10) : null };
  };

  const first = await page.evaluate(parse);
  const out = { keyword: kw, count: first.count, rows: first.rows };
  const nextHref = await page.evaluate(() => {
    const a = Array.from(document.querySelectorAll("a")).find((x) => (x.innerText || "").trim() === "下一頁");
    return a ? a.getAttribute("href") : null;
  });
  let href = nextHref;
  for (let p = 2; p <= maxPages && href; p++) {
    await page.goto(new URL(href, "https://www.lawbank.com.tw/treatise/").href, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1600);
    const part = await page.evaluate(parse);
    out.rows = out.rows.concat(part.rows);
    href = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll("a")).find((x) => (x.innerText || "").trim() === "下一頁");
      return a ? a.getAttribute("href") : null;
    });
    await sleep(DELAY);
  }
  return out;
}

/* ---------- 主流程 ---------- */
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ["--no-sandbox"] });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "zh-TW",
    storageState: STATE_FILE,
  });
  const page = await ctx.newPage();

  const JOB = JSON.parse(fs.readFileSync(JOB_FILE, "utf8"));
  const raw = {
    fetched_at: new Date().toISOString(),
    source: "lawbank.com.tw",
    statutes: [], judgments: [], interpretations: [], treatises: [],
  };

  for (const s of JOB.statutes) {
    const r = await fetchStatute(page, s.lsid, s.lno);
    Object.assign(r, { lsid: s.lsid, lno: s.lno, tag: s.tag });
    raw.statutes.push(r);
    console.log("[statute]", s.lno, s.tag, "| paras:", r.article_paragraphs.length, "| len:", r.article_text.length);
    await sleep(DELAY);
  }

  for (const j of JOB.judgment_keywords) {
    const r = await fjSearch(page, j.kw, j.pages || 1);
    r.tag = j.tag;
    raw.judgments.push(r);
    console.log("[judgment]", j.kw, "->", r.rows.length, "rows |", r.count_text);
    await sleep(DELAY);
  }

  for (const f of JOB.interpretation_keywords) {
    try {
      const r = await fintSearch(page, f.kw, f.pages || 1);
      r.tag = f.tag;
      raw.interpretations.push(r);
      console.log("[fint]", f.kw, "->", r.rows.length, "rows");
    } catch (e) {
      raw.interpretations.push({ keyword: f.kw, tag: f.tag, rows: [], error: e.message });
      console.log("[fint]", f.kw, "-> ERROR", e.message);
    }
    await sleep(DELAY);
  }

  for (const t of JOB.treatise_keywords || []) {
    try {
      const r = await treatiseSearch(page, t.kw, t.pages || 1);
      r.tag = t.tag;
      raw.treatises.push(r);
      console.log("[treatise]", t.kw, "->", r.rows.length, "rows | count:", r.count);
    } catch (e) {
      raw.treatises.push({ keyword: t.kw, tag: t.tag, rows: [], error: e.message });
      console.log("[treatise]", t.kw, "-> ERROR", e.message);
    }
    await sleep(DELAY);
  }

  fs.writeFileSync(RAW_FILE, JSON.stringify(raw, null, 2), "utf8");
  console.log("WROTE", RAW_FILE);
  await browser.close();
})().catch((e) => { console.error("ERR", e.message, e.stack); process.exit(2); });

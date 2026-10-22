// M1 原型煙霧測試（Node + playwright-core，自帶本機伺服器）
// 驗證：模板選擇切換、表單動態生成、輸出組裝與 templates.json 規則一致、無 JS 錯誤。
const path = require("path");
const { spawn } = require("child_process");
const { chromium } = require(process.env.PW_PATH);

const PKG = path.join(__dirname, "..");
const PORT = process.env.PORT || "8794";
const BASE = process.env.BASE_URL || `http://127.0.0.1:${PORT}/prototype/`;

(async () => {
  const server = spawn("py", ["-3", "-m", "http.server", String(PORT), "--bind", "127.0.0.1", "--directory", PKG], {
    stdio: "ignore",
  });
  await new Promise((r) => setTimeout(r, 1600));

  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

  await page.goto(BASE, { waitUntil: "networkidle" });

  const out = { errors: [], steps: [] };
  out.steps.push({
    step: "初始載入",
    bootVisible: await page.locator("#boot").isVisible(),
    appVisible: await page.locator("#app").isVisible(),
    hit: (await page.locator("#hit").innerText()).trim(),
  });

  // 切換三個開關，確認能切到三種模板
  const cases = [
    { has_victim: "true", is_solved: "false", subject_identified: "true", expect: "被害人條陳" },
    { has_victim: "true", is_solved: "true", subject_identified: "true", expect: "涉嫌人條陳，有被害人版" },
    { has_victim: "false", is_solved: "true", subject_identified: "true", expect: "涉嫌人條陳，無被害人版" },
  ];
  for (const c of cases) {
    await page.selectOption('select[data-key="has_victim"]', c.has_victim);
    await page.selectOption('select[data-key="is_solved"]', c.is_solved);
    await page.selectOption('select[data-key="subject_identified"]', c.subject_identified);
    const hit = (await page.locator("#hit").innerText()).trim();
    const preview = await page.locator("#preview").innerText();
    const labels = await page.locator("#form .fl").allInnerTexts();
    // 免責註記（規劃書第六章要求自動加註）不列入斷定語檢查
    const body = preview.split("模擬填充，不構成正式文書。")[0];
    out.steps.push({
      step: c.expect,
      hit,
      hitOk: hit.includes(c.expect),
      firstFieldLabels: labels.slice(0, 3).map((s) => s.split("\n")[0].trim()),
      previewHead: preview.split("\n").slice(0, 4),
      previewHasTodo: preview.includes("（待補）"),
      previewHasFooter: preview.includes("模擬填充，不構成正式文書。"),
      previewNoVerdict: !/(犯罪成立|構成要件|應論以|該當)/.test(body),
    });
  }

  // 無對應模板的情境
  await page.selectOption('select[data-key="has_victim"]', "true");
  await page.selectOption('select[data-key="is_solved"]', "true");
  await page.selectOption('select[data-key="subject_identified"]', "false");
  out.steps.push({
    step: "已破獲但主體未特定",
    hit: (await page.locator("#hit").innerText()).trim(),
    preview: (await page.locator("#preview").innerText()).trim(),
  });

  // 回到模板一，填值並檢查輸出
  await page.selectOption('select[data-key="has_victim"]', "true");
  await page.selectOption('select[data-key="is_solved"]', "false");
  await page.selectOption('select[data-key="subject_identified"]', "true");
  await page.fill('[data-field="case_reason"]', "被害人於超商遭人持刀威脅並取走財物（候選）");
  await page.fill('[data-field="occurred_time"]', "114年5月1日21時30分");
  await page.fill('[data-field="occurred_location"]', "○○市○○區○○路○○號");
  await page.fill('[data-field="report_time"]', "114年5月1日22時10分");
  await page.fill('[data-field="case_summary"]', "114年5月1日21時30分，遭男子持刀威脅，交付現金後對方離去。");
  await page.fill('[data-field="jurisdiction"]', "本所轄區");
  await page.fill('[data-field="handling_officer"]', "王小明");
  const filled = await page.locator("#preview").innerText();
  out.steps.push({
    step: "填值輸出",
    preview: filled,
    todoGone: !filled.includes("（待補）"),
    keepsFixed: filled.includes("（三）處理員警：警員 王小明。"),
    keepsCaseNumber: filled.includes("165案號：)"),
    reasonHasStatute: /第\s*\d+\s*條/.test(filled),
  });

  // 下載 .txt 內容檢查
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#btnDl"),
  ]);
  const dlPath = await download.path();
  const fs = require("fs");
  const dlText = fs.readFileSync(dlPath, "utf8");
  out.download = {
    filename: download.suggestedFilename(),
    hasFooter: dlText.includes("模擬填充，不構成正式文書。"),
    hasCandidateNotice: dlText.includes("所有罪名均為候選，不認定犯罪成立。"),
    bom: dlText.charCodeAt(0) === 0xfeff,
  };

  out.errors = errors;
  const json = JSON.stringify(out, null, 2);
  if (process.env.OUT_FILE) {
    require("fs").writeFileSync(process.env.OUT_FILE, json, "utf8");
    console.log("written: " + process.env.OUT_FILE);
  } else {
    console.log(json);
  }
  await browser.close();
  server.kill();
  process.exit(errors.length ? 1 : 0);
})().catch((e) => {
  console.error("FAIL", e);
  process.exit(2);
});

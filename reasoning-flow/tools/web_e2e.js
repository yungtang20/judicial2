// M6 Web 端到端測試：以瀏覽器操作完整工作台
// 事實輸入 → 分析 → 候選路徑 → 缺口 → 問句清單 → 條陳填充 → 匯出
// 用法：
//   node tools/web_e2e.js
// 需先啟動本機 HTTP 伺服器（tools/web_e2e.js 會自行啟動並於結束時關閉）
const { chromium } = require(process.env.PW_PATH);
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const PKG = path.join(__dirname, "..");
const PORT = process.env.PORT || "8795";
const BASE = `http://127.0.0.1:${PORT}/web/`;

const results = [];
function check(ok, name, detail = "") {
  results.push({ ok: !!ok, name, detail });
  console.log((ok ? "  [OK] " : "  [FAIL] ") + name + (ok ? "" : "  → " + detail));
}

(async () => {
  // 啟動本機伺服器
  const server = spawn("py", ["-3", "-m", "http.server", PORT, "--bind", "127.0.0.1", "--directory", PKG], {
    stdio: "ignore",
  });
  await new Promise((r) => setTimeout(r, 1800));

  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH,
    args: ["--no-sandbox"],
  });
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 }, locale: "zh-TW" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

  try {
    await page.goto(BASE, { waitUntil: "networkidle", timeout: 60000 });
    check(errors.length === 0, "載入頁面無 console 錯誤", errors.join(" | "));

    // 資料分頁已載入
    await page.click('.tab[data-tab="data"]');
    await page.waitForTimeout(300);
    const flowText = await page.locator("#flowBox").innerText();
    check(flowText.includes("推理路徑"), "資料分頁顯示法源推理流程");
    const rulesText = await page.locator("#rulesBox").innerText();
    check(rulesText.includes("rule_id"), "資料分頁顯示問句規則");
    await page.click('.tab[data-tab="work"]');
    await page.waitForTimeout(200);

    // 載入範例並分析
    await page.click("#btnExample");
    await page.waitForTimeout(900);
    const candText = await page.locator("#candBox").innerText();
    check(candText.includes("候選路徑"), "產出候選路徑", candText.slice(0, 80));
    check(/§\d/.test(candText), "候選路徑含條號");

    const gapText = await page.locator("#gapBox").innerText();
    check(gapText.length > 20, "產出缺口清單");

    const qText = await page.locator("#qBox").innerText();
    check(qText.includes("對相對人"), "問句清單含對相對人");
    check(qText.includes("對行為人"), "問句清單含對行為人");

    const fillText = await page.locator("#fillBox").innerText();
    check(fillText.includes("受理案由"), "條陳表單含受理案由欄位");

    const preview = await page.locator("#preview").innerText();
    check(preview.startsWith("被害人條陳"), "預覽以模板標題起始", preview.slice(0, 20));
    check(preview.includes("模擬填充，不構成正式文書。"), "預覽含免責註記");
    check(preview.includes("所有罪名均為候選，不認定犯罪成立。"), "預覽含候選聲明");
    // 斷定語檢查：排除規劃書明文要求之免責語
    const scanText = preview.replace("不認定犯罪成立。", "").replace("所有罪名均為候選，", "");
    check(!/(犯罪成立|構成要件|應論以|該當)/.test(scanText), "預覽無斷定語");

    // 順序檢查：條陳各項順序與 條陳.txt 原文一致
    const order = await page.evaluate(async () => {
      const t = await fetch("../data/templates.json").then((r) => r.json());
      const tv = t.templates.find((x) => x.template_id === "victim_report");
      const fixed = [];
      tv.sections.forEach((s) => s.fields.forEach((f) => { if (f.fixed_text) fixed.push(f.fixed_text.trim()); }));
      const prev = document.querySelector("#preview").textContent;
      return fixed.map((f) => prev.indexOf(f));
    });
    check(order.every((p) => p >= 0) && order.every((p, i) => i === 0 || p > order[i - 1]),
      "條陳順序與 templates.json 原序一致（順序不可變）", JSON.stringify(order));

    // 手動覆寫欄位
    await page.fill('[data-fill="occurred_location"]', "Manual 覆寫之地點");
    await page.waitForTimeout(250);
    const preview2 = await page.locator("#preview").innerText();
    check(preview2.includes("Manual 覆寫之地點"), "手動覆寫反映於預覽");

    // 切換模板
    await page.selectOption("#tplSel", "suspect_no_victim");
    await page.waitForTimeout(400);
    const preview3 = await page.locator("#preview").innerText();
    check(preview3.startsWith("涉嫌人條陳，無被害人版"), "切換模板後預覽隨之更新", preview3.slice(0, 24));
    const fillText2 = await page.locator("#fillBox").innerText();
    check(fillText2.includes("查獲案由"), "切換模板後欄位隨之更新（查獲案由）");

    // 指代不明情境 → 主體不明警示
    await page.selectOption("#tplSel", "victim_report");
    await page.fill("#facts", "他跟對方說了一些話，好像是要搶東西的事，對方嚇得不敢動，後來好像就走了，東西也不曉得去哪裡。");
    await page.click("#btnAnalyze");
    await page.waitForTimeout(800);
    const warnText = await page.locator("#warnBox").innerText();
    check(warnText.includes("主體不明警示"), "指代不明時出現【主體不明警示】", warnText.slice(0, 80));
    const fillText3 = await page.locator("#fillBox").innerText();
    check(fillText3.includes("主體待確認"), "主體不明時欄位標（主體待確認）");
    const preview4 = await page.locator("#preview").innerText();
    check(preview4.includes("（主體待確認）"), "預覽含（主體待確認）標記");

    // 下載
    const [download] = await Promise.all([page.waitForEvent("download"), page.click("#btnDl")]);
    const dlPath = await download.path();
    const dlText = fs.readFileSync(dlPath, "utf8");
    check(dlText.includes("模擬填充，不構成正式文書。"), "下載檔含免責註記");
    check(dlText.charCodeAt(0) === 0xfeff, "下載檔含 UTF-8 BOM");

    check(errors.length === 0, "全程無 console 錯誤", errors.join(" | "));
  } catch (e) {
    check(false, "測試執行", e.message);
  } finally {
    await browser.close();
    server.kill();
  }

  const failed = results.filter((r) => !r.ok);
  console.log("-".repeat(60));
  console.log(`檢查項目：${results.length}　通過：${results.length - failed.length}　失敗：${failed.length}`);
  process.exit(failed.length ? 1 : 0);
})();

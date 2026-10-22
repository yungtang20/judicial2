// M7 Web 端 LLM 測試：於瀏覽器中按「LLM 分析」，驗證端點、輸出校驗與退回機制。
// 用法：node tools/web_llm_e2e.js
const { chromium } = require(process.env.PW_PATH);
const { spawn } = require("child_process");
const path = require("path");

const PKG = path.join(__dirname, "..");
const PORT = process.env.PORT || "8798";
const results = [];
function check(ok, name, detail = "") {
  results.push({ ok: !!ok, name, detail });
  console.log((ok ? "  [OK] " : "  [FAIL] ") + name + (ok ? "" : "  → " + detail));
}

(async () => {
  const server = spawn("py", ["-3", path.join(__dirname, "serve.py"), String(PORT)], { stdio: "ignore" });
  await new Promise((r) => setTimeout(r, 2200));

  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 }, locale: "zh-TW" });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

  try {
    await page.goto(`http://127.0.0.1:${PORT}/web/`, { waitUntil: "networkidle", timeout: 60000 });
    check(errors.length === 0, "載入頁面無 console 錯誤", errors.join(" | "));

    // 規則版先行
    await page.click("#btnExample");
    await page.waitForTimeout(900);
    check((await page.locator("#analyzeStatus").innerText()).includes("規則版"), "規則版分析完成");

    // LLM 版
    await page.click("#btnLlm");
    await page.waitForFunction(
      () => !document.querySelector("#btnLlm").disabled,
      null,
      { timeout: 300000 }
    );
    await page.waitForTimeout(800);
    const status = await page.locator("#analyzeStatus").innerText();
    const warn = await page.locator("#warnBox").innerText();
    check(
      /LLM 分析完成|已退回規則版/.test(status),
      "LLM 分析按鈕完成（成功或退回）",
      status
    );
    const usedLLM = status.includes("LLM 分析完成");
    if (usedLLM) {
      check(warn.includes("LLM 語意判讀"), "採 LLM 結果時有明確標示");
      const gapText = await page.locator("#gapBox").innerText();
      check(gapText.includes("g"), "LLM 缺口清單已產出");
      const qText = await page.locator("#qBox").innerText();
      check(qText.includes("對相對人"), "LLM 缺口已產生問句");
      const preview = await page.locator("#preview").innerText();
      check(preview.includes("模擬填充，不構成正式文書。"), "LLM 版預覽含免責註記");
    } else {
      check(warn.includes("退回規則版"), "退回時有明確說明", warn.slice(0, 120));
    }
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

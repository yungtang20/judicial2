// M6 工作台截圖存證
const { chromium } = require(process.env.PW_PATH);
const { spawn } = require("child_process");
const path = require("path");

const PKG = path.join(__dirname, "..");
const PORT = process.env.PORT || "8796";
const SHOTS = path.join(PKG, "docs", "screenshots");

(async () => {
  const server = spawn("py", ["-3", "-m", "http.server", PORT, "--bind", "127.0.0.1", "--directory", PKG], { stdio: "ignore" });
  await new Promise((r) => setTimeout(r, 1800));
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  await page.goto(`http://127.0.0.1:${PORT}/web/`, { waitUntil: "networkidle" });
  await page.click("#btnExample");
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SHOTS, "m6_workbench.png"), fullPage: true });
  await page.click('.tab[data-tab="data"]');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, "m6_data_rules.png"), fullPage: true });
  await browser.close();
  server.kill();
  console.log("screenshots done");
})();

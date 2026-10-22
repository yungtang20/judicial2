// 法源登入：取得 session 存檔，供 lawbank_scrape.js 重用。
// 憑證僅由環境變數傳入（LB_USER / LB_PASS），不寫入任何檔案。
// session 存於 raw/lb_state.json（該目錄已在 .gitignore 中）。
const { chromium } = require(process.env.PW_PATH);
const fs = require("fs");
const path = require("path");

const RAW_DIR = process.env.RAW_DIR || path.join(__dirname, "..", "raw");
const STATE_FILE = process.env.LB_STATE || path.join(RAW_DIR, "lb_state.json");

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH,
    args: ["--no-sandbox"],
  });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "zh-TW",
  });
  const page = await ctx.newPage();

  await page.goto("https://www.lawbank.com.tw/member/MemLogin.aspx", {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(1200);
  await page.fill("#ctl00_cphMain_txtLoginID", process.env.LB_USER);
  await page.fill("#ctl00_cphMain_txtPWD", process.env.LB_PASS);
  await Promise.all([
    page.waitForLoadState("domcontentloaded", { timeout: 60000 }).catch(() => {}),
    page.click("#ctl00_cphMain_butLogin"),
  ]);
  await page.waitForTimeout(2500);

  const info = await page.evaluate(() => ({
    url: location.href,
    title: document.title,
    stillHasPasswordField: !!document.querySelector("#ctl00_cphMain_txtPWD"),
  }));
  fs.mkdirSync(RAW_DIR, { recursive: true });
  await ctx.storageState({ path: STATE_FILE });

  const ok = !info.stillHasPasswordField && /index\.aspx/.test(info.url);
  console.log("登入結果:", ok ? "成功" : "失敗", "| url:", info.url);
  console.log("session 已存:", STATE_FILE);
  await browser.close();
  process.exit(ok ? 0 : 1);
})().catch((e) => {
  console.error("ERR", e.message);
  process.exit(2);
});

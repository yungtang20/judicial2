// M1 原型截圖存證
const { chromium } = require(process.env.PW_PATH);
const BASE = process.env.BASE_URL || "http://127.0.0.1:8791/prototype/";
const OUT = process.env.SHOT_DIR || ".";

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.fill('[data-field="case_reason"]', "被害人於超商遭人持刀威脅並取走財物（候選）");
  await page.fill('[data-field="occurred_time"]', "114年5月1日21時30分");
  await page.fill('[data-field="occurred_location"]', "○○市○○區○○路○○號");
  await page.fill('[data-field="report_time"]', "114年5月1日22時10分");
  await page.fill('[data-field="case_summary"]', "114年5月1日21時30分，遭男子持刀威脅，交付現金後對方離去。");
  await page.fill('[data-field="jurisdiction"]', "本所轄區");
  await page.fill('[data-field="handling_officer"]', "王小明");
  await page.screenshot({ path: OUT + "/m1_prototype_victim_report.png", fullPage: true });

  await page.selectOption('select[data-key="has_victim"]', "false");
  await page.selectOption('select[data-key="is_solved"]', "true");
  await page.screenshot({ path: OUT + "/m1_prototype_no_victim.png", fullPage: true });

  await browser.close();
  console.log("screenshots done");
})();

// 為 templates.json 之可填欄位補上 value_hints（如何自事實描述抽取欄位值）。
// 幂等：重複執行不會改變既有值。型別：
//   summary   – 整段事實之摘要
//   datetime  – 以正則擷取時間
//   location  – 以正則擷取地點
//   person    – 以正則擷取姓名
//   constant  – 固定值
//   manual    – 不由系統抽取，一律標為待補
const fs = require("fs");
const path = require("path");

const FILE = process.env.TEMPLATES_FILE || path.join(__dirname, "..", "data", "templates.json");

const HINTS = {
  header_office: {
    type: "manual",
    note: "報告單位名稱不由事實描述抽取，須由承辦人填寫；未填時保留原文佔位。",
  },
  case_reason: {
    type: "summary",
    role: "事實描述摘要",
    max_length: 120,
    suffix: "（候選）",
    note: "僅填事實描述，不得填具體法條罪名；末尾以（候選）標示本欄位內容尚待釐清。",
  },
  occurred_time: {
    type: "datetime",
    patterns: [
      "\\d{2,3}年\\d{1,2}月\\d{1,2}日(?:\\d{1,2}時\\d{1,2}分)?",
      "\\d{1,2}月\\d{1,2}日(?:\\d{1,2}時\\d{1,2}分)?",
      "(?:早上|中午|下午|晚上|凌晨|傍晚)\\d{1,2}時(?:\\d{1,2}分)?",
      "\\d{1,2}時\\d{1,2}分",
    ],
  },
  occurred_location: {
    type: "location",
    patterns: [
      "(?![我在于到去來從對他她它])[^，。；\\s]{0,12}?(?:市|縣)[^，。；\\s]{0,10}?(?:區|鄉|鎮)[^，。；\\s]{0,20}?(?:號|路|街|巷)",
      "(?![我在于到去來從對他她它])[^，。；\\s]{0,20}?(?:超商|公園|市場|車站|停車場|騎樓|住處|店面前|旁)",
    ],
  },
  report_time: {
    type: "datetime",
    context_before: ["報案", "報警", "通報", "向警察"],
    context_window: 30,
    patterns: [
      "\\d{2,3}年\\d{1,2}月\\d{1,2}日(?:\\d{1,2}時\\d{1,2}分)?",
      "\\d{1,2}月\\d{1,2}日(?:\\d{1,2}時\\d{1,2}分)?",
      "(?:早上|中午|下午|晚上|凌晨)\\d{1,2}時(?:\\d{1,2}分)?",
    ],
  },
  solved_time: {
    type: "datetime",
    context_before: ["到案", "破獲", "查獲", "移送", "帶回"],
    context_window: 30,
    patterns: [
      "\\d{2,3}年\\d{1,2}月\\d{1,2}日(?:\\d{1,2}時\\d{1,2}分)?",
      "\\d{1,2}月\\d{1,2}日(?:\\d{1,2}時\\d{1,2}分)?",
      "(?:早上|中午|下午|晚上|凌晨)\\d{1,2}時(?:\\d{1,2}分)?",
    ],
  },
  case_summary: {
    type: "summary",
    role: "案情摘要",
    max_length: 400,
    suffix: "",
  },
  jurisdiction: {
    type: "constant",
    value: "本所轄區",
  },
  handling_officer: {
    type: "person",
    patterns: ["警員\\s*([\\u4e00-\\u9fff]{2,4})", "處理員警[:：]\\s*([\\u4e00-\\u9fff]{2,4})"],
  },
};

const data = JSON.parse(fs.readFileSync(FILE, "utf8"));
let changed = 0;
for (const tpl of data.templates || []) {
  for (const sec of tpl.sections || []) {
    for (const f of sec.fields || []) {
      if (f.editable === false) continue;
      const hint = HINTS[f.field_id];
      if (!hint) continue;
      if (JSON.stringify(f.value_hints) === JSON.stringify(hint)) continue;
      f.value_hints = hint;
      changed++;
    }
  }
}
fs.writeFileSync(FILE, JSON.stringify(data, null, 2), "utf8");
console.log("value_hints 套用欄位數:", changed);
console.log("檔案:", FILE);

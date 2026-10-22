// 清洗擷取資料：過濾無關函釋、修正 pub_date、去重
const fs = require("fs");
const RAW_DIR = process.env.RAW_DIR || require("path").join(__dirname, "..", "raw");
const RAW_FILE = process.env.LB_RAW || require("path").join(RAW_DIR, "lb_raw.json");
const CLEAN_FILE = process.env.LB_CLEAN || require("path").join(RAW_DIR, "lb_clean.json");
const raw = JSON.parse(fs.readFileSync(RAW_FILE, "utf8"));

// FINT 權限提示雜訊
const NOISE = /本筆資料僅供付費會員查閱|歡迎\\s*購買授權|授權人數已滿額/;
// 與本次主題無關的機關（選舉委員會、殯葬等）
const IRRELEVANT_ORGS = /中央選舉委員會|中選務字/;

const cleanInterpretations = [];
for (const grp of raw.interpretations) {
  const rows = grp.rows.filter((r) => {
    const t = (r.holding || "") + " " + (r.doc_no || "");
    if (NOISE.test(t)) return false;
    if (IRRELEVANT_ORGS.test(t)) return false;
    if (!r.holding || r.holding.length < 6) return false;
    return true;
  });
  cleanInterpretations.push({ keyword: grp.keyword, tag: grp.tag, rows });
}

// 判解去重（以 case_ref 為鍵，保留要旨最完整者）
const byRef = new Map();
for (const grp of raw.judgments) {
  for (const r of grp.rows) {
    if (!r.case_ref) continue;
    const prev = byRef.get(r.case_ref);
    const score = (x) => ((x.holding_key || []).join("").length || 0) + (x.holding_snippet || "").length;
    if (!prev) { byRef.set(r.case_ref, { ...r, tags: [grp.tag] }); }
    else {
      if (score(r) > score(prev)) {
        const tags = prev.tags;
        byRef.set(r.case_ref, { ...r, tags });
      }
      if (!prev.tags.includes(grp.tag)) prev.tags.push(grp.tag);
    }
  }
}
const judgments = [...byRef.values()];

// 論著：修正 pub_date（重複問題）、去重
const trMap = new Map();
for (const grp of raw.treatises) {
  for (const r of grp.rows) {
    let date = r.pub_date;
    if (date) {
      const m = String(date).match(/^([\d]{4}\.[\d]{1,2})/);
      if (m) date = m[1];
    }
    const key = r.link;
    if (!trMap.has(key)) trMap.set(key, { ...r, pub_date: date, tags: [grp.tag] });
    else if (!trMap.get(key).tags.includes(grp.tag)) trMap.get(key).tags.push(grp.tag);
  }
}
const treatises = [...trMap.values()];

const out = {
  fetched_at: raw.fetched_at,
  source: raw.source,
  cleaned_at: new Date().toISOString(),
  statutes: raw.statutes,
  judgments,
  interpretations: cleanInterpretations,
  treatises,
};
fs.writeFileSync(CLEAN_FILE, JSON.stringify(out, null, 2), "utf8");
console.log("statutes:", out.statutes.length);
console.log("judgments (dedup):", out.judgments.length);
console.log("interpretations:", cleanInterpretations.map((i) => i.tag + "=" + i.rows.length).join(", "));
console.log("treatises (dedup):", out.treatises.length);
console.log("WROTE", CLEAN_FILE);

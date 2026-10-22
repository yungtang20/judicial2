// 將 CommonJS 模組轉為 UMD（Node 與瀏覽器皆可載入）。
// 用法：node tools/to_umd.js analyzer.js generator.js
const fs = require("fs");
const path = require("path");

const HEADER = [
  "// 可同時於 Node（CommonJS）與瀏覽器（掛載至 window.RF.<Name>）載入。",
  "//",
  "(function (root, factory) {",
  "  if (typeof module === 'object' && module.exports) {",
  "    module.exports = factory();",
  "  } else {",
  "    root.RF = root.RF || {};",
  "    root.RF.__NAME__ = factory();",
  "  }",
  "})(typeof self !== 'undefined' ? self : this, function () {",
  "",
].join("\n");

const files = process.argv.slice(2);
if (!files.length) {
  console.error("用法：node tools/to_umd.js <file.js> [...]");
  process.exit(2);
}

for (const f of files) {
  const p = path.resolve(f);
  let c = fs.readFileSync(p, "utf8");
  if (c.includes("typeof module === 'object' && module.exports")) {
    console.log("已是 UMD，略過：", path.basename(p));
    continue;
  }
  const name = path.basename(p, ".js");
  const idx = c.indexOf('"use strict";');
  if (idx < 0) throw new Error(path.basename(p) + "：找不到 use strict 標記");
  let body = c.slice(idx);
  // 將 module.exports = {...}; 改為 return {...};
  body = body.replace(/module\.exports\s*=\s*\{/g, "return {");
  const header = HEADER.replace("__NAME__", name);
  c = header + body.replace(/\s*$/, "") + "\n});\n";
  fs.writeFileSync(p, c, "utf8");
  console.log("已轉為 UMD：", path.basename(p), "→ window.RF." + name);
}

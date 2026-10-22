// M7 LLM 橋接：以 opencode CLI 呼叫語意模型，沿用使用者既有認證。
// 金鑰不進 repo；模型可由環境變數 LB_MODEL 指定。
//
// 輸出取自 opencode --format json 的串流事件，收集 part.text 後回傳。
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const MODEL = process.env.LB_MODEL || "opencode/minimax-m3.1-flash-free";
const TIMEOUT_MS = Number(process.env.LB_TIMEOUT_MS || 120000);

/** 找出 opencode 執行檔：Windows 優先使用真正之 .exe，避免 shell 引號處理問題 */
function resolveOpencode() {
  if (process.env.LB_OPENCODE) return process.env.LB_OPENCODE;
  if (process.platform === "win32") {
    const npmDir = path.join(os.homedir(), "AppData", "Roaming", "npm", "node_modules", "@opencode", "cli", "bin");
    for (const c of [path.join(npmDir, "opencode.exe")]) {
      try { if (fs.existsSync(c)) return c; } catch (e) { /* ignore */ }
    }
  }
  return "opencode";
}

/**
 * 呼叫 LLM 並回傳其文字輸出。逾時或失敗時重試。
 * @param {string} prompt
 * @returns {Promise<{ok:boolean, text:string, error?:string, elapsedMs:number, attempts:number}>}
 */
async function callLLM(prompt) {
  const attempts = Number(process.env.LB_RETRIES || 2) + 1;
  let last = { ok: false, text: "", error: "未執行" };
  for (let i = 0; i < attempts; i++) {
    last = await callOnce(prompt);
    if (last.ok) return Object.assign({}, last, { attempts: i + 1 });
  }
  return Object.assign({}, last, { attempts });
}

function callOnce(prompt) {
  return new Promise((resolve) => {
    const started = Date.now();
    const child = spawn(
      resolveOpencode(),
      ["run", "--format", "json", "--model", MODEL, prompt],
      { stdio: ["ignore", "pipe", "pipe"], windowsHide: true }
    );
    let out = "";
    let err = "";
    let settled = false;
    const finish = (r) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try { child.kill(); } catch (e) { /* ignore */ }
      resolve(Object.assign({ elapsedMs: Date.now() - started }, r));
    };
    const timer = setTimeout(() => finish({ ok: false, text: "", error: "LLM 逾時" }), TIMEOUT_MS);

    child.stdout.on("data", (d) => { out += d.toString(); });
    child.stderr.on("data", (d) => { err += d.toString(); });
    child.on("error", (e) => finish({ ok: false, text: "", error: "無法啟動 opencode：" + e.message }));
    child.on("close", (code) => {
      if (code !== 0) {
        return finish({ ok: false, text: "", error: "opencode 結束碼 " + code + "：" + err.slice(-300) });
      }
      const text = collectText(out);
      if (!text.trim()) {
        return finish({ ok: false, text: "", error: "LLM 未回傳文字內容：" + out.slice(-300) });
      }
      finish({ ok: true, text });
    });
  });
}

/** 從 opencode --format json 的串流事件中取出所有 part.text 片段並串接 */
function collectText(raw) {
  const parts = [];
  for (const line of raw.split(/\r?\n/)) {
    const s = line.trim();
    if (!s || s[0] !== "{") continue;
    let ev;
    try { ev = JSON.parse(s); } catch (e) { continue; }
    if (ev.type === "text" && ev.part && typeof ev.part.text === "string") {
      parts.push(ev.part.text);
    } else if (ev.type === "error") {
      throw new Error(ev.error && ev.error.message ? ev.error.message : "LLM 回傳錯誤");
    }
  }
  return parts.join("");
}

/** 從可能含 Markdown 圍欄或前後雜訊的文字中取出 JSON 物件 */
function extractJSON(text) {
  if (!text) return null;
  let s = String(text).trim();
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) s = fence[1].trim();
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    return JSON.parse(s.slice(start, end + 1));
  } catch (e) {
    return null;
  }
}

module.exports = { callLLM, extractJSON, collectText, MODEL };

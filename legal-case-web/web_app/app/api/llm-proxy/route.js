import { execFileSync } from "child_process";

export async function GET() {
  return Response.json(globalThis.__lastApiDebug || { message: "尚未收到任何請求" });
}

function safeJsonParse(text) {
  const raw = String(text || "").trim();
  const fenced = raw.replace(/^```json\s*/i, "").replace(/^```/i, "").replace(/\s*```$/i, "").trim();
  const start = fenced.indexOf("{");
  const end = fenced.lastIndexOf("}");
  if (start >= 0 && end > start) {
    return JSON.parse(fenced.slice(start, end + 1));
  }
  throw new Error("Upstream response is not valid JSON");
}

function callCurl(apiKey, payload) {
  const body = JSON.stringify(payload);
  let stdout = "";
  try {
    stdout = execFileSync("curl", [
      "-sS", "-X", "POST", "https://api.hcnsec.cn/v1/chat/completions",
      "-H", `Authorization: Bearer ${apiKey}`,
      "-H", "Content-Type: application/json",
      "-H", "Connection: close",
      "-H", "User-Agent: Mozilla/5.0",
      "--max-time", "280",
      "-d", body,
      "-w", "\nHTTPSTATUS:%{http_code}"
    ], { encoding: "utf8", maxBuffer: 10 * 1024 * 1024, timeout: 290000 });
  } catch (err) {
    throw new Error(`curl failed: ${err.code || ""} ${err.message || err}`);
  }

  const splitIndex = stdout.lastIndexOf("HTTPSTATUS:");
  const httpCodeStr = splitIndex >= 0 ? stdout.slice(splitIndex + "HTTPSTATUS:".length).trim() : "0";
  const status = parseInt(httpCodeStr, 10) || 0;
  const raw = splitIndex >= 0 ? stdout.slice(0, splitIndex).trim() : stdout.trim();
  let upstream = {};
  try { upstream = JSON.parse(raw); } catch { upstream = { raw }; }
  return { status, upstream };
}

export async function POST(req) {
  try {
    const body = await req.json();
    const gate = body.gate ?? Number(body.gate) ?? 1;
    const caseSummary = body.caseSummary || "";
    const apiKey = process.env.HCNSEC_API_KEY;

    if (!apiKey || apiKey === "your_actual_api_key_here") {
      const payload = { error: "伺服器未設定有效 HCNSEC_API_KEY", request_id: null };
      globalThis.__lastApiDebug = payload;
      return Response.json(payload, { status: 500 });
    }

    let systemPrompt;
    let userPrompt = `案情摘要：${caseSummary}`;

    if (gate === 1) {
      systemPrompt = `你是一位資深執法筆錄問句設計專家。請把案件拆解成 JSON 事實登錄表 (Fact Registry)。
每筆 include: fact_type ("人"/"事"/"時"/"地"/"物"), content, epistemic_status ("已知"/"未知"/"待查")。
嚴禁法律術語。Output 
ONLY compact JSON: {"facts":[{"fact_type":"...","content":"...","epistemic_status":"..."}]} 
Limit: at most 7 facts, content <= 40 Chinese chars each. Do not output analysis.`;
      userPrompt += `\n請拆解為 Fact Registry JSON。`;
    } else if (gate === 2) {
      systemPrompt = `你是一位資深執法筆錄問句設計專家。
任務：自動研判案情最可能涉及的罪章，並生成必要數量之「底層事實問句」。

鐵律：
1. 先比對案情摘要。凡摘要已載明的事实，一律不得再問；只問 gap。
2. 題數不限，但只以 gap 为准：若某事实已明确 stated，就不要問；只問摘要未提过的 detective gap。
3. 問句必须為一般民眾 readable 的白話，不誘導，不預設罪名。
4. 禁止直接問心理性是/否問法：如「你是否同意」「你是不是自願」；應问具体情境（时间、地点、人物、動作、對話、物品狀態）。
5. 允许回答「不知道」「不確定」「記不清楚」。
6. 只輸出合法 JSON，無 markdown。

Few-shot style（quest-to-gap）：
- 已知摘要說甲拿手機储值，不要問「做了什么」，要问「乙是否知悉/是否同意」。
- 已知摘要說几天后视频 threats，就應問「具体说了什么、谁在場、有无其他 witnesses」。

輸出 JSON: {"pair_id":"auto","target_role":"suspect","generated_questions":["問句1？","問句2？"]}`;
      userPrompt += `\n請自動分析罪章並生成問句。`;
    } else if (gate === 3) {
      const qaText = (body.qa || "")
        .map((x, i) => `${i + 1}. ${x.q}\n答: ${x.a || "（未填）"}`)
        .join("\n");

      systemPrompt = `你是一位司法條陳與筆錄整合專家。
任務：整合案件摘要、問答，輸出 strictly JSON：
{
  "memo": "<案情摘要/條陳，最多 100 中文字>",
  "consolidated_questions": "<整合後之關鍵事實 gaps，文字 concise>",
  "notes": "<需要人工追補/確認的事項>"
}
限制：
- memo 不得超過 100 個中文字
- 不得包含法律術語/法条转写
- 只輸出 JSON`;
      userPrompt = `案情摘要：${caseSummary}\n問答：\n${qaText}\n案號：${body.caseNumber || "未載"}\n請整合。`;
    } else {
      return Response.json({ error: "unknown gate" }, { status: 400 });
    }

    const { status, upstream } = callCurl(apiKey, {
      model: (process.env.HCNSEC_MODEL || "DeepSeek-V4-Flash"),
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt }
      ],
      temperature: 0.1,
      response_format: { type: "json_object" }
    });

    const requestId =
      upstream?.request_id ||
      upstream?.id ||
      upstream?.error?.request_id ||
      upstream?.error?.id ||
      null;

    if (status < 200 || status >= 300) {
      const msg = (typeof upstream?.error === "string"
        ? upstream.error
        : (upstream?.error?.message || upstream?.message || `API ${status}`));
      const detail = { error: msg, request_id: requestId, upstream_status: status, upstream_detail: upstream };
      globalThis.__lastApiDebug = detail;
      return Response.json(detail, { status: 502 });
    }

    const content = upstream.choices?.[0]?.message?.content;
    const cleaned = String(content || "").trim().replace(/^```json\s*/i, "").replace(/^```/i, "").replace(/\s*```$/i, "").trim();
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    let parsed;
    try {
      parsed = JSON.parse(start >= 0 && end > start ? cleaned.slice(start, end + 1) : cleaned);
    } catch (parseErr) {
      const detail = { error: `JSON Parse 失敗: ${parseErr.message}`, request_id: requestId, raw_upstream_text: content };
      globalThis.__lastApiDebug = detail;
      return Response.json(detail, { status: 502 });
    }

    const success = { ok: true, request_id: requestId, data: parsed };
    globalThis.__lastApiDebug = success;
    return Response.json(success);
  } catch (error) {
    const fallback = { error: error.message || "內部伺服器錯誤" };
    globalThis.__lastApiDebug = fallback;
    return Response.json(fallback, { status: 500 });
  }
}

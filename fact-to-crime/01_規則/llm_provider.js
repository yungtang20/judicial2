// llm_provider.js
// LLM Provider 抽象層：Gemini / OpenAI / Claude / Local，不讓 LLM 控制 Workflow。
// LLM Engine 邊界：只做語意理解、推理建議、問句生成；不判真偽、不自創法條、不直接輸出罪名（R30）。
// API key 由環境變數注入，不寫死。錯誤不 silent fallback，必須帶明確 error。

const fs = require('fs');
const path = require('path');

function loadConfig() {
  const configPath = path.join(__dirname, '..', 'llm_config.json');
  if (!fs.existsSync(configPath)) return null;
  return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
}

async function callAgnes(prompt, config) {
  const apiKey = process.env[config.llm_api_key_env || 'AGNES_API_KEY'];
  if (!apiKey) throw new Error('Missing AGNES_API_KEY environment variable');

  const res = await fetch(config.llm_endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: config.llm_model || 'agnes-2.5-flash',
      messages: [
        ...(config.system_prompt ? [{ role: 'system', content: config.system_prompt }] : []),
        { role: 'user', content: prompt },
      ],
      max_tokens: config.max_tokens || 500,
      temperature: config.temperature || 0.3,
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`LLM API ${res.status}: ${errText.slice(0, 120)}`);
  }

  const data = await res.json();
  return {
    content: data.choices?.[0]?.message?.content || '',
    model: config.llm_model,
    modelVersion: data.model || config.llm_model,
    promptVersion: 'v15',
    inputReferences: [prompt.slice(0, 200)],
  };
}

function createProvider(providerName = 'agnes') {
  const config = loadConfig();
  return {
    async generate(prompt) {
      if (providerName === 'agnes' || providerName === 'local') {
        return await callAgnes(prompt, config);
      }
      throw new Error(`Provider not implemented: ${providerName}`);
    },
    getName() {
      return providerName;
    },
  };
}

module.exports = { createProvider, loadConfig };

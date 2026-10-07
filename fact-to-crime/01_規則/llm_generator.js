// llm_generator.js
// 非核心缺口 LLM 生成骨架（v15 第九節 1、2、5、6）
// 核心要件由 rule_library 處理（question_library.js）
// 非核心缺口（requires_all_optional、requires_any_result、欄位矛盾、時點空白）由 LLM 生成
// 本檔為「LLM 生成骨架」，實際 LLM 調用由外部（如 omp eval）注入 prompt 並回傳結果

const fs = require('fs');
const path = require('path');

// LLM 生成介面（可注入）：使用者可自行替換為真實 LLM 調用
// 預設為 stub，標 `generated_by: llm_unimplemented`
let LLM_CALL = null;
try {
  // 嘗試從本地配置載入 LLM 生成器（OpenAI 相容介面，如 Agnes）
  const configPath = path.join(__dirname, '..', 'llm_config.json');
  if (fs.existsSync(configPath)) {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    if (config.llm_endpoint) {
      // API key 由環境變數注入（安全；key 不寫死在配置檔）
      const apiKey = process.env[config.llm_api_key_env || 'AGNES_API_KEY'];
      if (apiKey) {
        LLM_CALL = async (prompt) => {
          const res = await fetch(config.llm_endpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`,
            },
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
          // OpenAI 相容：choices[0].message.content
          return data.choices?.[0]?.message?.content || data.text || data.response || '';
        };
      }
    }
  }
} catch (e) { /* ignore */ }

function normalizeStatus(state) {
  if (!state) return '資料不足';
  if (state.status === '推論符合' && (!state.source_raw || state.source_raw.length === 0)) return '資料不足';
  return state.status || '資料不足';
}
function isPositive(st) { return st === '符合' || st === '推論符合'; }

// v15 第九節 5：問句類型標籤（開放/聚焦/封閉）
// v15 第九節 6：措辭中立（不含罪名、法律用語、元件名稱）
function buildPrompt(element, charge, identity, context = {}) {
  const identityHint = {
    '被害人': '受詢問人為被害人。問句聚焦其親身經歷的事實：時間線、操作步驟、金額與帳戶、對話內容、損失結果。不要求被害人回答其無從知悉的事項（例如對方的內心意圖）。',
    '被告': '受詢問人為被告。問句聚焦行為與主觀意圖。開放式提問，先問客觀事實，後問主觀認知。',
    '證人': '受詢問人為證人。問句聚焦現場見聞。開放式，邀請說明、描述。',
    '關係人': '受詢問人為關係人。問句聚焦關係與身分。',
  }[identity] || '受詢問人身分未明。';

  return `請依以下規則生成一個問句：

規則（v15 第九節）：
1. 措辭中立：不含罪名、法律用語、元件名稱，以日常用語提問
2. 禁止選項題、誘導題、預設答案題
3. 問句目的：取得準確資訊
4. 依身分調整：${identityHint}
5. 追問引用受詢問人自己的用語

資訊：
- 缺口：${element.semantic || element.name}
- 罪名背景（不寫入問句）：${charge.article}
- 身分：${identity}
${context.source_quote ? `- 受詢問人原話（供追問引用）：${context.source_quote}` : ''}

請生成一個問句（僅回傳問句文字本身，不加說明）：`;
}

// 生成非核心缺口問句
// element: 元件定義（需要 semantic、name）
// charge: 罪名定義
// identity: 身分
// context: 其他上下文（如 source_quote）
async function generateNonCoreQuestion(element, charge, identity = '被害人', context = {}) {
  const prompt = buildPrompt(element, charge, identity, context);
  if (LLM_CALL) {
    try {
      const text = await LLM_CALL(prompt);
      return {
        stage: 'B',
        priority: 5,
        type: '開放',
        text: text.trim(),
        generated_by: 'llm',
        bound_element: element.id,
        bound_charge: charge.id,
        identity_sensitive: [identity],
        neutral: true,
      };
    } catch (e) {
      return {
        stage: 'B',
        priority: 5,
        type: '開放',
        text: `（LLM 調用失敗：${e.message}）`,
        generated_by: 'llm_error',
        bound_element: element.id,
        bound_charge: charge.id,
        identity_sensitive: [identity],
        neutral: true,
      };
    }
  }
  // 無 LLM 配置 → stub
  return {
    stage: 'B',
    priority: 5,
    type: '開放',
    text: `（LLM 生成器未配置，需人工針對元件 ${element.id} 生成）`,
    generated_by: 'llm_unimplemented',
    bound_element: element.id,
    bound_charge: charge.id,
    identity_sensitive: [identity],
    neutral: true,
  };
}

module.exports = { generateNonCoreQuestion, buildPrompt, LLM_CALL };

// CLI test
if (require.main === module) {
  const element = { id: 'E-FR-006', name: '高金額門檻', semantic: '詐欺金額達特別法門檻' };
  const charge = { id: 'charge_fraud_special_high', article: '詐欺犯罪危害防制條例§43、§44' };
  generateNonCoreQuestion(element, charge, '被害人').then(q => {
    console.log(JSON.stringify(q, null, 2));
  });
}

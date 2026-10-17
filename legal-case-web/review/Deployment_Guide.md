# 免費部署指南 (Vercel / Hugging Face Spaces)
適用模型 API：`https://api.hcnsec.cn/v1/chat/completions`（model: `auto`）

## 1. 架構概述
- 前端：Streamlit / Gradio 或簡單 HTML 頁面，負責輸入 `case_summary`、`pair_id`、`target_role` 並顯示生成問句。
- 後端：API Route（如 Vercel 的 `/api/generate` 或 Spaces 內的 FastAPI endpoint），僅後端持有 `HCNSEC_API_KEY`。
- 資料層：本地/庫內的 `knowledge_base_v1.md` 與 `llm_system_prompt_v1.md`。

呼叫流程：
1. 使用者在前端輸入案情摘要與 PAIR。
2. 後端讀取 `knowledge_base_v1.md` 中對應 PAIR 區塊。
3. 後端組裝 System Prompt + Few-Shot + User Prompt，呼叫 `https://api.hcnsec.cn/v1/chat/completions`。
4. 後端解析 JSON 並回傳 `generated_questions` 給前端。

## 2. 環境變數設定
- 絕對不要將 API Key 寫死在程式碼或前端。
- Vercel：Project Settings -> Environment Variables -> 新增 `HCNSEC_API_KEY`（Production/Preview/Development 皆設定）。
- Hugging Face Spaces：Settings -> Variables and secrets -> 新增 `HCNSEC_API_KEY`。
- 本機開發：使用 `.env` + `python-dotenv`，並將 `.env` 加入 `.gitignore`。

## 3. Prompt 組裝邏輯 (Pseudo-code)
```
system_prompt  = read_file("llm_system_prompt_v1.md")
kb_text        = read_file("knowledge_base_v1.md")
pair_block     = extract_between(kb_text, "## PAIR-xxx", next "## ")
few_shot       = [
    {"role": "user", "content": "以下是該 PAIR 的底層事實問句風格範例，請模仿：\n" + pair_block},
    {"role": "assistant", "content": "已理解該 PAIR 的問句風格，將依 Core Rules 生成。"}
]
user_prompt    = "案情摘要：" + case_summary + "\n" +
                 "候選混淆罪名 (PAIR)：" + pair_id + "\n" +
                 "目標角色：" + target_role + "\n" +
                 "請依 System Prompt 生成 3-4 題底層事實問句，並以指定 JSON 格式輸出。"
messages       = [ {"role": "system", "content": system_prompt} ] + few_shot + [ {"role": "user", "content": user_prompt} ]
payload        = { "model": "auto", "messages": messages, "temperature": 0.2 }
resp           = POST("https://api.hcnsec.cn/v1/chat/completions", headers=auth, json=payload)
```

## 4. 錯誤處理與降級策略 (Graceful Degradation)
- API 超時：設定 timeout（建議 30–60 秒），超時後改回傳 `knowledge_base_v1.md` 中對應 PAIR 的靜態問句，並於前端提示「AI 服務忙碌，已載入備用問句」。
- 非 JSON 回應：先 `try json.loads`，失敗則記錄原始回應，回傳系統預設的通用問句（如身分核對＋自由意識確認）。
- 限流/429：指數退避重試 3 次，最終失敗則進入靜態降級。
- Key 錯誤/401：立即停止重試，前端提示「API Key 設定異常，請聯絡管理員」。
- 內容安全：生成問句若檢測到禁止詞彙，再進行一次本地正規化/人工覆核後才允許輸出。

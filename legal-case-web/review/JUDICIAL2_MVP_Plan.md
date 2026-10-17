# JUDICIAL2 完整多閘道系統 · MVP 決策與路徑

## 決策摘要
- 模板格式：以 `.docx` 為基準，使用占位符 `{{...}}`；若原檔為 `.doc`，請先轉成 `.docx` 後放入 web_app/templates。
- 本地資料儲存：使用 Browser localStorage + 後端 JSON 暫存；不做帳號/多租戶（MVP 階段）。
- AI 模型：使用 https://api.hcnsec.cn/v1/chat/completions, model `auto`，透過 Next.js API Route；`HCNSEC_API_KEY` 只能放 `.env.local`。
- 問句策略：Gate 2 由 LLM 即時分析 candidate charges，並引用 B_master_case_studies.yaml 的 PAIR neutral questions 作為 Few-Shot，不預先 hardcode 全部罪名。
- 調查手冊：後續再把《犯罪偵查手冊》或書狀規範拆成 prompt，MVP 先採「通用底層事實問句」。
- 輸出：先以 Markdown + DOCX 模板組裝字組；`{{問句區塊}}` 以 AI 生成的文章字串填入。

## 閘道流程
1. Home: 時間/地點/摘要
2. Gate 1: 人/事/時/地/物 + 行為 + 因果 → 原子事实条目
3. Gate 2: 得出候选 sin章 + core/補強問句 + 追加 PAIR 問句 (one Q one A)
4. Gate 3: AI 批判/整合 → victim memo + complete survivor.doc
5. Gate 4/5: suspect paths

## 8 page limit / 100 chars memo
- UI 顯示 estimated page count (chapter 1200 chars/page) and memo max 100 chars validator
- On submission, if >limit, prompt to tighten

## case number appendix
- gate2 完成後暂停并 display:
  - 證明單案號 (必填)
  - 婦幼案號 (only if 證人为 code)
  - 165案號 (only if 詐欺)
- memo 只显示 applicable ones

## Next step task (MVP-1)
1. 建立 `web_app/templates` 並放入 your 通用*.docx templates (with placeholders)
2. 完成 gates 1-2 的 form + proxy script
3. 完成 docx 生成 API
4. harden security and deploy free (Vercel/VSC Spaces)
5. integration QA with blind test queries

## Request to user
Please confirm these decisions and send the .docx templates (or screenshots/placeholders table). After confirmation, I will implement Gate 1 and Gate 2 first.
# 法律案件工作台

本專案是獨立、本機優先的 Gate 1–5 工作台。它不會復原父目錄中已刪除的舊系統檔案，也不會把案件內容送往外部 AI。

## 啟動

需求：Windows、Python 3、LibreOffice，以及 `requirements.txt` 中的套件。

```powershell
cd D:\工作用\judicial1\legal-case-web
py -3 -m pip install -r requirements.txt
.\start.ps1
```

網址固定為 `http://127.0.0.1:8787/`。服務不監聽外部網路介面。

## 已實作流程

1. 首頁輸入發生／破獲時間、地點及案情摘要（進階欄位收合）。
2. Gate 1 由使用者確認人、事、時、地、物、行為、因果及 `UNKNOWN`。
3. Gate 2 以規則或 AI（api.iamhc.cn，OpenAI 相容）提出零個或多個候選罪章。使用者必須人工選擇罪章並回答全部核心問題。AI 僅接收案情摘要；問答內容不外傳。
4. Gate 2 同頁填寫受詢問人年籍與詢問起訖時間，問答採逐題呈現（上一題／下一題／進度）。
5. Gate 2.5 依規則顯示證明單、婦幼及 165 案號欄位。
6. Gate 3 產生被害人筆錄及條陳。
7. 同一案件可繼續 Gate 4 的涉嫌人問答及文件。
8. 無被害人案件使用 Gate 5 移送分支。
9. 重新開啟案件時保存舊核准快照，並使後續核准失效。

## 法律與人工核准邊界

- 候選引擎為確定性規則，或外部 AI 分類；兩者都不是法律判斷。
- 系統可以安全回傳零候選。
- 每個候選都維持 `NEED_REVIEW`。
- 題庫維持 `HUMAN_REVIEW_REQUIRED`，並於啟動時載入父目錄 `questions/` 中已核實的全罪章 Markdown 問句（核心／補充／補強／區分／加重分節載入）。
- 公司三份範本（通用被害人、通用涉嫌人、移送涉嫌人）之必問題逐字保留於 `app/company_templates.py`；筆錄輸出含公司表頭、年籍表、應告知事項（刑訴 §95 經 §100-2 準用；移送另含提審法 §1）及簽名區。
- 公司套表罪章題（`新套表.xlsm` 各罪章欄）逐字載入（`app/xlsm_questions.py`），公式插值題跳過由承辦人補實。
- 操作人員必須確認 Gate 1、罪章、問句與回答後才能輸出。
- 法源、程序或必要案號不足時，不得把文件標示為完整。
- 現行公開法規核對入口（2026-10-11 以 twlegalrag 核對現行條文）：
  - 刑事訴訟法 §95、§100-2、§100-3：https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=C0010001
  - 提審法 §1：https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=C0010008
  - 個人資料保護法：https://law.moj.gov.tw/LawClass/LawAll.aspx?PCode=I0050021
- 《警察犯罪偵查手冊》現行公開全文仍為 `UNKNOWN`，因此題庫不可宣稱已依該手冊逐條核准。

## 外部 AI 邊界

- 僅 Gate 2 候選罪章分析可送出案情摘要（上限 4000 字）至 `IAMHC_BASE_URL`（預設 https://api.iamhc.cn/v1）。
- 金鑰存於 `legal-case-web/.env`（`IAMHC_API_KEY`），已列入 `.gitignore`。
- 金鑰未設定或服務失敗時自動退回規則候選；重試 4 次後放棄。
- 年籍、問答內容、案號、條陳不送任何外部服務。

## 問句來源與優先序

載入順序（review-checklist.md 第四節）：

1. 公司三份 `.doc` 範本通用必問題（`app/company_templates.py`，逐字）。
2. 通用程序題（`data/question_bank.json` common）。
3. 公司套表罪章題（`data/xlsm_questions.json`，抽取自 `新套表.xlsm` 被害人／涉嫌人／證人筆錄工作表之各罪章欄，公式插值題跳過）。
4. 本庫 Markdown 核心／補充／補強／區分／加重題（`questions/*.md`，分節載入）。
5. JSON 要件題（僅在 md 未涵蓋同一 element 時補入）。

語意相同之題目自動去重（全文比對）。罪章題預算上限 30 題（8 頁防線）；公司題與核心題優先保留。

## 文件規則

- 輸出格式為 `.docx`，不修改三份舊式 `.doc`。
- 筆錄 DOCX 依公司範本結構重建：標題列、詢問時間地點、案由、受詢問人年籍表（11 欄＋家庭經濟狀況）、涉嫌人應告知事項、問答、結尾簽名區。
- 版面固定為 A4、標楷體 12pt、1.15 倍行距。
- 下載筆錄前，以本機 LibreOffice 轉成 PDF 並讀取實際頁數。
- 超過 8 頁、LibreOffice 不存在或排版失敗時，系統會阻止筆錄下載。
- 條陳案情摘要最多 100 個 Unicode 字元。
- 下載的 DOCX 是未加密明文，使用者需自行依機關規定保存。

## 隱私與安全

- 僅綁定 IPv4 `127.0.0.1`。
- CORS 關閉；例外：Gate 2 罪章候選可送案情摘要至外部 AI（見「外部 AI 邊界」）。
- API 驗證記憶體 session token、`Host`、`Origin` 及 body 大小。
- 回應使用 CSP、`no-store`、`nosniff` 與 frame deny。
- 案件 payload 使用 Windows DPAPI current-user scope 加密後存入 SQLite。
- SQLite metadata 只保存隨機案件 ID、revision、Gate 狀態及時間。
- 稽核事件不保存姓名、案號、自由文字或問答內容。
- DPAPI 資料通常不能移到其他 Windows 帳號或電腦解密。密文損壞時系統 fail closed，不會建立空案件取代原資料。

## 驗證

```powershell
py -3 -X utf8 -m pytest -q
node --check app\static\app.js
```

測試涵蓋：零候選、AI 候選解析與失敗退回、關聯候選、問句單一判斷、公司必問逐字輸出、xlsm 公司罪章題載入、權利告知與提審告知、案號條件、100 字摘要、Gate 禁止跳過、年籍儲存、向後修改失效、同案被害人至涉嫌人流程、無被害人分支、DPAPI 明文 sentinel、revision 衝突、密文損壞、DOCX 完整性、LibreOffice 實際頁數、session token、Host、Origin、CSP、CORS 及路徑穿越。

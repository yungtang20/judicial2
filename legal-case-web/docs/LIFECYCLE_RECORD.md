# Lifecycle Record

```yaml
execution_mode: REVIEWED_PIPELINE
risk_level: HIGH
routing_triggers: [H1, H2, H5]
included_phases: [PLAN, DESIGN, BUILD, TEST]
skipped_phases:
  - phase: DEPLOY
    status: SKIPPED_WITH_REASON
    reason: 使用者未授權部署，且刑事案件資料不得在未核准前跨越本機邊界
  - phase: MAINTAIN
    status: SKIPPED_WITH_REASON
    reason: 本次沒有持續監控要求
authorization_status: LOCAL_IMPLEMENTATION_AUTHORIZED
final_status: COMPLETE
```

## PLAN

- Input：Gate 1 至 Gate 5 需求、三份 `.doc`、`新套表.xlsm`、`條陳.txt`。
- Output：本機、安全、可重新開啟案件的獨立 Web 應用計畫。
- Gate：不復原或覆蓋工作樹中 263 個既有刪除。
- Evidence：實作範圍固定在 `legal-case-web/`。

## DESIGN

- Input：刑事案件個資、問句中立性、8 頁與文件相容需求。
- Output：規則候選、Human Gate、DPAPI 密文、revision、DOCX 實際排版檢查。
- Gate：外部 AI 關閉；候選不得作為犯罪成立判斷；必要資料缺失時阻止輸出。
- Evidence：`app/workflow.py`、`app/security.py`、`app/documents.py`。

## BUILD

- Input：已核准的本機安全設計。
- Output：UI、API、狀態機、題庫、加密保存、條陳與 DOCX。
- Gate：所有變更只在新子目錄；原始範本只讀。
- Evidence：`data/source_manifest.json`、應用程式原始碼。

## TEST

- Input：規則、Gate、儲存、HTTP 安全、文件與無障礙驗收條件。
- Output：pytest、JavaScript 語法、實際 LibreOffice 頁數、手動瀏覽器驗證結果。
- Gate：失敗先修產品程式碼；同根因最多修復兩次。
- Evidence：`tests/` 與最終驗證紀錄。

最終驗證紀錄：

- `py -3 -X utf8 -m pytest -q`：20 passed。
- `python compileall`：PASS。
- `node --check app/static/app.js`：PASS。
- JSON 載入：2 files PASS。
- Playwright 桌面及 390px 手機：無 console error、無水平溢位、所有表單控制項有 label。
- Playwright 完整流程：首頁 → Gate 1 → Gate 2 → Gate 2.5 → 條陳 → DOCX；DOCX HTTP 200，LibreOffice 實際排版 2 頁。
- Git 範圍：新增內容僅在 `legal-case-web/`；263 個既有刪除未復原，0 個既有追蹤檔被修改。

## DEPLOY

- Output：`NOT_DEPLOYED`
- Gate：需另行取得部署位置、資料處理與外部服務的人工作業授權。

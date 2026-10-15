# 本地執行環境診斷報告

**診斷時間**: 2026-10-15  
**專案目錄**: D:\工作用\judicial1\legal-case-web  
**作業系統**: Windows (win32)

---

## 1. 工具可用性清單

| 工具類別 | 可用工具 | 備註 |
|---------|----------|------|
| **系統 Shell** | `shell` | Windows PowerShell (pwsh)，**無 `bash`** |
| **JavaScript 執行** | `tools.node_repl.js`, `js_add_node_module_dir`, `js_reset` | 持久化 Node REPL，可跨呼叫保持狀態 |
| **程式碼搜尋/圖譜** | `tools["codebase-memory-mcp"]` 17 支工具 | search_graph, trace_path, get_code_snippet, query_graph 等 |
| **文獻/文檔查詢** | `tools.context7` (resolve-library-id, query-docs) | 需先 resolve-library-id |
| **法規/判決/釋字** | `tools["taiwan-legal-db"]` 26 支工具 | search_judgments, get_judgment, query_regulation, get_interpretation 等 |
| **程式碼審查** | `tools["open-code-review"]` (scan_diff, heal_code, explain_issue, scan_directory) | |
| **OCR/審計** | `tools.ocr_health`, `tools.ocr_review` | |
| **OpenCode 自身** | `tools.opencode` (session, worktree, models, mcp resources) | |
| **網路搜尋/抓取** | `websearch`, `webfetch` | |
| **檔案操作** | `read`, `write`, `edit`, `grep`, `glob`, `list_all_goals`, `get_goal`, `create_goal` 等 | |
| **子代理** | `subagent` (agent-os-*, explore, general) | |

> ⚠️ **關鍵缺口**: **無 `bash` 工具**，亦無獨立的 `python`、`cmd`、`powershell` 具名工具。所有外部指令需透過 `shell` (PowerShell) 執行。

---

## 2. 卡頓/失敗原因分析

### 2.1 `No tool named "bash"`
- **原因**: 工具註冊表中根本沒有名為 `bash` 的工具。  
- **環境事實**: `shell` 在 Windows 上預設使用 **PowerShell (pwsh)**，不是 bash。若腳本或指令假設有 `bash` 會直接失敗。

### 2.2 `Endpoint is unavailable` (重試 10 次仍失敗)
- **可能原因**:
  1. **後端沙箱/服務暫時性離線** — `execute` 內部呼叫的 node_repl / MCP 服務在該時間點不可用。
  2. **Context Window / 輸出過大** — 先前抓取的裁判全文極長（數萬字），若一次性傳回可能觸發沙箱截斷或超時。
  3. **網路/代理波動** — MCP 服務之間的內部 gRPC/HTTP 呼叫失敗。
- **非原因**: 非使用者端網路、非權限問題（其他工具同期間正常）。

---

## 3. 後續防卡死執行建議

| 場景 | 建議做法 |
|------|----------|
| **執行 Python 腳本** | 用 `shell` + `cmd /c python ...` 或 `powershell -c "python ..."`<br>例：`shell({"command": "cmd /c python C:\\path\\script.py"})` |
| **搜尋裁判 (taiwan-legal-db)** | - `max_results: 5~10` 即可<br>- 僅用 `keyword` + `case_type` + `year_from/to` 縮小範圍<br>- 先用 `search_judgments` 取得 jid，再用 `get_judgment({jid})` 抓全文，必要時加 `reasoning_keyword` 只取片段 |
| **抓取全文後處理** | - 全文極長時，**先在 `get_judgment` 階段用 `reasoning_keyword` 只取關鍵段落**<br>- 或抓回後立即在本地用 `grep`/`python` 切片，**不要把完整全文塞進下一輪對話** |
| **大量 YAML/報告寫入** | - 分批寫入，單檔 ≤ 200 KB<br>- 完成後用 `read` 確認而非再次列印全部內容 |
| **子代理並行** | - `subagent` 背景模式 (`background: true`) 可並行跑多個探查任務，主執行緒不阻塞 |
| **重試策略** | - 遇到 `Endpoint is unavailable`：等待 10–30 秒後**單次重試**，失敗則改用替代工具 (如改用 `websearch`/`webfetch` 直取裁判網頁) |
| **記憶體/Context 管理** | - 長文本處理後立即 `update_goal` 或寫檔，釋放上下文<br>- 單輪對話避免同時載入 > 3 份完整判決全文 |

---

## 4. 具體指令範例

```powershell
# 執行 Python 檢查腳本 (正確方式)
shell({"command": "cmd /c python C:\\Users\\yungtang\\AppData\\Local\\Temp\\opencode\\batch3_audit.py"})

# 只抓裁判理由片段 (避免全文過長)
tools["taiwan-legal-db"].get_judgment({
  jid: "TPHM,110,上易,216,20220830,1",
  reasoning_keyword: "乘人之危"
})

# 平行啟動多個子代理搜尋不同 PAIR
subagent({agent: "explore", description: "PAIR-008 search", prompt: "...", background: true})
subagent({agent: "explore", description: "PAIR-010 search", prompt: "...", background: true})
```

---

## 5. 結論

- **環境可用**，但 **Shell = PowerShell**，無 bash。
- **Python 腳本請走 `shell` + `cmd /c python`**。
- **裁判全文抓取請「關鍵字片段優先，必要時才全文」**，並立即切片存檔，避免塞爆 Context / 觸發沙箱超時。
- **下一步 (Task 3 Batch 4) 前請先確認上述策略**，我將在收到指示後開始執行。

---

*報告完成。等待下一步指示。*
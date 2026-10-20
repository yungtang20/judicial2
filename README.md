# 法律案件工作台 (Judicial Case Workbench)

獨立、本機優先的 Gate 1–5 法律案件工作台。核心目標是整理事實、保留多個候選法律路由、產生角色化問句及輸出筆錄。

## 線上服務資訊

- **服務名稱**：`legal-case-workbench`
- **線上工作台網址**：[https://legal-case-workbench.onrender.com](https://legal-case-workbench.onrender.com)
- **登入 / 首次註冊入口**：[https://legal-case-workbench.onrender.com/login](https://legal-case-workbench.onrender.com/login)
- **健康檢查端點**：[https://legal-case-workbench.onrender.com/api/health](https://legal-case-workbench.onrender.com/api/health)

## 快速指引

- **完整說明文件**：請參閱 [`legal-case-web/README.md`](legal-case-web/README.md)
- **系統架構與信任邊界**：請參閱 [`legal-case-web/docs/SYSTEM_ARCHITECTURE.md`](legal-case-web/docs/SYSTEM_ARCHITECTURE.md)
- **本機啟動**：
  ```powershell
  cd legal-case-web
  py -3 -m pip install -r requirements.txt
  .\start.ps1
  ```
  本機服務網址：`http://127.0.0.1:8787/`

# syntax=docker/dockerfile:1
FROM python:3.12-slim

# 安裝 Linux 下的 LibreOffice 與中文字體（楷體/思源黑體）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    fonts-noto-cjk \
    fonts-arphic-ukai \
    fonts-arphic-uming \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 複製整個專案（包含父層 questions/ 題庫與 legal-case-web/）
COPY . /app

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r legal-case-web/requirements.txt

# 切換到 legal-case-web 工作目錄
WORKDIR /app/legal-case-web

# Render 預設注入 PORT 環境變數（如 10000）
ENV HOST=0.0.0.0
ENV PORT=8787
ENV PYTHONUNBUFFERED=1
ENV RENDER=true

EXPOSE 8787

CMD ["python", "-X", "utf8", "-m", "app.server"]

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    AUTH_REQUIRED=true \
    AUTH_DATABASE_PATH=/tmp/accounts.sqlite3 \
    ALLOW_EXTERNAL_AI=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY questions ./questions

WORKDIR /srv/legal-case-web
COPY legal-case-web/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY legal-case-web .

EXPOSE 10000
CMD ["python", "-m", "app.server"]

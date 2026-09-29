FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    wget libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

RUN camoufox fetch

COPY config.py ./config.py
COPY backend ./backend

ENV PORT=8080
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port $PORT
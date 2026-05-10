FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    cron \
    wget ca-certificates fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libexpat1 libfontconfig1 libgbm1 libgcc1 libglib2.0-0 libgtk-3-0 \
    libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 \
    xdg-utils --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium

COPY main.py .
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY entrypoint.sh .
COPY run_report.sh .
RUN chmod +x entrypoint.sh run_report.sh

RUN mkdir -p /data
ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/data

VOLUME ["/data"]
ENTRYPOINT ["./entrypoint.sh"]

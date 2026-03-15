FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim

LABEL maintainer="RoyalityBots"
LABEL description="Auto Emoji Reaction Telegram Bot"
LABEL version="2.0.0"

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

RUN useradd --no-create-home --shell /bin/false botuser \
    && chown -R botuser:botuser /app

USER botuser

EXPOSE 8000

ENV PORT=8000 \
    NODE_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

CMD ["python", "app.py"]

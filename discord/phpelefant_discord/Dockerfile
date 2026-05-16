FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && groupadd --system phpelefant-env \
    && useradd --system --gid phpelefant-env --home-dir /home/phpelefant-env --create-home --shell /bin/sh phpelefant-env \
    && mkdir -p /data \
    && chown phpelefant-env:phpelefant-env /data \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R root:root /app \
    && chmod -R go-w /app

USER phpelefant-env

CMD ["python", "-m", "phpelefant_discord.main"]


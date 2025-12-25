FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.lock requirements.runtime.txt ./
RUN pip3 install -r requirements.runtime.txt -c requirements.lock

COPY . .

RUN mkdir -p downloads data/config data/media data/logs
RUN chmod +x docker/entrypoint.sh docker/healthcheck.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["./docker/healthcheck.sh"]

EXPOSE 10000

CMD ["./docker/entrypoint.sh"]

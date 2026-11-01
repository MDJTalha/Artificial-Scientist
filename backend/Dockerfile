FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    ARTIFICIAL_SCIENTIST_DB_PATH=/app/data/asds.sqlite3

WORKDIR /app

RUN groupadd --system --gid 10001 asds \
    && useradd --system --uid 10001 --gid asds --home-dir /app --shell /usr/sbin/nologin asds \
    && mkdir -p /app/data /tmp/matplotlib \
    && chown -R asds:asds /app /tmp/matplotlib

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER 10001:10001

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"]

CMD ["uvicorn", "artificial_scientist.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /opt/asds

COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && groupadd --gid 10001 asds \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin asds \
    && mkdir -p /var/lib/asds /tmp/matplotlib \
    && chown -R 10001:10001 /var/lib/asds /tmp/matplotlib \
    && chmod 0750 /var/lib/asds

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "artificial_scientist.main:app", "--host", "0.0.0.0", "--port", "8000"]

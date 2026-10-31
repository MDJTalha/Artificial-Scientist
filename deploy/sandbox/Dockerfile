# Fixed allowlist laboratory worker image.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/asds

COPY backend/pyproject.toml backend/README.md /opt/asds/backend/
COPY backend/src /opt/asds/backend/src

RUN useradd --uid 65532 --create-home --shell /usr/sbin/nologin asds \
    && python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir /opt/asds/backend \
    && chown -R 65532:65532 /opt/asds

USER 65532:65532
ENTRYPOINT ["python", "-m", "artificial_scientist.lab.sandbox_worker"]

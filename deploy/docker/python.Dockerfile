FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY market_os ./market_os
COPY apps ./apps

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin marketos \
    && mkdir -p /var/lib/autonomous-market-os/state /var/lib/autonomous-market-os/logs \
    && chown -R marketos:marketos /app /var/lib/autonomous-market-os

USER marketos

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=2).read()"

CMD ["python", "-m", "apps.gateway", "--host", "127.0.0.1", "--port", "8787"]

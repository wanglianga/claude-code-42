# ---------- 构建阶段：安装依赖到独立 venv ----------
FROM python:3.12-slim AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- 运行阶段 ----------
FROM python:3.12-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app

# 非 root 运行
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/uploads \
    && chown -R appuser:appuser /app /data/uploads
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /app

# OS deps if you need to compile wheels (uncomment build-essential if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy code
COPY . .

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Optional Gunicorn config
COPY gunicorn.conf.py /app/gunicorn.conf.py

EXPOSE 8000

# Healthcheck using Python stdlib (no curl dependency)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health/check').status==200 else sys.exit(1)"

# If you don't use a gunicorn.conf.py, see command below for inline flags
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]

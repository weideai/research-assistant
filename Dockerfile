FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system research && useradd --system --gid research --home /app research
COPY requirements.txt requirements-prod.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements-prod.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh /app/scripts/backup.sh && mkdir -p /app/instance/uploads/backgrounds && chown -R research:research /app
USER research

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--workers", "2", "--threads", "2", "--timeout", "60", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "run:app"]

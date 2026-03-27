#!/bin/sh
set -eu

mode="${SERVICE_MODE:-web}"
import_dir="${IMPORT_STORAGE_DIR:-/tmp/valid8_imports}"
logo_dir="${SCHOOL_LOGO_STORAGE_DIR:-/tmp/valid8_school_logos}"

case "$mode" in
  web)
    mkdir -p "$import_dir" "$logo_dir"
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --workers "${UVICORN_WORKERS:-2}" \
      --proxy-headers
    ;;
  worker)
    exec celery -A app.workers.celery_app.celery_app worker --loglevel="${CELERY_LOGLEVEL:-info}"
    ;;
  beat)
    exec celery -A app.workers.celery_app.celery_app beat \
      --loglevel="${CELERY_LOGLEVEL:-info}" \
      --schedule /tmp/celerybeat-schedule
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *)
    echo "Unsupported SERVICE_MODE: $mode" >&2
    exit 1
    ;;
esac

#!/bin/sh
set -eu

# The migration runner records immutable checksums and skips versions already
# applied.  The full chain therefore supports clean installs without replaying
# historical DDL on every container boot.
for migration in /app/migrations/*.sql; do
  case "$migration" in /app/migrations/001_*) continue ;; esac
  python scripts/apply_migration.py "$migration"
done

exec gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 --timeout 120 --graceful-timeout 30 --keep-alive 75

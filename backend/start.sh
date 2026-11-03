#!/usr/bin/env bash
set -euo pipefail

# Render sets PITCHIQ_DATABASE_PATH to the mounted persistent disk. The local
# default keeps this command useful from backend/ during development as well.
export PITCHIQ_DATABASE_PATH="${PITCHIQ_DATABASE_PATH:-data/pitchiq_v2.sqlite3}"

python -m app.ingestion.bootstrap

# Render routes traffic to PORT; local runs fall back to the standard API port.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

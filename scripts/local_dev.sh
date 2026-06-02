#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -e ".[dev]"
[[ -f .env ]] || cp .env.example .env

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

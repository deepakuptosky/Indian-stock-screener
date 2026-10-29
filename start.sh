#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if [ ! -f .venv/installed.ok ]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/installed.ok
fi
exec .venv/bin/python -m streamlit run app.py --server.address localhost --server.port 8501

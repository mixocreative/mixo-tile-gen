#!/usr/bin/env bash
# Command-line tile maker. Example: ./mixo.sh photo.jpg --corners "510,564 2616,534 2514,2508 594,2478" --format 3mftex
PY=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3 || command -v python)
exec "$PY" "$(dirname "$0")/scripts/mixo.py" "$@"

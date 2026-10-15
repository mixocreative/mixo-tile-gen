#!/usr/bin/env bash
# Run mixo-tile-gen on this computer.   ./start-mac-linux.sh          (this computer)
#                                       ./start-mac-linux.sh phone    (+ QR code for your phone)
cd "$(dirname "$0")"
PY=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "Python is not installed. Get it from https://www.python.org/downloads/ and run this again."
  exit 1
fi
if [ "$1" = "phone" ]; then exec "$PY" scripts/run_local.py --phone; else exec "$PY" scripts/run_local.py; fi

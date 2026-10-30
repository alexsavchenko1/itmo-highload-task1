#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bash check-stage3.sh
python3 scripts/check_stage4.py

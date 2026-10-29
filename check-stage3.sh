#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Проверяет уже запущенный Compose-стек, не меняя его состояние.
BASE=http://127.0.0.1:8080 EXPECTED_POD=pod-1 EXPECTED_DC=dc-a bash check-stage2.sh
BASE=http://127.0.0.1:8081 EXPECTED_POD=pod-2 EXPECTED_DC=dc-b bash check-stage2.sh

python3 scripts/check_stage3.py

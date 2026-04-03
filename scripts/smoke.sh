#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=src

python -m lucifer_runtime.cli commands >/dev/null
python -m lucifer_runtime.cli write smoke.txt "hello from smoke" >/dev/null
python -m lucifer_runtime.cli read smoke.txt >/dev/null
python -m lucifer_runtime.cli state >/dev/null
python -m lucifer_runtime.cli info >/dev/null
python -m lucifer_runtime.cli doctor >/dev/null
python -m lucifer_runtime.cli bench >/dev/null
python -m lucifer_runtime.cli self-improve analyze >/dev/null
python -m lucifer_runtime.cli trace --output smoke_trace.html >/dev/null

echo "smoke ok"

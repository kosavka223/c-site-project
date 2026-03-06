#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-10000}"

# Находим backend (где лежит wsgi.py), который создал render-build.sh
BACKEND_DIR=$(python - <<'PY'
import os
candidates=[]
for root, dirs, files in os.walk("appsrc"):
    if "wsgi.py" in files:
        candidates.append(root)
candidates.sort(key=len)
print(candidates[0] if candidates else "")
PY
)

if [ -z "$BACKEND_DIR" ]; then
  echo "ERROR: backend with wsgi.py not found. Build step probably failed."
  exit 1
fi

echo "==> Starting gunicorn from: $BACKEND_DIR"
exec gunicorn --chdir "$BACKEND_DIR" --bind "0.0.0.0:${PORT}" --workers 2 wsgi:app

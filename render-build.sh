#!/usr/bin/env bash
set -euo pipefail

ZIP_NAME="gen.zip"   # <-- поменяй на gen.zip если переименовал

echo "==> Extract $ZIP_NAME to ./appsrc"
rm -rf appsrc
mkdir -p appsrc

# Распаковка через Python (на Render Python точно есть)
python - <<PY
import zipfile
zf = zipfile.ZipFile("$ZIP_NAME")
zf.extractall("appsrc")
print("Extracted:", len(zf.namelist()), "files")
PY

echo "==> Override frontend if frontend_override/index.html exists"
if [ -f "frontend_override/index.html" ]; then
  FRONT_INDEX=$(python - <<'PY'
import os
candidates=[]
for root, dirs, files in os.walk("appsrc"):
    if root.endswith("frontend") and "index.html" in files:
        candidates.append(os.path.join(root, "index.html"))
candidates.sort(key=len)
print(candidates[0] if candidates else "")
PY
)
  if [ -n "$FRONT_INDEX" ]; then
    cp "frontend_override/index.html" "$FRONT_INDEX"
    echo "==> Frontend overridden: $FRONT_INDEX"
  else
    echo "WARNING: frontend/index.html not found inside zip"
  fi
fi

echo "==> Find requirements.txt inside zip"
REQ=$(python - <<'PY'
import os
candidates=[]
for root, dirs, files in os.walk("appsrc"):
    if "requirements.txt" in files:
        candidates.append(os.path.join(root, "requirements.txt"))
candidates.sort(key=len)
print(candidates[0] if candidates else "")
PY
)

if [ -z "$REQ" ]; then
  echo "ERROR: requirements.txt not found inside zip"
  echo "Open the zip on your PC and make sure backend/requirements.txt exists."
  exit 1
fi

BACKEND_DIR=$(dirname "$REQ")
echo "==> Backend directory: $BACKEND_DIR"

echo "==> Install deps + gunicorn"
python -m pip install --upgrade pip
python -m pip install -r "$REQ" gunicorn

echo "==> Create wsgi.py (entrypoint for gunicorn) + serve frontend on /"
python - <<PY
from pathlib import Path

backend = Path("$BACKEND_DIR").resolve()

# ищем frontend/index.html рядом или уровнем выше
frontend_candidates = [
    backend.parent / "frontend",
    backend.parent.parent / "frontend",
    backend.parent.parent.parent / "frontend",
]
frontend = None
for c in frontend_candidates:
    if (c / "index.html").exists():
        frontend = c
        break

wsgi = backend / "wsgi.py"

# wsgi делает две вещи:
# 1) запускает Flask app (через create_app() или app)
# 2) отдаёт index.html по "/"
wsgi.write_text(f'''
from pathlib import Path
from flask import send_from_directory

try:
    from app import create_app
    app = create_app()
except Exception:
    # если в app.py сразу app = Flask(...)
    from app import app

FRONTEND_DIR = Path(r"{frontend if frontend else backend}").resolve()

@app.get("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")
''')

print("Created", wsgi)
PY

echo "==> Build done"

#!/bin/bash
# Double-click this file to start Sift. Keep the window open while you use it.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
echo "Starting Sift..."

pause_exit() { echo; read -r -p "Press Enter to close this window."; exit 1; }

if [ ! -x .venv/bin/python ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "Sift needs Python 3.10 or newer."
    echo "Install it from https://www.python.org/downloads/ and then double-click this file again."
    pause_exit
  fi
  echo "First-time setup. This takes a minute or two..."
  "$PY" -m venv .venv && .venv/bin/pip install -q -r requirements.txt || {
    echo "Setup didn't finish. Please send a screenshot of this window to your IT contact."; pause_exit; }
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Sift needs Node.js."
  echo "Install the LTS version from https://nodejs.org and then double-click this file again."
  pause_exit
fi

.venv/bin/python start.py --build --open || pause_exit

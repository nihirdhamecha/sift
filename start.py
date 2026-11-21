"""Start Sift: FastAPI backend (:8000) + Vite frontend (:5173) with one command.

    python start.py            # dev: open http://localhost:5173
    python start.py --build    # build the frontend and serve everything from :8000
    python start.py --build --open   # what "Start Sift.command" runs: also opens the browser

The API is api/index.py, the same stateless app Vercel runs.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"


def load_env() -> None:
    """Load KEY=VALUE lines from .env. The key stays in the server process only."""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip().removeprefix("export ").strip(), v.strip().strip("\"'"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="serve a production build from :8000")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the browser when ready")
    args = ap.parse_args()

    if _alive(f"http://127.0.0.1:{args.port}/api/health"):
        url = f"http://localhost:{args.port}" if args.build else "http://localhost:5173"
        print(f"Sift is already running at {url}")
        if args.open:
            webbrowser.open(url)
        return

    try:
        import fastapi, uvicorn  # noqa: F401, E401
        import multipart  # noqa: F401
    except ImportError:
        sys.exit("Missing Python deps. Run: pip install -r requirements.txt")
    npm = shutil.which("npm")
    if not npm:
        sys.exit("Node.js (npm) is required for the frontend: https://nodejs.org")

    load_env()
    if not (WEB / "node_modules").exists():
        print("Installing frontend dependencies (first run)...")
        subprocess.check_call([npm, "install", "--no-audit", "--no-fund"], cwd=WEB)

    key, pw = os.environ.get("TYPESAFE_API_KEY"), os.environ.get("DEMO_PASSWORD")
    print(f"TYPESAFE_API_KEY: {'set' if key else 'NOT set'} · DEMO_PASSWORD: {'set' if pw else 'NOT set'}")
    if not (key and pw):
        print("Real scores need both in .env. Until then Sift runs with MOCK scores.")

    procs: list[subprocess.Popen] = []
    api_cmd = [sys.executable, "-m", "uvicorn", "api.index:app", "--host", "127.0.0.1",
               "--port", str(args.port), "--no-access-log"]
    if args.build:
        subprocess.check_call([npm, "run", "build"], cwd=WEB)
        url = f"http://localhost:{args.port}"
    else:
        api_cmd.append("--reload")
        procs.append(subprocess.Popen([npm, "run", "dev", "--", "--host", "127.0.0.1"], cwd=WEB))
        url = "http://localhost:5173"
    procs.append(subprocess.Popen(api_cmd, cwd=ROOT))
    for _ in range(120):  # wait until the server answers, then open the browser
        if _alive(f"http://127.0.0.1:{args.port}/api/health"):
            break
        time.sleep(0.5)
    print(f"\nSift is running at {url}\nKeep this window open while you use it. Close it (or press Ctrl+C) to stop.\n")
    if args.open:
        webbrowser.open(url)

    def stop(*_):
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while all(p.poll() is None for p in procs):
        time.sleep(0.5)
    stop()


def _alive(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    main()

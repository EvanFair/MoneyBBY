"""
AIPulse — app.py
Run this to start the web server: python app.py
Then open http://localhost:8000 in your browser.
"""
import os
import sys
import subprocess
import webbrowser
import time

# ── Resolve paths ─────────────────────────────────────────────────────────────
ROOT_DIR    = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
SRC_DIR     = os.path.join(BACKEND_DIR, "src")
VENV_DIR    = os.path.join(BACKEND_DIR, "venv")

HOST = "127.0.0.1"
PORT = 8000

# ── Find Python / uvicorn ─────────────────────────────────────────────────────
def find_python():
    candidates = [
        os.path.join(VENV_DIR, "Scripts", "python.exe"),   # Windows venv
        os.path.join(VENV_DIR, "bin", "python"),            # Unix venv
        os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe"),
        os.path.join(BACKEND_DIR, ".venv", "bin", "python"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return sys.executable  # fall back to whatever python is running this file


def find_uvicorn(python_exe):
    """Return uvicorn path next to the python exe, or None."""
    scripts_dir = os.path.dirname(python_exe)
    for name in ("uvicorn.exe", "uvicorn"):
        path = os.path.join(scripts_dir, name)
        if os.path.exists(path):
            return path
    return None


# ── Auto-install dependencies if needed ───────────────────────────────────────
def ensure_deps(python_exe):
    req = os.path.join(BACKEND_DIR, "requirements.txt")
    if not os.path.exists(req):
        return
    try:
        import importlib
        # Quick check: if fastapi and uvicorn are importable we're good
        result = subprocess.run(
            [python_exe, "-c", "import fastapi, uvicorn"],
            capture_output=True
        )
        if result.returncode == 0:
            return
        print("Installing dependencies from requirements.txt ...")
        subprocess.run(
            [python_exe, "-m", "pip", "install", "-r", req, "--quiet"],
            check=True
        )
        print("Dependencies installed.\n")
    except Exception as e:
        print(f"Warning: could not auto-install deps: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  AIPulse — Starting server")
    print("=" * 60)

    python_exe = find_python()
    print(f"  Python  : {python_exe}")

    ensure_deps(python_exe)

    uvicorn_exe = find_uvicorn(python_exe)

    # Build the launch command
    if uvicorn_exe:
        cmd = [uvicorn_exe, "src.server:app"]
    else:
        cmd = [python_exe, "-m", "uvicorn", "src.server:app"]

    cmd += [
        "--host", HOST,
        "--port", str(PORT),
        "--reload",              # auto-reload on code changes
    ]

    url = f"http://{HOST}:{PORT}"
    print(f"  URL     : {url}")
    print(f"  Command : {' '.join(cmd)}")
    print()
    print("  Opening browser in 2 seconds... (Ctrl+C to stop)")
    print("=" * 60)

    # Launch the server as a subprocess from the backend directory
    env = os.environ.copy()
    # Ensure src/ is on PYTHONPATH so imports work
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.Popen(cmd, cwd=BACKEND_DIR, env=env)

    # Give the server a moment then open the browser
    time.sleep(2)
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print(f"\n  Server running at {url}")
    print("  Press Ctrl+C to stop.\n")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        proc.terminate()
        proc.wait()
        print("  Stopped.")


if __name__ == "__main__":
    main()

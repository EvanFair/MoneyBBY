import subprocess
import webbrowser
import threading
import time
import os

def open_browser():
    time.sleep(3)
    webbrowser.open("http://localhost:8000")

# Start browser opener in background
threading.Thread(target=open_browser, daemon=True).start()

# Start the server
src_dir = os.path.join(os.path.dirname(__file__), "backend", "src")
subprocess.run(
    ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
    cwd=src_dir
)

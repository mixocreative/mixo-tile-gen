"""Run the whole mixo-tile-gen app (website + engine) on this computer.

    python scripts/run_local.py           # this computer only
    python scripts/run_local.py --phone   # also a free Cloudflare link + QR code for your phone

First run creates .venv and installs the engine's packages (a few minutes, ~400 MB).
Press Ctrl+C (or close the window) to stop everything.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND, FRONTEND, TOOLS = ROOT / "backend", ROOT / "frontend", ROOT / "tools"
VENV = ROOT / ".venv"
REQS = BACKEND / "requirements.txt"
CF_BASE = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def say(msg: str) -> None:
    print(f"[mixo] {msg}", flush=True)


def fail(msg: str) -> None:
    say("ERROR: " + msg)
    sys.exit(1)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_env() -> Path:
    if sys.version_info < (3, 11):
        fail(f"Python 3.11 or newer is needed (this is {platform.python_version()}). "
             "Get it from https://www.python.org/downloads/")
    py = venv_python()
    if not py.exists():
        say("First run: creating a private Python environment in .venv ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    stamp = VENV / ".reqs-installed"
    want = hashlib.sha256(REQS.read_bytes()).hexdigest()
    if not stamp.exists() or stamp.read_text().strip() != want:
        say("Installing the engine's packages (first run only, a few minutes) ...")
        reqs = REQS
        if sys.version_info >= (3, 14):                # pinned wheels stop at 3.13: let pip pick newer builds
            reqs = VENV / "requirements-relaxed.txt"
            reqs.write_text(REQS.read_text().replace("==", ">="))
        subprocess.check_call([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q",
                               "-r", str(reqs)])
        stamp.write_text(want)
    return py


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_health(url: str, proc: subprocess.Popen, secs: int = 120) -> None:
    t0 = time.time()
    while time.time() - t0 < secs:
        if proc.poll() is not None:
            fail("the engine stopped while starting (see the messages above).")
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            pass
        time.sleep(1)
    fail("the engine did not start within 2 minutes.")


def lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))           # no packet is sent; just picks the outgoing interface
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def cloudflared() -> str:
    found = shutil.which("cloudflared")
    if found:
        return found
    TOOLS.mkdir(exist_ok=True)
    system, machine = platform.system(), platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
    exe = TOOLS / ("cloudflared.exe" if system == "Windows" else "cloudflared")
    if exe.exists():
        return str(exe)
    say("Downloading Cloudflare's free tunnel tool (one time, ~40 MB) ...")
    if system == "Windows":
        urllib.request.urlretrieve(CF_BASE + f"cloudflared-windows-{arch}.exe", exe)
    elif system == "Darwin":
        tgz = TOOLS / "cloudflared.tgz"
        urllib.request.urlretrieve(CF_BASE + f"cloudflared-darwin-{arch}.tgz", tgz)
        with tarfile.open(tgz) as t:
            t.extract("cloudflared", TOOLS)
        tgz.unlink()
    else:
        urllib.request.urlretrieve(CF_BASE + f"cloudflared-linux-{arch}", exe)
    exe.chmod(0o755)
    return str(exe)


def start_tunnel(port: int) -> tuple[subprocess.Popen, str]:
    proc = subprocess.Popen([cloudflared(), "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace")
    found: list[str] = []

    def read() -> None:                              # keep draining the log so the tunnel never blocks
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not found:
                found.append(m.group(0))

    threading.Thread(target=read, daemon=True).start()
    t0 = time.time()
    while not found and time.time() - t0 < 60:
        if proc.poll() is not None:
            fail("the Cloudflare tunnel stopped. Check your internet connection and try again.")
        time.sleep(0.5)
    if not found:
        fail("no tunnel address after 60 s. Try again in a minute.")
    return proc, found[0]


def phone_page(links: list[tuple[str, str]]) -> Path:
    TOOLS.mkdir(exist_ok=True)
    blocks = "".join(
        f'<section><h2>{title}</h2><div class="qr" data-url="{url}"></div><p><a href="{url}">{url}</a></p></section>'
        for title, url in links)
    page = TOOLS / "phone.html"
    page.write_text(f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>mixo-tile-gen on your phone</title>
<style>body{{font:15px system-ui,sans-serif;background:#faf8f5;color:#1c1a17;margin:0;padding:24px;text-align:center}}
section{{display:inline-block;margin:12px;padding:16px;background:#fff;border:1px solid #e6e1da;border-radius:8px;vertical-align:top}}
h2{{font-size:15px;margin:0 0 12px}} .qr{{display:inline-block}} p{{max-width:260px;word-break:break-all;font-size:12px}}</style>
<h1 style="font-size:18px">Scan with your phone's camera</h1>{blocks}
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script>document.querySelectorAll('.qr').forEach(e=>new QRCode(e,{{text:e.dataset.url,width:220,height:220}}))</script>
""", encoding="utf-8")
    return page


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", action="store_true", help="also make a free Cloudflare link + QR code for phones")
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    py = ensure_env()
    if not port_free(a.port):
        fail(f"port {a.port} is busy (is mixo-tile-gen already running?). Close it or use --port 8090.")
    env = dict(os.environ, FRONTEND_DIR=str(FRONTEND), ALLOWED_ORIGINS="*", PYTHONUNBUFFERED="1")
    say("Starting the engine ...")
    engine = subprocess.Popen([str(py), "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(a.port),
                               "--workers", "1", "--log-level", "warning"], cwd=BACKEND, env=env)
    procs = [engine]
    try:
        local = f"http://localhost:{a.port}"
        wait_health(local, engine)
        app_url = local + "/?api=self"
        print()
        say(f"READY  ->  open {app_url}")
        if not a.no_browser:
            webbrowser.open(app_url)
        if a.phone:
            links = []
            ip = lan_ip()
            if ip:
                links.append(("Same Wi-Fi (fastest)", f"http://{ip}:{a.port}/?api=self"))
            say("Opening a free Cloudflare tunnel for your phone ...")
            tunnel, pub = start_tunnel(a.port)
            procs.append(tunnel)
            links.append(("Anywhere (Cloudflare link)", pub + "/?api=self"))
            for title, url in links:
                say(f"PHONE  {title}:  {url}")
            say("The Cloudflare link is public while this window is open; it changes every run.")
            page = phone_page(links)
            if not a.no_browser:
                webbrowser.open(page.as_uri())
        print()
        say("Keep this window open while you use the app. Press Ctrl+C to stop.")
        while engine.poll() is None:
            time.sleep(1)
        fail("the engine stopped.")
    except KeyboardInterrupt:
        say("Stopping ...")
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()

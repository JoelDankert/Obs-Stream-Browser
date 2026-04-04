#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
import subprocess
import os
import json
import threading
from collections import deque
import re
from pathlib import Path

RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"

BASE = os.path.dirname(os.path.abspath(__file__))
HOSTCONTROL_DIR = os.path.join(BASE, "hostcontrol")
RUNTIME_DIR = os.path.join(BASE, "runtime")
ALLOWLIST_PATH = os.path.join(RUNTIME_DIR, "access.json")
LOCALHOST_IPS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
SHOUT_DURATION_PER_CHAR_MS = 120
SHOUT_DURATION_MIN_MS = 2500
SHOUT_DURATION_MAX_MS = 9000
IMAGE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
DATA_IMAGE_RE = re.compile(r"^data:image/", re.IGNORECASE)


def load_access_config():
    try:
        data = json.loads(Path(ALLOWLIST_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"mode": "all", "ips": []}
    except Exception as exc:
        print(f"{RED}[WARN] Failed to load access config: {exc}{RESET}")
        return {"mode": "all", "ips": []}

    mode = data.get("mode")
    ips = data.get("ips")
    if mode not in {"all", "restricted"} or not isinstance(ips, list):
        print(f"{RED}[WARN] Invalid access config, defaulting to allow all{RESET}")
        return {"mode": "all", "ips": []}
    return {"mode": mode, "ips": [str(ip) for ip in ips]}


ACCESS_CONFIG = load_access_config()


def run_script(name):
    path = os.path.join(HOSTCONTROL_DIR, name)
    if os.path.exists(path):
        subprocess.run([path])
    else:
        print(f"{RED}[WARN] Script not found: {path}{RESET}")


def run_shout(message: str, duration_ms: int):
    path = os.path.join(HOSTCONTROL_DIR, "shout.sh")
    if os.path.exists(path):
        env = os.environ.copy()
        env["DURATION_MS"] = str(duration_ms)
        subprocess.run([path, message], env=env, check=False)
    else:
        print(f"{RED}[WARN] Shout script not found: {path}{RESET}")

def play_named_sound(name: str):
    path = os.path.join(HOSTCONTROL_DIR, "play_sound.sh")
    if os.path.exists(path):
        res = subprocess.run([path, f"{name}.*"], check=False)
        if res.returncode != 0:
            print(f"{RED}[WARN] play_sound.sh failed for: {name}{RESET}")
    else:
        print(f"{RED}[WARN] play_sound.sh not found: {path}{RESET}")

# Simple shout queue to serialize overlays
shout_queue = deque()
shout_cv = threading.Condition()
shout_stop = threading.Event()

# Track perceived online clients by IP (best-effort)
presence_ips = set()
presence_lock = threading.Lock()


def shout_worker():
    while not shout_stop.is_set():
        with shout_cv:
            while not shout_queue and not shout_stop.is_set():
                shout_cv.wait()
            if shout_stop.is_set():
                break
            message, duration_ms = shout_queue.popleft()
        try:
            run_shout(message, duration_ms)
        except Exception as e:
            print(f"{RED}[WARN] shout error: {e}{RESET}")


class Handler(SimpleHTTPRequestHandler):

    def _safe_write(self, payload: bytes):
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _ip_allowed(self):
        ip = self.client_address[0]
        if ip in LOCALHOST_IPS:
            return True
        if ACCESS_CONFIG["mode"] == "all":
            return True
        return ip in set(ACCESS_CONFIG["ips"])

    def _deny_access(self):
        ip = self.client_address[0]
        wants_html = "text/html" in self.headers.get("Accept", "") or self.path == "/"
        message = "access denied"
        detail = "ask the host to add you to the stream allow list"

        self.send_response(403)
        if wants_html:
            body = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>access denied</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #000;
        color: #fff;
        font: 16px/1.5 sans-serif;
      }
      main {
        min-width: 220px;
        max-width: 24rem;
        padding: 18px 20px 16px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.16);
        background: rgba(18, 18, 18, 0.94);
        text-align: center;
        box-shadow: 0 18px 60px rgba(0, 0, 0, 0.35);
      }
      .spinner {
        width: 28px;
        height: 28px;
        margin: 0 auto 12px;
        border-radius: 999px;
        border: 2px solid rgba(255, 255, 255, 0.18);
        border-top-color: #fff;
        animation: spin 0.85s linear infinite;
      }
      p {
        color: rgba(255, 255, 255, 0.82);
        margin: 8px 0 0;
        font-size: 13px;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
    </style>
  </head>
  <body>
    <main>
      <div class="spinner" aria-hidden="true"></div>
      <p>access denied</p>
    </main>
  </body>
</html>
"""
            payload = body.encode("utf-8")
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            payload = f"{message}\n{detail}".encode("utf-8")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self._safe_write(payload)
        print(f"{RED}[ACCESS] Denied {ip} for {self.path}{RESET}")

    # Deny directory listings and noisy logs from default
    def log_message(self, format, *args):
        return

    # Restrict POST endpoints
    def do_POST(self):
        try:
            if not self._ip_allowed():
                self._deny_access()
                return

            ip_suffix = self.client_address[0].split(".")[-1] if "." in self.client_address[0] else self.client_address[0]

            mapping = {
                "/space": "space.sh",
                "/left":  "left.sh",
                "/right": "right.sh",
                "/up":    "up.sh",
                "/down":  "down.sh"
            }

            if self.path == "/shout":
                self._handle_shout()
                return
            if self.path == "/presence":
                self._handle_presence()
                return

            if self.path in mapping:
                print(f"{BLUE}{ip_suffix}: sent request at {self.path}{RESET}")
                run_script(mapping[self.path])
                self.send_response(200)
                self.end_headers()
                self._safe_write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            return

    # Restrict GET requests (serving index.html and assets)
    def do_GET(self):
        try:
            if not self._ip_allowed():
                self._deny_access()
                return

            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            if self.path == "/soundlist":
                self._handle_soundlist()
                return

            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            return

    # Keep file serving inside ./stream
    def translate_path(self, path):
        if path == "/":
            return os.path.join(BASE, "stream", "index.html")
        return os.path.join(BASE, "stream", path.lstrip("/"))

    def _handle_shout(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self.send_response(400)
            self.end_headers()
            return

        try:
            raw = self.rfile.read(length)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        message = data.get("message", "")
        if not isinstance(message, str):
            self.send_response(400)
            self.end_headers()
            return

        sanitized = " ".join(message.strip().split())
        if not sanitized:
            self.send_response(400)
            self.end_headers()
            return

        if sanitized.startswith("#"):
            sound = sanitized[1:].strip()
            if not sound:
                self.send_response(400)
                self.end_headers()
                return
            ip_suffix = self.client_address[0].split(".")[-1] if "." in self.client_address[0] else self.client_address[0]
            print(f"{MAGENTA}{ip_suffix}: #{sound}{RESET}")
            play_named_sound(sound)
            self.send_response(200)
            self.end_headers()
            self._safe_write(b"OK")
            return
        if DATA_IMAGE_RE.match(sanitized):
            final_msg = sanitized
        elif IMAGE_URL_RE.match(sanitized):
            final_msg = sanitized
        elif sanitized.startswith("."):
            final_msg = sanitized[1:].lstrip()
        else:
            final_msg = sanitized.upper()

        if not final_msg:
            self.send_response(400)
            self.end_headers()
            return

        duration_ms = 3000

        ip_suffix = self.client_address[0].split(".")[-1] if "." in self.client_address[0] else self.client_address[0]
        print(f"{MAGENTA}{ip_suffix}: {final_msg}{RESET}")
        with shout_cv:
            shout_queue.append((final_msg, duration_ms))
            shout_cv.notify()

        self.send_response(200)
        self.end_headers()
        self._safe_write(b"OK")

    def _handle_presence(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = b""
        if length > 0:
            try:
                body = self.rfile.read(length)
            except Exception:
                body = b""
        event = "unknown"
        if body:
            try:
                data = json.loads(body.decode("utf-8"))
                event = data.get("event", event)
            except Exception:
                pass
        ip = self.client_address[0]
        ip_label = ip.split(".")[-1] if "." in ip else ip
        with presence_lock:
            if event == "join":
                was_present = ip in presence_ips
                presence_ips.add(ip)
            elif event == "leave":
                was_present = ip in presence_ips
                presence_ips.discard(ip)
            else:
                was_present = ip in presence_ips
        if event == "join" and not was_present:
            print(f"{YELLOW}{ip_label}: connected{RESET}")
        elif event == "leave" and was_present:
            print(f"{YELLOW}{ip_label}: disconnected{RESET}")
        self.send_response(200)
        self.end_headers()
        self._safe_write(b"OK")

    def _handle_soundlist(self):
        sounds_dir = os.path.join(HOSTCONTROL_DIR, "sounds")
        trimmed_dir = os.path.join(sounds_dir, "trimmed")
        base_dir = trimmed_dir if os.path.isdir(trimmed_dir) else sounds_dir
        names = []
        try:
            for fname in os.listdir(base_dir):
                path = os.path.join(base_dir, fname)
                if not os.path.isfile(path):
                    continue
                if fname.startswith("."):
                    continue
                stem, ext = os.path.splitext(fname)
                if not stem:
                    continue
                names.append(stem)
        except Exception:
            names = []

        unique = sorted(set(names))
        body = json.dumps({"sounds": unique}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._safe_write(body)


if __name__ == "__main__":
    worker = threading.Thread(target=shout_worker, daemon=True)
    worker.start()

    server = HTTPServer(("0.0.0.0", 8090), Handler)
    print(f"{GREEN}Server running on port 8090{RESET}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{GREEN}Shutting down...{RESET}")
    finally:
        shout_stop.set()
        with shout_cv:
            shout_cv.notify_all()
        worker.join(timeout=2)
        server.server_close()

#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
import subprocess
import os
import json
import threading
from collections import deque
import re

BASE = os.path.dirname(os.path.abspath(__file__))
HOSTCONTROL_DIR = os.path.join(BASE, "hostcontrol")

ALLOWED_SUBNET = "10.66.66."   # Only allow WireGuard clients
SHOUT_DURATION_PER_CHAR_MS = 120
SHOUT_DURATION_MIN_MS = 2500
SHOUT_DURATION_MAX_MS = 9000
IMAGE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def run_script(name):
    path = os.path.join(HOSTCONTROL_DIR, name)
    if os.path.exists(path):
        subprocess.run([path])
    else:
        print(f"[WARN] Script not found: {path}")


def run_shout(message: str, duration_ms: int):
    path = os.path.join(HOSTCONTROL_DIR, "shout.sh")
    if os.path.exists(path):
        env = os.environ.copy()
        env["DURATION_MS"] = str(duration_ms)
        subprocess.run([path, message], env=env, check=False)
    else:
        print(f"[WARN] Shout script not found: {path}")


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
            print(f"[WARN] shout error: {e}")


class Handler(SimpleHTTPRequestHandler):

    # Check if client IP starts with 10.66.66.
    def _ip_allowed(self):
        ip = self.client_address[0]
        return ip.startswith(ALLOWED_SUBNET)

    # Deny directory listings and noisy logs from default
    def log_message(self, format, *args):
        return

    # Restrict POST endpoints
    def do_POST(self):
        if not self._ip_allowed():
            self.send_response(403)
            self.end_headers()
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
            print(f"{ip_suffix}: sent request at {self.path}")
            run_script(mapping[self.path])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    # Restrict GET requests (serving index.html and assets)
    def do_GET(self):
        if not self._ip_allowed():
            self.send_response(403)
            self.end_headers()
            return

        super().do_GET()

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

        if IMAGE_URL_RE.match(sanitized):
            final_msg = sanitized
        elif sanitized.startswith("."):
            final_msg = sanitized[1:].lstrip()
        else:
            final_msg = sanitized.upper()

        if not final_msg:
            self.send_response(400)
            self.end_headers()
            return

        duration_ms = 5000

        ip_suffix = self.client_address[0].split(".")[-1] if "." in self.client_address[0] else self.client_address[0]
        print(f"{ip_suffix}: sent request at /shout")
        print(f"{ip_suffix}: {final_msg}")
        with shout_cv:
            shout_queue.append((final_msg, duration_ms))
            shout_cv.notify()

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def _handle_presence(self):
        return
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
        last_octet = ip.split(".")[-1] if "." in ip else ip
        with presence_lock:
            if event == "join":
                presence_ips.add(ip)
            elif event == "leave":
                presence_ips.discard(ip)
            count = len(presence_ips)
            octets = [p.split(".")[-1] if "." in p else p for p in sorted(presence_ips)]
            current_ips = ", ".join(octets)
        print(f"{ip} {event}")
        print(f"online: {count} [{current_ips}]")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


if __name__ == "__main__":
    worker = threading.Thread(target=shout_worker, daemon=True)
    worker.start()

    server = HTTPServer(("0.0.0.0", 8090), Handler)
    print("Server running on port 8090 (WireGuard-only)...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        shout_stop.set()
        with shout_cv:
            shout_cv.notify_all()
        worker.join(timeout=2)
        server.server_close()

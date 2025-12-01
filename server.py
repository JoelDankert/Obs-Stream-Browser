#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
import subprocess
import os

BASE = os.path.dirname(os.path.abspath(__file__))
HOSTCONTROL_DIR = os.path.join(BASE, "hostcontrol")

ALLOWED_SUBNET = "10.66.66."   # Only allow WireGuard clients


def run_script(name):
    path = os.path.join(HOSTCONTROL_DIR, name)
    if os.path.exists(path):
        subprocess.run([path])
    else:
        print(f"[WARN] Script not found: {path}")


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

        mapping = {
            "/space": "space.sh",
            "/left":  "left.sh",
            "/right": "right.sh",
            "/up":    "up.sh",
            "/down":  "down.sh"
        }

        if self.path in mapping:
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


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8090), Handler)
    print("Server running on port 8090 (WireGuard-only)...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()

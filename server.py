#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
import subprocess
import os

BASE = os.path.dirname(os.path.abspath(__file__))
HOSTCONTROL_DIR = os.path.join(BASE, "hostcontrol")


def run_script(name):
    path = os.path.join(HOSTCONTROL_DIR, name)
    if os.path.exists(path):
        subprocess.run([path])
    else:
        print(f"[WARN] Script not found: {path}")


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
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

    def translate_path(self, path):
        if path == "/":
            return os.path.join(BASE, "stream", "index.html")
        return os.path.join(BASE, "stream", path.lstrip("/"))


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8090), Handler)
    print("Server running on port 8090...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()

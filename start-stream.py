#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUNTIME_DIR = BASE / "runtime"
ACCESS_PATH = RUNTIME_DIR / "access.json"
MEDIA_TEMPLATE_PATH = BASE / "mediamtx.yml"
MEDIA_RUNTIME_PATH = RUNTIME_DIR / "mediamtx.generated.yml"
SUBNET_PREFIX = "10.66.66."
LOCALHOST_IPS = ["127.0.0.1", "::1"]


def parse_allowed_hosts(raw_value: str):
    raw_value = raw_value.strip()
    if not raw_value:
        return None

    host_numbers = {1}
    for token in raw_value.split():
        try:
            host = int(token)
        except ValueError:
            raise ValueError(f"Invalid host number: {token!r}") from None
        if host < 1 or host > 254:
            raise ValueError(f"Host number out of range 1-254: {host}")
        host_numbers.add(host)
    return sorted(host_numbers)


def build_ip_list(host_numbers):
    if host_numbers is None:
        return []
    return [f"{SUBNET_PREFIX}{host}" for host in host_numbers]


def render_mediamtx_config(allowed_ips):
    template = MEDIA_TEMPLATE_PATH.read_text(encoding="utf-8")
    quoted_ips = ", ".join(f"'{ip}'" for ip in [*LOCALHOST_IPS, *allowed_ips])
    replacement = f"  ips: [{quoted_ips}]" if allowed_ips else "  ips: []"
    marker = "  ips: []"
    if marker not in template:
        raise RuntimeError("Could not find default authInternalUsers ips entry in mediamtx.yml")
    return template.replace(marker, replacement, 1)


def write_runtime_files(host_numbers):
    RUNTIME_DIR.mkdir(exist_ok=True)
    allowed_ips = build_ip_list(host_numbers)
    mode = "all" if host_numbers is None else "restricted"
    access_payload = {
        "mode": mode,
        "ips": allowed_ips,
        "hosts": [] if host_numbers is None else host_numbers,
        "subnetPrefix": SUBNET_PREFIX,
    }
    ACCESS_PATH.write_text(json.dumps(access_payload, indent=2) + "\n", encoding="utf-8")
    MEDIA_RUNTIME_PATH.write_text(render_mediamtx_config(allowed_ips), encoding="utf-8")
    return allowed_ips


def require_command(name: str):
    if shutil.which(name):
        return
    print(f"Missing required command: {name}", file=sys.stderr)
    sys.exit(1)


def open_terminal(title: str, command: str):
    subprocess.Popen(
        [
            "alacritty",
            "--title",
            title,
            "-e",
            "bash",
            "-lc",
            command,
        ],
        cwd=BASE,
    )


def main():
    require_command("alacritty")
    require_command("python3")

    while True:
        try:
            print("Allowed hosts in 10.66.66.x")
            raw_value = input()
            host_numbers = parse_allowed_hosts(raw_value)
            break
        except ValueError as exc:
            print(exc, file=sys.stderr)

    allowed_ips = write_runtime_files(host_numbers)

    if host_numbers is None:
        print("Access: all IPs allowed")
    else:
        print("Access:", " ".join(str(host) for host in host_numbers))
        print("Allowed IPs:", ", ".join(allowed_ips))

    server_command = (
        "echo 'Starting server.py...'; "
        "python3 server.py; "
        "status=$?; "
        "echo; "
        "echo \"server.py exited with status $status. Press Enter to close.\"; "
        "read"
    )
    mediamtx_command = (
        "echo 'Starting MediaMTX...'; "
        f"./mediamtx {MEDIA_RUNTIME_PATH}; "
        "status=$?; "
        "echo; "
        "echo \"MediaMTX exited with status $status. Press Enter to close.\"; "
        "read"
    )

    open_terminal("HostControl Server", server_command)
    open_terminal("MediaMTX", mediamtx_command)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()

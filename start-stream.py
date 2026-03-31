#!/usr/bin/env python3

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUNTIME_DIR = BASE / "runtime"
ACCESS_PATH = RUNTIME_DIR / "access.json"
MEDIA_TEMPLATE_PATH = BASE / "mediamtx.yml"
MEDIA_RUNTIME_PATH = RUNTIME_DIR / "mediamtx.generated.yml"
SUBNET_PREFIX = "10.66.66."
LOCALHOST_IPS = ["127.0.0.1", "::1"]
MEDIAMTX_IGNORED_WARNINGS = (
    "reader is too slow, discarding",
)


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
    template = template.replace("logLevel: info", "logLevel: warn", 1)
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


def stream_output(process: subprocess.Popen[str], ignored_substrings: tuple[str, ...] = ()):
    assert process.stdout is not None
    for line in process.stdout:
        stripped = line.rstrip()
        if ignored_substrings and any(token in stripped for token in ignored_substrings):
            continue
        print(stripped)


def stop_process(process: subprocess.Popen[str]):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_processes():
    server_process = subprocess.Popen(
        ["python3", "-u", "server.py"],
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    mediamtx_process = subprocess.Popen(
        ["./mediamtx", str(MEDIA_RUNTIME_PATH)],
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    threads = [
        threading.Thread(target=stream_output, args=(server_process,), daemon=True),
        threading.Thread(
            target=stream_output,
            args=(mediamtx_process, MEDIAMTX_IGNORED_WARNINGS),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    print("[startstream] running server and mediamtx in this terminal")
    print("[startstream] press Ctrl+C to stop both")

    processes = {"server": server_process, "mediamtx": mediamtx_process}
    try:
        while True:
            for name, process in processes.items():
                code = process.poll()
                if code is not None:
                    other_name = "mediamtx" if name == "server" else "server"
                    stop_process(processes[other_name])
                    for thread in threads:
                        thread.join(timeout=1)
                    return code
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()
        print("[startstream] stopping...")
        for process in processes.values():
            stop_process(process)
        for thread in threads:
            thread.join(timeout=1)
        return 130


def main():
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

    sys.exit(run_processes())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()

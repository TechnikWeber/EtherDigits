"""Run the station in the background, start it at boot or login, restart it when it falls over.

- Linux: a systemd user service (Restart=always). For running without anybody
  logged in: `loginctl enable-linger <user>` once.
- macOS: a launchd agent (KeepAlive).
- Windows: an entry in the Startup folder that runs `etherdigits service run`,
  a small supervisor that restarts the station when it exits.
No admin rights are needed for any of them.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

NAME = "etherdigits"
LABEL = "io.github.technikweber.etherdigits"


def _base() -> list[str]:
    if getattr(sys, "frozen", False):  # a packaged program
        return [sys.executable]
    return [sys.executable, "-m", "etherdigits"]


def _options(host: str, port: int, data: str | None) -> list[str]:
    opts = ["--host", host, "--port", str(port)]
    if data:
        opts += ["--data", str(Path(data).expanduser().resolve())]
    return opts


def serve_command(host: str, port: int, data: str | None) -> list[str]:
    return _base() + ["serve"] + _options(host, port, data)


def supervised_command(host: str, port: int, data: str | None) -> list[str]:
    return _base() + ["service", "run"] + _options(host, port, data)


def systemd_unit(cmd: list[str], workdir: str) -> str:
    return f"""[Unit]
Description=EtherDigits numbers station

[Service]
Type=simple
WorkingDirectory={workdir}
ExecStart={shlex.join(cmd)}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""


def launchd_plist(cmd: list[str], workdir: str, log_dir: str) -> str:
    from xml.sax.saxutils import escape
    args = "\n".join(f"    <string>{escape(a)}</string>" for a in cmd)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{args}
  </array>
  <key>WorkingDirectory</key><string>{escape(workdir)}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>{escape(log_dir)}/etherdigits.log</string>
  <key>StandardErrorPath</key><string>{escape(log_dir)}/etherdigits.log</string>
</dict>
</plist>
"""


def windows_cmd(cmd: list[str]) -> str:
    """A Startup-folder script; pythonw runs without a console window."""
    exe = cmd[0]
    if exe.lower().endswith("python.exe") and Path(exe[:-10] + "pythonw.exe").exists():
        exe = exe[:-10] + "pythonw.exe"
    quoted = " ".join(f'"{a}"' if " " in a else a for a in cmd[1:])
    return f'@echo off\r\nstart "" "{exe}" {quoted}\r\n'


def paths() -> dict:
    home = Path.home()
    return {
        "systemd": home / ".config" / "systemd" / "user" / f"{NAME}.service",
        "launchd": home / "Library" / "LaunchAgents" / f"{LABEL}.plist",
        "startup": Path(os.environ.get("APPDATA", home)) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                   / "Startup" / "EtherDigits.cmd",
    }


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def install(host: str, port: int, data: str | None) -> str:
    cmd = serve_command(host, port, data)
    workdir = str(Path.home())
    p = paths()
    if sys.platform.startswith("linux"):
        p["systemd"].parent.mkdir(parents=True, exist_ok=True)
        p["systemd"].write_text(systemd_unit(cmd, workdir))
        _run(["systemctl", "--user", "daemon-reload"])
        _run(["systemctl", "--user", "enable", "--now", f"{NAME}.service"])
        _run(["systemctl", "--user", "restart", f"{NAME}.service"])
        linger = _run(["loginctl", "show-user", os.environ.get("USER", ""), "-p", "Linger"], check=False)
        note = "" if "Linger=yes" in linger.stdout else (
            "\nTo keep it running when nobody is logged in, run once: loginctl enable-linger $USER")
        return f"installed {p['systemd']}, running now{note}"
    if sys.platform == "darwin":
        log_dir = Path.home() / "Library" / "Logs"
        p["launchd"].parent.mkdir(parents=True, exist_ok=True)
        p["launchd"].write_text(launchd_plist(cmd, workdir, str(log_dir)))
        domain = f"gui/{os.getuid()}"
        _run(["launchctl", "bootout", domain, str(p["launchd"])], check=False)
        _run(["launchctl", "bootstrap", domain, str(p["launchd"])])
        return f"installed {p['launchd']}, running now; log in {log_dir / 'etherdigits.log'}"
    if sys.platform == "win32":
        p["startup"].parent.mkdir(parents=True, exist_ok=True)
        p["startup"].write_text(windows_cmd(supervised_command(host, port, data)))
        subprocess.Popen(["cmd", "/c", str(p["startup"])], creationflags=0x08000000)  # CREATE_NO_WINDOW
        return f"installed {p['startup']}; it starts at every login and runs now"
    raise RuntimeError(f"no service support for {sys.platform}; run 'etherdigits serve' yourself")


def uninstall() -> str:
    p = paths()
    if sys.platform.startswith("linux"):
        _run(["systemctl", "--user", "disable", "--now", f"{NAME}.service"], check=False)
        p["systemd"].unlink(missing_ok=True)
        _run(["systemctl", "--user", "daemon-reload"], check=False)
        return "removed the systemd service"
    if sys.platform == "darwin":
        _run(["launchctl", "bootout", f"gui/{os.getuid()}", str(p["launchd"])], check=False)
        p["launchd"].unlink(missing_ok=True)
        return "removed the launchd agent"
    if sys.platform == "win32":
        p["startup"].unlink(missing_ok=True)
        return "removed the Startup entry; a running station stops at the next logout (or end it in the Task Manager)"
    raise RuntimeError(f"no service support for {sys.platform}")


def status() -> str:
    p = paths()
    if sys.platform.startswith("linux"):
        r = _run(["systemctl", "--user", "status", f"{NAME}.service", "--no-pager", "-n", "5"], check=False)
        return r.stdout or r.stderr or "not installed"
    if sys.platform == "darwin":
        r = _run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], check=False)
        return r.stdout[:2000] if r.returncode == 0 else "not installed"
    if sys.platform == "win32":
        return f"installed: {p['startup']}" if p["startup"].exists() else "not installed"
    return "no service support on this platform"


def supervise(cmd: list[str]) -> int:
    """Restart the station whenever it exits; wait longer after quick crashes."""
    delay = 5
    while True:
        started = time.monotonic()
        code = subprocess.call(cmd)
        if code == 0:
            return 0
        delay = 5 if time.monotonic() - started > 300 else min(delay * 2, 300)
        print(f"station exited with {code}; restarting in {delay} s", file=sys.stderr, flush=True)
        time.sleep(delay)

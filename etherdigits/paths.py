"""Where the station keeps its data: database, pads, recordings."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_data_dir() -> Path:
    """The usual place per platform; ETHERDIGITS_DATA overrides it."""
    env = os.environ.get("ETHERDIGITS_DATA")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "EtherDigits"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "EtherDigits"
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "etherdigits"


def prepare(data_dir: Path) -> Path:
    data_dir = Path(data_dir)
    for sub in ("", "pads", "recordings"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        # Pads are keys: nobody else on this machine should read them.
        os.chmod(data_dir, 0o700)
        os.chmod(data_dir / "pads", 0o700)
    return data_dir

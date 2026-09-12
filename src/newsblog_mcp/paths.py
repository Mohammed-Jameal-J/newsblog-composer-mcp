"""Where this server keeps the files it owns.

There are two very different situations and they need different answers.

Running from a source checkout (``pip install -e .``, or straight from the
cloned folder) the project directory is the right place: the author expects
``output/`` and ``profile.json`` to sit next to the code where they can see
them, and ``.env`` to be read from there.

Installed as a package from PyPI, that same logic resolves to somewhere inside
site-packages - which is the wrong answer twice over. Generated posts would be
written into a virtualenv where nobody would look for them, and the identity
profile would be destroyed by ``pip install --upgrade``, making the server ask
its setup questions again after every upgrade. On a system-wide install it may
not even be writable.

So: source checkout keeps the old behaviour; an installed package writes to the
platform's user data directory, which survives upgrades and belongs to the user
rather than to the interpreter.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "newsblog-composer-mcp"

# <package>/paths.py -> <package> -> src -> project root
_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _is_source_checkout(root: Path) -> bool:
    """A checkout has the build files; an installed copy never does."""
    return (root / "pyproject.toml").is_file() and (root / "src").is_dir()


def user_data_dir() -> Path:
    """Per-user, per-platform, survives reinstalls.

    Deliberately not using platformdirs: this is the only place the server needs
    it, and the package's whole premise is that it runs with nothing extra
    installed.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_NAME


def data_dir() -> Path:
    """The directory this install writes to. Created on demand."""
    override = (os.environ.get("NEWSBLOG_DATA_DIR") or "").strip()
    if override:
        target = Path(override).expanduser()
    elif _is_source_checkout(_SOURCE_ROOT):
        target = _SOURCE_ROOT
    else:
        target = user_data_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        # An unwritable target is worth falling back from rather than crashing
        # at import time, which would take the whole MCP server down.
        target = user_data_dir()
        target.mkdir(parents=True, exist_ok=True)
    return target


def dotenv_path() -> Path:
    """.env sits beside the code in a checkout, in the data dir otherwise."""
    if _is_source_checkout(_SOURCE_ROOT):
        return _SOURCE_ROOT / ".env"
    return data_dir() / ".env"


def profile_path() -> Path:
    return data_dir() / "profile.json"


def default_output_dir() -> Path:
    return data_dir() / "output"


def describe() -> dict:
    """For diagnose, so a user can see where their files actually go."""
    return {
        "mode": "source checkout" if _is_source_checkout(_SOURCE_ROOT)
                else "installed package",
        "data_dir": str(data_dir()),
        "profile": str(profile_path()),
        "output": str(default_output_dir()),
        "env_file": str(dotenv_path()),
        "override_with": "NEWSBLOG_DATA_DIR",
    }

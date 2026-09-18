"""Where this server keeps the files it owns.

Three situations, not two, and the third is the one that bit us.

**A developer checkout** (``git clone``, ``pip install -e .``) writes beside the
code. That is what the author expects: ``output/`` and ``profile.json`` next to
the project, ``.env`` read from there.

**An installed package** (``pip install`` from PyPI) resolves to site-packages,
which is wrong twice over - posts land inside a virtualenv where nobody looks,
and the identity profile is destroyed by ``pip install --upgrade``. So it writes
to the platform user data directory instead.

**An installed .mcpb extension** looks exactly like a checkout: the packed
extension contains ``pyproject.toml`` and ``src/``, so the original test said
"checkout" and wrote into the extension's own folder. Claude Desktop replaces
that folder wholesale on every upgrade, so installing a new version silently
deleted the user's byline, their voice, and **every post they had ever
generated**. Confirmed in the wild:

    ...\Claude Extensions\local.mcpb.<author>.<name>\output\<post>

An extension install is therefore detected explicitly - by where it sits, and by
what a packed extension lacks (``.git`` and ``tests/`` are both excluded from the
package) - and sent to the user data directory with everything else that must
survive an upgrade.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "newsblog-composer-mcp"

# <package>/paths.py -> <package> -> src -> project root
_SOURCE_ROOT = Path(__file__).resolve().parents[2]

# Directory names that only ever appear in an installed desktop extension.
# "local.dxt." is the older prefix, kept so an extension installed before the
# rename is still recognised.
_EXTENSION_MARKERS = ("claude extensions", "claude-extensions")
_EXTENSION_PREFIXES = ("local.mcpb.", "local.dxt.")


def _is_extension_install(root: Path) -> bool:
    """True when this copy was unpacked from a .mcpb by a desktop client."""
    for part in root.parts:
        lowered = part.lower()
        if lowered in _EXTENSION_MARKERS:
            return True
        if lowered.startswith(_EXTENSION_PREFIXES):
            return True
    return False


def _is_source_checkout(root: Path) -> bool:
    """A working copy someone is developing in.

    The build files alone are not enough - a packed extension has those too.
    What a checkout also has, and the package deliberately does not, is version
    control and the test suite; ``.mcpbignore`` excludes both. Requiring one of
    them is what separates "I am working on this" from "this was installed".
    """
    if _is_extension_install(root):
        return False
    if not ((root / "pyproject.toml").is_file() and (root / "src").is_dir()):
        return False
    return (root / ".git").exists() or (root / "tests").is_dir()


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
    if target != _SOURCE_ROOT:
        _rescue_from_extension_folder(target)
    return target


def _rescue_from_extension_folder(target: Path) -> None:
    """Move a profile stranded in an old extension folder into the data dir.

    Anyone upgrading from a version that wrote beside the code has their byline,
    company and voice sitting in a directory the next install will delete.
    Copying it out on first run means they are not asked the setup questions
    again, and they never find out this bug existed.

    Best effort by design: a failure here must not stop the server starting, and
    an existing profile in the data directory always wins.
    """
    stale = _SOURCE_ROOT / "profile.json"
    fresh = target / "profile.json"
    if fresh.exists() or not stale.is_file():
        return
    try:
        shutil.copy2(stale, fresh)
    except OSError:
        return
    # Leave the original in place. It is about to be deleted by the upgrade
    # anyway, and removing it ourselves would destroy the only copy if the
    # write above turned out to be somewhere unexpected.


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
        "mode": ("source checkout" if _is_source_checkout(_SOURCE_ROOT)
                 else "installed extension" if _is_extension_install(_SOURCE_ROOT)
                 else "installed package"),
        "code_at": str(_SOURCE_ROOT),
        "data_dir": str(data_dir()),
        "profile": str(profile_path()),
        "output": str(default_output_dir()),
        "env_file": str(dotenv_path()),
        "override_with": "NEWSBLOG_DATA_DIR",
    }

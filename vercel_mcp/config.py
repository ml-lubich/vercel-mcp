"""Filesystem locations for the Vercel CLI config and our own account store.

Every lookup honours an environment override so tests never touch a real
home directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Point the tool at a different Vercel CLI config directory.
VERCEL_DIR_ENV = "VERCEL_CLI_CONFIG_DIR"
#: Point the tool at a different accounts store file.
STORE_ENV = "VERCEL_MCP_STORE"


def vercel_config_dir() -> Path:
    """Directory where the Vercel CLI keeps auth.json / config.json."""
    override = os.environ.get(VERCEL_DIR_ENV)
    if override:
        return Path(override).expanduser()

    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "com.vercel.cli"

    # Linux: newer CLIs use XDG data, older ones XDG config.
    share = home / ".local" / "share" / "com.vercel.cli"
    if share.exists():
        return share
    return home / ".config" / "com.vercel.cli"


def auth_path() -> Path:
    """The Vercel CLI credential file."""
    return vercel_config_dir() / "auth.json"


def auth_backup_path() -> Path:
    """Where the credential file is copied before we overwrite it."""
    return vercel_config_dir() / "auth.json.bak"


def vercel_settings_path() -> Path:
    """The Vercel CLI settings file (holds ``currentTeam``)."""
    return vercel_config_dir() / "config.json"


def store_path() -> Path:
    """Our accounts store."""
    override = os.environ.get(STORE_ENV)
    if override:
        return Path(override).expanduser()

    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / "vercel-mcp" / "accounts.json"

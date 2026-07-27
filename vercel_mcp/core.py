"""The operations behind both the CLI and the MCP server.

Everything here returns plain data so the two front-ends never duplicate
logic. There is deliberately no logout: the Vercel CLI keeps one credential
at a time, and discarding it is what this tool exists to prevent.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import config, store, vercel_api
from .store import Account


class CoreError(Exception):
    """A failure worth showing the user verbatim, without a traceback."""


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise CoreError(f"{path} not found — run `vercel login` first") from None
    except json.JSONDecodeError as exc:
        raise CoreError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CoreError(f"{path} does not contain a JSON object")
    return data


def _write_json(path: Path, data: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(mode)


def current_token() -> str:
    """The access token the Vercel CLI would use right now."""
    token = _read_json(config.auth_path()).get("token", "")
    if not token:
        raise CoreError("no token in auth.json — run `vercel login` first")
    return str(token)


def current_team() -> str | None:
    """The team the Vercel CLI is currently scoped to, if any."""
    try:
        return _read_json(config.vercel_settings_path()).get("currentTeam") or None
    except CoreError:
        return None


def sync() -> Account:
    """Snapshot the currently active login into the store."""
    auth = _read_json(config.auth_path())
    token = str(auth.get("token") or "")
    if not token:
        raise CoreError("no token in auth.json — run `vercel login` first")

    try:
        user = vercel_api.whoami(token)
        teams = vercel_api.list_teams(token)
    except vercel_api.VercelAuthError as exc:
        raise CoreError(f"{exc}. Run `vercel login` and try again.") from exc
    except vercel_api.VercelAPIError as exc:
        raise CoreError(str(exc)) from exc

    account = Account(
        email=user.get("email", ""),
        username=user.get("username", ""),
        user_id=user.get("uid") or user.get("id", ""),
        name=user.get("name", ""),
        token=token,
        refresh_token=str(auth.get("refreshToken") or ""),
        expires_at=auth.get("expiresAt"),
        teams=teams,
        synced_at=time.time(),
    )
    if not account.email:
        raise CoreError("Vercel did not return an email for this token")

    store.add_or_update(account)
    return account


def switch(selector: str, force: bool = False) -> Account:
    """Make a stored account the one the Vercel CLI uses."""
    account = store.get(selector)

    if account.is_expired() and not force:
        raise CoreError(
            f"the stored credential for {account.email} has expired. "
            "Run `vercel login` then `vgate sync` to refresh it "
            "(or pass --force to write it anyway)."
        )

    auth_file = config.auth_path()
    # Preserve the Vercel CLI's "//" comment keys and anything else it wrote.
    try:
        payload = _read_json(auth_file)
        shutil.copy2(auth_file, config.auth_backup_path())
    except CoreError:
        payload = {}

    payload["token"] = account.token
    if account.refresh_token:
        payload["refreshToken"] = account.refresh_token
    else:
        payload.pop("refreshToken", None)
    if account.expires_at is not None:
        payload["expiresAt"] = account.expires_at
    else:
        payload.pop("expiresAt", None)

    _write_json(auth_file, payload)
    return account


def use_team(slug_or_id: str) -> str:
    """Scope the Vercel CLI to a team, leaving other settings untouched."""
    settings_file = config.vercel_settings_path()
    try:
        settings = _read_json(settings_file)
    except CoreError:
        settings = {}
    settings["currentTeam"] = slug_or_id
    _write_json(settings_file, settings, mode=0o644)
    return slug_or_id


def active() -> dict:
    """Describe the login the Vercel CLI is currently holding."""
    result: dict = {
        "token_present": False,
        "email": None,
        "username": None,
        "status": "unknown",
        "known_account": False,
        "current_team": current_team(),
    }
    try:
        token = current_token()
    except CoreError:
        return result

    result["token_present"] = True
    for account in store.load():
        if account.token and account.token == token:
            result.update(
                email=account.email,
                username=account.username,
                status=account.status(),
                known_account=True,
            )
            break
    return result


def doctor() -> list[dict]:
    """Health checks, as ``{name, ok, detail}`` records."""
    checks: list[dict] = []

    vercel_cli = shutil.which("vercel")
    checks.append(
        {
            "name": "vercel CLI",
            "ok": bool(vercel_cli),
            "detail": vercel_cli or "not found on PATH — install with `npm i -g vercel`",
        }
    )

    config_dir = config.vercel_config_dir()
    checks.append(
        {
            "name": "config directory",
            "ok": config_dir.is_dir(),
            "detail": str(config_dir),
        }
    )

    auth_file = config.auth_path()
    checks.append(
        {
            "name": "auth.json",
            "ok": auth_file.is_file(),
            "detail": str(auth_file) if auth_file.is_file() else f"missing: {auth_file}",
        }
    )

    state = active()
    if not state["token_present"]:
        detail = "no active login — run `vercel login`"
    elif state["known_account"]:
        detail = f"{state['email']} ({state['status']})"
    else:
        detail = "active token is not in the store — run `vgate sync` to save it"
    checks.append(
        {
            "name": "active login",
            "ok": state["token_present"] and state["status"] != "expired",
            "detail": detail,
        }
    )

    accounts = store.load()
    expired = [a.email for a in accounts if a.is_expired()]
    checks.append(
        {
            "name": "stored accounts",
            "ok": bool(accounts) and not expired,
            "detail": (
                f"{len(accounts)} stored"
                + (f"; expired: {', '.join(expired)}" if expired else "")
                if accounts
                else "none yet — run `vgate sync` after each `vercel login`"
            ),
        }
    )
    return checks

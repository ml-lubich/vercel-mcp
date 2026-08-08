"""Persistent store of Vercel credentials, one record per account.

Unlike snapshotting just the access token, every record keeps the refresh
token and expiry alongside it. Dropping those is what turns an expired
credential into an unexplained 401 later on.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import store_path

#: Epoch values at or above this are milliseconds, below it seconds.
_MS_THRESHOLD = 10**11
#: Credentials inside this window are reported as "expiring-soon". They are
#: still VALID and usable — the label warns that a refresh is due shortly, and
#: is deliberately not "expiring", which reads as "expired" at a glance.
EXPIRING_SOON_SECONDS = 24 * 60 * 60


class AccountNotFound(LookupError):
    """Raised when a selector matches no stored account."""


def normalize_expiry(value: object) -> float | None:
    """Return ``value`` as epoch *seconds*, or None when there is no expiry.

    Vercel has written this field as both seconds and milliseconds, so the
    unit is inferred from the magnitude rather than trusted.
    """
    if value is None or value == "":
        return None
    try:
        seconds = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return seconds / 1000.0 if seconds >= _MS_THRESHOLD else seconds


@dataclass
class Account:
    """One saved Vercel login."""

    email: str
    username: str = ""
    user_id: str = ""
    name: str = ""
    token: str = ""
    refresh_token: str = ""
    #: Stored exactly as the Vercel CLI wrote it, so it round-trips verbatim.
    expires_at: object = None
    teams: list[dict] = field(default_factory=list)
    synced_at: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> Account:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict:
        return asdict(self)

    def status(self, now: float | None = None) -> str:
        """One of ``valid``, ``expiring-soon``, ``expired`` or ``unknown``.

        ``expiring-soon`` still means the credential WORKS; only ``expired``
        means it does not.
        """
        expiry = normalize_expiry(self.expires_at)
        if expiry is None:
            return "unknown"
        now = time.time() if now is None else now
        if expiry <= now:
            return "expired"
        if expiry - now <= EXPIRING_SOON_SECONDS:
            return "expiring-soon"
        return "valid"

    def is_expired(self, now: float | None = None) -> bool:
        return self.status(now) == "expired"


def load(path: Path | None = None) -> list[Account]:
    """Read every stored account; an absent or unreadable store is empty."""
    target = path or store_path()
    try:
        raw = json.loads(target.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [Account.from_dict(item) for item in raw.get("accounts", [])]


def save(accounts: list[Account], path: Path | None = None) -> Path:
    """Write the store with owner-only permissions — it holds credentials."""
    target = path or store_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "accounts": [a.to_dict() for a in accounts]}
    target.write_text(json.dumps(payload, indent=2))
    target.chmod(0o600)
    return target


def add_or_update(account: Account, path: Path | None = None) -> list[Account]:
    """Insert ``account``, replacing any existing record with the same email."""
    accounts = [a for a in load(path) if a.email.lower() != account.email.lower()]
    accounts.append(account)
    save(accounts, path)
    return accounts


def get(selector: str, path: Path | None = None) -> Account:
    """Resolve an account by email, username, or 1-based index."""
    accounts = load(path)
    if not accounts:
        raise AccountNotFound("no accounts stored yet — run `vgate sync` first")

    needle = str(selector).strip().lower()
    for account in accounts:
        if account.email.lower() == needle or account.username.lower() == needle:
            return account

    if needle.isdigit():
        index = int(needle)
        if 1 <= index <= len(accounts):
            return accounts[index - 1]

    raise AccountNotFound(f"no stored account matches {selector!r}")


def remove(selector: str, path: Path | None = None) -> Account:
    """Delete a stored account and return the record that was removed."""
    account = get(selector, path)
    save([a for a in load(path) if a.email != account.email], path)
    return account

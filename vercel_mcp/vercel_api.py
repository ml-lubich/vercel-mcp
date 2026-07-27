"""Minimal Vercel REST client — just enough to identify a token."""

from __future__ import annotations

import httpx

API_ROOT = "https://api.vercel.com"
TIMEOUT_SECONDS = 10.0


class VercelAuthError(Exception):
    """The token was rejected (expired, revoked, or wrong account)."""


class VercelAPIError(Exception):
    """The API answered, but not with something usable."""


def _get(path: str, token: str) -> dict:
    url = f"{API_ROOT}{path}"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:  # network down, DNS, timeout
        raise VercelAPIError(f"could not reach {url}: {exc}") from exc

    if response.status_code in (401, 403):
        raise VercelAuthError("Vercel rejected this token — it is expired or revoked")
    if response.status_code >= 400:
        raise VercelAPIError(f"{url} returned HTTP {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise VercelAPIError(f"{url} returned a non-JSON body") from exc


def whoami(token: str) -> dict:
    """Return the user record owning ``token``."""
    payload = _get("/v2/user", token)
    # The endpoint has shipped both {"user": {...}} and a bare user object.
    user = payload.get("user") if isinstance(payload, dict) else None
    return user if isinstance(user, dict) else payload


def list_teams(token: str) -> list[dict]:
    """Return the teams ``token`` can act on, as ``{id, slug, name}`` records."""
    payload = _get("/v2/teams", token)
    teams = payload.get("teams", []) if isinstance(payload, dict) else []
    return [
        {
            "id": team.get("id", ""),
            "slug": team.get("slug", ""),
            "name": team.get("name", ""),
        }
        for team in teams
    ]

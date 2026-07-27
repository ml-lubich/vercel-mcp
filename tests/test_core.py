import json
import time

import pytest

from vercel_mcp import config, core, store, vercel_api
from vercel_mcp.store import Account

FUTURE_MS = (time.time() + 90 * 24 * 3600) * 1000
PAST_MS = (time.time() - 3600) * 1000


def stored(email="saved@example.com", expires_at=FUTURE_MS, **kwargs) -> Account:
    return Account(
        email=email,
        username=kwargs.pop("username", "saved"),
        token=kwargs.pop("token", "vca_saved"),
        refresh_token=kwargs.pop("refresh_token", "rt_saved"),
        expires_at=expires_at,
        **kwargs,
    )


def test_switch_writes_full_credential_and_keeps_comment_keys(auth_file, store_file):
    store.add_or_update(stored(), store_file)
    core.switch("saved@example.com")

    written = json.loads(auth_file.read_text())
    assert written["token"] == "vca_saved"
    assert written["refreshToken"] == "rt_saved"
    assert written["expiresAt"] == FUTURE_MS
    assert written["// Note"].startswith("This is your Vercel")


def test_switch_backs_up_previous_auth(auth_file, store_file):
    store.add_or_update(stored(), store_file)
    core.switch("saved@example.com")

    backup = json.loads(config.auth_backup_path().read_text())
    assert backup["token"] == "vca_original"


def test_switch_refuses_expired_credential(auth_file, store_file):
    store.add_or_update(stored(expires_at=PAST_MS), store_file)
    with pytest.raises(core.CoreError, match="expired"):
        core.switch("saved@example.com")
    # the active login is untouched
    assert json.loads(auth_file.read_text())["token"] == "vca_original"


def test_switch_force_overrides_expiry(auth_file, store_file):
    store.add_or_update(stored(expires_at=PAST_MS), store_file)
    core.switch("saved@example.com", force=True)
    assert json.loads(auth_file.read_text())["token"] == "vca_saved"


def test_switch_drops_stale_refresh_token(auth_file, store_file):
    store.add_or_update(stored(refresh_token=""), store_file)
    core.switch("saved@example.com")
    assert "refreshToken" not in json.loads(auth_file.read_text())


def test_use_team_preserves_other_settings(vercel_dir):
    settings = vercel_dir / "config.json"
    settings.write_text(json.dumps({"currentTeam": "old", "telemetry": {"enabled": False}}))

    core.use_team("mlubich-projects")

    data = json.loads(settings.read_text())
    assert data["currentTeam"] == "mlubich-projects"
    assert data["telemetry"] == {"enabled": False}


def test_use_team_creates_missing_settings(vercel_dir):
    core.use_team("team-a")
    assert json.loads((vercel_dir / "config.json").read_text())["currentTeam"] == "team-a"


def test_sync_captures_refresh_token_and_expiry(auth_file, store_file, monkeypatch):
    monkeypatch.setattr(
        vercel_api,
        "whoami",
        lambda token: {"email": "me@example.com", "username": "me", "uid": "u1", "name": "Me"},
    )
    monkeypatch.setattr(
        vercel_api, "list_teams", lambda token: [{"id": "t1", "slug": "team", "name": "Team"}]
    )

    account = core.sync()

    assert account.email == "me@example.com"
    assert account.refresh_token == "rt_original"
    assert account.expires_at == 4102444800000
    assert store.load(store_file)[0].teams[0]["slug"] == "team"


def test_sync_surfaces_auth_failure_as_core_error(auth_file, store_file, monkeypatch):
    def _reject(token):
        raise vercel_api.VercelAuthError("Vercel rejected this token")

    monkeypatch.setattr(vercel_api, "whoami", _reject)
    with pytest.raises(core.CoreError, match="vercel login"):
        core.sync()


def test_sync_without_auth_file_is_a_clean_error(vercel_dir, store_file):
    with pytest.raises(core.CoreError, match="vercel login"):
        core.sync()


def test_active_reports_known_account(auth_file, store_file):
    store.add_or_update(stored(token="vca_original"), store_file)
    state = core.active()
    assert state["known_account"] and state["email"] == "saved@example.com"


def test_active_flags_unknown_token(auth_file, store_file):
    state = core.active()
    assert state["token_present"] and not state["known_account"]


def test_active_without_login(vercel_dir, store_file):
    assert core.active()["token_present"] is False


def test_doctor_returns_named_checks(auth_file, store_file):
    names = [check["name"] for check in core.doctor()]
    assert names == [
        "vercel CLI",
        "config directory",
        "auth.json",
        "active login",
        "stored accounts",
    ]
    assert all({"name", "ok", "detail"} <= set(check) for check in core.doctor())


def test_doctor_flags_expired_stored_account(auth_file, store_file):
    store.add_or_update(stored(expires_at=PAST_MS), store_file)
    stored_check = next(c for c in core.doctor() if c["name"] == "stored accounts")
    assert not stored_check["ok"] and "saved@example.com" in stored_check["detail"]


def test_there_is_no_logout():
    assert not hasattr(core, "logout")

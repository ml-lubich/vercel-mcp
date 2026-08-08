import stat
import time

import pytest

from vercel_mcp import store
from vercel_mcp.store import Account, AccountNotFound

FUTURE_SECONDS = time.time() + 90 * 24 * 3600
PAST_SECONDS = time.time() - 3600


def make(email="a@example.com", **kwargs) -> Account:
    return Account(email=email, username=kwargs.pop("username", "user-a"), **kwargs)


def test_load_missing_store_is_empty(store_file):
    assert store.load(store_file) == []


def test_roundtrip_preserves_full_credential(store_file):
    store.add_or_update(
        make(token="tok", refresh_token="rt", expires_at=1785205694, teams=[{"slug": "t"}]),
        store_file,
    )
    (loaded,) = store.load(store_file)
    assert (loaded.token, loaded.refresh_token, loaded.expires_at) == ("tok", "rt", 1785205694)
    assert loaded.teams == [{"slug": "t"}]


def test_store_file_is_owner_only(store_file):
    store.add_or_update(make(), store_file)
    assert stat.S_IMODE(store_file.stat().st_mode) == 0o600


def test_add_or_update_replaces_same_email(store_file):
    store.add_or_update(make(token="old"), store_file)
    store.add_or_update(make(token="new"), store_file)
    accounts = store.load(store_file)
    assert len(accounts) == 1 and accounts[0].token == "new"


def test_get_by_email_username_and_index(store_file):
    store.add_or_update(make("a@example.com", username="alpha"), store_file)
    store.add_or_update(make("b@example.com", username="beta"), store_file)

    assert store.get("A@EXAMPLE.COM", store_file).email == "a@example.com"
    assert store.get("beta", store_file).email == "b@example.com"
    assert store.get("2", store_file).email == "b@example.com"


def test_get_rejects_unknown_and_out_of_range(store_file):
    store.add_or_update(make(), store_file)
    with pytest.raises(AccountNotFound):
        store.get("nope@example.com", store_file)
    with pytest.raises(AccountNotFound):
        store.get("9", store_file)


def test_get_on_empty_store_explains_sync(store_file):
    with pytest.raises(AccountNotFound, match="vgate sync"):
        store.get("1", store_file)


def test_remove(store_file):
    store.add_or_update(make("a@example.com"), store_file)
    store.add_or_update(make("b@example.com"), store_file)
    assert store.remove("a@example.com", store_file).email == "a@example.com"
    assert [a.email for a in store.load(store_file)] == ["b@example.com"]


@pytest.mark.parametrize(
    "value,expected",
    [
        (FUTURE_SECONDS, "valid"),
        (FUTURE_SECONDS * 1000, "valid"),  # milliseconds
        (PAST_SECONDS, "expired"),
        (PAST_SECONDS * 1000, "expired"),  # milliseconds
        (None, "unknown"),
        ("", "unknown"),
        ("garbage", "unknown"),
    ],
)
def test_status_handles_both_epoch_units(value, expected):
    assert make(expires_at=value).status() == expected


def test_status_expiring_window():
    soon = time.time() + 3600
    assert make(expires_at=soon).status() == "expiring-soon"


def test_expiring_soon_is_not_expired():
    """A credential inside the warning window still works.

    The old label for this state was "expiring", which reads as "expired" at a
    glance — it cost a real debugging session, where every account showed
    "expiring" and the tokens were wrongly declared dead. The label must never
    again be mistakable for the terminal state.
    """
    soon = make(expires_at=time.time() + 3600)
    assert not soon.is_expired()
    assert soon.status() != "expired"


def test_is_expired_matches_status():
    assert make(expires_at=PAST_SECONDS).is_expired()
    assert not make(expires_at=FUTURE_SECONDS).is_expired()


def test_normalize_expiry_units():
    assert store.normalize_expiry(1785205694) == pytest.approx(1785205694)
    assert store.normalize_expiry(1785205694000) == pytest.approx(1785205694)
    assert store.normalize_expiry(0) is None

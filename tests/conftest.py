import json

import pytest

from vercel_mcp import config


@pytest.fixture
def vercel_dir(tmp_path, monkeypatch):
    """An isolated Vercel CLI config directory."""
    directory = tmp_path / "com.vercel.cli"
    directory.mkdir()
    monkeypatch.setenv(config.VERCEL_DIR_ENV, str(directory))
    return directory


@pytest.fixture
def store_file(tmp_path, monkeypatch):
    """An isolated accounts store path."""
    path = tmp_path / "store" / "accounts.json"
    monkeypatch.setenv(config.STORE_ENV, str(path))
    return path


@pytest.fixture
def auth_file(vercel_dir):
    """A realistic auth.json, including the CLI's comment keys."""
    path = vercel_dir / "auth.json"
    path.write_text(
        json.dumps(
            {
                "// Note": "This is your Vercel credentials file.",
                "// Docs": "https://vercel.com/docs/cli",
                "token": "vca_original",
                "refreshToken": "rt_original",
                "expiresAt": 4102444800000,
            },
            indent=2,
        )
    )
    return path


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if a test ever tries to make a real HTTP call."""

    def _blocked(*args, **kwargs):  # pragma: no cover - only runs on a bug
        raise AssertionError("tests must not hit the network")

    monkeypatch.setattr("httpx.get", _blocked)

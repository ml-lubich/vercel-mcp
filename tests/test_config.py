from pathlib import Path

from vercel_mcp import config


def test_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv(config.VERCEL_DIR_ENV, str(tmp_path / "custom"))
    assert config.vercel_config_dir() == tmp_path / "custom"


def test_macos_default(monkeypatch, tmp_path):
    monkeypatch.delenv(config.VERCEL_DIR_ENV, raising=False)
    monkeypatch.setattr(config.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    expected = tmp_path / "Library" / "Application Support" / "com.vercel.cli"
    assert config.vercel_config_dir() == expected


def test_linux_prefers_existing_share_dir(monkeypatch, tmp_path):
    monkeypatch.delenv(config.VERCEL_DIR_ENV, raising=False)
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert config.vercel_config_dir() == tmp_path / ".config" / "com.vercel.cli"

    share = tmp_path / ".local" / "share" / "com.vercel.cli"
    share.mkdir(parents=True)
    assert config.vercel_config_dir() == share


def test_auth_and_settings_paths(tmp_path, monkeypatch):
    monkeypatch.setenv(config.VERCEL_DIR_ENV, str(tmp_path))
    assert config.auth_path() == tmp_path / "auth.json"
    assert config.auth_backup_path() == tmp_path / "auth.json.bak"
    assert config.vercel_settings_path() == tmp_path / "config.json"


def test_store_path_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv(config.STORE_ENV, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.store_path() == tmp_path / "vercel-mcp" / "accounts.json"


def test_store_path_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(config.STORE_ENV, str(tmp_path / "a.json"))
    assert config.store_path() == tmp_path / "a.json"

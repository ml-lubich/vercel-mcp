import json
import time

from typer.testing import CliRunner

from vercel_mcp import store
from vercel_mcp.cli import app
from vercel_mcp.store import Account

runner = CliRunner()
FUTURE_MS = (time.time() + 90 * 24 * 3600) * 1000


def saved(email="saved@example.com", token="vca_saved") -> Account:
    return Account(
        email=email,
        username="saved",
        token=token,
        refresh_token="rt",
        expires_at=FUTURE_MS,
        teams=[{"id": "t1", "slug": "team", "name": "Team"}],
    )


def test_version():
    for option in ("-V", "--version"):
        result = runner.invoke(app, [option])
        assert result.exit_code == 0 and "vgate" in result.stdout


def test_root_help_has_only_supported_framework_options():
    result = runner.invoke(app, ["-h"])
    assert result.exit_code == 0
    assert "-V" in result.stdout and "--version" in result.stdout
    assert "--install-completion" not in result.stdout
    assert "--show-completion" not in result.stdout


def test_empty_group_invocation_prints_help_without_touching_account_store():
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Commands" in result.stdout


def test_help_short_flag_on_root_and_subcommands():
    for args in (["-h"], ["--help"], ["ls", "-h"], ["sync", "-h"], ["agent", "-h"], ["agent", "schema", "-h"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.output)
        assert "Usage" in result.output


def test_agent_schema_is_json_with_tool_key():
    result = runner.invoke(app, ["agent", "schema"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["tool"] == "vgate"
    assert {"sync", "switch", "doctor"} <= {c["name"] for c in payload["commands"]}


def test_ls_empty_store_guides_the_user(store_file, vercel_dir):
    result = runner.invoke(app, ["ls"])
    assert result.exit_code == 0 and "vgate sync" in result.stdout


def test_ls_lists_accounts(store_file, vercel_dir):
    store.add_or_update(saved(), store_file)
    result = runner.invoke(app, ["ls"])
    assert result.exit_code == 0 and "saved@example.com" in result.stdout


def test_switch_unknown_selector_exits_one(store_file, auth_file):
    store.add_or_update(saved(), store_file)
    result = runner.invoke(app, ["switch", "ghost@example.com"])
    assert result.exit_code == 1 and "error" in result.stdout + result.stderr


def test_switch_activates_account(store_file, auth_file):
    store.add_or_update(saved(), store_file)
    result = runner.invoke(app, ["switch", "saved@example.com"])
    assert result.exit_code == 0
    assert json.loads(auth_file.read_text())["token"] == "vca_saved"


def test_whoami_without_login_exits_one(vercel_dir, store_file):
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 1


def test_whoami_reports_active_account(auth_file, store_file):
    store.add_or_update(saved(token="vca_original"), store_file)
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 0 and "saved@example.com" in result.stdout


def test_use_sets_team(vercel_dir, store_file):
    result = runner.invoke(app, ["use", "mlubich-projects"])
    assert result.exit_code == 0
    assert json.loads((vercel_dir / "config.json").read_text())["currentTeam"] == "mlubich-projects"


def test_doctor_runs_and_warns_about_logout(auth_file, store_file):
    result = runner.invoke(app, ["doctor"])
    assert "vercel logout" in result.stdout


def test_path_shows_both_locations(vercel_dir, store_file):
    result = runner.invoke(app, ["path"])
    assert result.exit_code == 0 and "vgate store" in result.stdout


def test_rm_forgets_account(store_file, vercel_dir):
    store.add_or_update(saved(), store_file)
    result = runner.invoke(app, ["rm", "saved@example.com"], input="y\n")
    assert result.exit_code == 0 and store.load(store_file) == []


def test_rm_asks_before_deleting_and_keeps_account_on_no(store_file, vercel_dir):
    store.add_or_update(saved(), store_file)
    result = runner.invoke(app, ["rm", "saved@example.com"], input="n\n")
    assert result.exit_code != 0
    assert "saved@example.com" in result.stdout
    assert store.load(store_file) == [saved()]


def test_rm_yes_skips_the_prompt(store_file, vercel_dir):
    store.add_or_update(saved(), store_file)
    result = runner.invoke(app, ["rm", "--yes", "saved@example.com"])
    assert result.exit_code == 0 and store.load(store_file) == []


def test_delete_is_an_alias_for_rm(store_file, vercel_dir):
    store.add_or_update(saved(), store_file)
    result = runner.invoke(app, ["delete", "saved@example.com"], input="y\n")
    assert result.exit_code == 0 and store.load(store_file) == []


def test_rm_unknown_account_never_prompts(store_file, vercel_dir):
    result = runner.invoke(app, ["rm", "nobody@example.com"])
    assert result.exit_code == 1

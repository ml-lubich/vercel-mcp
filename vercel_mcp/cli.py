"""``vgate`` — switch between Vercel logins from the terminal."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, config, core, store

app = typer.Typer(
    name="vgate",
    help="Manage multiple Vercel CLI logins. Switch accounts instead of logging out.",
    no_args_is_help=True,
    add_completion=False,
)
agent_app = typer.Typer(help="Machine-readable output for scripts and AI agents.")
app.add_typer(agent_app, name="agent")

console = Console()
err_console = Console(stderr=True)

STATUS_STYLE = {
    "valid": "green",
    "expiring": "yellow",
    "expired": "red",
    "unknown": "dim",
}


def _fail(message: str) -> typer.Exit:
    err_console.print(f"[red]error:[/red] {message}")
    return typer.Exit(1)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"vgate {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Manage multiple Vercel CLI logins."""


@app.command()
def sync() -> None:
    """Save the currently active `vercel login` into the store."""
    try:
        account = core.sync()
    except core.CoreError as exc:
        raise _fail(str(exc)) from exc
    teams = ", ".join(t["slug"] for t in account.teams) or "none"
    console.print(f"[green]synced[/green] {account.email} (teams: {teams})")


@app.command("ls")
@app.command("list", hidden=True)
def list_accounts() -> None:
    """List every stored account and its credential status."""
    accounts = store.load()
    if not accounts:
        console.print(
            "No accounts stored yet. "
            "Run [bold]vercel login[/bold], then [bold]vgate sync[/bold]."
        )
        return

    state = core.active()
    table = Table(box=None, pad_edge=False)
    table.add_column("#", style="dim", justify="right")
    table.add_column("email")
    table.add_column("username", style="dim")
    table.add_column("teams", justify="right")
    table.add_column("token")
    table.add_column("", style="cyan")

    for index, account in enumerate(accounts, start=1):
        status = account.status()
        table.add_row(
            str(index),
            account.email,
            account.username or "-",
            str(len(account.teams)),
            f"[{STATUS_STYLE[status]}]{status}[/{STATUS_STYLE[status]}]",
            "active" if state.get("email") == account.email else "",
        )
    console.print(table)


@app.command()
def switch(
    selector: str | None = typer.Argument(
        None, help="Email, username, or list number. Omit to pick interactively."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Switch even if the credential expired."
    ),
) -> None:
    """Make a stored account the active Vercel login."""
    if selector is None:
        accounts = store.load()
        if not accounts:
            raise _fail("no accounts stored yet — run `vgate sync` first")
        list_accounts()
        selector = typer.prompt("Account (number, email, or username)")

    try:
        account = core.switch(selector, force=force)
    except (core.CoreError, store.AccountNotFound) as exc:
        raise _fail(str(exc)) from exc
    console.print(f"[green]switched[/green] to {account.email}")


@app.command()
def use(team: str = typer.Argument(..., help="Team slug or id to scope the CLI to.")) -> None:
    """Set the team the Vercel CLI acts on."""
    try:
        core.use_team(team)
    except core.CoreError as exc:
        raise _fail(str(exc)) from exc
    console.print(f"[green]current team[/green] {team}")


@app.command()
def whoami() -> None:
    """Show which account and team the Vercel CLI is currently using."""
    state = core.active()
    if not state["token_present"]:
        raise _fail("no active login — run `vercel login`")

    label = state["email"] or "unknown account (not in store — run `vgate sync`)"
    status = state["status"]
    console.print(f"{label}  [{STATUS_STYLE[status]}]{status}[/{STATUS_STYLE[status]}]")
    console.print(f"team: {state['current_team'] or 'personal'}")


@app.command()
def doctor() -> None:
    """Check the local Vercel setup and stored credentials."""
    failures = 0
    for check in core.doctor():
        if check["ok"]:
            console.print(f"[green]ok[/green]   {check['name']}: {check['detail']}")
        else:
            failures += 1
            console.print(f"[red]warn[/red] {check['name']}: {check['detail']}")
    console.print(
        "\n[dim]Never run `vercel logout` — it destroys the only stored credential. "
        "Use `vgate switch` instead.[/dim]"
    )
    if failures:
        raise typer.Exit(1)


@app.command()
def path() -> None:
    """Print the Vercel config directory and our store location."""
    console.print(f"vercel config: {config.vercel_config_dir()}")
    console.print(f"vgate store:   {config.store_path()}")


@app.command("rm")
def remove(selector: str = typer.Argument(..., help="Email, username, or list number.")) -> None:
    """Forget a stored account."""
    try:
        account = store.remove(selector)
    except store.AccountNotFound as exc:
        raise _fail(str(exc)) from exc
    console.print(f"[green]removed[/green] {account.email}")


@agent_app.command("schema")
def agent_schema() -> None:
    """Print a machine-readable description of every command."""
    schema = {
        "tool": "vgate",
        "version": __version__,
        "description": "Manage multiple Vercel CLI logins on one machine.",
        "mcp_server": "vgate-mcp",
        "commands": [
            {"name": "sync", "args": [], "description": "Save the active login into the store."},
            {"name": "ls", "args": [], "description": "List stored accounts and token status."},
            {
                "name": "switch",
                "args": ["selector"],
                "description": "Activate a stored account by email, username, or index.",
            },
            {"name": "use", "args": ["team"], "description": "Set the current team."},
            {"name": "whoami", "args": [], "description": "Show the active account and team."},
            {"name": "doctor", "args": [], "description": "Check setup and credential health."},
            {"name": "path", "args": [], "description": "Print config and store locations."},
            {"name": "rm", "args": ["selector"], "description": "Forget a stored account."},
        ],
        "notes": [
            "There is no logout command by design.",
            "Run `vgate sync` after every `vercel login`.",
        ],
    }
    typer.echo(json.dumps(schema, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()

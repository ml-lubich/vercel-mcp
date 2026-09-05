"""MCP server exposing account switching to AI agents.

Thin wrapper: every tool delegates to :mod:`vercel_mcp.core`.
"""

from __future__ import annotations

from . import __version__, core, store

try:  # keep the module importable without the optional SDK present
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised via the install hint
    FastMCP = None  # type: ignore[assignment]


def build_server():
    """Construct the MCP server, or raise if the SDK is missing."""
    if FastMCP is None:
        raise RuntimeError(
            "the `mcp` package is required to run vgate-mcp — install it with "
            "`pip install 'vercel-mcp[mcp]'` or `pip install mcp`"
        )

    # FastMCP takes no `version` kwarg — passing one raises TypeError and the
    # server never starts, which is why this showed up in Claude Code only as
    # "Connection closed". The version still travels in the tool description.
    server = FastMCP("vgate", instructions=f"Vercel account switching (vgate {__version__})")

    @server.tool()
    def list_accounts() -> list[dict]:
        """List stored Vercel accounts with their credential status."""
        return [
            {
                "index": index,
                "email": account.email,
                "username": account.username,
                "teams": [team["slug"] for team in account.teams],
                "status": account.status(),
            }
            for index, account in enumerate(store.load(), start=1)
        ]

    @server.tool()
    def switch_account(selector: str, force: bool = False) -> dict:
        """Activate a stored account by email, username, or index."""
        account = core.switch(selector, force=force)
        return {"switched_to": account.email, "status": account.status()}

    @server.tool()
    def whoami() -> dict:
        """Report the currently active Vercel account and team."""
        return core.active()

    @server.tool()
    def use_team(slug: str) -> dict:
        """Scope the Vercel CLI to a team."""
        return {"current_team": core.use_team(slug)}

    @server.tool()
    def doctor() -> list[dict]:
        """Run health checks on the local Vercel setup."""
        return core.doctor()

    return server


def main() -> None:
    try:
        server = build_server()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()

# vercel-mcp

**Switch between Vercel accounts instead of logging out.** A `vgate` CLI plus an MCP server, so scripts and AI agents can change accounts too.

[![PyPI](https://img.shields.io/pypi/v/vercel-mcp.svg)](https://pypi.org/project/vercel-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/vercel-mcp.svg)](https://pypi.org/project/vercel-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/ml-lubich/vercel-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ml-lubich/vercel-mcp/actions/workflows/ci.yml)

## Why

The Vercel CLI holds **one login at a time, machine-wide**. Work on a client account for ten minutes and your own project's `vercel deploy` quietly starts targeting the wrong place — or fails with `Not authorized`. The usual fix, `vercel logout` followed by `vercel login`, means an email round-trip every single time.

Worse is the silent version: a saved credential that has expired. You get a bare 401 with no hint that the token simply aged out, because the access token was snapshotted **without** the refresh token or the expiry that would have explained it.

`vgate` stores the complete credential — token, refresh token, and expiry — for every account, tells you at a glance which ones are still good, and switches between them instantly.

> **It has no `logout` command, on purpose.** `vercel logout` destroys the only credential on the machine. Switch instead.

## Install

```bash
# Homebrew
brew tap ml-lubich/tap && brew install vgate

# pipx
pipx install vercel-mcp

# uv
uv tool install vercel-mcp
```

## Quickstart

Log in once per account, saving each one as you go:

```bash
vercel login you@personal.com   && vgate sync
vercel login you@client.com     && vgate sync
```

Then switch whenever you like:

```bash
$ vgate ls
  #  email               username   teams  token
  1  you@personal.com    you           2  valid     active
  2  you@client.com      you-client    1  expiring-soon

$ vgate switch you@client.com
switched to you@client.com

$ vgate whoami
you@client.com  valid
team: client-projects
```

`switch` takes an email, a username, or the row number — so it works unattended in scripts and CI, not just as an interactive picker.

## Commands

| Command | What it does |
| --- | --- |
| `vgate sync` | Save the currently active login into the store |
| `vgate ls` | List stored accounts with credential status |
| `vgate switch <selector>` | Activate an account by email, username, or index |
| `vgate use <team>` | Set the team the Vercel CLI acts on |
| `vgate whoami` | Show the active account and team |
| `vgate doctor` | Check the local setup and flag expired credentials |
| `vgate path` | Print the Vercel config and store locations |
| `vgate rm <selector>` | Forget a stored account (asks y/N; `--yes` skips, `delete` is an alias) |
| `vgate agent schema` | Machine-readable command list (JSON) for automation |

Run `vgate sync` after **every** `vercel login` — that is what makes an account switchable later.

## MCP server

Register `vgate-mcp` with any MCP client to let an agent manage accounts:

```json
{
  "mcpServers": {
    "vgate": {
      "command": "vgate-mcp"
    }
  }
}
```

Tools exposed: `list_accounts`, `switch_account`, `whoami`, `use_team`, `doctor`.

## How it compares

Prior art: [khanakia/vercelgate](https://github.com/khanakia/vercelgate), a Go tool with the same goal.

| | vercelgate | vercel-mcp |
| --- | --- | --- |
| Stores access token | ✅ | ✅ |
| Stores refresh token + expiry | ❌ | ✅ |
| Detects expired credentials | ❌ | ✅ (`ls`, `doctor`) |
| Non-interactive switch | ❌ arrow-key prompt only | ✅ `switch <email>` |
| Backs up `auth.json` before overwriting | ❌ | ✅ |
| MCP server for AI agents | ❌ | ✅ |
| Install | Go / brew | pip / pipx / uv / brew |

## Security

- Credentials live in `~/.config/vercel-mcp/accounts.json`, written with `0600` (owner-only) permissions.
- `auth.json` is copied to `auth.json.bak` before every switch, so a bad switch is recoverable.
- Nothing leaves your machine except calls to `api.vercel.com` to identify a token.
- No logout command exists, by design.

## Development

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest -q
uv run ruff check .
```

The pytest configuration measures `vercel_mcp` and fails the suite below 80%
aggregate line coverage. Tests use isolated temporary configuration and fake
HTTP responses; they do not switch real Vercel accounts or call the live API.

## License

MIT © 2026 Misha Lubich

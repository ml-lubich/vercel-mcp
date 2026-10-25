from __future__ import annotations

import pytest

from vercel_mcp import mcp_server


def test_build_server_install_hint_matches_required_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_server, "FastMCP", None)

    with pytest.raises(RuntimeError, match="pip install vercel-mcp"):
        mcp_server.build_server()

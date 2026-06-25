from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from nbot.utils.sandbox_bridge import _bridge_to_qq_sandbox, _should_bridge


def test_should_bridge() -> None:
    assert _should_bridge("/tmp/file.txt") is True
    assert _should_bridge("http://example.com/file.txt") is False
    assert _should_bridge("https://example.com/file.txt") is False
    assert _should_bridge("base64://...") is False
    assert _should_bridge("data:image/png;base64,...") is False
    assert _should_bridge(None) is False


def test_bridge_to_qq_sandbox(tmp_path, monkeypatch) -> None:
    sandbox = tmp_path / "sandbox"
    monkeypatch.setattr(
        "nbot.utils.sandbox_bridge.QQ_SANDBOX_DIR", str(sandbox)
    )
    local = tmp_path / "source.txt"
    local.write_text("hello")
    result = _bridge_to_qq_sandbox(str(local))
    assert result == str(sandbox / "source.txt")
    assert (sandbox / "source.txt").exists()
    assert os.path.samefile(str(local), str(sandbox / "source.txt"))

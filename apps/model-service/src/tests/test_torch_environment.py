from __future__ import annotations

import os
from pathlib import Path

from pytest import MonkeyPatch

from src.torch_environment import configure_torch_cache_dir


def test_configure_torch_cache_dir_does_not_need_windows_username(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("TORCHINDUCTOR_CACHE_DIR", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("LOGNAME", raising=False)
    monkeypatch.delenv("LNAME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "C:\\runtime-cache")

    configure_torch_cache_dir()

    assert Path(os.environ["TORCHINDUCTOR_CACHE_DIR"]) == Path(
        "C:\\runtime-cache",
        "pytorch-model",
        "torchinductor",
    )

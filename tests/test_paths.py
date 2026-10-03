"""Tests for lagos_waste.paths."""

from pathlib import Path

import pytest

from lagos_waste import paths


def test_root_contains_claude_md() -> None:
    """ROOT points at the repository root, identified by CLAUDE.md."""
    assert (paths.ROOT / "CLAUDE.md").is_file()


@pytest.mark.parametrize(
    "path",
    [
        paths.ROOT,
        paths.DATA_RAW,
        paths.DATA_INTERIM,
        paths.DATA_PROCESSED,
        paths.FIGURES,
        paths.MAPS,
    ],
)
def test_path_constant_is_directory(path: Path) -> None:
    """Every path constant exists as a directory."""
    assert path.is_dir()

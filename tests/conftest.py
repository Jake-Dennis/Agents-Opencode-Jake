"""
Pytest configuration and shared fixtures for the Agents-Opencode-Jake test suite.

Currently provides:
  - `repo_path` fixture: absolute path to the repo root (the directory
    containing `opencode.json` and `tests/`).
  - `cfg` fixture: parsed `opencode.json` as a Python dict.

A future task (Layer 2, #9) will expand this with `agent_cfg(name)`,
`runtime_timeout`, and `graph_data` fixtures and migrate the existing
tests to use them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# Single source of truth for the repo location. The existing test files
# still hardcode this path internally; the fixtures here exist so that
# future tests (and the #9 refactor) can avoid the duplication.
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_path() -> Path:
    """Absolute path to the repo root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def cfg(repo_path: Path) -> dict:
    """Parsed `opencode.json` from the repo root."""
    with open(repo_path / "opencode.json", encoding="utf-8") as fh:
        return json.load(fh)

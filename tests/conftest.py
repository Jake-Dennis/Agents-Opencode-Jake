"""Pytest configuration and shared fixtures for the Agents-Opencode-Jake test suite.

Provides:
  - `repo_path` fixture: absolute path to the repo root.
  - `cfg` fixture: parsed `opencode.json` as a Python dict.
  - `agent_names` fixture: list of all 13 agent names.
  - `work_log_path` fixture: path to .opencode/work-log.md.
  - `reset_work_log` autouse fixture: ensures work-log tests don't leave side effects.

Layer 2 task #9 expanded this from a 2-fixture stub to a full fixture library.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_AGENT_NAMES = [
    "conductor", "planner", "builder", "architect", "reviewer", "tester",
    "docs", "debugger", "refactor", "git", "explorer", "security", "perf",
]


@pytest.fixture(scope="session")
def repo_path() -> Path:
    """Absolute path to the repo root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def cfg(repo_path: Path) -> dict:
    """Parsed `opencode.json` from the repo root."""
    with open(repo_path / "opencode.json", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def schema(repo_path: Path) -> dict:
    """Parsed `opencode.schema.json` from the repo root."""
    with open(repo_path / "opencode.schema.json", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def agent_names(cfg) -> list[str]:
    """List of all 13 agent names from opencode.json."""
    return list(cfg["agent"].keys())


@pytest.fixture(scope="session")
def conductor_prompt(cfg) -> str:
    """The conductor's prompt text."""
    return cfg["agent"]["conductor"]["prompt"]


@pytest.fixture
def work_log_path(repo_path: Path) -> Path:
    """Path to .opencode/work-log.md. Yields the path; tests should append/read freely."""
    return repo_path / ".opencode" / "work-log.md"


@pytest.fixture
def reset_work_log(work_log_path: Path):
    """Snapshot the work-log, yield, then restore on test exit.

    Use this in any test that modifies work-log.md to ensure no side effects.
    """
    original = work_log_path.read_text(encoding="utf-8") if work_log_path.exists() else ""
    yield work_log_path
    work_log_path.write_text(original, encoding="utf-8")


@pytest.fixture
def plans_dir(repo_path: Path) -> Path:
    """Path to .opencode/plans/. Yields the dir; tests can add/remove plan files."""
    return repo_path / ".opencode" / "plans"


@pytest.fixture
def completed_plans_dir(repo_path: Path) -> Path:
    """Path to .opencode/plans/completed/."""
    return repo_path / ".opencode" / "plans" / "completed"

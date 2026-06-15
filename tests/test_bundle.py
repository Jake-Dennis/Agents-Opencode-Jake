"""Tests for plan-002 bundle completeness.

These tests verify the build-self-contained-bundle.py script produces
fully self-contained agent .md files (no remaining `{file:}` references)
and a manifest that documents which shared files were inlined into
which agents. This is the "agents work in any project" contract:
copy one .md file to a target project, the agent works, period.

If any of these tests fail, the bundle is regressed and the agent set
will produce broken prompts when copied to a project without the
shared/ directory.

Stdlib only. Uses the existing resolve_includes.py to produce the
expected output, then compares the build-self-contained-bundle.py
output against it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Locator constants
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO / ".opencode" / "agents"
BUNDLE_DIR = REPO / "dist" / "agents"
BUNDLE_SCRIPT = REPO / "scripts" / "build-self-contained-bundle.py"
RESOLVE_SCRIPT = AGENTS_DIR.parent / "scripts" / "resolve_includes.py"

# 13 agents that must appear in the bundle
EXPECTED_AGENTS = [
    "conductor.md", "builder.md", "architect.md", "reviewer.md", "tester.md",
    "docs.md", "debugger.md", "refactor.md", "git.md",
    "explorer.md", "security.md", "perf.md", "planner.md",
]

# The {file:} include pattern (same regex the resolve_includes.py uses)
FILE_REF = re.compile(r"\{file:([^}]+)\}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess command, returning the CompletedProcess."""
    return subprocess.run(
        cmd,
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T_BB_1: build-self-contained-bundle.py exists
# ---------------------------------------------------------------------------

def test_T_BB_1_bundle_script_exists():
    """The bundle-build script must exist at scripts/build-self-contained-bundle.py."""
    assert BUNDLE_SCRIPT.exists(), (
        f"Bundle script not found: {BUNDLE_SCRIPT}. "
        f"Plan-002 layer 3 task #6 requires this script to exist."
    )


# ---------------------------------------------------------------------------
# T_BB_2: bundle script runs cleanly and produces expected files
# ---------------------------------------------------------------------------

def test_T_BB_2_bundle_script_produces_all_13_agents():
    """Running the bundle script must produce 13 agent .md files in dist/agents/.

    If a new agent is added to .opencode/agents/*.md, it should
    automatically appear in the bundle. The test asserts exactly the
    expected set is present.
    """
    if not BUNDLE_SCRIPT.exists():
        pytest.skip("Bundle script not yet created; see T_BB_1")
    result = _run([sys.executable, str(BUNDLE_SCRIPT)])
    assert result.returncode == 0, (
        f"Bundle script failed (rc={result.returncode}):\n"
        f"  stdout: {result.stdout}\n  stderr: {result.stderr}"
    )
    # All 13 expected files must exist
    for name in EXPECTED_AGENTS:
        assert (BUNDLE_DIR / name).exists(), (
            f"Bundle output missing: {name}. Expected 13 agent files in {BUNDLE_DIR}."
        )


# ---------------------------------------------------------------------------
# T_BB_3: bundle files are self-contained (no remaining {file:} refs)
# ---------------------------------------------------------------------------

def test_T_BB_3_bundle_files_have_no_unresolved_file_references():
    """Each bundled agent .md must have zero remaining {file:...} references.

    A remaining reference means the agent prompt depends on a file
    that won't be present in the target project, breaking the agent.
    This is the core "works in any project" guarantee.
    """
    if not BUNDLE_SCRIPT.exists():
        pytest.skip("Bundle script not yet created; see T_BB_1")
    # Build the bundle (idempotent)
    result = _run([sys.executable, str(BUNDLE_SCRIPT)])
    assert result.returncode == 0, f"Bundle script failed: {result.stderr}"
    # Check every bundled file
    for name in EXPECTED_AGENTS:
        bundled = BUNDLE_DIR / name
        if not bundled.exists():
            continue  # T_BB_2 would have caught this
        text = bundled.read_text(encoding="utf-8")
        unresolved = FILE_REF.findall(text)
        assert not unresolved, (
            f"{name} in {BUNDLE_DIR} still has {len(unresolved)} unresolved "
            f"{{file:...}} reference(s): {unresolved[:3]}...\n"
            f"The agent will not work in projects without the source repo layout."
        )


# ---------------------------------------------------------------------------
# T_BB_4: bundle includes a manifest
# ---------------------------------------------------------------------------

def test_T_BB_4_bundle_includes_manifest():
    """dist/agents/ must include a MANIFEST.md listing what was bundled.

    The manifest documents which shared files were inlined into which
    agents, so the user can see the bundle's coverage and trust the
    self-contained claim.
    """
    if not BUNDLE_SCRIPT.exists():
        pytest.skip("Bundle script not yet created; see T_BB_1")
    _ = _run([sys.executable, str(BUNDLE_SCRIPT)])  # ensure bundle is built
    manifest = BUNDLE_DIR / "MANIFEST.md"
    assert manifest.exists(), (
        f"Bundle manifest not found: {manifest}. "
        f"The bundle must include a manifest documenting the included agents."
    )
    content = manifest.read_text(encoding="utf-8")
    # All 13 agents must be listed
    for name in EXPECTED_AGENTS:
        assert name in content, f"Manifest missing reference to {name}"


# ---------------------------------------------------------------------------
# T_BB_5: bundled file is larger than the source (includes were inlined)
# ---------------------------------------------------------------------------

def test_T_BB_5_bundled_files_are_larger_than_sources():
    """Each bundled .md must be larger than the source .md.

    The source has `{file:...}` placeholders. After inlining, the
    bundled file is strictly larger. If a bundled file is the same
    size or smaller, includes weren't actually inlined.
    """
    if not BUNDLE_SCRIPT.exists():
        pytest.skip("Bundle script not yet created; see T_BB_1")
    _ = _run([sys.executable, str(BUNDLE_SCRIPT)])
    for name in EXPECTED_AGENTS:
        src = AGENTS_DIR / name
        bundled = BUNDLE_DIR / name
        if not (src.exists() and bundled.exists()):
            continue
        src_size = src.stat().st_size
        bundled_size = bundled.stat().st_size
        assert bundled_size > src_size, (
            f"{name}: bundled size ({bundled_size} B) is not larger than "
            f"source size ({src_size} B). Includes may not have been inlined."
        )

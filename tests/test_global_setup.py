"""Tests for the opencode_jsonc_merge helper (.opencode/scripts/opencode_jsonc_merge.py).

These tests are isolation-friendly: every test uses pytest's ``tmp_path``
fixture to create a fresh project / global / manifest layout, so no real
user config is touched. The helper is imported by adding
``.opencode/scripts`` to ``sys.path`` at the top of this file (no conftest
fixture is required, per the plan-002 instructions).

Why no class wrappers or extra fixtures: matches the project's existing
test style (``tests/test_conductor_workflow.py`` etc.) and the conductor's
explicit instruction in plan-002 to keep this file self-contained.

Coverage target (from plan-002 Layer 3 task #7):
- JSONC tolerance: line / block / trailing-comma stripping
- Atomic write semantics (.tmp + os.replace, no leftover)
- ``dedupe_union`` is case-insensitive and order-preserving
- ``deep_merge`` is recursive, b wins
- ``header_comment`` emits a valid ``//`` header
- ``cmd_install`` per-key merge policy (scalars overwrite, skills.paths
  union, instructions union + auto-adds repo AGENTS.md, agents deep-merge
  with collision warn, manifest written)
- ``cmd_install`` idempotency
- ``cmd_remove`` is surgical: drops only what ``manifest.added`` lists,
  leaves user scalars + user agents alone
- Round trip: install -> remove is a clean (per-design) no-op for the
  parts the user owned, and removes everything the project contributed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pytest

# Make the helper importable without touching conftest.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".opencode" / "scripts"))
import opencode_jsonc_merge  # noqa: E402


# ---------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------


def _project_file(tmp_path: Path, **cfg) -> Path:
    """Write a project ``opencode.json`` and return its path.

    Defaults are the three scalar keys the helper overwrites, so callers
    can omit them and just specify the key(s) they care about. The parent
    dir is created so the helper can also auto-discover ``AGENTS.md``.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir(exist_ok=True)
    project = {
        "default_agent": "conductor",
        "model": "opencode/minimax-m3-free",
        "small_model": "opencode/minimax-m3-free",
    }
    project.update(cfg)
    project_file = project_dir / "opencode.json"
    project_file.write_text(json.dumps(project), encoding="utf-8")
    return project_file


def _global_file(tmp_path: Path, **cfg) -> Path:
    """Write a global ``opencode.jsonc`` and return its path."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(exist_ok=True)
    g = cfg_dir / "opencode.jsonc"
    g.write_text(json.dumps(cfg), encoding="utf-8")
    return g


def _manifest_file(tmp_path: Path) -> Path:
    return tmp_path / "manifest.json"


def _install_args(project: Path, global_path: Path, manifest: Path, *,
                  force: bool = False, dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        project=str(project),
        global_path=str(global_path),
        manifest=str(manifest),
        force=force,
        dry_run=dry_run,
    )


def _remove_args(global_path: Path, manifest: Path, *,
                 dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        global_path=str(global_path),
        manifest=str(manifest),
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------
# JSONC loading
# ---------------------------------------------------------------------


def test_load_jsonc_handles_missing_file(tmp_path):
    """Missing file -> empty dict (first-install bootstrap case)."""
    assert opencode_jsonc_merge.load_jsonc(tmp_path / "nonexistent.json") == {}


def test_load_jsonc_strips_line_comments(tmp_path):
    p = tmp_path / "test.jsonc"
    p.write_text('{"key": "value"} // trailing comment\n', encoding="utf-8")
    assert opencode_jsonc_merge.load_jsonc(p) == {"key": "value"}


def test_load_jsonc_strips_block_comments(tmp_path):
    p = tmp_path / "test.jsonc"
    p.write_text('{"key": /* block comment */ "value"}', encoding="utf-8")
    assert opencode_jsonc_merge.load_jsonc(p) == {"key": "value"}


def test_load_jsonc_strips_trailing_commas(tmp_path):
    p = tmp_path / "test.jsonc"
    p.write_text('{"a": 1, "b": 2,}', encoding="utf-8")
    assert opencode_jsonc_merge.load_jsonc(p) == {"a": 1, "b": 2}


def test_load_jsonc_handles_all_three_together(tmp_path):
    p = tmp_path / "test.jsonc"
    p.write_text(
        '{\n'
        '  // a line comment\n'
        '  "key": "value", /* inline block */\n'
        '  "arr": [1, 2, 3,],\n'
        '}\n',
        encoding="utf-8",
    )
    assert opencode_jsonc_merge.load_jsonc(p) == {"key": "value", "arr": [1, 2, 3]}


# ---------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------


def test_atomic_write_creates_tmp_and_replaces(tmp_path):
    p = tmp_path / "out.json"
    opencode_jsonc_merge.atomic_write(p, {"a": 1, "b": 2}, None)
    # File exists.
    assert p.exists()
    # The .tmp sibling is gone (os.replace moved it).
    assert not (tmp_path / "out.json.tmp").exists()
    # A re-read returns the same data.
    assert opencode_jsonc_merge.load_jsonc(p) == {"a": 1, "b": 2}


def test_atomic_write_prepends_header(tmp_path):
    p = tmp_path / "out.jsonc"
    opencode_jsonc_merge.atomic_write(
        p, {"a": 1}, "// header line 1\n// header line 2\n"
    )
    text = p.read_text(encoding="utf-8")
    # The header is literally at the top, before the JSON body.
    assert text.startswith("// header line 1\n// header line 2\n")
    # The header is a valid JSONC comment, so a re-read still parses.
    assert opencode_jsonc_merge.load_jsonc(p) == {"a": 1}


# ---------------------------------------------------------------------
# Pure-function utilities
# ---------------------------------------------------------------------


def test_dedupe_union_case_insensitive_preserves_order():
    """Case-insensitive path dedupe; first-seen order wins."""
    a = [r"C:\Foo\Bar", r"C:\Baz"]
    b = [r"c:\foo\bar", r"C:\Quux"]
    result = opencode_jsonc_merge.dedupe_union(a, b)
    assert result == [r"C:\Foo\Bar", r"C:\Baz", r"C:\Quux"]


def test_deep_merge_recursive_b_wins():
    """Recursive dict merge; b wins on leaf conflicts; inputs not mutated."""
    a = {"x": 1, "nested": {"a": 1, "b": 2}}
    b = {"y": 2, "nested": {"b": 20, "c": 3}}
    result = opencode_jsonc_merge.deep_merge(a, b)
    assert result == {"x": 1, "y": 2, "nested": {"a": 1, "b": 20, "c": 3}}
    # Inputs are not mutated (per docstring: returns a new dict).
    assert a == {"x": 1, "nested": {"a": 1, "b": 2}}
    assert b == {"y": 2, "nested": {"b": 20, "c": 3}}


# ---------------------------------------------------------------------
# Header comment
# ---------------------------------------------------------------------


def test_header_comment_install_mode():
    h = opencode_jsonc_merge.header_comment(
        "install", "/path/to/project", {"agent_names": ["foo", "bar"]}
    )
    assert h.startswith("//")
    assert "opencode-jake" in h
    assert "installed" in h
    assert "foo, bar" in h


def test_header_comment_remove_mode():
    h = opencode_jsonc_merge.header_comment("remove", "/path/to/project", {})
    assert h.startswith("//")
    assert "opencode-jake" in h
    assert "uninstalled" in h


def test_header_survives_reread(tmp_path):
    """The // header written by install is valid JSONC, so a re-read works."""
    project = _project_file(tmp_path)
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)
    rc = opencode_jsonc_merge.cmd_install(
        _install_args(project, g, manifest)
    )
    assert rc == 0

    text = g.read_text(encoding="utf-8")
    assert text.startswith("//")

    # Re-loading strips the // comments and returns the data intact.
    reloaded = opencode_jsonc_merge.load_jsonc(g)
    assert isinstance(reloaded, dict)
    assert reloaded.get("default_agent") == "conductor"


# ---------------------------------------------------------------------
# cmd_install — scalars
# ---------------------------------------------------------------------


def test_install_merges_scalar_keys(tmp_path):
    """default_agent, model, small_model are overwritten from the project."""
    project = _project_file(
        tmp_path,
        default_agent="conductor",
        model="opencode/project-model",
        small_model="opencode/project-small",
    )
    g = _global_file(
        tmp_path,
        default_agent="user-default",
        model="opencode/old",
        small_model="opencode/old-small",
    )
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    result = opencode_jsonc_merge.load_jsonc(g)
    assert result["default_agent"] == "conductor"
    assert result["model"] == "opencode/project-model"
    assert result["small_model"] == "opencode/project-small"


# ---------------------------------------------------------------------
# cmd_install — skills.paths and instructions unions
# ---------------------------------------------------------------------


def test_install_unions_skills_paths_idempotent(tmp_path):
    """Two consecutive installs do not duplicate skills.paths entries."""
    project = _project_file(tmp_path, skills={"paths": [r"C:\proj\skill-A"]})
    g = _global_file(tmp_path, skills={"paths": [r"C:\existing\skill"]})
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    opencode_jsonc_merge.cmd_install(args)
    first = opencode_jsonc_merge.load_jsonc(g)["skills"]["paths"]

    opencode_jsonc_merge.cmd_install(args)
    second = opencode_jsonc_merge.load_jsonc(g)["skills"]["paths"]

    assert first == second


def test_install_unions_instructions_and_adds_repo_agents_md(tmp_path):
    """instructions unions with the project's, and the repo's AGENTS.md
    is auto-appended (per the merge policy in plan-002)."""
    project = _project_file(tmp_path, instructions=[r"C:\proj\instructions.md"])
    # _project_file created project/ — now drop the AGENTS.md next to opencode.json.
    (project.parent / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    g = _global_file(tmp_path, instructions=[r"C:\user\instructions.md"])
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    instrs = opencode_jsonc_merge.load_jsonc(g)["instructions"]
    # Pre-existing user instruction is preserved.
    assert r"C:\user\instructions.md" in instrs
    # Project's instruction is added.
    assert r"C:\proj\instructions.md" in instrs
    # The repo's AGENTS.md is auto-added.
    assert any(p.endswith("AGENTS.md") for p in instrs), (
        f"expected AGENTS.md in instructions, got: {instrs}"
    )


# ---------------------------------------------------------------------
# cmd_install — agent block (collision / --force)
# ---------------------------------------------------------------------


def test_install_deep_merges_agent_block_warns_on_collision(tmp_path, capsys):
    """On agent-name collision, helper warns to stderr and preserves the
    user's existing entry (does not overwrite without --force)."""
    project = _project_file(tmp_path, agent={"conductor": {"description": "PROJ"}})
    g = _global_file(tmp_path, agent={"conductor": {"description": "USER"}})
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    captured = capsys.readouterr()
    assert "WARN" in captured.err
    assert "conductor" in captured.err


def test_install_collision_preserves_user_agent(tmp_path):
    """Explicit assertion: the user's agent survives a collision skip."""
    project = _project_file(tmp_path, agent={"conductor": {"description": "PROJ"}})
    g = _global_file(tmp_path, agent={"conductor": {"description": "USER"}})
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert result["agent"]["conductor"]["description"] == "USER"


def test_install_with_force_overwrites_agents(tmp_path):
    """With --force, the project's agent value wins on conflict."""
    project = _project_file(tmp_path, agent={"conductor": {"description": "PROJ"}})
    g = _global_file(tmp_path, agent={"conductor": {"description": "USER"}})
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(
        _install_args(project, g, manifest, force=True)
    )

    result = opencode_jsonc_merge.load_jsonc(g)
    assert result["agent"]["conductor"]["description"] == "PROJ"


# ---------------------------------------------------------------------
# cmd_install — manifest + dry-run
# ---------------------------------------------------------------------


def test_install_writes_manifest(tmp_path):
    """Install writes a manifest with version, installed_at, repo_dir, added[]."""
    project = _project_file(tmp_path)
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0
    assert manifest.exists()

    data = opencode_jsonc_merge.load_jsonc(manifest)
    assert data.get("version") == 1
    assert "installed_at" in data
    assert "repo_dir" in data
    assert "added" in data


def test_install_dry_run_writes_nothing(tmp_path):
    """With --dry-run, neither the global nor the manifest is written."""
    project = _project_file(
        tmp_path,
        default_agent="conductor",
        model="opencode/x",
        small_model="opencode/y",
    )
    g = _global_file(tmp_path, default_agent="user-default")
    initial_text = g.read_text(encoding="utf-8")
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(
        _install_args(project, g, manifest, dry_run=True)
    )
    assert rc == 0

    # Global untouched.
    assert g.read_text(encoding="utf-8") == initial_text
    # Manifest never created.
    assert not manifest.exists()


# ---------------------------------------------------------------------
# cmd_remove — surgical drops
# ---------------------------------------------------------------------


def test_remove_surgically_drops_merged_agents(tmp_path):
    """Remove deletes only the agents the manifest says we added."""
    project = _project_file(tmp_path, agent={"tester": {"description": "T"}})
    g = _global_file(tmp_path, agent={"user-agent": {"description": "USER"}})
    manifest = _manifest_file(tmp_path)

    # Install.
    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert "tester" in opencode_jsonc_merge.load_jsonc(g)["agent"]

    # Remove.
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))
    result = opencode_jsonc_merge.load_jsonc(g)

    # Project's agent is gone; user's agent is preserved.
    assert "tester" not in result["agent"]
    assert "user-agent" in result["agent"]


def test_remove_surgically_drops_merged_skills_paths(tmp_path):
    """Remove drops only the skills.paths entries the manifest recorded."""
    project = _project_file(tmp_path, skills={"paths": [r"C:\proj\my-skill"]})
    g = _global_file(tmp_path, skills={"paths": [r"C:\existing\path"]})
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    paths = result.get("skills", {}).get("paths", [])

    # Merged paths are gone; only the user's original survives.
    assert r"C:\proj\my-skill" not in paths
    assert r"C:\existing\path" in paths
    # The helper also adds <global parent>/skills to the merged list, and
    # that should be removed too. After the remove, only the user's path
    # remains.
    assert len(paths) == 1


def test_remove_surgically_drops_merged_instructions(tmp_path):
    """Remove drops only the instructions the manifest recorded."""
    project = _project_file(tmp_path, instructions=[r"C:\proj\instr.md"])
    (project.parent / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    g = _global_file(tmp_path, instructions=[r"C:\user\instr.md"])
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    instrs = result.get("instructions", [])

    # Project's contribution and the auto-added AGENTS.md are gone.
    assert r"C:\proj\instr.md" not in instrs
    assert not any(p.endswith("AGENTS.md") for p in instrs)
    # User's instruction survives.
    assert r"C:\user\instr.md" in instrs


def test_remove_preserves_scalars(tmp_path):
    """Explicit: scalar keys are NOT restored on remove (architect's design).

    See the long comment in ``cmd_remove`` and ADR-002. We overwrite
    ``default_agent`` on install because the project is authoritative for
    this project family. On remove we cannot safely restore the user's
    previous value (another project may have overwritten it in the
    meantime), so we leave the current value alone. The user can edit it
    by hand.
    """
    project = _project_file(tmp_path, default_agent="conductor")
    g = _global_file(tmp_path, default_agent="user-default")
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    # Sanity: install overwrote the scalar.
    assert opencode_jsonc_merge.load_jsonc(g)["default_agent"] == "conductor"

    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))
    result = opencode_jsonc_merge.load_jsonc(g)

    # Still "conductor" — NOT restored to "user-default".
    assert result["default_agent"] == "conductor"


def test_remove_preserves_user_agents_not_in_manifest(tmp_path):
    """User agents that pre-existed in the global are not in the manifest,
    so remove leaves them alone."""
    project = _project_file(tmp_path, agent={"tester": {"description": "T"}})
    g = _global_file(
        tmp_path,
        agent={
            "user-agent-1": {"description": "U1"},
            "user-agent-2": {"description": "U2"},
        },
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert "user-agent-1" in result["agent"]
    assert "user-agent-2" in result["agent"]
    assert "tester" not in result["agent"]


def test_remove_deletes_manifest(tmp_path):
    """After a successful remove, the manifest file is gone."""
    project = _project_file(tmp_path)
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert manifest.exists()

    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))
    assert not manifest.exists()


# ---------------------------------------------------------------------
# End-to-end / round trip
# ---------------------------------------------------------------------


def test_round_trip_install_then_remove(tmp_path):
    """Install then remove leaves the global in a known post-state.

    Per the merge policy + ADR-002:
    * Project-contributed agents / skills.paths / instructions are gone.
    * Pre-existing user entries (instructions etc.) survive.
    * Scalars are NOT restored — see test_remove_preserves_scalars.
    * Manifest is deleted.
    """
    project = _project_file(
        tmp_path,
        agent={"tester": {"description": "T"}},
        skills={"paths": [r"C:\proj\skill"]},
        instructions=[r"C:\proj\instr.md"],
    )
    (project.parent / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    g = _global_file(
        tmp_path,
        default_agent="user-default",
        instructions=[r"C:\user\instr.md"],
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)

    # User's pre-existing instructions are preserved.
    assert r"C:\user\instr.md" in result.get("instructions", [])
    # Project's contribution is gone.
    assert r"C:\proj\instr.md" not in result.get("instructions", [])
    assert "tester" not in result.get("agent", {})
    # default_agent is NOT restored (architect's design).
    assert result["default_agent"] == "conductor"
    # Manifest is gone.
    assert not manifest.exists()


def test_idempotent_install(tmp_path):
    """Running install twice produces a deep-equal global config."""
    project = _project_file(
        tmp_path,
        agent={"tester": {"description": "T"}},
        skills={"paths": [r"C:\proj\skill"]},
        instructions=[r"C:\proj\instr.md"],
    )
    g = _global_file(tmp_path, default_agent="user-default")
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    opencode_jsonc_merge.cmd_install(args)
    first = opencode_jsonc_merge.load_jsonc(g)

    opencode_jsonc_merge.cmd_install(args)
    second = opencode_jsonc_merge.load_jsonc(g)

    # Deep-equal: same scalars, same lists (no dupes), same agent map.
    assert first == second


def test_manifest_preserves_agent_names_across_idempotent_reruns(tmp_path):
    """Re-running install on a no-op (all collisions) MUST NOT clobber the
    manifest's added.agent_names. Otherwise a later uninstall would leave
    stale agents in the global config."""
    import json
    project = _project_file(
        tmp_path,
        agent={"conductor": {"description": "T", "mode": "primary", "prompt": "p"}},
    )
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    # First install: should add the agent.
    opencode_jsonc_merge.cmd_install(args)
    m1 = json.loads(manifest.read_text())
    assert m1["added"]["agent_names"] == ["conductor"]

    # Second install: collision (agent already in global), 0 added.
    opencode_jsonc_merge.cmd_install(args)
    m2 = json.loads(manifest.read_text())
    # Manifest must STILL remember the original 13 (here, 1) additions
    # so uninstall can later remove them.
    assert m2["added"]["agent_names"] == ["conductor"]
    assert len(m2["added"]["collisions"]) == 1
    assert m2["added"]["collisions"][0] == "conductor"


def test_manifest_unions_skills_paths_and_instructions_across_reruns(tmp_path):
    """Re-running install should union (not replace) the manifest's
    skills_paths and instructions lists."""
    import json
    project = _project_file(
        tmp_path,
        skills={"paths": [r"C:\proj\skill"]},
        instructions=[r"C:\proj\instr.md"],
    )
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    opencode_jsonc_merge.cmd_install(args)
    m1 = json.loads(manifest.read_text())
    assert r"C:\proj\skill" in m1["added"]["skills_paths"]
    assert r"C:\proj\instr.md" in m1["added"]["instructions"]

    opencode_jsonc_merge.cmd_install(args)
    m2 = json.loads(manifest.read_text())
    # No duplicate entries on re-run.
    assert m2["added"]["skills_paths"].count(r"C:\proj\skill") == 1
    assert m2["added"]["instructions"].count(r"C:\proj\instr.md") == 1

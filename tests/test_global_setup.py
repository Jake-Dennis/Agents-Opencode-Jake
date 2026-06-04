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
    """Install writes a manifest with version, installed_at, repo_dir, added[].
    Plan-003 bumped the version to 2 and added new list-valued fields to
    ``added``. The snapshot fields (`provider_snapshot`, `permission_snapshot`)
    are only present when the project actually contributed those blocks
    — absence means "we never touched this block, nothing to restore on
    uninstall"."""
    project = _project_file(tmp_path)
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0
    assert manifest.exists()

    data = opencode_jsonc_merge.load_jsonc(manifest)
    assert data.get("version") == 2
    assert "installed_at" in data
    assert "repo_dir" in data
    added = data.get("added", {})
    assert "agent_names" in added
    # Plan-003 list-valued fields are always present (empty list when
    # the project doesn't contribute to that block).
    assert "command_names" in added
    assert "mcp_names" in added
    assert "enabled_providers_added" in added
    # Snapshot fields are conditional: present only if the project
    # actually contributed provider/permission. The plain
    # _project_file() does not contribute either, so both keys are
    # absent here.
    assert "provider_snapshot" not in added
    assert "permission_snapshot" not in added


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
    """Re-running install on a no-op MUST NOT clobber the manifest's
    added.agent_names. Otherwise a later uninstall would leave stale
    agents in the global config.

    On a re-install with the same project, the existing global copy of
    each agent deep-equals the project copy, so it is treated as a
    no-op: 0 added, 0 collisions. The manifest-merge step still unions
    the new run's empty agent_names with prev_added, so the manifest
    carries the cumulative 1 entry forward."""
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

    # Second install: existing global copy deep-equals project copy,
    # so no-op. Manifest must STILL remember the original 1 addition
    # so uninstall can later remove it.
    opencode_jsonc_merge.cmd_install(args)
    m2 = json.loads(manifest.read_text())
    assert m2["added"]["agent_names"] == ["conductor"]
    assert m2["added"]["collisions"] == []


def test_agent_collision_only_when_content_differs(tmp_path):
    """A re-install on a no-op should NOT report a collision (the
    existing global copy deep-equals the project copy, so there is
    nothing to skip or warn about). A genuine user-customized agent
    with the same name should still be reported as a collision."""
    import json

    def _make_project(parent: Path, prompt: str) -> Path:
        parent.mkdir(exist_ok=True)
        pf = parent / "opencode.json"
        pf.write_text(
            json.dumps(
                {
                    "default_agent": "conductor",
                    "model": "opencode/x",
                    "agent": {
                        "conductor": {
                            "description": "T",
                            "mode": "primary",
                            "prompt": prompt,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return pf

    project1 = _make_project(tmp_path / "p1", "ORIG")
    project2 = _make_project(tmp_path / "p2", "DIFFERENT")
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)

    # First install with project1.
    opencode_jsonc_merge.cmd_install(_install_args(project1, g, manifest))
    m1 = json.loads(manifest.read_text())
    assert m1["added"]["agent_names"] == ["conductor"]
    assert m1["added"]["collisions"] == []

    # Re-install with project1: no-op (deep-equal).
    opencode_jsonc_merge.cmd_install(_install_args(project1, g, manifest))
    m2 = json.loads(manifest.read_text())
    assert m2["added"]["agent_names"] == ["conductor"]
    assert m2["added"]["collisions"] == []

    # Install with project2 (different prompt): collision, no overwrite
    # without --force.
    opencode_jsonc_merge.cmd_install(_install_args(project2, g, manifest))
    m3 = json.loads(manifest.read_text())
    assert m3["added"]["agent_names"] == ["conductor"]  # no new addition
    assert m3["added"]["collisions"] == ["conductor"]  # but flagged
    # Global still has the project1 version.
    g_cfg = opencode_jsonc_merge.load_jsonc(g)
    assert g_cfg["agent"]["conductor"]["prompt"] == "ORIG"


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


# ---------------------------------------------------------------------
# Plan-003: command / mcp / provider / permission / enabled_providers / $schema
# ---------------------------------------------------------------------


def test_install_deep_merges_command_block(tmp_path):
    """Project's `command` block is merged into the global. User's
    pre-existing `command.<name>` entries survive."""
    project = _project_file(
        tmp_path,
        command={
            "setup-project": {
                "description": "Init project",
                "template": "Do the thing",
            },
        },
    )
    g = _global_file(
        tmp_path,
        command={
            "user-cmd": {"description": "USER", "template": "User template"},
        },
    )
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    result = opencode_jsonc_merge.load_jsonc(g)
    cmds = result.get("command", {})
    # Project's command is now in global.
    assert "setup-project" in cmds
    assert cmds["setup-project"]["description"] == "Init project"
    # User's pre-existing command survives.
    assert "user-cmd" in cmds
    assert cmds["user-cmd"]["description"] == "USER"


def test_install_command_overwrites_on_name_conflict(tmp_path):
    """On `command.<name>` conflict, project's value wins (no warn)."""
    project = _project_file(
        tmp_path,
        command={
            "setup-project": {
                "description": "PROJ",
                "template": "Project template",
            },
        },
    )
    g = _global_file(
        tmp_path,
        command={
            "setup-project": {
                "description": "USER",
                "template": "User template",
            },
        },
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert result["command"]["setup-project"]["description"] == "PROJ"
    assert result["command"]["setup-project"]["template"] == "Project template"


def test_install_records_command_names_in_manifest(tmp_path):
    """Manifest's added.command_names lists every command name the project contributed."""
    import json
    project = _project_file(
        tmp_path,
        command={
            "setup-project": {"description": "d", "template": "t"},
            "build": {"description": "d", "template": "t"},
        },
    )
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    data = json.loads(manifest.read_text())
    assert "command_names" in data["added"]
    assert set(data["added"]["command_names"]) == {"setup-project", "build"}


def test_install_deep_merges_mcp_block(tmp_path):
    """Project's `mcp` block is merged into global. User's MCPs survive."""
    project = _project_file(
        tmp_path,
        mcp={
            "graphify": {
                "type": "local",
                "command": ["python3", "-m", "graphify.serve"],
                "enabled": True,
            },
        },
    )
    g = _global_file(
        tmp_path,
        mcp={
            "user-mcp": {"type": "local", "command": ["x"], "enabled": True},
        },
    )
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    result = opencode_jsonc_merge.load_jsonc(g)
    assert "graphify" in result["mcp"]
    assert "user-mcp" in result["mcp"]


def test_install_mcp_overwrites_on_name_conflict(tmp_path):
    """On `mcp.<name>` conflict, project's value wins."""
    project = _project_file(
        tmp_path,
        mcp={"graphify": {"type": "local", "command": ["PROJ"], "enabled": True}},
    )
    g = _global_file(
        tmp_path,
        mcp={"graphify": {"type": "local", "command": ["USER"], "enabled": True}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert result["mcp"]["graphify"]["command"] == ["PROJ"]


def test_install_deep_merges_provider_block(tmp_path):
    """Project's `provider` block is recursively deep-merged. User's
    other providers survive; project wins at leaf conflicts."""
    project = _project_file(
        tmp_path,
        provider={
            "opencode": {"options": {"reasoning_effort": "max", "new_key": "proj"}},
        },
    )
    g = _global_file(
        tmp_path,
        provider={
            "opencode": {"options": {"reasoning_effort": "min"}},
            "anthropic": {"options": {"api_key_env": "ANTHROPIC_API_KEY"}},
        },
    )
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    result = opencode_jsonc_merge.load_jsonc(g)
    p = result["provider"]
    # User's other provider survives.
    assert "anthropic" in p
    assert p["anthropic"]["options"]["api_key_env"] == "ANTHROPIC_API_KEY"
    # Project's new option is added.
    assert p["opencode"]["options"]["new_key"] == "proj"
    # Project wins on the leaf conflict.
    assert p["opencode"]["options"]["reasoning_effort"] == "max"


def test_install_snapshots_provider_before_merge(tmp_path):
    """Provider snapshot in manifest captures the pre-merge value, not the
    post-merge value. This is the safety net for safe uninstall."""
    import json
    project = _project_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "max"}}},
    )
    g = _global_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "min"}}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    data = json.loads(manifest.read_text())

    snap = data["added"]["provider_snapshot"]
    # Snapshot captured the user's pre-install value.
    assert snap is not None
    assert snap["opencode"]["options"]["reasoning_effort"] == "min"


def test_install_provider_snapshot_is_deep_copy(tmp_path):
    """The snapshot is a deep copy — mutating the global's provider after
    install does not bleed into the manifest's snapshot."""
    import json
    project = _project_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "max"}}},
    )
    g = _global_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "min"}}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    # Mutate the global's provider post-install.
    cfg = opencode_jsonc_merge.load_jsonc(g)
    cfg["provider"]["opencode"]["options"]["reasoning_effort"] = "TAMPERED"
    # The snapshot in the manifest must NOT reflect this tamper.
    data = json.loads(manifest.read_text())
    snap = data["added"]["provider_snapshot"]
    assert snap["opencode"]["options"]["reasoning_effort"] == "min"


def test_install_snapshot_not_taken_on_rerun_if_already_captured(tmp_path):
    """Regression: on re-install, the snapshot for `provider` must
    reflect the PRE-FIRST-install value, not the post-merge value
    (which is what the global currently has because the first install
    already merged)."""
    import json
    # User has NO provider pre-install. Project has one.
    project = _project_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "max"}}},
    )
    g = _global_file(tmp_path)  # no pre-existing provider
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    # First install: snapshot is None (user had no provider).
    opencode_jsonc_merge.cmd_install(args)
    m1 = json.loads(manifest.read_text())
    assert m1["added"]["provider_snapshot"] is None

    # Re-run: snapshot must STILL be None — the install must not
    # re-snapshot the now-merged global value.
    opencode_jsonc_merge.cmd_install(args)
    m2 = json.loads(manifest.read_text())
    assert m2["added"]["provider_snapshot"] is None, (
        f"snapshot became non-None on re-run: {m2['added']['provider_snapshot']!r}"
    )


def test_install_permission_snapshot_not_taken_on_rerun_if_already_captured(tmp_path):
    """Same as test_install_provider_snapshot_not_taken_on_rerun_if_already_captured
    but for the permission block. Belt and braces: the same code path
    but verifying the separate field behaves identically."""
    import json
    project = _project_file(
        tmp_path,
        permission={"bash": {"*": "deny"}},
    )
    g = _global_file(tmp_path)  # no pre-existing permission
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    opencode_jsonc_merge.cmd_install(args)
    m1 = json.loads(manifest.read_text())
    assert m1["added"]["permission_snapshot"] is None

    opencode_jsonc_merge.cmd_install(args)
    m2 = json.loads(manifest.read_text())
    assert m2["added"]["permission_snapshot"] is None


def test_install_deep_merges_permission_block(tmp_path):
    """Project's `permission` block is recursively deep-merged. User's
    existing rules survive; project's rules are added; conflicts at the
    leaf are resolved in project's favor."""
    project = _project_file(
        tmp_path,
        permission={
            "bash": {
                "git *": "allow",
                "npm *": "allow",
                "rm *": "deny",
                "*": "ask",
            },
        },
    )
    g = _global_file(
        tmp_path,
        permission={
            "bash": {"git *": "ask", "docker *": "allow"},
            "external_directory": {"*": "allow"},
        },
    )
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    result = opencode_jsonc_merge.load_jsonc(g)
    perm = result["permission"]
    # User's external_directory rule survives.
    assert perm["external_directory"]["*"] == "allow"
    # User's docker rule survives (project didn't define it).
    assert perm["bash"]["docker *"] == "allow"
    # Project's new bash rules are added.
    assert perm["bash"]["npm *"] == "allow"
    assert perm["bash"]["rm *"] == "deny"
    # Project wins on leaf conflict (git *).
    assert perm["bash"]["git *"] == "allow"


def test_install_unions_enabled_providers(tmp_path):
    """enabled_providers unions and dedupes. User's existing providers
    survive; project's providers are added."""
    project = _project_file(tmp_path, enabled_providers=["opencode", "github-copilot"])
    g = _global_file(tmp_path, enabled_providers=["anthropic"])
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    result = opencode_jsonc_merge.load_jsonc(g)
    ep = result.get("enabled_providers", [])
    # User's provider survives.
    assert "anthropic" in ep
    # Project's providers are added.
    assert "opencode" in ep
    assert "github-copilot" in ep


def test_install_enabled_providers_dedupes_across_reruns(tmp_path):
    """Re-running install does not duplicate enabled_providers entries."""
    project = _project_file(tmp_path, enabled_providers=["opencode"])
    g = _global_file(tmp_path, enabled_providers=["opencode"])
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    opencode_jsonc_merge.cmd_install(args)
    first = opencode_jsonc_merge.load_jsonc(g)["enabled_providers"]
    opencode_jsonc_merge.cmd_install(args)
    second = opencode_jsonc_merge.load_jsonc(g)["enabled_providers"]

    assert first == second
    assert first.count("opencode") == 1


def test_install_overwrites_schema(tmp_path):
    """Project's $schema is copied to global (simple overwrite)."""
    project = _project_file(tmp_path, **{"$schema": "https://opencode.ai/config.json"})
    g = _global_file(tmp_path, **{"$schema": "https://example.com/old-schema"})
    manifest = _manifest_file(tmp_path)

    rc = opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    assert rc == 0

    result = opencode_jsonc_merge.load_jsonc(g)
    assert result["$schema"] == "https://opencode.ai/config.json"


def test_remove_surgically_drops_merged_command_names(tmp_path):
    """Remove deletes only the command names the manifest recorded."""
    project = _project_file(
        tmp_path,
        command={
            "setup-project": {"description": "d", "template": "t"},
            "build": {"description": "d", "template": "t"},
        },
    )
    g = _global_file(
        tmp_path,
        command={"user-cmd": {"description": "U", "template": "t"}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    # Project's commands are gone.
    assert "setup-project" not in result.get("command", {})
    assert "build" not in result.get("command", {})
    # User's command survives.
    assert "user-cmd" in result.get("command", {})


def test_remove_drops_empty_command_block(tmp_path):
    """When the project was the only contributor to `command`, the key
    is removed entirely on uninstall (no empty {} left behind)."""
    project = _project_file(
        tmp_path,
        command={"setup-project": {"description": "d", "template": "t"}},
    )
    g = _global_file(tmp_path)  # No pre-existing command
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert "command" not in result


def test_remove_surgically_drops_merged_mcp_names(tmp_path):
    """Remove deletes only the MCP names the manifest recorded."""
    project = _project_file(
        tmp_path,
        mcp={"graphify": {"type": "local", "command": ["x"], "enabled": True}},
    )
    g = _global_file(
        tmp_path,
        mcp={"user-mcp": {"type": "local", "command": ["y"], "enabled": True}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert "graphify" not in result.get("mcp", {})
    assert "user-mcp" in result.get("mcp", {})


def test_remove_filters_enabled_providers(tmp_path):
    """Remove filters out only the items we added; user's pre-existing
    items survive (even if the project also lists them)."""
    # Project adds "github-copilot" (new) and lists "opencode" (already
    # in the user's config — not a new addition from our perspective).
    project = _project_file(tmp_path, enabled_providers=["opencode", "github-copilot"])
    g = _global_file(tmp_path, enabled_providers=["anthropic", "opencode"])
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    ep = result.get("enabled_providers", [])
    # Item we actually added is gone.
    assert "github-copilot" not in ep
    # User's pre-existing items survive (anthropic AND opencode).
    assert "anthropic" in ep
    assert "opencode" in ep


def test_remove_drops_empty_enabled_providers_key(tmp_path):
    """When the project contributed all entries and the user had none,
    the enabled_providers key is removed entirely on uninstall."""
    project = _project_file(tmp_path, enabled_providers=["opencode"])
    g = _global_file(tmp_path)  # No pre-existing providers
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert "enabled_providers" not in result


def test_remove_restores_provider_from_snapshot(tmp_path):
    """Remove restores the provider block to its exact pre-install value,
    not the post-install deep-merged value."""
    import json
    project = _project_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "max"}}},
    )
    g = _global_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "min"}}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    # Sanity: install changed the global.
    assert opencode_jsonc_merge.load_jsonc(g)["provider"]["opencode"]["options"]["reasoning_effort"] == "max"

    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))
    result = opencode_jsonc_merge.load_jsonc(g)
    # Restored to the pre-install value.
    assert result["provider"]["opencode"]["options"]["reasoning_effort"] == "min"


def test_remove_restores_permission_from_snapshot(tmp_path):
    """Remove restores the permission block to its exact pre-install value."""
    project = _project_file(
        tmp_path,
        permission={"bash": {"*": "deny"}},
    )
    g = _global_file(
        tmp_path,
        permission={"bash": {"git *": "ask"}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    # Sanity: install changed the global.
    assert opencode_jsonc_merge.load_jsonc(g)["permission"]["bash"]["*"] == "deny"

    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))
    result = opencode_jsonc_merge.load_jsonc(g)
    # Restored to pre-install value; project's "*": "deny" is gone.
    assert "bash" in result["permission"]
    assert "*" not in result["permission"]["bash"]
    assert result["permission"]["bash"]["git *"] == "ask"


def test_remove_deletes_provider_key_if_no_snapshot(tmp_path):
    """If the user had no `provider` key pre-install, the key is deleted
    on remove (not left as an empty dict)."""
    project = _project_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "max"}}},
    )
    g = _global_file(tmp_path)  # No pre-existing provider
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert "provider" not in result


def test_remove_deletes_permission_key_if_no_snapshot(tmp_path):
    """If the user had no `permission` key pre-install, the key is deleted on remove."""
    project = _project_file(
        tmp_path,
        permission={"bash": {"*": "deny"}},
    )
    g = _global_file(tmp_path)  # No pre-existing permission
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    opencode_jsonc_merge.cmd_remove(_remove_args(g, manifest))

    result = opencode_jsonc_merge.load_jsonc(g)
    assert "permission" not in result


def test_manifest_unions_command_names_across_idempotent_reruns(tmp_path):
    """Re-running install unions command_names; no duplicates."""
    import json
    project = _project_file(
        tmp_path,
        command={"setup-project": {"description": "d", "template": "t"}},
    )
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    opencode_jsonc_merge.cmd_install(args)
    opencode_jsonc_merge.cmd_install(args)
    data = json.loads(manifest.read_text())
    assert data["added"]["command_names"].count("setup-project") == 1


def test_manifest_unions_mcp_names_across_idempotent_reruns(tmp_path):
    """Re-running install unions mcp_names; no duplicates."""
    import json
    project = _project_file(
        tmp_path,
        mcp={"graphify": {"type": "local", "command": ["x"], "enabled": True}},
    )
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)
    args = _install_args(project, g, manifest)

    opencode_jsonc_merge.cmd_install(args)
    opencode_jsonc_merge.cmd_install(args)
    data = json.loads(manifest.read_text())
    assert data["added"]["mcp_names"].count("graphify") == 1


def test_manifest_first_wins_for_provider_snapshot(tmp_path):
    """The first install that contributes a `provider` block takes the
    snapshot; subsequent installs (with the same or different project)
    preserve the original snapshot, even if the global's current
    `provider` value has been mutated by a prior install.

    Snapshot-key presence semantics: the key is present in the manifest
    iff the project that ran contributed `provider` (or the install
    took a snapshot for some other reason). Absence means "no install
    has touched this block yet", and the value None means "the user
    had no pre-existing value when the snapshot was taken"."""
    import json
    # Project v1 has no provider. Project v2 adds one. We run two
    # different "projects" in series to simulate the scenario.
    project_v1_dir = tmp_path / "p1"
    project_v1_dir.mkdir()
    (project_v1_dir / "opencode.json").write_text(
        json.dumps({"default_agent": "conductor", "model": "opencode/x"}),
        encoding="utf-8",
    )
    project_v2_dir = tmp_path / "p2"
    project_v2_dir.mkdir()
    (project_v2_dir / "opencode.json").write_text(
        json.dumps({
            "default_agent": "conductor",
            "model": "opencode/x",
            "provider": {"opencode": {"options": {"reasoning_effort": "max"}}},
        }),
        encoding="utf-8",
    )
    g = _global_file(
        tmp_path,
        provider={"opencode": {"options": {"reasoning_effort": "USER-ORIGINAL"}}},
    )
    manifest = _manifest_file(tmp_path)

    # First install: project v1 has no provider, so the helper does not
    # touch the provider block at all. The manifest's `added` block
    # does NOT contain a provider_snapshot key.
    opencode_jsonc_merge.cmd_install(_install_args(project_v1_dir / "opencode.json", g, manifest))
    m1 = json.loads(manifest.read_text())
    assert "provider_snapshot" not in m1["added"]

    # Second install: project v2 DOES have provider. The global still
    # has USER-ORIGINAL (v1 didn't touch it). The helper takes a
    # snapshot = USER-ORIGINAL.
    opencode_jsonc_merge.cmd_install(_install_args(project_v2_dir / "opencode.json", g, manifest))
    m2 = json.loads(manifest.read_text())
    assert "provider_snapshot" in m2["added"]
    assert m2["added"]["provider_snapshot"]["opencode"]["options"]["reasoning_effort"] == "USER-ORIGINAL"

    # Third install: re-run with the same v2 project. The snapshot must
    # STILL be USER-ORIGINAL (first-wins, not "last-wins"), even though
    # the global now has the merged value (which is "max", not "USER-ORIGINAL").
    cfg = opencode_jsonc_merge.load_jsonc(g)
    assert cfg["provider"]["opencode"]["options"]["reasoning_effort"] == "max"
    opencode_jsonc_merge.cmd_install(_install_args(project_v2_dir / "opencode.json", g, manifest))
    m3 = json.loads(manifest.read_text())
    assert m3["added"]["provider_snapshot"]["opencode"]["options"]["reasoning_effort"] == "USER-ORIGINAL"


def test_manifest_first_wins_for_permission_snapshot(tmp_path):
    """Same as test_manifest_first_wins_for_provider_snapshot but for
    permission. Belt and braces: same code path but verifying the
    separate field behaves identically."""
    import json
    project_v1_dir = tmp_path / "p1"
    project_v1_dir.mkdir()
    (project_v1_dir / "opencode.json").write_text(
        json.dumps({"default_agent": "conductor", "model": "opencode/x"}),
        encoding="utf-8",
    )
    project_v2_dir = tmp_path / "p2"
    project_v2_dir.mkdir()
    (project_v2_dir / "opencode.json").write_text(
        json.dumps({
            "default_agent": "conductor",
            "model": "opencode/x",
            "permission": {"bash": {"*": "deny"}},
        }),
        encoding="utf-8",
    )
    g = _global_file(
        tmp_path,
        permission={"bash": {"git *": "USER-ASK"}},
    )
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project_v1_dir / "opencode.json", g, manifest))
    m1 = json.loads(manifest.read_text())
    assert "permission_snapshot" not in m1["added"]

    opencode_jsonc_merge.cmd_install(_install_args(project_v2_dir / "opencode.json", g, manifest))
    m2 = json.loads(manifest.read_text())
    assert "permission_snapshot" in m2["added"]
    assert m2["added"]["permission_snapshot"]["bash"]["git *"] == "USER-ASK"

    # Re-run v2; snapshot stays.
    opencode_jsonc_merge.cmd_install(_install_args(project_v2_dir / "opencode.json", g, manifest))
    m3 = json.loads(manifest.read_text())
    assert m3["added"]["permission_snapshot"]["bash"]["git *"] == "USER-ASK"


def test_install_skips_empty_command_block(tmp_path):
    """An empty `command: {}` in the project should not record any
    command_names in the manifest. Defensive: a malformed project file
    must not produce surprising manifest entries."""
    import json
    project = _project_file(tmp_path, command={})
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    data = json.loads(manifest.read_text())
    assert data["added"]["command_names"] == []
    # Global config does not gain a `command` key.
    assert "command" not in opencode_jsonc_merge.load_jsonc(g)


def test_install_skips_empty_mcp_block(tmp_path):
    """An empty `mcp: {}` is a no-op for install."""
    import json
    project = _project_file(tmp_path, mcp={})
    g = _global_file(tmp_path)
    manifest = _manifest_file(tmp_path)

    opencode_jsonc_merge.cmd_install(_install_args(project, g, manifest))
    data = json.loads(manifest.read_text())
    assert data["added"]["mcp_names"] == []
    assert "mcp" not in opencode_jsonc_merge.load_jsonc(g)

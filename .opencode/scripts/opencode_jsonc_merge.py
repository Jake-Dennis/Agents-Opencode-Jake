"""opencode_jsonc_merge.py — install/remove helper for the global opencode config.

Stdlib-only, Python 3.10+. JSONC tolerant (strips ``/* */`` and ``//`` comments
and trailing commas before ``json.loads``). Writes atomically (write ``.tmp``
file, then ``os.replace``) so a crash mid-write cannot corrupt the user's
``opencode.jsonc``.

Usage
-----
    python opencode_jsonc_merge.py install \\
        --project <path/to/opencode.json> \\
        --global  <path/to/global/opencode.jsonc> \\
        --manifest <path/to/global/.opencode-jake-installed.json> \\
        [--force] [--dry-run]

    python opencode_jsonc_merge.py remove \\
        --global  <path/to/global/opencode.jsonc> \\
        --manifest <path/to/global/.opencode-jake-installed.json> \\
        [--dry-run]

Exit codes
----------
    0 success
    2 invalid args / required file missing
    3 JSONC parse failure
    4 permission denied (or other OSError on write)
    5 reserved (collision-blocked mode — currently we warn, not fail)

The merge policy and CLI are documented in
``docs/decisions/adr-002-global-setup-merge-strategy.md`` and
``.opencode/plans/plan-002-fix-global-setup.md``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# JSONC tolerance
# ----------------------------------------------------------------------

# Order matters: strip /* ... */ first because a block comment may contain //.
# A naive regex strip breaks URLs like "https://..." — the `//` looks like a
# line comment. We need a tiny state machine that tracks whether we are
# inside a string literal so that `//`, `/*`, and `*/` are only treated as
# comment markers in code context.

_TRAILING_COMMA_RE = re.compile(r",(\s*[\]\}])")


def _strip_jsonc(text: str) -> str:
    """Strip block comments, line comments, and trailing commas.

    Comment markers are only recognized outside of double-quoted strings.
    Backslash escapes inside strings are honored so that ``"a\\\"b"`` stays
    a single string. Single-quoted strings are not legal JSON / JSONC, so
    we don't need to handle them.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        # Outside a string.
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                # Line comment — consume up to (but not including) the newline
                i += 2
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if nxt == "*":
                # Block comment — consume through the matching */
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                if i + 1 < n:
                    i += 2  # skip the closing */
                else:
                    i = n   # unterminated; consume the rest
                continue
        out.append(c)
        i += 1
    return _TRAILING_COMMA_RE.sub(r"\1", "".join(out))


def load_jsonc(path: str | Path) -> dict:
    """Load a JSONC file as a dict.

    * ``FileNotFoundError`` returns ``{}`` (a missing global config is fine;
      we will create one on first install).
    * Other ``OSError`` propagates (e.g. permission denied on read).
    * ``json.JSONDecodeError`` prints ``[ERROR] failed to parse {path}: {e}``
      to stderr and ``sys.exit(3)``.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as e:
        # Permission denied / locked file — bubble up; caller will report.
        print(f"[ERROR] cannot read {p}: {e}", file=sys.stderr)
        sys.exit(4)
    text = _strip_jsonc(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] failed to parse {p}: {e}", file=sys.stderr)
        sys.exit(3)
    if not isinstance(data, dict):
        # A bare array or scalar isn't a valid opencode config. Treat as
        # empty so we don't crash, but warn so the user can fix it.
        print(
            f"[WARN] {p} did not contain a JSON object — treating as empty",
            file=sys.stderr,
        )
        return {}
    return data


# ----------------------------------------------------------------------
# Path normalization
# ----------------------------------------------------------------------


def _norm_path(p: str) -> str:
    """Case-insensitive, separator-normalized key for dedupe comparisons.

    On Windows, ``os.path.normcase`` lowercases the drive and folds
    separators to backslashes; on POSIX it leaves case alone. This is the
    canonical comparison key for filesystem paths.
    """
    return os.path.normcase(os.path.normpath(p))


# ----------------------------------------------------------------------
# Set operations
# ----------------------------------------------------------------------


def dedupe_union(a: list, b: list) -> list:
    """Concatenate ``a`` and ``b``, then deduplicate.

    String items are compared case-insensitively on their normalized path
    (``os.path.normcase(os.path.normpath(p))``). Non-string items fall
    back to identity + ``repr`` for safety. First-seen order is preserved
    (items from ``a`` come first, then items from ``b`` that were not
    already present).
    """
    seen: set[tuple] = set()
    out: list = []
    for item in list(a) + list(b):
        if isinstance(item, str):
            key: tuple = ("path", _norm_path(item))
        else:
            key = ("raw", id(item), repr(item))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


# ----------------------------------------------------------------------
# Dict merge
# ----------------------------------------------------------------------


def deep_merge(a: dict, b: dict) -> dict:
    """Recursive dict merge. For conflicting keys, ``b`` wins.

    Returns a new dict — neither input is mutated. Non-dict values in ``a``
    are replaced wholesale by ``b``'s value (which is the expected semantics
    for "b wins on conflict").
    """
    result = dict(a)
    for key, b_val in b.items():
        a_val = result.get(key)
        if isinstance(a_val, dict) and isinstance(b_val, dict):
            result[key] = deep_merge(a_val, b_val)
        else:
            result[key] = b_val
    return result


# ----------------------------------------------------------------------
# Atomic write
# ----------------------------------------------------------------------


def atomic_write(path: str | Path, data: Any, header: str | None) -> None:
    """Write ``data`` as pretty JSON to ``path``, atomically.

    If ``header`` is non-None, prepend it as a ``// ...`` JSONC comment
    (with a trailing newline if it doesn't already end in one). The body
    is ``json.dumps(..., indent=2, ensure_ascii=False, sort_keys=True)``
    plus a trailing newline.

    Implementation: write to ``<path>.tmp`` first, then ``os.replace`` it
    on top of the target. This is atomic on Windows and POSIX.

    On ``PermissionError`` or other ``OSError`` during write, prints to
    stderr and ``sys.exit(4)``.
    """
    p = Path(path)
    # Place the tmp file next to the target so os.replace is a same-volume
    # operation. Suffix is "<ext>.tmp" so e.g. opencode.jsonc.tmp.
    tmp = p.with_name(p.name + ".tmp")
    body = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    parts: list[str] = []
    if header:
        parts.append(header if header.endswith("\n") else header + "\n")
    parts.append(body)
    parts.append("\n")
    text = "".join(parts)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)
    except PermissionError as e:
        # Clean up the tmp file if it got created.
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        print(f"[ERROR] permission denied writing {p}: {e}", file=sys.stderr)
        sys.exit(4)
    except OSError as e:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        print(f"[ERROR] failed to write {p}: {e}", file=sys.stderr)
        sys.exit(4)


# ----------------------------------------------------------------------
# Header comment (JSONC)
# ----------------------------------------------------------------------


def header_comment(mode: str, project_path: str, manifest_added: dict) -> str:
    """Build the ``// ...`` header line(s) for the global ``opencode.jsonc``.

    * ``install`` mode: stamps the install time, project, and a
      human-readable list of added agent names.
    * ``remove`` mode: stamps the uninstall time and a pointer back to the
      project (so a future operator can find the source repo).
    """
    ts = datetime.now(timezone.utc).isoformat()
    if mode == "install":
        agents = []
        if isinstance(manifest_added, dict):
            raw = manifest_added.get("agent_names", [])
            if isinstance(raw, list):
                agents = [str(a) for a in raw]
        agents_str = ", ".join(agents) if agents else "(none)"
        return (
            f"// opencode-jake: installed {ts} from {project_path}\n"
            f"// added agents: {agents_str}\n"
            f"// remove with: uninstall-global.bat\n"
        )
    if mode == "remove":
        return f"// opencode-jake: uninstalled {ts} (see {project_path})\n"
    raise ValueError(f"unknown header mode: {mode!r}")


# ----------------------------------------------------------------------
# Path helpers
# ----------------------------------------------------------------------


def _resolve_global_skills_dir(global_path: str | Path) -> str:
    """``<parent of opencode.jsonc>/skills`` — the dir whose junction the
    installer creates for our project-local skill."""
    parent = Path(global_path).resolve().parent
    p = parent / "skills"
    return _display_path(p)


def _resolve_project_agents_md(project_path: str | Path) -> str:
    """``<parent of opencode.json>/AGENTS.md`` — the project's AGENTS.md
    (not anything in the install dir)."""
    parent = Path(project_path).resolve().parent
    p = parent / "AGENTS.md"
    return _display_path(p)


def _resolve_link_paths(global_path: str | Path) -> dict[str, str]:
    """Junction paths derived from the global config location.

    These are the *links* (where the junction lives), not the targets. The
    .bat uses ``fsutil reparsepoint query`` to verify the target.
    """
    parent = Path(global_path).resolve().parent
    return {
        "agent_junction": _display_path(parent / "agents" / "Agents-Opencode-Jake"),
        "skill_junction": _display_path(parent / "skills" / "graphify-agent-workflow"),
    }


def _display_path(p: Path) -> str:
    """Stringify a path with backslashes on Windows (opencode is a
    Windows-first CLI; mixed separators in jsonc look ugly)."""
    s = str(p)
    if os.name == "nt":
        s = s.replace("/", "\\")
    return s


# ----------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------


def _coerce_str_list(v: Any) -> list[str]:
    """Best-effort list-of-strings coercion. Filters out non-strings."""
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, str)]


def _diff_added(old_list: list, new_list: list) -> list:
    """Return the items in ``new_list`` that are not in ``old_list`` (by
    case-insensitive path). Preserves ``new_list`` order."""
    if not old_list:
        return [x for x in new_list if isinstance(x, str)]
    old_keys = {_norm_path(x) for x in old_list if isinstance(x, str)}
    return [x for x in new_list if isinstance(x, str) and _norm_path(x) not in old_keys]


def cmd_install(args: argparse.Namespace) -> int:
    # Existence check for the project file — we want a clear error rather
    # than silently merging from an empty dict.
    if not Path(args.project).exists():
        print(f"[ERROR] project file not found: {args.project}", file=sys.stderr)
        return 2

    project = load_jsonc(args.project)
    global_cfg = load_jsonc(args.global_path)

    if not isinstance(project, dict):
        print(f"[ERROR] project config is not a JSON object: {args.project}", file=sys.stderr)
        return 2
    if not isinstance(global_cfg, dict):
        print(f"[ERROR] global config is not a JSON object: {args.global_path}", file=sys.stderr)
        return 2

    added: dict[str, Any] = {
        "agent_names": [],
        "collisions": [],
        "instructions": [],
        "skills_paths": [],
        "scalar_changes": {},
    }

    # 1. Scalar keys (default_agent, model, small_model): overwrite, record change.
    for key in ("default_agent", "model", "small_model"):
        if key in project:
            old_val = global_cfg.get(key)
            new_val = project[key]
            global_cfg[key] = new_val
            if old_val != new_val:
                added["scalar_changes"][key] = {"old": old_val, "new": new_val}

    # 2. skills.paths: union + dedupe. Also include the global skills dir
    #    so opencode's skill discovery finds our project-local skill.
    skills = global_cfg.get("skills")
    if not isinstance(skills, dict):
        skills = {}
        global_cfg["skills"] = skills
    paths_in = skills.get("paths")
    if not isinstance(paths_in, list):
        paths_in = []
        skills["paths"] = paths_in
    old_skills = list(paths_in)

    project_paths = []
    proj_skills = project.get("skills")
    if isinstance(proj_skills, dict):
        project_paths = _coerce_str_list(proj_skills.get("paths"))

    global_skills_dir = _resolve_global_skills_dir(args.global_path)
    new_skills = list(project_paths) + [global_skills_dir]
    merged_skills = dedupe_union(old_skills, new_skills)
    skills["paths"] = merged_skills
    added["skills_paths"] = _diff_added(old_skills, merged_skills)

    # 3. instructions: union + dedupe. Also include the project's AGENTS.md.
    instr_in = global_cfg.get("instructions")
    if not isinstance(instr_in, list):
        instr_in = []
        global_cfg["instructions"] = instr_in
    old_instr = list(instr_in)
    project_instr = _coerce_str_list(project.get("instructions"))
    agents_md = _resolve_project_agents_md(args.project)
    new_instr = list(project_instr) + [agents_md]
    merged_instr = dedupe_union(old_instr, new_instr)
    global_cfg["instructions"] = merged_instr
    added["instructions"] = _diff_added(old_instr, merged_instr)

    # 4. agent.<name>: deep-merge. On collision without --force, warn and
    #    skip; with --force, deep-merge (project wins on conflicts).
    agents = global_cfg.get("agent")
    if not isinstance(agents, dict):
        agents = {}
        global_cfg["agent"] = agents
    project_agents = project.get("agent")
    if isinstance(project_agents, dict):
        for name, agent_def in project_agents.items():
            if name in agents and not args.force:
                added["collisions"].append(name)
                print(
                    f"[WARN] agent '{name}' already in global config — "
                    "skipped (use --force to overwrite)",
                    file=sys.stderr,
                )
                continue
            if name in agents:
                # --force path: deep-merge so we don't clobber global-only
                # fields. Project values still win on conflict (b wins).
                agents[name] = deep_merge(agents[name], agent_def)
            else:
                agents[name] = agent_def
            added["agent_names"].append(name)

    # 5. Build manifest. If a previous manifest exists, merge this run's
    #    `added` with the previous one so the manifest always reflects the
    #    cumulative set of contributions (so a later `uninstall` can remove
    #    everything, not just what the most recent run added).
    project_root = _display_path(Path(args.project).resolve().parent)
    manifest: dict[str, Any] = {
        "version": 1,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "repo_dir": project_root,
        "links": _resolve_link_paths(args.global_path),
        "added": added,
    }
    manifest_path = Path(args.manifest)
    if manifest_path.exists():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[WARN] could not read previous manifest, overwriting: {e}", file=sys.stderr)
            previous = None
        if isinstance(previous, dict) and isinstance(previous.get("added"), dict):
            prev_added = previous["added"]
            # Union agent_names (set semantics, preserve latest order).
            merged_agent_names = list(
                dict.fromkeys(
                    list(prev_added.get("agent_names") or []) + list(added.get("agent_names") or [])
                )
            )
            # Scalar changes: last writer wins per key (project is authoritative).
            merged_scalars = dict(prev_added.get("scalar_changes") or {})
            merged_scalars.update(added.get("scalar_changes") or {})
            # Union skills_paths and instructions (case-insensitive dedupe).
            prev_skills = list(prev_added.get("skills_paths") or [])
            new_skills = list(added.get("skills_paths") or [])
            seen = set()
            merged_skills = []
            for p in prev_skills + new_skills:
                k = _norm_path(p) if isinstance(p, str) else id(p)
                if k in seen:
                    continue
                seen.add(k)
                merged_skills.append(p)
            seen = set()
            merged_instr = []
            for p in list(prev_added.get("instructions") or []) + list(added.get("instructions") or []):
                k = _norm_path(p) if isinstance(p, str) else id(p)
                if k in seen:
                    continue
                seen.add(k)
                merged_instr.append(p)
            # Collisions: union so we can see what was always-skipped across runs.
            merged_collisions = list(
                dict.fromkeys(
                    list(prev_added.get("collisions") or []) + list(added.get("collisions") or [])
                )
            )
            manifest["added"] = {
                "agent_names": merged_agent_names,
                "scalar_changes": merged_scalars,
                "skills_paths": merged_skills,
                "instructions": merged_instr,
                "collisions": merged_collisions,
            }
            # Refresh installed_at and repo_dir to the latest run.
            manifest["installed_at"] = datetime.now(timezone.utc).isoformat()
            manifest["repo_dir"] = project_root

    # 6. Summary
    _print_install_summary(added, project_root, args.global_path, args.manifest)

    # 7. Write
    if args.dry_run:
        print("[dry-run] no files written")
        return 0

    header = header_comment("install", project_root, added)
    atomic_write(args.global_path, global_cfg, header)
    print(f"[merge] wrote {_display_path(Path(args.global_path).resolve())}")
    atomic_write(args.manifest, manifest, None)
    print(f"[merge] wrote {_display_path(Path(args.manifest).resolve())}")
    return 0


def _print_install_summary(
    added: dict, project_root: str, global_path: str, manifest_path: str
) -> None:
    scalars = added.get("scalar_changes", {}) or {}
    print(f"[merge] scalar changes: {len(scalars)}")
    for k in sorted(scalars.keys()):
        change = scalars[k]
        print(f"  {k}: {change.get('old')!r} -> {change.get('new')!r}")

    skills = added.get("skills_paths", []) or []
    print(f"[merge] skills.paths added: {len(skills)}")
    for p in skills:
        print(f"  + {p}")

    instr = added.get("instructions", []) or []
    print(f"[merge] instructions added: {len(instr)}")
    for p in instr:
        print(f"  + {p}")

    agents = added.get("agent_names", []) or []
    collisions = added.get("collisions", []) or []
    print(f"[merge] agents added: {len(agents)} (collisions: {len(collisions)})")
    for name in agents:
        print(f"  + agent {name}")
    for name in collisions:
        print(f"  ! agent {name} (skipped: collision)")


# ----------------------------------------------------------------------
# Remove
# ----------------------------------------------------------------------


def cmd_remove(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[ERROR] manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    manifest = load_jsonc(args.manifest)
    if not isinstance(manifest, dict):
        print(f"[ERROR] manifest is not a JSON object: {manifest_path}", file=sys.stderr)
        return 2

    global_cfg = load_jsonc(args.global_path)
    if not isinstance(global_cfg, dict):
        print(f"[ERROR] global config is not a JSON object: {args.global_path}", file=sys.stderr)
        return 2

    added = manifest.get("added")
    if not isinstance(added, dict):
        added = {}
    project_root = str(manifest.get("repo_dir", "") or "")

    removed: dict[str, Any] = {
        "agent_names": [],
        "skills_paths": [],
        "instructions": [],
    }

    # 1. Agents — only remove names we actually added (collisions were
    #    never touched, so we mustn't touch them on the way out either).
    agent_names = added.get("agent_names")
    if isinstance(agent_names, list):
        agents = global_cfg.get("agent")
        if isinstance(agents, dict):
            for name in agent_names:
                if isinstance(name, str) and name in agents:
                    del agents[name]
                    removed["agent_names"].append(name)

    # 2. skills.paths — only remove the specific entries we added.
    skills_paths_added = added.get("skills_paths")
    if isinstance(skills_paths_added, list):
        skills = global_cfg.get("skills")
        if isinstance(skills, dict):
            paths = skills.get("paths")
            if isinstance(paths, list):
                target_keys = {
                    _norm_path(p) for p in skills_paths_added if isinstance(p, str)
                }
                new_paths = []
                for p in paths:
                    if isinstance(p, str) and _norm_path(p) in target_keys:
                        removed["skills_paths"].append(p)
                    else:
                        new_paths.append(p)
                skills["paths"] = new_paths

    # 3. instructions — only remove the specific entries we added.
    instr_added = added.get("instructions")
    if isinstance(instr_added, list):
        instr_list = global_cfg.get("instructions")
        if isinstance(instr_list, list):
            target_keys = {
                _norm_path(p) for p in instr_added if isinstance(p, str)
            }
            new_instr = []
            for p in instr_list:
                if isinstance(p, str) and _norm_path(p) in target_keys:
                    removed["instructions"].append(p)
                else:
                    new_instr.append(p)
            global_cfg["instructions"] = new_instr

    # 4. Scalars — DO NOT TOUCH. We may have over-written the user's
    #    `default_agent`/`model`/`small_model` on install (this is by
    #    design — the project is authoritative for this project family).
    #    But we cannot safely *restore* them on remove: another project
    #    may have installed the same agents in the meantime, and
    #    restoring would clobber that project's contribution. The user
    #    can edit those three scalars by hand if they want to undo the
    #    overwrite. The manifest still records the change in
    #    `scalar_changes` for reference.
    #    See ADR-002 and the "Consequences / negatives" section.

    # 5. Summary
    _print_remove_summary(removed)

    # 6. Write
    if args.dry_run:
        print("[dry-run] no files written")
        # In dry-run we still want to leave the manifest in place so a
        # subsequent real run can do its job.
        return 0

    header = header_comment("remove", project_root, added)
    atomic_write(args.global_path, global_cfg, header)
    print(f"[merge] wrote {_display_path(Path(args.global_path).resolve())}")

    # 7. Unlink manifest
    try:
        manifest_path.unlink()
        print(f"[merge] removed manifest {_display_path(manifest_path.resolve())}")
    except OSError as e:
        print(
            f"[WARN] could not remove manifest {manifest_path}: {e}",
            file=sys.stderr,
        )
    return 0


def _print_remove_summary(removed: dict) -> None:
    agents = removed.get("agent_names", []) or []
    print(f"[merge] agents removed: {len(agents)}")
    for name in agents:
        print(f"  - agent {name}")

    skills = removed.get("skills_paths", []) or []
    print(f"[merge] skills.paths removed: {len(skills)}")
    for p in skills:
        print(f"  - {p}")

    instr = removed.get("instructions", []) or []
    print(f"[merge] instructions removed: {len(instr)}")
    for p in instr:
        print(f"  - {p}")

    scalars = removed.get("scalars", {}) or {}
    print(f"[merge] scalar changes: {len(scalars)}")
    for k in sorted(scalars.keys()):
        change = scalars[k]
        print(f"  {k}: {change.get('new')!r} -> {change.get('old')!r}")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opencode_jsonc_merge.py",
        description=(
            "Install or remove Agents-Opencode-Jake entries in the global "
            "opencode.jsonc, with per-key merge policy and a manifest so "
            "uninstall is reversible."
        ),
    )
    p.add_argument(
        "mode",
        choices=("install", "remove"),
        help="install: merge project config into global jsonc. "
             "remove: surgically undo a previous install via the manifest.",
    )
    p.add_argument(
        "--project",
        help="Path to the project's opencode.json (install mode only).",
    )
    p.add_argument(
        "--global",
        dest="global_path",
        required=True,
        help="Path to the global opencode.jsonc.",
    )
    p.add_argument(
        "--manifest",
        required=True,
        help="Path to the install manifest "
             "(e.g. ~/.config/opencode/.opencode-jake-installed.json).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing agent entries in the global config (install only).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned changes but do not write any files.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode == "install" and not args.project:
        parser.error("--project is required for install mode")

    if args.mode == "install":
        return cmd_install(args)
    return cmd_remove(args)


if __name__ == "__main__":
    sys.exit(main())

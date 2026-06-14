"""Verify a plan by extracting and running commands from its ## Verification section.

The plan format expected is:
    ## Verification
    - [x] #1 - `python -c "..."`  (or any runnable command)
    - [x] #2 - `bash command ...`

Each backtick contains a runnable command. The script runs each command from
the repo root. Exit 0 = pass, anything else = fail.

If a verification is a file path (e.g., `.opencode/decisions/adr-001.md`), the
script checks for file existence instead of running it.

In addition to running each verification command, the script fires 5
mechanical checks on the plan's structure (Momus's 4-criteria rubric
reframed as mechanical regex / string checks, per project priority #5 —
no LLM-judgment gates):

    1. @-assignment check       — every ### Layer N task has @-agent
    2. non-empty description    — every task has 10+ chars after @-agent
    3. verification coverage    — at least N verification entries (one per layer)
    4. no duplicate task IDs    — no two #N in the verification section
    5. cross-reference resolve  — backticked .md/.py/.json paths exist

This is the conductor's mandatory gate before archiving a plan. Skipping it is
a process violation: a plan is not "done" until this script returns exit 0.

Usage:
    python scripts/verify-plan.py <plan-file>
"""
import re
import subprocess
import sys
from pathlib import Path

TIMEOUT_SEC = 300  # 5 minutes per check
MAX_OUTPUT = 500   # truncate stdout/stderr in report

# Patterns that suggest a runnable command vs a file path
COMMAND_HINTS = (
    "python", "pytest", "git", "bash", "node", "npm", "cargo", "go ",
    "pip", "ruby", "perl", "powershell", "cmd", "opencode", "/",
    "$ ", "echo ", "dir ", "ls ",
)
FILE_HINTS = (".md", ".json", ".yml", ".yaml", ".py", ".sh", ".txt", ".html")


def is_runnable_command(text, workdir=None):
    """Heuristic: does the text look like a shell command vs a file path?

    Returns True if it should be run as a command.
    Returns False if it looks like a file path to check.

    Order of checks (most specific first):
    1. If file exists at workdir/text → it's a file path
    2. If it contains shell metacharacters (=|&;<>(){} or backtick or $) → command
    3. If it has a space → likely a command (file paths with spaces are quoted)
    4. If it ends with a known file extension → file path
    5. If it starts with a known command prefix → command
    6. Default: try to run as command
    """
    text = text.strip()
    # 1. File exists check
    if workdir is not None:
        candidate = (workdir / text).resolve()
        try:
            if candidate.exists():
                return False  # it's a real file/dir
        except (OSError, ValueError):
            pass
    # 2. Shell metacharacters
    if any(c in text for c in "=|&;<>(){}$"):
        return True
    # 3. Has a space (and not quoted) → likely a command
    if " " in text:
        return True
    # 4. Known file extensions
    if any(text.endswith(h) for h in FILE_HINTS):
        return False
    # 5. Known command prefixes
    lower = text.lower()
    if any(lower.startswith(h) for h in COMMAND_HINTS):
        return True
    # 6. Default
    return True


def find_repo_root(start):
    """Walk up from `start` until we find a .git directory."""
    workdir = Path(start).resolve()
    while workdir != workdir.parent:
        if (workdir / ".git").exists():
            return workdir
        workdir = workdir.parent
    return Path(start).resolve().parent


# ---------------------------------------------------------------------
# Mechanical checks (plan-007, layer 1, T2)
# ---------------------------------------------------------------------

# A backticked file reference must have no whitespace and end in one of
# these extensions. Strings with spaces (e.g. `` `python -c "..."` ``) are
# commands, not file paths, and are intentionally skipped. Globs
# (containing ``*`` or ``?``) are patterns, not single files, and are
# also skipped.
_FILE_REF_RE = re.compile(r"`(?P<ref>[^`\s*?]+\.(?:md|py|json))`")
_EXPLICIT_REF_RE = re.compile(r"\[ref:(?P<ref>[^\]\s*?]+)\]")

# Verification-section entry pattern. Allows optional ``**`` bold markers
# around the task ID (matches the existing ``extract_tasks`` regex shape)
# so the coverage and duplicate checks see entries like ``- [x] **#1** ...``.
_V_ENTRY_RE = re.compile(
    r"^\s*-\s*\[(?:\s|x)\]\s*\**#(\d+)", re.MULTILINE,
)


def _find_section(text, name):
    """Return the body of the first top-level ``## <name>`` section, or None.

    Case-insensitive match on the section name. Body runs until the next
    ``## `` header (or end of file).
    """
    pattern = re.compile(
        r"^##\s*" + re.escape(name) + r"\s*$(.+?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    return m.group(1) if m else None


def _find_layer_sections(text):
    """Find all ``### Layer N`` sections.

    Returns a list of ``(layer_id, body)`` tuples where ``layer_id`` is the
    numeric portion ("1", "2", ...) and ``body`` is the text from the
    header line's end up to the next ``## `` or ``### `` header (or EOF).
    """
    matches = []
    header_re = re.compile(r"^###\s+Layer\s+(\d+).*?$", re.MULTILINE)
    for m in header_re.finditer(text):
        layer_id = m.group(1)
        start = m.end()
        rest = text[start:]
        next_header = re.search(r"^#{2,3}\s", rest, re.MULTILINE)
        end = start + next_header.start() if next_header else len(text)
        matches.append((layer_id, text[start:end]))
    return matches


def _extract_layer_tasks(layer_body):
    """Return the text of every task line in a layer section's body.

    Matches ``- [x] ...`` and ``- [ ] ...`` (one leading checkbox), plus
    ``- [x] **#N** ...`` and any other content after the checkbox. The
    captured text excludes the leading ``- [x] `` marker.
    """
    pattern = re.compile(r"^\s*-\s*\[[\sx]?\]\s*(.+?)$", re.MULTILINE)
    return [m.group(1).rstrip() for m in pattern.finditer(layer_body)]


def _ref_resolves(ref, workdir):
    """Return True iff ``ref`` resolves to an existing path under ``workdir``.

    URLs and mailto links are treated as resolvable (they're not local
    file references). Empty / whitespace-only refs are not resolvable.
    """
    if not ref:
        return False
    if ref.startswith(("http://", "https://", "file://", "mailto:")):
        return True
    try:
        return (workdir / ref).exists()
    except (OSError, ValueError):
        return False


def _collect_file_refs(text, workdir):
    """Find every backticked .md/.py/.json path and ``[ref:filename]`` in text.

    Returns a list of ``(display_string, exists_bool)`` tuples. The
    display string is the original token (`` `path` `` or ``[ref:path]``)
    for use in failure messages.

    Globs (paths containing ``*`` or ``?``) are intentionally skipped —
    they are patterns, not single files. The regex (``_FILE_REF_RE`` /
    ``_EXPLICIT_REF_RE``) already excludes them, so this function just
    surfaces what the regex found.
    """
    refs = []
    for m in _EXPLICIT_REF_RE.finditer(text):
        ref = m.group("ref").strip()
        if not ref.startswith(("http://", "https://", "file://")):
            refs.append((f"[ref:{ref}]", _ref_resolves(ref, workdir)))
    for m in _FILE_REF_RE.finditer(text):
        ref = m.group("ref").strip()
        if not ref.startswith(("http://", "https://", "file://")):
            refs.append((f"`{ref}`", _ref_resolves(ref, workdir)))
    return refs


def run_mechanical_checks(plan_path, workdir):
    """Run the 5 mechanical plan-structure checks defined in plan-007.

    Returns a list of ``(name, passed, failure_messages)`` tuples. The
    caller is responsible for printing + deciding the exit code based
    on the ``passed`` flag. Failure messages are stable, lowercase, and
    safe to grep.
    """
    text = Path(plan_path).read_text(encoding="utf-8", errors="replace")
    results = []

    # ---- discover layer sections + their task lines ----
    layer_sections = _find_layer_sections(text)
    layer_count = len(layer_sections)
    layer_tasks = []  # list of (layer_id, task_text)
    for layer_id, body in layer_sections:
        for task_text in _extract_layer_tasks(body):
            layer_tasks.append((layer_id, task_text))

    # ---- check 1: @-assignment ----
    at_re = re.compile(r"(?<!\S)@\w+")
    no_at = [(lid, t) for lid, t in layer_tasks if not at_re.search(t)]
    results.append((
        "@-assignment check",
        not no_at,
        [f"Layer {lid}: '{t[:60]}' has no @-agent assignment"
         for lid, t in no_at],
    ))

    # ---- check 2: non-empty description (>= 10 chars after @-assignment) ----
    short = []
    for lid, t in layer_tasks:
        m = at_re.search(t)
        if m is not None:
            after = t[m.end():].strip()
        else:
            # No @-assignment: per the spec, description check is run on
            # the line's content after the checkbox (the whole text). The
            # 10-char minimum still applies; this gives the @-missing
            # task a chance to also flag here as a hint, but the primary
            # signal is check 1.
            after = t.strip()
        if len(after) < 10:
            short.append((lid, t[:60], len(after)))
    results.append((
        "non-empty description check",
        not short,
        [f"Layer {lid}: '{t}' has only {n} chars after @-assignment (need >= 10)"
         for lid, t, n in short],
    ))

    # ---- check 3: verification coverage ----
    v_section = _find_section(text, "Verification")
    v_count = 0
    if v_section is not None:
        v_count = len(_V_ENTRY_RE.findall(v_section))
    coverage_ok = v_count >= layer_count
    coverage_msg = (
        f"Verification section has {v_count} entries; need >= {layer_count} (one per layer)"
        if not coverage_ok else None
    )
    results.append((
        "verification coverage check",
        coverage_ok,
        [coverage_msg] if coverage_msg else [],
    ))

    # ---- check 4: no duplicate task IDs in verification ----
    v_ids = []
    if v_section is not None:
        v_ids = _V_ENTRY_RE.findall(v_section)
    seen, duplicates = set(), []
    for vid in v_ids:
        if vid in seen and vid not in duplicates:
            duplicates.append(vid)
        seen.add(vid)
    results.append((
        "no duplicate task IDs check",
        not duplicates,
        [f"Task ID #{d} appears multiple times in Verification section"
         for d in sorted(duplicates)],
    ))

    # ---- check 5: cross-reference resolution ----
    refs = _collect_file_refs(text, workdir)
    unresolved = [display for display, exists in refs if not exists]
    results.append((
        "cross-reference resolution check",
        not unresolved,
        [f"{u} does not resolve to an existing file (relative to repo root)"
         for u in unresolved],
    ))

    # ---- check 6: knowledge graph exists and is usable (ADVISORY) ----
    # This is a soft check: a missing or empty graph does NOT fail the plan.
    # It prints a warning so the user knows context may be incomplete, but
    # plans unrelated to the knowledge graph should still verify.
    graph_path = workdir / "graphify-out" / "graph.json"
    graph_ok = graph_path.exists() and graph_path.stat().st_size > 100
    graph_msg = None
    if not graph_path.exists():
        graph_msg = "graphify-out/graph.json does not exist — run /graphify . first (advisory, not blocking)"
    elif graph_path.stat().st_size <= 100:
        graph_msg = "graphify-out/graph.json exists but is nearly empty (less than 100 bytes) — run /graphify . to rebuild (advisory, not blocking)"
    results.append((
        "knowledge graph exists check",
        graph_ok,
        [graph_msg] if graph_msg else [],
    ))

    # ---- check 7: agent registry sync check ----
    # Every agent in opencode.json must have a row in AGENT-ROLES.md,
    # and the mode (primary/all/subagent) must match.
    roles_path = workdir / "AGENT-ROLES.md"
    config_path = workdir / "opencode.json"
    sync_errors = []
    if roles_path.exists() and config_path.exists():
        roles_text = roles_path.read_text(encoding="utf-8", errors="replace")
        config_text = config_path.read_text(encoding="utf-8", errors="replace")
        # Extract agent names from opencode.json (lightweight JSON parse)
        # Avoid importing json to keep dependencies minimal
        import json as _json
        try:
            config = _json.loads(config_text)
            agents_in_config = set(config.get("agent", {}).keys())
        except (_json.JSONDecodeError, KeyError):
            agents_in_config = set()

        if agents_in_config:
            # Find agent names mentioned in the AGENT-ROLES.md table
            # The table has rows like: | `builder` | all | Implementation | ...
            table_agent_re = re.compile(r"\|\s*`(\w+)`\s*\|")
            agents_in_roles = set(table_agent_re.findall(roles_text))

            # Check: every config agent must appear in roles
            missing_from_roles = agents_in_config - agents_in_roles
            for name in sorted(missing_from_roles):
                sync_errors.append(
                    f"agent '{name}' in opencode.json but not in AGENT-ROLES.md table"
                )

            # Check: every roles agent must appear in config
            missing_from_config = agents_in_roles - agents_in_config
            for name in sorted(missing_from_config):
                sync_errors.append(
                    f"agent '{name}' in AGENT-ROLES.md but not in opencode.json"
                )

    results.append((
        "agent registry sync check",
        not sync_errors,
        sync_errors,
    ))

    return results


def extract_tasks(plan_path):
    """Extract (task_id, command_or_path) pairs from the plan's Verification section."""
    text = Path(plan_path).read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"^##\s*Verification\s*$(.+?)(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []
    section = m.group(1)
    # Match lines like: - [x] **#1** — description — `command` — VERIFIED
    # Capture: task ID, the FIRST backticked command on the line
    pattern = re.compile(
        r"^\s*-\s*\[(?:\s|x)\]\s*\**#(\d+)\**.*?`([^`]+)`",
        re.MULTILINE,
    )
    tasks = []
    for m in pattern.finditer(section):
        task_id = f"#{m.group(1)}"
        content = m.group(2).strip()
        if content and not content.startswith("#"):
            tasks.append({"id": task_id, "content": content})
    return tasks


def run_check(task_id, content, workdir):
    """Run a check. If content looks like a command, run it. If it looks like a
    file path, check existence. Otherwise, try running it."""
    if is_runnable_command(content, workdir=workdir):
        try:
            result = subprocess.run(
                content, shell=True, capture_output=True, text=True,
                timeout=TIMEOUT_SEC, cwd=workdir,
            )
            return {
                "task_id": task_id, "content": content, "kind": "command",
                "passed": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": (result.stdout or "")[-MAX_OUTPUT:],
                "stderr": (result.stderr or "")[-MAX_OUTPUT:],
            }
        except subprocess.TimeoutExpired:
            return {
                "task_id": task_id, "content": content, "kind": "command",
                "passed": False, "error": f"TIMEOUT after {TIMEOUT_SEC}s",
            }
        except Exception as e:
            return {
                "task_id": task_id, "content": content, "kind": "command",
                "passed": False, "error": f"{type(e).__name__}: {e}",
            }
    else:
        # Treat as file path
        path = workdir / content
        exists = path.exists()
        is_file = path.is_file() if exists else False
        return {
            "task_id": task_id, "content": content, "kind": "file",
            "passed": exists and is_file,
            "exists": exists, "is_file": is_file,
            "resolved_path": str(path),
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify-plan.py <plan-file>")
        sys.exit(2)
    plan_path = Path(sys.argv[1])
    if not plan_path.exists():
        print(f"ERROR: plan file not found: {plan_path}")
        sys.exit(2)

    workdir = find_repo_root(plan_path)
    print(f"Plan:    {plan_path}")
    print(f"Workdir: {workdir}")
    print()

    tasks = extract_tasks(plan_path)
    if not tasks:
        print("ERROR: no verification tasks found.")
        print("Each line must be: - [x] #N - `command or file path`")
        sys.exit(2)

    print(f"Running {len(tasks)} verification check(s)...")
    print()
    results = [run_check(t["id"], t["content"], workdir) for t in tasks]

    n_pass = sum(1 for r in results if r["passed"])
    n_fail = sum(1 for r in results if not r["passed"])

    print("=" * 80)
    print(f"VERIFICATION: {n_pass}/{len(results)} passed, {n_fail} failed")
    print("=" * 80)
    print()
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        kind = r.get("kind", "?")
        print(f"[{status}] {r['task_id']} ({kind}): {r['content'][:80]}")
        if not r["passed"]:
            if "error" in r:
                print(f"       {r['error']}")
            elif r.get("kind") == "command":
                print(f"       exit code: {r.get('returncode', '?')}")
                if r.get("stderr"):
                    print(f"       stderr: {r['stderr'][:300]}")
                if r.get("stdout"):
                    print(f"       stdout: {r['stdout'][:300]}")
            elif r.get("kind") == "file":
                print(f"       exists={r.get('exists')}, is_file={r.get('is_file')}")
                print(f"       path: {r.get('resolved_path')}")
        print()

    # ----------------------------------------------------------------
    # Mechanical checks (plan-007, layer 1, T2)
    # These are 5 mechanical / regex / string checks — no LLM judgment
    # (per project priority #5). They run AFTER the verification commands
    # so a verification-stage failure is reported first.
    # ----------------------------------------------------------------
    mechanical = run_mechanical_checks(plan_path, workdir)
    m_pass = sum(1 for _, p, _ in mechanical if p)
    m_fail = sum(1 for _, p, _ in mechanical if not p)

    print("=" * 80)
    print("MECHANICAL CHECKS")
    print("=" * 80)
    print()
    for name, passed, failures in mechanical:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"       {f}")
        print()

    print(f"MECHANICAL CHECKS: {m_pass}/{len(mechanical)} passed, {m_fail} failed")
    print()

    # Separate mechanical checks into hard vs advisory.
    # Check 6 (knowledge graph exists) is advisory: a missing graph does NOT
    # fail the plan. All other mechanical checks are hard gates.
    m_hard_fail = sum(1 for name, p, _ in mechanical if not p and name != "knowledge graph exists check")
    m_advisory_fail = sum(1 for name, p, _ in mechanical if not p and name == "knowledge graph exists check")

    if n_fail == 0 and m_hard_fail == 0:
        print("ALL CHECKS PASSED. Plan is verified.")
        if m_advisory_fail > 0:
            print(f"  ({m_advisory_fail} advisory check(s) have warnings — see above)")
        sys.exit(0)

    # Build a single failure summary. Preserve the legacy
    # "1 CHECK(S) FAILED" wording the existing test suite asserts on
    # when there are NO mechanical-check failures; otherwise include
    # the mechanical count too.  Advisory checks are excluded from
    # the hard-fail count.
    if m_hard_fail == 0 and m_advisory_fail == 0:
        print(f"{n_fail} CHECK(S) FAILED. Plan is NOT verified.")
    elif m_hard_fail == 0 and m_advisory_fail > 0:
        # Hard mechanical checks passed, but advisory (graph) has warnings.
        # Verification failures still block the plan.
        total_fail = n_fail + m_hard_fail
        print(f"{n_fail} verification CHECK(S) FAILED. Plan is NOT verified.")
    else:
        total_hard = n_fail + m_hard_fail
        advisory_msg = f" ({m_advisory_fail} advisory)" if m_advisory_fail else ""
        print(
            f"{n_fail} verification and {m_hard_fail} mechanical{advisory_msg} CHECK(S) FAILED. "
            "Plan is NOT verified."
        )
    sys.exit(1)


if __name__ == "__main__":
    main()

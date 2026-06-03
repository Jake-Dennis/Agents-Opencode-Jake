"""Verify a plan by extracting and running commands from its ## Verification section.

The plan format expected is:
    ## Verification
    - [x] #1 - `python -c "..."`  (or any runnable command)
    - [x] #2 - `bash command ...` 

Each backtick contains a runnable command. The script runs each command from
the repo root. Exit 0 = pass, anything else = fail.

If a verification is a file path (e.g., `.opencode/decisions/adr-001.md`), the
script checks for file existence instead of running it.

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

    if n_fail == 0:
        print("ALL CHECKS PASSED. Plan is verified.")
        sys.exit(0)
    else:
        print(f"{n_fail} CHECK(S) FAILED. Plan is NOT verified.")
        sys.exit(1)


if __name__ == "__main__":
    main()

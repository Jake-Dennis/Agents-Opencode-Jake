import json
import re
import sys
from pathlib import Path

REPO = Path(r"C:\Users\JakeP\Documents\GitHub\Agents-Opencode-Jake")
errors = []
passed = []

def check(cond, msg):
    if cond:
        passed.append(msg)
        print(f"  PASS: {msg}")
    else:
        errors.append(msg)
        print(f"  FAIL: {msg}")

def fuzzy_match(keyword, body):
    """Check if keyword appears in body, with simple pluralization tolerance."""
    body_l = body.lower()
    k_l = keyword.lower()
    if k_l in body_l:
        return True
    if k_l.endswith('y') and k_l[:-1] + 'ies' in body_l:
        return True
    if k_l.endswith('s') and k_l[:-1] in body_l:
        return True
    if not k_l.endswith('s') and k_l + 's' in body_l:
        return True
    return False


def main():
    # In the new architecture:
    #   conductor + planner  = primary
    #   all subagents        = "all" (CLI-testable AND @mentionable)
    EXPECTED = {
        "conductor": {
            "mode": "primary",
            "permissions": {},
            "must_mention": [
                "@builder", "@architect", "@reviewer", "@tester", "@docs",
                "@debugger", "@refactor", "@git", "@explorer", "@security",
                "@perf"
            ],
        },
        "planner": {
            "mode": "primary",
            "permissions": {"edit": "deny"},
            "must_mention": ["design", "plan", "architecture"],
        },
        "builder":     {"mode": "all", "permissions": {"edit": "allow", "bash": "allow"},       "must_mention": ["implementation", "code", "test"]},
        "architect":   {"mode": "all", "permissions": {"edit": "deny", "read": "allow"},         "must_mention": ["design", "component", "data model", "API"]},
        "reviewer":    {"mode": "all", "permissions": {"edit": "deny", "read": "allow"},         "must_mention": ["review", "bug", "security", "vulnerability"]},
        "tester":      {"mode": "all", "permissions": {"edit": "allow", "bash": "allow"},       "must_mention": ["test", "unit", "integration", "fixture"]},
        "docs":        {"mode": "all", "permissions": {"edit": "allow"},                          "must_mention": ["documentation", "README", "API doc"]},
        "debugger":    {"mode": "all", "permissions": {"edit": "allow", "bash": "allow", "read": "allow"}, "must_mention": ["reproduce", "root cause", "stack trace", "log"]},
        "refactor":    {"mode": "all", "permissions": {"edit": "allow", "bash": "ask"},          "must_mention": ["refactor", "cleanup", "behavior preservation"]},
        "git":         {"mode": "all", "permissions": {"bash": {"git *": "allow", "*": "deny"}}, "must_mention": ["git", "commit", "branch", "merge"]},
        "explorer":    {"mode": "all", "permissions": {"edit": "deny", "read": "allow", "bash": "allow"}, "must_mention": ["find", "search", "grep", "explor"]},
        "security":    {"mode": "all", "permissions": {"edit": "deny", "read": "allow", "bash": "ask"}, "must_mention": ["vulnerabilit", "OWASP", "injection", "auth"]},
        "perf":        {"mode": "all", "permissions": {"edit": "allow", "bash": "allow", "read": "allow"}, "must_mention": ["profile", "bottleneck", "optimize", "performance"]},
    }
    
    with open(REPO / "opencode.json", encoding="utf-8") as fh:
        cfg = json.load(fh)
    
    print("=" * 70)
    print("PER-AGENT TEST SUITE v2 (JSON-source architecture)")
    print("=" * 70)
    
    # Per-agent checks
    for name, spec in EXPECTED.items():
        print(f"\n[{name.upper()}]")
        entry = cfg["agent"].get(name)
        if not entry:
            check(False, f"{name} missing from opencode.json")
            continue
    
        check(entry.get("mode") == spec["mode"], f"mode == {spec['mode']}")
        check(entry.get("model") == "opencode/minimax-m3-free", "model == minimax-m3-free")
        check(entry.get("fallback_model") == "opencode/big-pickle", "fallback_model == big-pickle")
        desc = entry.get("description", "")
        check(len(desc) >= 30, f"description length {len(desc)} >= 30")
    
        prompt = entry.get("prompt", "")
        check(len(prompt) >= 50, f"prompt length {len(prompt)} >= 50")
    
        actual_perms = entry.get("permission", {})
        expected_perms = spec["permissions"]
        for perm_key, perm_val in expected_perms.items():
            if perm_key == "bash" and isinstance(perm_val, dict):
                check(actual_perms.get("bash") == perm_val, f"permission.bash matches pattern")
            else:
                check(actual_perms.get(perm_key) == perm_val, f"permission.{perm_key} == {perm_val}")
    
        # keywords — check prompt + description
        for keyword in spec.get("must_mention", []):
            full = (prompt + "\n" + desc).lower()
            check(fuzzy_match(keyword, full), f"agent mentions: '{keyword}' (in prompt or desc)")
    
    # Conductor references all other agents
    print("\n[CONDUCTOR -> OTHER AGENTS]")
    conductor_prompt = cfg["agent"]["conductor"]["prompt"]
    for name in EXPECTED:
        if name == "conductor":
            continue
        check(f"@{name}" in conductor_prompt, f"conductor has @{name}")
    
    # Routing triggers
    print("\n[ROUTING] description triggers")
    TRIGGERS = {
        "builder":   ["code", "implement", "writ"],
        "architect": ["design", "architect", "data model", "api", "system"],
        "reviewer":  ["review", "qa", "quality"],
        "tester":    ["test", "spec"],
        "docs":      ["document", "readme", "api doc"],
        "debugger":  ["bug", "error", "crash", "fix"],
        "refactor":  ["refactor", "cleanup", "improve"],
        "git":       ["git", "commit", "branch", "pr"],
        "explorer":  ["search", "find", "grep", "codebase"],
        "security":  ["secur", "vulnerab", "owasp", "penetration"],
        "perf":      ["performance", "optimiz", "profile", "slow", "bottleneck"],
    }
    for name, words in TRIGGERS.items():
        desc = cfg["agent"][name]["description"].lower()
        matched = [w for w in words if w in desc]
        check(len(matched) >= 1, f"{name} description has trigger ({matched})")
    
    # Safety
    print("\n[SAFETY] permission sanity")
    for ro_agent in ["planner", "architect", "reviewer", "explorer", "security"]:
        perms = cfg["agent"][ro_agent].get("permission", {})
        check(perms.get("edit") == "deny", f"{ro_agent} edit:deny")
    for rw_agent in ["builder", "tester", "docs", "debugger", "refactor", "perf"]:
        perms = cfg["agent"][rw_agent].get("permission", {})
        check(perms.get("edit") == "allow", f"{rw_agent} edit:allow")
    git_perms = cfg["agent"]["git"].get("permission", {})
    check(git_perms.get("bash", {}).get("*") == "deny", "git bash:* = deny")
    
    # Body length (now: prompt length)
    print("\n[LENGTHS] prompt content")
    for name in EXPECTED:
        prompt = cfg["agent"][name].get("prompt", "")
        check(len(prompt.strip()) >= 200, f"{name}.prompt has substance (>=200 chars, got {len(prompt.strip())})")
    
    # Conductor workflow steps
    print("\n[CONDUCTOR WORKFLOW STEPS]")
    required_steps = [
        "1. CLARIFY", "2. GRAPHIFY", "3. PLAN", "4. TODO",
        "5. DISPATCH", "6. TRACK", "7. REVIEW", "8. VERIFY",
        "9. DOCUMENT", "10. SYNC TODO", "11. GRAPHIFY UPDATE",
        "12. GIT", "13. REPORT", "14. RESUME"
    ]
    for step in required_steps:
        check(step in conductor_prompt, f"conductor has step: {step}")
    
    # Opencode CLI schema validation
    print("\n[OPENCODE CLI SCHEMA VALIDATION]")
    import subprocess, os
    env = {**os.environ, "OPENCODE_SERVER_PASSWORD": "", "OPENCODE_SERVER_USERNAME": ""}
    result = subprocess.run(
        ["opencode", "agent", "list"],
        capture_output=True, text=True, timeout=30, shell=True,
        env=env, cwd=str(REPO),
    )
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    check(result.returncode == 0, f"opencode agent list exits 0 (got {result.returncode})")
    for name in EXPECTED:
        check(name in clean, f"opencode CLI lists: {name}")
    
    # No .md files (JSON is source of truth)
    print("\n[NO STALE .MD FILES]")
    md_files = list((REPO / ".opencode/agents").glob("*.md"))
    check(len(md_files) == 0, f"0 agent .md files in .opencode/agents (got {len(md_files)})")
    
    print("\n" + "=" * 70)
    print(f"PASSED: {len(passed)}")
    print(f"FAILED: {len(errors)}")
    print("=" * 70)
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\nAll per-agent tests passed!")


if __name__ == "__main__":
    main()

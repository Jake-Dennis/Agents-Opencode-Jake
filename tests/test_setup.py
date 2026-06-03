import json
import re
import sys
from pathlib import Path

REPO = Path(r"C:\Users\JakeP\Documents\GitHub\Agents-Opencode-Jake")
errors = []
warnings = []
passed = []

def check(condition, msg):
    if condition:
        passed.append(msg)
        print(f"  PASS: {msg}")
    else:
        errors.append(msg)
        print(f"  FAIL: {msg}")

def warn(msg):
    warnings.append(msg)
    print(f"  WARN: {msg}")

# 1. Required files exist
print("\n[1] File structure")
required = [
    "opencode.json",
    "AGENTS.md",
    "setup.bat",
    "global-setup.bat",
    "uninstall.bat",
    "uninstall-global.bat",
    ".opencode/work-log.md",
    ".opencode/todo.md",
    ".opencode/plans/.gitkeep",
    ".opencode/plans/completed/.gitkeep",
    ".opencode/decisions/.gitkeep",
    ".opencode/skills/graphify-agent-workflow/SKILL.md",
    "dist/opencode.json",
    "dist/README.md",
    "dist/AGENTS.md",
    "dist/setup.bat",
    "dist/uninstall.bat",
    "dist/scripts/verify-plan.py",
    "dist/scripts/pre-commit",
]
for f in required:
    check((REPO / f).exists(), f"exists: {f}")

# 2. opencode.json valid JSON
print("\n[2] opencode.json validation")
try:
    with open(REPO / "opencode.json") as fh:
        cfg = json.load(fh)
    passed.append("opencode.json is valid JSON")
    print("  PASS: opencode.json is valid JSON")
except Exception as e:
    errors.append(f"opencode.json invalid: {e}")
    print(f"  FAIL: {e}")
    sys.exit(1)

check(cfg.get("$schema") == "https://opencode.ai/config.json", "schema URL correct")
check(cfg.get("default_agent") == "conductor", "default_agent is conductor")
check(cfg.get("model") == "opencode/deepseek-v4-flash-free", "top-level model is deepseek-v4-flash-free")
check(cfg.get("small_model") == "opencode/deepseek-v4-flash-free", "small_model is deepseek-v4-flash-free")
check(cfg.get("enabled_providers") == ["opencode"], "enabled_providers is opencode")
check("plugin" not in cfg or "oh-my-openagent@latest" not in cfg.get("plugin", []), "oh-my-openagent plugin NOT registered")
check("mcp" in cfg and "graphify" in cfg["mcp"], "graphify MCP server configured")
check("skills" in cfg and "paths" in cfg["skills"], "skills paths configured")
check("command" in cfg and "setup-project" in cfg["command"], "/setup-project command defined")
check("command" in cfg and "build" in cfg["command"], "/build command defined")
check("permission" in cfg, "permission block exists")
check("external_directory" in cfg.get("permission", {}), "external_directory permission set")

# 3. Agent entries in opencode.json match .md files
print("\n[3] Agent cross-reference (opencode.json <-> .md files)")
EXPECTED_AGENTS = [
    "conductor", "planner", "builder", "architect", "reviewer",
    "tester", "docs", "debugger", "refactor", "git",
    "explorer", "security", "perf"
]
agents_in_cfg = set(cfg.get("agent", {}).keys())
check(agents_in_cfg == set(EXPECTED_AGENTS),
      f"opencode.json has exactly the 13 expected agents (got {len(agents_in_cfg)})")

# 4. Each agent entry has model + fallback_model + prompt
print("\n[4] Agent config in opencode.json")
for name in EXPECTED_AGENTS:
    entry = cfg["agent"].get(name)
    if not entry:
        errors.append(f"agent '{name}' missing from opencode.json")
        continue
    check(entry.get("model") == "opencode/deepseek-v4-flash-free",
          f"agent.{name}.model == deepseek-v4-flash-free")
    check(entry.get("fallback_model") == "opencode/deepseek-v4-flash-free",
          f"agent.{name}.fallback_model == deepseek-v4-flash-free")
    check("description" in entry and len(entry["description"]) > 20,
          f"agent.{name} has description")
    check("mode" in entry and entry["mode"] in ("primary", "subagent", "all"),
          f"agent.{name}.mode is valid")
    check("prompt" in entry and len(entry["prompt"]) > 50,
          f"agent.{name} has prompt (>=50 chars)")

# 5. Schema validation via opencode CLI (catches template vs prompt, etc.)
print("\n[5] opencode schema validation")
import subprocess
result = subprocess.run(
    ["opencode", "agent", "list"],
    capture_output=True, text=True, timeout=30, shell=True,
    env={**__import__("os").environ,
         "OPENCODE_SERVER_PASSWORD": "",
         "OPENCODE_SERVER_USERNAME": ""},
    cwd=str(REPO),
)
clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
check(result.returncode == 0,
      f"opencode agent list exits 0 (got {result.returncode})")
for name in EXPECTED_AGENTS:
    check(name in clean, f"opencode agent list shows: {name}")

# 6. Conductor has full workflow (now in opencode.json prompt)
print("\n[6] Conductor workflow completeness")
conductor_prompt = cfg["agent"]["conductor"]["prompt"]
required_steps = [
    "1. CLARIFY", "2. GRAPHIFY", "3. PLAN", "4. TODO",
    "5. DISPATCH", "6. TRACK", "7. REVIEW", "8. VERIFY",
    "9. DOCUMENT", "10. SYNC TODO", "11. GRAPHIFY UPDATE",
    "12. GIT", "13. REPORT", "14. RESUME"
]
for step in required_steps:
    check(step in conductor_prompt, f"conductor has step: {step}")

# 7. Agent reference list in conductor covers all 13
print("\n[7] Conductor agent reference list")
for name in EXPECTED_AGENTS:
    check(f"@{name}" in conductor_prompt or name in conductor_prompt,
          f"conductor references agent: {name}")

# 8. Skill well-formed
print("\n[8] Graphify skill")
skill = (REPO / ".opencode/skills/graphify-agent-workflow/SKILL.md").read_text()
check("---" in skill and "name: graphify-agent-workflow" in skill,
      "skill has frontmatter with name")
check("description:" in skill, "skill has description")
check("graphify" in skill.lower() or "knowledge graph" in skill.lower(),
      "skill mentions graphify/knowledge graph")

# 9. AGENTS.md has correct content
print("\n[9] AGENTS.md")
agents_md = (REPO / "AGENTS.md").read_text()
check("conductor" in agents_md, "AGENTS.md mentions conductor")
check("setup-project" in agents_md or "/setup-project" in agents_md, "AGENTS.md mentions /setup-project")
check("build" in agents_md.lower() and "/build" in agents_md.lower(), "AGENTS.md mentions /build")
check("deepseek" in agents_md.lower(), "AGENTS.md mentions deepseek-v4-flash-free")
check("graphify" in agents_md.lower(), "AGENTS.md mentions graphify")

# 10. setup files exist
print("\n[10] Setup scripts")
setup = (REPO / "setup.bat").read_text()
gsetup = (REPO / "global-setup.bat").read_text()
check("graphify" in setup.lower(), "local setup.bat mentions graphify")
check("pre-commit" in setup.lower(), "local setup.bat installs pre-commit hook")
check(".config\\opencode" in gsetup or ".config/opencode" in gsetup, "global-setup.bat targets opencode config")
check("mklink" in gsetup, "global-setup.bat uses symlinks")

# 11. Uninstall scripts exist
print("\n[11] Uninstall scripts")
check((REPO / "uninstall.bat").exists(), "uninstall.bat exists")
check((REPO / "uninstall-global.bat").exists(), "uninstall-global.bat exists")
check("pre-commit" in (REPO / "uninstall.bat").read_text(), "uninstall.bat removes pre-commit hook")
check("AGENTS_DIR" in (REPO / "uninstall-global.bat").read_text(), "uninstall-global.bat references global directories")

# 12. Plan file structure
print("\n[12] Plan/archive structure")
check((REPO / ".opencode/plans").is_dir(), ".opencode/plans is a directory")
check((REPO / ".opencode/plans/completed").is_dir(), ".opencode/plans/completed is a directory")
check((REPO / ".opencode/decisions").is_dir(), ".opencode/decisions is a directory")

# 13. Counting
print("\n[13] Counts")
md_files = list((REPO / ".opencode/agents").glob("*.md"))
check(len(md_files) == 0, f"0 agent .md files (JSON is source of truth) (got {len(md_files)})")
check(len(cfg["agent"]) == 13, f"13 agent entries in opencode.json (got {len(cfg['agent'])})")
check(len(cfg["command"]) == 2, f"2 custom commands (got {len(cfg['command'])})")

# 14. dist/opencode.json matches root opencode.json
print("\n[14] dist/opencode.json integrity")
try:
    with open(REPO / "dist/opencode.json", encoding="utf-8") as fh:
        dist_cfg = json.load(fh)
    check(len(dist_cfg["agent"]) == len(cfg["agent"]),
          f"dist/opencode.json has {len(dist_cfg['agent'])} agents (root has {len(cfg['agent'])})")
    check(dist_cfg["model"] == cfg["model"], "dist/opencode.json model matches root")
    check(dist_cfg["default_agent"] == cfg["default_agent"], "dist/opencode.json default_agent matches root")
    check("AGENTS.md" in dist_cfg.get("instructions", []), "dist/opencode.json points to AGENTS.md")
except Exception as e:
    errors.append(f"dist/opencode.json invalid: {e}")
    print(f"  FAIL: dist/opencode.json: {e}")

# Summary
print("\n" + "=" * 60)
print(f"PASSED: {len(passed)}")
print(f"WARNINGS: {len(warnings)}")
print(f"FAILED: {len(errors)}")
print("=" * 60)
if errors:
    print("\nERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\nAll checks passed!")
    sys.exit(0)

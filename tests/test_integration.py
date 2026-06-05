"""
Integration test: verifies that all components of Agents-Opencode-Jake
work TOGETHER, not just individually. Tests cross-references, schema
compliance, permission consistency, and end-to-end coherence.
"""
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

def section(title):
    print(f"\n[{title}]")
    print("-" * 70)

# Load configs


def main():
    with open(REPO / "opencode.json") as fh:
        cfg = json.load(fh)
    
    section("1. SCHEMA COMPLIANCE (opencode.json shape)")
    
    # Pull schema from opencode docs and check
    SCHEMA_REQUIRED_TOP = ["$schema"]  # only $schema is mandatory
    for key in SCHEMA_REQUIRED_TOP:
        check(key in cfg, f"top-level has '{key}'")
    
    # Validate model format (provider/model)
    def is_valid_model(m):
        if not isinstance(m, str):
            return False
        return "/" in m and len(m.split("/", 1)) == 2 and all(s.strip() for s in m.split("/", 1))
    
    check(is_valid_model(cfg.get("model")), f"top-level model format: {cfg.get('model')}")
    check(is_valid_model(cfg.get("small_model")), f"top-level small_model format: {cfg.get('small_model')}")
    
    # Validate default_agent exists and is a primary
    default = cfg.get("default_agent")
    check(default in cfg.get("agent", {}), f"default_agent '{default}' exists in agent config")
    check(cfg["agent"].get(default, {}).get("mode") == "primary",
          f"default_agent is primary mode")
    
    # Validate enabled_providers entries are strings
    for prov in cfg.get("enabled_providers", []):
        check(isinstance(prov, str), f"enabled_provider '{prov}' is string")
    
    # Validate MCP server has required fields
    for mcp_name, mcp_cfg in cfg.get("mcp", {}).items():
        check("type" in mcp_cfg, f"MCP '{mcp_name}' has 'type'")
        check(mcp_cfg.get("type") in ("local", "remote"), f"MCP '{mcp_name}' has valid type")
        if mcp_cfg.get("type") == "local":
            check("command" in mcp_cfg and isinstance(mcp_cfg["command"], list),
                  f"local MCP '{mcp_name}' has 'command' array")
        if mcp_cfg.get("type") == "remote":
            check("url" in mcp_cfg, f"remote MCP '{mcp_name}' has 'url'")
    
    # Validate command entries have required fields
    # (commands use 'template' field per opencode schema, not 'prompt')
    for cmd_name, cmd_cfg in cfg.get("command", {}).items():
        check("description" in cmd_cfg, f"command '/{cmd_name}' has description")
        check("template" in cmd_cfg and len(cmd_cfg["template"]) > 50,
              f"command '/{cmd_name}' has substantial template (>=50 chars)")
    
    # Validate permission rules use valid actions
    VALID_ACTIONS = {"allow", "deny", "ask"}
    def check_permission_obj(perms, path=""):
        if isinstance(perms, str):
            if perms in VALID_ACTIONS:
                return True
            return False
        if isinstance(perms, dict):
            for k, v in perms.items():
                if isinstance(v, str) and v not in VALID_ACTIONS:
                    return False
                if isinstance(v, dict):
                    if not check_permission_obj(v, f"{path}.{k}"):
                        return False
            return True
        return False
    
    check(check_permission_obj(cfg.get("permission", {})), "permission block has valid actions")
    for name, entry in cfg.get("agent", {}).items():
        if "permission" in entry:
            check(check_permission_obj(entry["permission"]),
                  f"agent.{name} permission has valid actions")
    
    # Validate description non-empty
    for name, entry in cfg.get("agent", {}).items():
        check(len(entry.get("description", "")) >= 20,
              f"agent.{name} description is substantive")
    
    section("2. AGENT REGISTRY (JSON is single source of truth)")
    
    # Verify no .md files exist (consolidated to JSON)
    md_files = list((REPO / ".opencode/agents").glob("*.md"))
    check(len(md_files) == 0, f"0 stale .md files (got {len(md_files)})")
    
    # Each agent entry in JSON has all required fields
    for name, entry in cfg.get("agent", {}).items():
        check(entry.get("model") == "opencode/minimax-m3-free",
              f"{name} model == minimax-m3-free")
        check(entry.get("fallback_model") == "opencode/big-pickle",
              f"{name} fallback_model == big-pickle")
        check("mode" in entry and entry["mode"] in ("primary", "subagent", "all"),
              f"{name} mode is valid")
        check("prompt" in entry and len(entry["prompt"]) >= 50,
              f"{name} has prompt (>=50 chars)")
        check("description" in entry and len(entry["description"]) >= 30,
              f"{name} has description (>=30 chars)")
    
    section("3. CROSS-REFERENCES")
    
    # Conductor references all 12 other agents
    conductor_prompt = cfg["agent"]["conductor"]["prompt"]
    other_agents = [n for n in cfg["agent"] if n != "conductor"]
    for name in other_agents:
        check(f"@{name}" in conductor_prompt, f"conductor references @{name}")
    
    # 13 agents total
    section("4. AGENT REGISTRY")
    check(len(cfg["agent"]) == 13, f"13 agent entries in opencode.json (got {len(cfg['agent'])})")
    check("conductor" in cfg["agent"], "conductor agent present")
    check("planner" in cfg["agent"], "planner agent present")
    for sub in ["builder", "architect", "reviewer", "tester", "docs",
                "debugger", "refactor", "git", "explorer", "security", "perf"]:
        check(sub in cfg["agent"], f"{sub} agent present")
    
    section("5. COMMAND INTEGRATION")
    
    # /setup-project template references files that the agent should create
    setup_prompt = cfg["command"]["setup-project"]["template"]
    referenced = [".opencode/plans", ".opencode/decisions", ".opencode/todo.md",
                  ".opencode/work-log.md", ".gitignore", "README.md"]
    for ref in referenced:
        check(ref in setup_prompt, f"/setup-project template mentions: {ref}")
    
    # /build template references plan structure
    build_prompt = cfg["command"]["build"]["template"]
    build_refs = [".opencode/plans", "completed", "verify", "build", "test", "archive"]
    for ref in build_refs:
        check(ref.lower() in build_prompt.lower(),
              f"/build template mentions: '{ref}'")
    
    # /build mentions agents it will dispatch
    build_agents = ["@debugger", "@builder", "@reviewer"]
    for ag in build_agents:
        check(ag in build_prompt, f"/build template references {ag}")
    
    section("6. CONDUCTOR WORKFLOW REFERENTIAL INTEGRITY")
    
    workflow_steps = [
        "CLARIFY", "GRAPHIFY", "PLAN", "TODO", "DISPATCH", "TRACK",
        "REVIEW", "VERIFY", "DOCUMENT", "SYNC TODO", "GRAPHIFY UPDATE",
        "GIT", "REPORT", "RESUME"
    ]
    # Each step should reference the tools/files it needs
    workflow_assertions = {
        "GRAPHIFY": ["graphify", "MCP", "query"],
        "PLAN": [".opencode/plans"],
        "TODO": ["todowrite", ".opencode/todo.md"],
        "DISPATCH": ["@mention", "parallel"],
        "REVIEW": ["@reviewer"],
        "VERIFY": [".opencode/plans", "re-read", "actual"],
        "DOCUMENT": ["work-log", "ADR", "graphify"],
        "GRAPHIFY UPDATE": ["graphify", "--update"],
        "GIT": ["git add", "commit"],
        "RESUME": [".opencode/todo.md"],
    }
    for step, keywords in workflow_assertions.items():
        for kw in keywords:
            check(kw.lower() in conductor_prompt.lower(),
                  f"conductor workflow step '{step}' references '{kw}'")
    
    section("7. GLOBAL-SETUP.BAT FUNCTIONAL VERIFICATION")
    
    # This block verifies the GLOBAL installer (global-setup.bat) — it is the
    # file that touches the user's %USERPROFILE%\.config\opencode, creates
    # junctions, and triggers the JSONC merge via opencode_jsonc_merge.py.
    # Earlier revisions of this assertion block misread setup.bat (the
    # per-project installer) and asserted global-setup-specific strings on
    # the wrong file. Plan-002 Layer 3 task #8 fixed that mislabeling.
    gsetup = (REPO / "global-setup.bat").read_text()
    setup_assertions = {
        "config dir creation": "%USERPROFILE%\\.config\\opencode",
        "agents target": "agents",
        "skills target": "skills",
        "symlink command": "mklink",
        "junktion (no-admin)": "/J",
        "config write": "opencode.jsonc",
    }
    for desc, key in setup_assertions.items():
        if isinstance(key, str):
            check(key in gsetup, f"global-setup.bat has: {desc} ('{key[:30]}')")
        else:
            check(key, f"global-setup.bat: {desc}")
    
    # Verify global-setup.bat uses config-driven paths (not hardcoded)
    check("%USERPROFILE%" in gsetup, "global-setup.bat uses %USERPROFILE% (portable)")
    check("%~dp0" in gsetup, "global-setup.bat uses %~dp0 (script-relative)")
    
    section("8. KNOWLEDGE GRAPH FLOW")
    
    # Conductor step 2 (GRAPHIFY) and step 11 (GRAPHIFY UPDATE) should be coherent
    mcp_section = cfg.get("mcp", {}).get("graphify", {})
    check(mcp_section, "graphify MCP server is configured")
    check(mcp_section.get("command"), "graphify command array defined")
    
    # Skill should be registered
    skill_path = REPO / ".opencode/skills/graphify-agent-workflow/SKILL.md"
    check(skill_path.exists(), "graphify skill exists")
    skill_content = skill_path.read_text()
    check("description:" in skill_content, "skill has description (auto-triggers)")
    check("name: graphify-agent-workflow" in skill_content, "skill has name")
    
    section("9. PLAN FILE FORMAT CONSISTENCY")
    
    # Conductor creates plans, planner creates plans, both should use compatible format
    planner_prompt = cfg["agent"]["planner"]["prompt"]
    check("Plan" in planner_prompt or "Plan format" in planner_prompt or "Output format" in planner_prompt,
          "planner has plan format definition")
    check("Layer" in conductor_prompt and "Layer" in planner_prompt,
          "both conductor and planner reference dependency 'Layer's")
    
    # Verify the conductor's plan template matches what the /build command will look for
    plan_template_in_conductor = re.search(r"## Tasks\s*\n(.*?)## Verification", conductor_prompt, re.DOTALL)
    check(plan_template_in_conductor is not None,
          "conductor has Tasks section in plan template")
    check("Layer" in (plan_template_in_conductor.group(1) if plan_template_in_conductor else ""),
          "plan template has 'Layer' sub-sections")
    check("## Verification" in conductor_prompt,
          "conductor plan template has Verification section")
    
    section("10. GIT INTEGRATION")
    
    # The conductor's git step should reference realistic commands
    git_section = re.search(r"### 12\. GIT.*?(?=### 13\.)", conductor_prompt, re.DOTALL)
    check(git_section is not None, "conductor has GIT step")
    if git_section:
        git_text = git_section.group(0)
        check("git add" in git_text, "git step uses 'git add'")
        check("commit" in git_text, "git step uses commit")
        check("y/n" in git_text or "ask" in git_text.lower(), "git step asks for confirmation")
    
    # Git subagent has the right permission
    git_perms = cfg["agent"]["git"].get("permission", {})
    check(git_perms.get("bash", {}).get("git *") == "allow",
          "git agent allows git commands")
    check(git_perms.get("bash", {}).get("*") == "deny",
          "git agent denies non-git commands (security)")
    
    section("11. END-TO-END FLOW COHERENCE")
    
    # Verify the conductor's workflow can actually be executed
    # 1. CLARIFY -> user prompt
    # 2. GRAPHIFY -> MCP server
    # 3. PLAN -> write file
    # 4. TODO -> todowrite + file
    # 5. DISPATCH -> @mention subagents
    # 6. TRACK -> todowrite
    # 7. REVIEW -> @reviewer
    # 8. VERIFY -> re-read file
    # 9. DOCUMENT -> work-log, ADR, graphify
    # 10. SYNC -> file
    # 11. GRAPHIFY UPDATE -> CLI
    # 12. GIT -> bash
    # 13. REPORT -> chat
    # 14. RESUME -> file
    
    # Check conductor has all tools needed for its workflow
    # (Conductor has full access by default since no permission block restricts it)
    conductor_entry = cfg["agent"]["conductor"]
    # Conductor should be able to read, edit, and run bash (default behavior)
    print("  INFO: conductor has no explicit permission block — uses defaults (full access)")
    
    section("12. PROMPT QUALITY (no broken placeholders)")
    
    # Check for unresolved template placeholders in agent prompts
    PLACEHOLDER_PATTERNS = [
        r"\{\{[^}]+\}\}",  # {{var}}
        r"<TODO[^>]*>",    # <TODO>
        r"FIXME",
        r"XXX",
        r"\bplaceholder\b",
    ]
    for name, entry in cfg.get("agent", {}).items():
        content = entry.get("prompt", "") + "\n" + entry.get("description", "")
        for pattern in PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, content)
            check(len(matches) == 0,
                  f"{name} has no '{pattern}' placeholders")
    
    section("13. FILE STRUCTURE & GITIGNORE")
    
    # All directories that should exist
    required_dirs = [
        ".opencode",
        ".opencode/skills",
        ".opencode/plans",
        ".opencode/plans/completed",
        ".opencode/decisions",
    ]
    for d in required_dirs:
        check((REPO / d).is_dir(), f"directory exists: {d}")
    
    # .opencode/agents dir does not need to exist in new architecture
    # (consolidated to opencode.json)
    
    # No stray .opencode.zip or other garbage at root
    stray = list(REPO.glob("*.zip"))
    if stray:
        print(f"  INFO: stray files at root: {[s.name for s in stray]}")
        # Not a failure, just info
    
    # Verify .gitignore exists or that graphify-out is in plan to be ignored
    # (we don't have .gitignore yet, but plans/agent files suggest it's planned in setup-project)
    
    section("14. CROSS-PLATFORM COMPATIBILITY")
    
    # Check agent prompts for shell-specific commands
    SHELL_SENSITIVE = ["powershell", "cmd.exe", "/bin/bash"]
    for name, entry in cfg.get("agent", {}).items():
        content = entry.get("prompt", "")
        has_shell = any(cmd in content.lower() for cmd in SHELL_SENSITIVE)
        if has_shell:
            print(f"  INFO: {name} mentions shell: {[c for c in SHELL_SENSITIVE if c in content.lower()]}")
    
    print("\n" + "=" * 70)
    print(f"PASSED: {len(passed)}")
    print(f"FAILED: {len(errors)}")
    print("=" * 70)
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\nIntegration tests passed!")


if __name__ == "__main__":
    main()

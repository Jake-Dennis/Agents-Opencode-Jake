"""Structural safety tests for opencode.json (plan-009 + plan-010).

These tests verify that:

  1. Every agent has a positive integer `steps` cap  (T-AS-1)
  2. Every agent denies all task invocations         (T-AS-2)
  3. Global `compaction.prune` and `compaction.auto`  (T-AS-3)
  4. Existing permission fields are preserved         (T-AS-4)
  5. Conductor's `steps` cap is at least 30          (T-AS-5)
  6. The conductor's prompt body lives in a markdown file (T-AS-6)
  7. The setup-project command lives in a markdown file (T-AS-7)
  8. The build command lives in a markdown file       (T-AS-8)
  9. The conductor's prompt is a `{file:...}` reference in JSON (T-AS-9)
 10. The 2 commands are absent from opencode.json (T-AS-10)

The plan-009 primitives enforce the "conductor is sole dispatcher"
architecture at the JSON level. The plan-010 markdown migration makes
prompts diffable and fixes Unicode mojibake (em-dashes and box-drawing
characters in the conductor prompt). See
`.opencode/plans/plan-009-agent-safety-primitives.md` and
`.opencode/plans/plan-010-agent-markdown-migration.md` for full specs.

Stdlib only. Clear failure messages naming the offending agent.
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO / "opencode.json"

# Markdown files added by plan-010 (the prompt + 2 commands moved out of JSON)
CONDUCTOR_MD = REPO / ".opencode" / "agents" / "conductor.md"
SETUP_PROJECT_MD = REPO / ".opencode" / "commands" / "setup-project.md"
BUILD_MD = REPO / ".opencode" / "commands" / "build.md"

# The complete agent roster per plan-009 T1 Spec (13 agents).
EXPECTED_AGENTS = {
    "conductor", "planner",
    "builder", "architect", "reviewer", "tester",
    "docs", "debugger", "refactor",
    "git", "explorer", "security", "perf",
}

# Permission keys each agent must KEEP after plan-009 is applied.
# Mirrors the current opencode.json state exactly. The builder must
# add `task` alongside these without dropping any. (12 agents have
# a permission block; `conductor` is the only one without.)
EXPECTED_PERMISSION_KEYS = {
    "planner":   {"edit", "bash"},
    "builder":   {"edit", "bash"},
    "architect": {"edit", "read"},
    "reviewer":  {"edit", "read"},
    "tester":    {"edit", "bash"},
    "docs":      {"edit"},
    "debugger":  {"edit", "bash", "read"},
    "refactor":  {"edit", "bash"},
    "git":       {"bash"},
    "explorer":  {"edit", "read", "bash"},
    "security":  {"edit", "read", "bash"},
    "perf":      {"edit", "bash", "read"},
}


def _load_config() -> dict:
    """Load opencode.json from the repo root.

    Centralized so every test sees the same file and any I/O error
    becomes a single, clear failure message.
    """
    assert CONFIG_PATH.exists(), (
        f"opencode.json not found at {CONFIG_PATH}. "
        f"This test file expects the standard layout "
        f"({REPO}/opencode.json at the repo root)."
    )
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        pytest.fail(f"opencode.json is not valid JSON: {e}")


# ---------------------------------------------------------------------------
# T-AS-1: All 13 agents have a positive integer `steps` field.
# ---------------------------------------------------------------------------

def test_T_AS_1_all_agents_have_positive_steps():
    """T-AS-1: every agent in opencode.json has `steps` set to a
    positive integer (>0). On failure, the message lists which
    agents are missing the field or have a non-positive value.
    """
    cfg = _load_config()
    agents = cfg.get("agent")
    assert isinstance(agents, dict), (
        f"opencode.json top-level `agent` block must be a dict, "
        f"got {type(agents).__name__}: {agents!r}"
    )

    missing_agents = EXPECTED_AGENTS - set(agents.keys())
    assert not missing_agents, (
        f"opencode.json is missing these agents entirely "
        f"(expected 13 total): {sorted(missing_agents)}"
    )

    invalid = []
    for name in sorted(EXPECTED_AGENTS):
        body = agents.get(name)
        if not isinstance(body, dict):
            invalid.append((name, f"body is {type(body).__name__}, not dict"))
            continue
        steps = body.get("steps", "__missing__")
        # bool is a subclass of int in Python — reject True/False explicitly.
        if steps == "__missing__":
            invalid.append((name, "no `steps` field"))
        elif isinstance(steps, bool) or not isinstance(steps, int):
            invalid.append((name, f"`steps` is {steps!r} (type {type(steps).__name__})"))
        elif steps <= 0:
            invalid.append((name, f"`steps` is {steps} (must be > 0)"))

    assert not invalid, (
        f"agents missing or with invalid `steps` (need positive int): "
        f"{invalid}\n"
        f"agents present: {sorted(agents.keys())}"
    )


# ---------------------------------------------------------------------------
# T-AS-2: All 13 agents deny all task invocations.
# ---------------------------------------------------------------------------

def test_T_AS_2_all_agents_deny_all_task():
    """T-AS-2: every agent has `permission.task` with `*` mapped to
    `"deny"`. This is the load-bearing safety primitive — it forces
    the conductor to be the sole dispatcher and prevents subagent
    recursion. On failure, lists the offending agents.
    """
    cfg = _load_config()
    agents = cfg.get("agent", {})

    missing_field = []   # no permission block, or no permission.task
    wrong_policy = []    # permission.task exists but "*" != "deny"

    for name in sorted(EXPECTED_AGENTS):
        body = agents.get(name)
        if not isinstance(body, dict):
            missing_field.append((name, f"agent body is {type(body).__name__}"))
            continue
        permission = body.get("permission")
        if not isinstance(permission, dict):
            missing_field.append((name, f"no permission block (got {permission!r})"))
            continue
        task = permission.get("task")
        if not isinstance(task, dict):
            missing_field.append((name, f"permission.task is {task!r} (need dict)"))
            continue
        if task.get("*") != "deny":
            wrong_policy.append((name, dict(task)))

    problems = []
    if missing_field:
        problems.append(
            "agents missing `permission.task` deny-all block:\n  - "
            + "\n  - ".join(f"{n}: {why}" for n, why in missing_field)
        )
    if wrong_policy:
        problems.append(
            "agents whose `permission.task.*` is not \"deny\":\n  - "
            + "\n  - ".join(f"{n}: {p}" for n, p in wrong_policy)
        )
    assert not problems, "\n".join(problems)


# ---------------------------------------------------------------------------
# T-AS-3: Global `compaction.prune` and `compaction.auto` are both true.
# ---------------------------------------------------------------------------

def test_T_AS_3_compaction_prune_and_auto():
    """T-AS-3: the top-level `compaction` block has both `prune: true`
    and `auto: true`. `prune` saves tokens on long sessions (upstream
    default is `false`); `auto` keeps the existing upstream default
    explicit so we can never silently lose it.
    """
    cfg = _load_config()
    compaction = cfg.get("compaction")
    assert isinstance(compaction, dict), (
        f"opencode.json top-level `compaction` block is missing or not a dict. "
        f"Got: {compaction!r}. Expected shape: {{\"auto\": true, \"prune\": true}}"
    )
    assert compaction.get("prune") is True, (
        f"`compaction.prune` must be true (got {compaction.get('prune')!r}). "
        f"Full compaction block: {compaction}"
    )
    assert compaction.get("auto") is True, (
        f"`compaction.auto` must be true (got {compaction.get('auto')!r}). "
        f"Full compaction block: {compaction}"
    )


# ---------------------------------------------------------------------------
# T-AS-4: Existing permission fields preserved when `task` is added.
# ---------------------------------------------------------------------------

def test_T_AS_4_existing_permission_fields_preserved():
    """T-AS-4: for every agent with a pre-existing `permission` block,
    the new `task` key is added ALONGSIDE the original keys — no
    original key is lost. Guards against accidental overwrite when
    the builder reshapes permission objects (e.g. the `git` agent's
    nested `bash` dict with `git *` allow-list must stay intact).
    """
    cfg = _load_config()
    agents = cfg.get("agent", {})

    problems = []
    for name in sorted(EXPECTED_PERMISSION_KEYS):
        expected_keys = EXPECTED_PERMISSION_KEYS[name]
        body = agents.get(name)
        if not isinstance(body, dict):
            problems.append((name, f"agent body is {type(body).__name__}, not dict"))
            continue
        permission = body.get("permission")
        if not isinstance(permission, dict):
            problems.append((
                name,
                f"permission block is missing or not a dict: {permission!r} "
                f"(expected keys: {sorted(expected_keys | {'task'})})",
            ))
            continue
        current_keys = set(permission.keys())
        required = expected_keys | {"task"}
        missing = required - current_keys
        if missing:
            problems.append((
                name,
                f"missing required keys {sorted(missing)}; got {sorted(current_keys)}",
            ))

    assert not problems, (
        "agents whose `permission` block lost required keys or has the wrong shape:\n"
        + "\n".join(f"  - {n}: {why}" for n, why in problems)
    )

    # Defensive sub-check for the most fragile case: git's nested bash
    # allow-list must keep its exact shape (mirrors plan-009 verify #7).
    git = agents.get("git", {})
    git_bash = git.get("permission", {}).get("bash") if isinstance(git, dict) else None
    assert git_bash == {"git *": "allow", "*": "deny"}, (
        f"git agent's permission.bash must keep the exact allow-list shape "
        f"{{'git *': 'allow', '*': 'deny'}}. Got: {git_bash!r}"
    )


# ---------------------------------------------------------------------------
# T-AS-5: Conductor's `steps` cap is at least 30.
# ---------------------------------------------------------------------------

def test_T_AS_5_conductor_steps_at_least_30():
    """T-AS-5: regression check — conductor's `steps` cap is >= 30.

    Plan-009 T1 Spec recommends 50 for conductor (dispatch + verify +
    commit takes ~10-30 steps in normal use). The upstream OpenCode
    docs example for a `quick-thinker` agent uses 5 steps. We must
    never accidentally apply that small cap to the orchestrator.
    """
    cfg = _load_config()
    agents = cfg.get("agent", {})
    assert "conductor" in agents, (
        f"conductor agent missing from opencode.json. "
        f"Agents present: {sorted(agents.keys())}"
    )
    conductor = agents["conductor"]
    assert isinstance(conductor, dict), (
        f"conductor agent body must be a dict, got {type(conductor).__name__}"
    )
    steps = conductor.get("steps")
    # bool is a subclass of int in Python — reject True/False explicitly.
    assert isinstance(steps, int) and not isinstance(steps, bool), (
        f"conductor.steps must be an int (got {steps!r}, "
        f"type {type(steps).__name__})"
    )
    assert steps >= 30, (
        f"conductor.steps must be >= 30 (current value: {steps}). "
        f"Conductor runs dispatch + verify + commit which needs at least 30 steps. "
        f"Recommended value per plan-009 T1 Spec: 50. "
        f"Never cap the orchestrator at 5 like the OpenCode `quick-thinker` example."
    )


# ---------------------------------------------------------------------------
# T-AS-6: The conductor's prompt body lives in `.opencode/agents/conductor.md`.
# ---------------------------------------------------------------------------

def test_T_AS_6_conductor_prompt_lives_in_markdown_file():
    """T-AS-6: the conductor agent's prompt is a markdown file at
    `.opencode/agents/conductor.md`. The file must exist and contain a
    substantial prompt body (the inline 5 KB string is now in the
    file). The body is plain text (no frontmatter required for a
    partial agent definition where config stays in JSON).
    """
    assert CONDUCTOR_MD.exists(), (
        f"Conductor prompt file is missing: {CONDUCTOR_MD}\n"
        f"Plan-010 moved the 5 KB inline conductor prompt out of "
        f"opencode.json to this file. The agent's config (description, "
        f"mode, steps, permission) stays in JSON; only the prompt body "
        f"moved."
    )

    # Read with explicit UTF-8 — em-dashes and box-drawing chars are
    # expected in the body. Reject the Unicode replacement char (\ufffd)
    # which would indicate a mojibake round-trip.
    body = CONDUCTOR_MD.read_text(encoding="utf-8")
    assert "\ufffd" not in body, (
        f"{CONDUCTOR_MD} contains U+FFFD replacement characters. "
        f"The file was probably written or read in a non-UTF-8 encoding. "
        f"Plan-010's goal is to fix this kind of mojibake."
    )

    # Body should be substantial — the original inline prompt was ~5 KB.
    # Threshold: 1000 chars. Anything less means the file was truncated.
    assert len(body) >= 1000, (
        f"conductor.md is suspiciously short ({len(body)} chars; expected "
        f">= 1000). The original inline prompt was ~5 KB. Was something "
        f"truncated during the extraction?"
    )

    # Sanity: first line should still identify the conductor.
    first_line = body.splitlines()[0] if body.splitlines() else ""
    assert "conductor" in first_line.lower(), (
        f"conductor.md first line should identify the conductor role. "
        f"Got: {first_line!r}"
    )


# ---------------------------------------------------------------------------
# T-AS-7: The setup-project command lives in `.opencode/commands/setup-project.md`.
# ---------------------------------------------------------------------------

def test_T_AS_7_setup_project_command_lives_in_markdown_file():
    """T-AS-7: the setup-project command is a markdown file at
    `.opencode/commands/setup-project.md`. Per the upstream OpenCode
    commands spec, the file must have YAML frontmatter (starting with
    `---` on line 1) and a body (the template).
    """
    assert SETUP_PROJECT_MD.exists(), (
        f"setup-project command file is missing: {SETUP_PROJECT_MD}\n"
        f"Plan-010 moved the inline `command.setup-project.template` "
        f"out of opencode.json to this file (the documented upstream "
        f"markdown-only command pattern)."
    )

    content = SETUP_PROJECT_MD.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Frontmatter: line 1 must be `---`. Close marker must exist.
    assert lines and lines[0].strip() == "---", (
        f"{SETUP_PROJECT_MD} line 1 must be `---` (YAML frontmatter "
        f"delimiter per the upstream Commands docs). "
        f"First line: {lines[0] if lines else ''!r}"
    )
    assert any(line.strip() == "---" for line in lines[1:]), (
        f"{SETUP_PROJECT_MD} is missing the closing `---` frontmatter "
        f"delimiter. The upstream Commands docs require frontmatter "
        f"with at least a `description` key."
    )

    # Description key must be present in the frontmatter.
    assert "description:" in content, (
        f"{SETUP_PROJECT_MD} frontmatter must contain a `description:` "
        f"key (shown in the TUI command palette per the upstream Commands "
        f"docs)."
    )

    # Body must exist between the closing `---` and EOF.
    closing_idx = next(i for i, line in enumerate(lines[1:], start=1)
                       if line.strip() == "---")
    body = "\n".join(lines[closing_idx + 1:]).strip()
    assert len(body) >= 50, (
        f"setup-project.md body is too short ({len(body)} chars). "
        f"Expected the full template text (>= 50 chars)."
    )


# ---------------------------------------------------------------------------
# T-AS-8: The build command lives in `.opencode/commands/build.md`.
# ---------------------------------------------------------------------------

def test_T_AS_8_build_command_lives_in_markdown_file():
    """T-AS-8: the build command is a markdown file at
    `.opencode/commands/build.md`. Same frontmatter requirements as
    setup-project.
    """
    assert BUILD_MD.exists(), (
        f"build command file is missing: {BUILD_MD}\n"
        f"Plan-010 moved the inline `command.build.template` out of "
        f"opencode.json to this file."
    )

    content = BUILD_MD.read_text(encoding="utf-8")
    lines = content.splitlines()

    assert lines and lines[0].strip() == "---", (
        f"{BUILD_MD} line 1 must be `---`. First line: "
        f"{lines[0] if lines else ''!r}"
    )
    assert any(line.strip() == "---" for line in lines[1:]), (
        f"{BUILD_MD} is missing the closing `---` frontmatter delimiter."
    )
    assert "description:" in content, (
        f"{BUILD_MD} frontmatter must contain a `description:` key."
    )

    closing_idx = next(i for i, line in enumerate(lines[1:], start=1)
                       if line.strip() == "---")
    body = "\n".join(lines[closing_idx + 1:]).strip()
    # Build command template is ~3 KB; threshold of 500 chars is conservative.
    assert len(body) >= 500, (
        f"build.md body is too short ({len(body)} chars; expected "
        f">= 500). The original template was ~3 KB."
    )


# ---------------------------------------------------------------------------
# T-AS-9: The conductor's prompt is a `{file:...}` reference in JSON.
# ---------------------------------------------------------------------------

def test_T_AS_9_conductor_prompt_is_file_reference():
    """T-AS-9: opencode.json's `agent.conductor.prompt` is a `{file:...}`
    string (per the upstream Agents docs "Prompt" section), NOT an
    inline multi-line string. This guards against accidentally
    re-inlining the 5 KB prompt.
    """
    cfg = _load_config()
    agents = cfg.get("agent", {})
    assert "conductor" in agents, (
        f"conductor agent missing from opencode.json. "
        f"Agents present: {sorted(agents.keys())}"
    )
    conductor = agents["conductor"]
    assert isinstance(conductor, dict), (
        f"conductor agent body must be a dict, got {type(conductor).__name__}"
    )
    prompt = conductor.get("prompt")
    assert isinstance(prompt, str), (
        f"conductor.prompt must be a string (the {{file:...}} ref), "
        f"got {type(prompt).__name__}: {prompt!r}"
    )
    assert prompt.startswith("{file:"), (
        f"conductor.prompt must start with `{{file:` (the upstream "
        f"prompt-substitution syntax). Got: {prompt[:60]!r}. "
        f"If you see a long multi-line string here, the conductor "
        f"prompt was re-inlined by accident."
    )
    assert "conductor.md" in prompt, (
        f"conductor.prompt file ref must point to `conductor.md`. "
        f"Got: {prompt!r}"
    )


# ---------------------------------------------------------------------------
# T-AS-10: The 2 commands are absent from opencode.json.
# ---------------------------------------------------------------------------

def test_T_AS_10_commands_removed_from_json():
    """T-AS-10: opencode.json does NOT have `command.setup-project` or
    `command.build` blocks. Per the upstream Commands docs, the
    markdown files in `.opencode/commands/` are the sole definition
    (the `template` field does not support `{file:...}`, so the JSON
    block must be removed entirely to avoid duplication / override
    ambiguity).
    """
    cfg = _load_config()
    command = cfg.get("command")

    # The command block may be present but empty, or removed entirely.
    if command is None:
        return  # command block was removed entirely (acceptable)

    if not isinstance(command, dict):
        pytest.fail(
            f"opencode.json top-level `command` block must be a dict, "
            f"got {type(command).__name__}: {command!r}"
        )

    for name in ("setup-project", "build"):
        assert name not in command, (
            f"opencode.json still has a `command.{name}` block. "
            f"Plan-010 moved this command to "
            f"`.opencode/commands/{name}.md`. The JSON block must be "
            f"removed because `template` doesn't support `{{file:...}}` "
            f"and having both definitions creates override ambiguity. "
            f"Current value: {command[name]!r}"
        )


# ===========================================================================
# plan-012: per-agent color + temperature + top_p + variant
# ===========================================================================

# Valid color values per upstream opencode config: a 6-digit hex
# (`#RRGGBB`) OR one of the 8 theme names. T-AS-11 enforces this for all
# 13 agents.
_VALID_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_VALID_THEME_COLORS = {
    "primary", "secondary", "accent",
    "success", "warning", "error", "info",
}


# ---------------------------------------------------------------------------
# T-AS-11: All 13 agents have a `color` field that is valid
# ---------------------------------------------------------------------------

def test_T_AS_11_all_agents_have_valid_color():
    """T-AS-11: Each agent has a `color` field that is either a valid
    hex (`^#[0-9a-fA-F]{6}$`) or one of the 8 theme names.
    Plan-012's design uses 13 distinct hex codes (tailwind-200/300/400
    palette) for the 13 agents.
    """
    cfg = _load_config()
    agents = cfg["agent"]
    assert len(agents) == 13, f"expected 13 agents, got {len(agents)}"

    bad = []
    for name, body in agents.items():
        if not isinstance(body, dict):
            bad.append((name, f"<not a dict: {type(body).__name__}>"))
            continue
        if "color" not in body:
            bad.append((name, "<missing color field>"))
            continue
        color = body["color"]
        if not isinstance(color, str):
            bad.append((name, f"<non-string: {type(color).__name__}: {color!r}>"))
            continue
        if _VALID_HEX_COLOR.match(color):
            continue  # valid hex
        if color in _VALID_THEME_COLORS:
            continue  # valid theme name
        bad.append((name, color))

    assert not bad, (
        f"agents with invalid color values: {bad}\n"
        f"Valid: a 6-digit hex (#RRGGBB) or one of "
        f"{sorted(_VALID_THEME_COLORS)}"
    )


# ---------------------------------------------------------------------------
# T-AS-12: temperature values are numbers in [0.0, 2.0]
# ---------------------------------------------------------------------------

def test_T_AS_12_temperature_in_range():
    """T-AS-12: For agents with a `temperature` field, the value is a
    number in [0.0, 2.0]. (Upstream docs say 0.0-1.0 but providers may
    accept up to 2.0.)
    Plan-012's design sets `temperature: 0.1` on `reviewer` + `security`
    and `temperature: 0.2` on `planner` + `architect`. All other agents
    have no `temperature` field and use the model default.
    """
    cfg = _load_config()
    agents = cfg["agent"]
    bad = []
    for name, body in agents.items():
        if not isinstance(body, dict) or "temperature" not in body:
            continue
        t = body["temperature"]
        if not isinstance(t, (int, float)) or isinstance(t, bool):
            bad.append((name, f"<non-numeric: {type(t).__name__}: {t!r}>"))
            continue
        if not (0.0 <= float(t) <= 2.0):
            bad.append((name, f"<out of range: {t!r}>"))

    assert not bad, f"agents with invalid temperature: {bad}"


# ---------------------------------------------------------------------------
# T-AS-13: top_p values are numbers in [0.0, 1.0]
# ---------------------------------------------------------------------------

def test_T_AS_13_top_p_in_range():
    """T-AS-13: For agents with a `top_p` field, the value is a number
    in [0.0, 1.0].
    Plan-012's design does NOT add `top_p` to any agent (mutually
    exclusive with `temperature` per the plan). This test passes
    trivially but guards against future plans that add `top_p`.
    """
    cfg = _load_config()
    agents = cfg["agent"]
    bad = []
    for name, body in agents.items():
        if not isinstance(body, dict) or "top_p" not in body:
            continue
        p = body["top_p"]
        if not isinstance(p, (int, float)) or isinstance(p, bool):
            bad.append((name, f"<non-numeric: {type(p).__name__}: {p!r}>"))
            continue
        if not (0.0 <= float(p) <= 1.0):
            bad.append((name, f"<out of range: {p!r}>"))

    assert not bad, f"agents with invalid top_p: {bad}"


# ---------------------------------------------------------------------------
# T-AS-14: variant values are non-empty strings
# ---------------------------------------------------------------------------

def test_T_AS_14_variant_is_nonempty_string():
    """T-AS-14: For agents with a `variant` field, the value is a
    non-empty string (after strip).
    Plan-012's design does NOT add `variant` to any agent (the model
    name `opencode/minimax-m3-free` is unverified; the `opencode models`
    CLI crashes; Zen free-tier variants are undocumented in the
    upstream docs). This test passes trivially but guards against
    future plans that add `variant`.
    """
    cfg = _load_config()
    agents = cfg["agent"]
    bad = []
    for name, body in agents.items():
        if not isinstance(body, dict) or "variant" not in body:
            continue
        v = body["variant"]
        if not isinstance(v, str) or not v.strip():
            bad.append((name, f"<not a non-empty string: {v!r}>"))

    assert not bad, f"agents with invalid variant: {bad}"


# ---------------------------------------------------------------------------
# T-AS-15: no agent has BOTH temperature AND top_p
# ---------------------------------------------------------------------------

def test_T_AS_15_no_temperature_AND_top_p():
    """T-AS-15: No agent has BOTH `temperature` and `top_p` set.
    Per plan-012: these are mutually exclusive in practice (both reduce
    randomness; applying both is redundant). Plan-012 sets `temperature`
    on 4 agents and `top_p` on none, so this test passes trivially.
    """
    cfg = _load_config()
    agents = cfg["agent"]
    bad = [
        name for name, body in agents.items()
        if isinstance(body, dict)
        and "temperature" in body
        and "top_p" in body
    ]
    assert not bad, (
        f"agents with BOTH temperature and top_p (mutually exclusive): {bad}"
    )

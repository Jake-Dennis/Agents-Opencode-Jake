# Plan 010 design: move conductor + 2 commands to markdown files

## Context

Plan 010 extracts the 5 KB+ conductor prompt and the 2 inline command templates
(`setup-project`, `build`) from `opencode.json` to markdown files. The
upstream OpenCode TUI has supported this since at least 2025: markdown agents
in `.opencode/agents/`, markdown commands in `.opencode/commands/`. The
project's `opencode.json` still inlines both forms as JSON-escaped strings,
which (a) is hard to diff in PRs, (b) already shows Unicode mojibake in the
work-log (line 155-167 corruption was a cp1252 round-trip), and (c) makes
`opencode.json` 27 KB of which ~5 KB is the conductor prompt alone.

Two upstream patterns apply, and they're different for agents vs commands:

### Agent pattern (partial definition)

For the conductor, the `prompt` field in `opencode.json` supports
`{file:./path/to/file.md}` substitution (per the upstream Agents docs,
"Prompt" section). The agent block stays in JSON with all its config
(`description`, `mode`, `steps`, `permission`, etc.); only the prompt body
moves to a file. This preserves the testability of T-AS-1..T-AS-5 (which
read the conductor's `steps` and `permission` from JSON).

### Command pattern (full definition)

For custom commands, the upstream pattern is markdown-only: a file in
`.opencode/commands/<name>.md` with YAML frontmatter (description, agent,
model) + body (the template). The JSON `command.<name>` block is REMOVED.
The docs are explicit: "Custom commands can override built-in commands.
If you define a custom command with the same name, it will override the
built-in command." Keeping both creates ambiguity; the markdown wins.
Note: `template` in JSON does NOT support `{file:...}` — that's why we
must remove the JSON block entirely for commands.

## File structure

```
.opencode/
├── agents/
│   └── conductor.md                # NEW: just the prompt body, no frontmatter needed
└── commands/
    ├── setup-project.md            # NEW: frontmatter (description) + body
    └── build.md                    # NEW: frontmatter (description) + body
```

## `opencode.json` refactor

### Agent (conductor)

BEFORE (in JSON):
```json
"conductor": {
  "description": "Orchestrator agent. ...",
  "mode": "primary",
  "prompt": "You are the conductor — ... [5 KB of inline string]",
  "steps": 50,
  "permission": { "task": { "*": "deny" } }
}
```

AFTER (in JSON):
```json
"conductor": {
  "description": "Orchestrator agent. ...",
  "mode": "primary",
  "prompt": "{file:./.opencode/agents/conductor.md}",
  "steps": 50,
  "permission": { "task": { "*": "deny" } }
}
```

The 5 KB prompt body moves to `.opencode/agents/conductor.md`. All other
fields stay in JSON (this preserves T-AS-1..T-AS-5 testability).

### Commands (setup-project, build)

BEFORE (in JSON):
```json
"command": {
  "setup-project": {
    "description": "Initialize a new project: ...",
    "template": "Run the project setup workflow: (1) detect ..."
  },
  "build": {
    "description": "Execute all plans to completion. ...",
    "template": "Enter BUILD LOOP mode. ..."
  }
}
```

AFTER (in JSON): the `command` block is removed entirely (or left empty
`{}` if the opencode schema requires the key to exist). The two commands
are defined in markdown files:

`.opencode/commands/setup-project.md`:
```markdown
---
description: Initialize a new project: build knowledge graph, create .opencode structure, init git, set up .gitignore
---

Run the project setup workflow: (1) detect project type and language,
(2) initialize git repo if missing, (3) run /graphify . to build the
knowledge graph, (4) create .opencode/plans/, .opencode/plans/completed/,
.opencode/decisions/, .opencode/todo.md, .opencode/work-log.md if they
don't exist, (5) create a sensible .gitignore (including graphify-out/,
node_modules/, .env, build artifacts, etc.), (6) create an initial
README.md if missing with project name and setup instructions, (7) report
the full setup summary to the user.
```

`.opencode/commands/build.md`:
```markdown
---
description: Execute all plans to completion. Continuously builds, tests, verifies, and archives each plan in a loop until every plan is done.
---

Enter BUILD LOOP mode. Your goal: execute ALL plans in .opencode/plans/
to completion. Do NOT stop until every plan is archived to
.opencode/plans/completed/. Follow this exact loop:

1. SCAN — list all files in .opencode/plans/ that are NOT in the
   completed/ subfolder. Read each one and check its Status line.
2. CHECK — if no in-progress plans remain, break the loop and go to
   step 9.
3. SELECT — pick the plan with the lowest NNN number. If there are
   multiple, ask the user which to prioritize.
[... rest of the original template, exactly as in the JSON ...]
```

The `description` in the markdown frontmatter is the same string that
was in the JSON `description` field (TUI command palette shows it).

## Frontmatter shape (exact)

### Conductor agent file (no frontmatter)

The conductor's markdown file has NO frontmatter. The agent's full
config (description, mode, steps, permission) stays in `opencode.json`;
the markdown file is JUST the prompt body. This is the documented
upstream pattern for `{file:...}` prompt references (per the Agents
docs, "Prompt" section).

If a future plan wants the conductor fully in markdown (option B), the
frontmatter would be:
```yaml
---
description: Orchestrator agent. ...
mode: primary
steps: 50
permission:
  task:
    "*": "deny"
---
```
…but that's a follow-up plan; this plan keeps the agent config in JSON
for testability.

### Command files (with frontmatter)

Per the upstream Commands docs, command markdown files have frontmatter
with at minimum a `description` key (which becomes the TUI label). The
body is the template (the prompt sent to the LLM). The upstream example
also shows optional `agent` and `model` keys; we don't set them (let
the command use the project's default model and the conductor agent).

## Risk analysis

### Risk 1: `{file:...}` path resolution
- **What:** The `{file:./.opencode/agents/conductor.md}` reference is
  resolved relative to the location of `opencode.json` (which is at the
  repo root). If the path is wrong, the conductor's prompt will be
  empty or opencode will fail to load the agent.
- **Why:** A typo in the path silently breaks the agent.
- **Mitigation:** T-AS-9 verifies the path contains `conductor.md`;
  the test file `tests/test_agent_safety.py` T-AS-1..T-AS-5 still
  check the JSON config. The integration test (running the conductor)
  is the only end-to-end check, but `opencode agent list` segfaults
  on Windows, so this is a known project limitation.

### Risk 2: Markdown commands may not take precedence over JSON
- **What:** Per the upstream docs, "Custom commands can override
  built-in commands. If you define a custom command with the same
  name, it will override the built-in command." The docs don't
  explicitly say what happens if BOTH JSON and markdown define the
  same custom command.
- **Why:** Keeping both creates ambiguity.
- **Mitigation:** Plan-010 REMOVES the JSON `command.setup-project`
  and `command.build` blocks. The markdown files are the sole
  definitions. This eliminates the ambiguity.

### Risk 3: Unicode in conductor prompt
- **What:** The inline conductor prompt has em-dashes (`—`, U+2014)
  rendered correctly when read via Python (UTF-8). The mojibake in
  the work-log (line 155-167, `�` characters) is a separate cp1252
  encoding issue that happens when PowerShell renders the file in
  the wrong encoding.
- **Why:** After moving to markdown, the file is read with explicit
  UTF-8 encoding, so the em-dashes and box-drawing characters should
  render correctly in any context.
- **Mitigation:** The builder reads the new file with `encoding='utf-8'`
  and checks for `\ufffd` (Unicode replacement character). The T-AS-6
  test will check the file starts with valid UTF-8 (no replacement
  chars in the body).

### Risk 4: Windows `opencode agent list` segfault
- **What:** We cannot directly verify that all 13 agents still
  resolve after the change. `opencode agent list` crashes on Windows
  (upstream issue; deferred per todo.md).
- **Why:** Without end-to-end verification, a broken `{file:...}` ref
  might not be caught until a user tries to use the agent.
- **Mitigation:** T-AS-9 verifies the `{file:...}` ref is well-formed.
  The agent's config in JSON is tested by T-AS-1..T-AS-5. The end-to-end
  test would need to run on a non-Windows machine; the user is aware
  of this limitation.

## Edge cases the builder needs to handle

1. **JSON path strings** — `{file:./.opencode/agents/conductor.md}` is
   a JSON string literal. It must be wrapped in double quotes in the
   JSON, with backslashes escaped properly. The path uses forward
   slashes (works on Windows too per the upstream docs: "This path
   is relative to where the config file is located").

2. **JSON `command` block** — after removing `setup-project` and
   `build`, the `command` block can either be removed entirely OR
   left as `{}`. Check the upstream schema; if `command` is not
   required, remove the key. If it is required, leave `{}`.

3. **Markdown file encoding** — write with UTF-8 explicitly. The
   current `opencode.json` has the conductor prompt as a
   JSON-escaped string (`\n` for newlines, etc.). When writing to
   the markdown file, the actual characters are used (real newlines,
   real em-dashes).

4. **JSON whitespace** — preserve the existing 2-space indentation
   in `opencode.json`. The `git diff` should show ONLY the 3 string
   changes (3 lines modified, no other fields touched).

5. **Verify after edit** — run
   `python -c "import json; json.load(open('opencode.json')); print('valid')"`
   to confirm the JSON is still parseable.

## Alternatives considered

### Full markdown for the conductor (move config out of JSON)

**Rejected for plan-010.** This would require moving the conductor's
`steps`, `permission`, and other config to the markdown frontmatter,
and updating T-AS-1..T-AS-5 to read from the markdown file. Higher
risk (more tests to update), higher value (uniform markdown pattern).
A future plan could do this for all 13 agents; for now, plan-010
keeps the agent config in JSON to preserve testability and minimize
the diff.

### Keep JSON command blocks with `{file:...}` template refs

**Rejected.** The upstream Commands docs do NOT show `{file:...}`
syntax for `template`. The `template` field is documented as a
plain string with `$ARGUMENTS` / `!command` / `@file` placeholders.
Trying `{file:...}` here would be an undocumented extension that
might or might not work. The markdown-only command pattern is
documented and reliable.

### Keep both JSON and markdown definitions

**Rejected.** The upstream docs warn that custom commands can
override built-ins; they don't clarify what happens with
duplicates. To eliminate ambiguity, plan-010 removes the JSON
blocks and lets the markdown files be the sole source of truth.

## Unicode recovery (concrete)

The current inline conductor prompt is written as a JSON-escaped
string. Em-dashes (`—`, U+2014) and box-drawing characters (`│`,
U+2502) appear correctly when read via Python with UTF-8 encoding.
No literal mojibake exists in `opencode.json` itself. The
mojibake seen in the work-log (line 155-167) is a separate issue
caused by PowerShell rendering the file in cp1252; that corruption
is in the work-log, not in the source.

After moving to `.opencode/agents/conductor.md`, the file is read
with explicit UTF-8 encoding, so em-dashes and box-drawing chars
should render correctly in any context (TUI, file readers, work-log
quotes, etc.).

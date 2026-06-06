# Plan 010: Move conductor agent + 2 commands to markdown files

## Goal

Extract the 5 KB+ conductor prompt and the 2 inline command templates (`setup-project`, `build`) from `opencode.json` to markdown files. Three concrete wins:

1. **Fix Unicode mojibake** in the conductor prompt (em-dashes and `\u2502` characters are already broken in the JSON-string-escaped form; the `Work-log` line 155-167 corruption is from this)
2. **Make prompts reviewable as diffs** — 5 KB inline JSON string is un-diffable; a `.md` file diffs cleanly
3. **Shrink `opencode.json`** from 27 KB to ~22 KB; future per-agent tweaks land in small focused files

OpenCode supports markdown agent files in the per-project agents/ directory (frontmatter + body) and markdown commands in the per-project commands/ directory (frontmatter + body with `$ARGUMENTS` / `$1` / `!shell` / `@file` syntax). The `prompt` field in `opencode.json` supports `{file:./.opencode/agents/conductor.md}` references.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1: @architect reads upstream docs (https://opencode.ai/docs/agents, https://opencode.ai/docs/commands), designs the exact frontmatter shape, the file paths, and the `opencode.json` refactor pattern (assigned: @architect)
- [ ] #2: @tester extends `tests/test_agent_safety.py` with T-AS-6..T-AS-10 (markdown files exist, frontmatter valid, `opencode.json` references resolve) (assigned: @tester)

### Layer 2 (depends on Layer 1)
- [ ] #3: @builder extracts the conductor prompt, `setup-project` template, and `build` template to markdown files; replaces inline strings with `{file:...}` references in `opencode.json` (assigned: @builder)

### Layer 3 (depends on Layer 2)
- [ ] #4: @reviewer reviews the diff and runs `scripts/verify-plan.py` + the new tests (assigned: @reviewer)

### Layer 4 (conductor, depends on Layer 3)
- [ ] #5: @conductor runs final verify, archives plan, appends work-log, asks user to commit (assigned: @conductor)

## T1 Spec (@architect)

Read first:
- https://opencode.ai/docs/agents (markdown agents section)
- https://opencode.ai/docs/commands (markdown commands section)
- `opencode.json` (the inline conductor prompt + the 2 commands)
- `.opencode/decisions/adr-004-agent-roles.md` (preserve the 7 conductor-only actions in the prompt body)

Write to: `.opencode/plans/plan-010-design.md` (new file, 50-200 lines, markdown)

Output must contain:

### Section 1: Markdown file structure
- `.opencode/agents/conductor.md` — the conductor prompt, frontmatter + body
- `.opencode/commands/setup-project.md` — the setup-project command
- `.opencode/commands/build.md` — the build command

For each file, specify the exact frontmatter keys (description, mode for the agent; description, template or subtask for commands) and a 1-paragraph body summary.

### Section 2: `opencode.json` refactor pattern
- `agent.conductor.prompt`: replace inline string with `"{file:./.opencode/agents/conductor.md}"`
- `command.setup-project.template`: replace with `"{file:./.opencode/commands/setup-project.md}"`
- `command.build.template`: replace with `"{file:./.opencode/commands/build.md}"`

Note: the path is relative to `opencode.json` location. Since `opencode.json` is at repo root, paths starting with `./.opencode/...` work.

### Section 3: Frontmatter shape (exact)
Quote the upstream docs example for markdown agents and commands. Confirm the YAML keys match the JSON schema (description, mode, prompt, model, temperature, permission, etc.).

### Section 4: Risk analysis
- **Risk 1**: `{file:...}` references are resolved at load time. If the file is missing or unreadable, agent resolution fails silently or with a confusing error. Test must verify the file exists.
- **Risk 2**: The Windows segfault in `opencode agent list` means we cannot directly verify all 13 agents still resolve after the change. Workaround: rely on `tests/test_agent_safety.py` (extended in T2) to verify the markdown files exist and the JSON references are well-formed. The integration test would need to run on a non-Windows machine.
- **Risk 3**: The conductor prompt's inline em-dashes and `\u2502` chars are already mojibake. After moving to markdown, the source file is UTF-8, so they should render correctly. Verify by reading the new file with a UTF-8 reader.

### Section 5: Unicode recovery (concrete)
List the specific broken characters in the current inline prompt (em-dashes `—`, box-drawing `\u2502`, etc.) and the correct UTF-8 characters they should be. Architect should specify whether to do a literal replacement (em-dash → em-dash) or accept the existing rendering.

## T2 Spec (@tester)

Extend `tests/test_agent_safety.py` (currently 274 lines) with 5 new tests:

- **T-AS-6**: `.opencode/agents/conductor.md` exists, has YAML frontmatter (starts with `---` on line 1), has `description` and `mode` keys.
- **T-AS-7**: `.opencode/commands/setup-project.md` exists with frontmatter.
- **T-AS-8**: `.opencode/commands/build.md` exists with frontmatter.
- **T-AS-9**: `opencode.json` agent.conductor.prompt is a `{file:...}` reference (starts with `{file:`), NOT an inline multi-line string. This guards against accidentally re-inlining the prompt.
- **T-AS-10**: `opencode.json` command.setup-project.template and command.build.template are `{file:...}` references. Same guard.

Constraints: stdlib only (per T2 spec from plan-009). Use `pathlib.Path` to find the markdown files relative to the test file's location.

## T3 Spec (@builder)

Apply T1's design:

1. Read `opencode.json` and extract the 3 inline strings:
   - `agent.conductor.prompt` (the long string starting with `"You are the conductor — the primary orchestrator agent..."`)
   - `command.setup-project.template` (the 200-char string)
   - `command.build.template` (the long string starting with `"Enter BUILD LOOP mode..."`)

2. Create 3 new files with the extracted content + frontmatter:
   - `.opencode/agents/conductor.md`
   - `.opencode/commands/setup-project.md`
   - `.opencode/commands/build.md`

3. Edit `opencode.json` to replace the 3 inline strings with `{file:...}` references. The `{file:...}` syntax is a string starting with `{file:./...}`. Use a path relative to the `opencode.json` location (which is repo root), so paths are `./.opencode/agents/conductor.md` etc.

4. Preserve all other content of `opencode.json` byte-for-byte (whitespace, key order, etc.).

5. Verify the new markdown files render correctly: read them back with UTF-8 encoding and check no `\ufffd` (replacement) characters appear.

6. Verify `opencode.json` is still valid JSON.

## T4 Spec (@reviewer)

Per project discipline, run `python scripts/verify-plan.py .opencode/plans/plan-010-agent-markdown-migration.md` FIRST. Report exit code.

Then verify:
- All 5 new tests (T-AS-6..T-AS-10) pass
- The 3 markdown files are well-formed (frontmatter delimiters, body content matches the original prompt intent)
- The 3 `{file:...}` references in `opencode.json` point to existing files
- `git diff opencode.json` shows ONLY the 3 string-replacement changes (no other fields modified)

## Verification

- [x] #1: `python -c "import json; json.load(open('opencode.json')); print('valid')"`
- [x] #2: `python -c "import os; p='.opencode/agents/conductor.md'; assert os.path.exists(p); c=open(p, encoding='utf-8').read(); assert len(c) >= 1000, f'conductor.md too short: {len(c)} chars'; assert '\ufffd' not in c, 'conductor.md has U+FFFD replacement chars (mojibake)'; print(f'OK: conductor.md is {len(c)} chars, no mojibake')"`
- [x] #3: `python -c "import os; assert os.path.exists('.opencode/commands/setup-project.md') and open('.opencode/commands/setup-project.md', encoding='utf-8').read().startswith('---')"`
- [x] #4: `python -c "import os; assert os.path.exists('.opencode/commands/build.md') and open('.opencode/commands/build.md', encoding='utf-8').read().startswith('---')"`
- [x] #5: `python -c "import json; c=json.load(open('opencode.json')); p=c['agent']['conductor']['prompt']; assert p.startswith('{file:'), f'prompt should be a file ref, got: {p[:60]}'; assert 'conductor.md' in p; print('OK: conductor prompt is a file ref')"`
- [x] #6: `python -c "import json; c=json.load(open('opencode.json')); cmd=c.get('command', {}); bad = [k for k in ('setup-project', 'build') if k in cmd]; assert not bad, f'opencode.json still has command blocks: {bad}. Per the upstream Commands docs, the template field does not support {file:...} so these blocks must be removed entirely (the markdown files in .opencode/commands/ are the sole definition).'; print('OK: command blocks removed from JSON (markdown is sole source)')"`
- [x] #7: `python -c "import os; assert os.path.exists('tests/test_agent_safety.py'); content=open('tests/test_agent_safety.py', encoding='utf-8').read(); assert all(f'T-AS-{n}' in content for n in range(6, 11)), 'tests T-AS-6..T-AS-10 must be present'; assert 350 <= len(content.splitlines()) <= 700, f'test file should be 350-700 lines, got {len(content.splitlines())}'"`
- [x] #8: `python -m pytest tests/test_agent_safety.py -q --tb=no`
- [x] #9: `python -c "import os; assert os.path.exists('.opencode/plans/plan-010-design.md') and 100 <= len(open('.opencode/plans/plan-010-design.md', encoding='utf-8').readlines()) <= 400, f'design doc should be 100-400 lines'"`
- [x] #10: `python -c "import re; t=open('.opencode/plans/plan-010-agent-markdown-migration.md', encoding='utf-8').read(); assert all(s in t for s in ['## Goal', '## Tasks', '## Verification', '## Deliverables']); print('OK: plan has all required sections')"`

## Deliverables

- `.opencode/agents/conductor.md` (new: frontmatter + extracted prompt)
- `.opencode/commands/setup-project.md` (new: frontmatter + extracted command)
- `.opencode/commands/build.md` (new: frontmatter + extracted command)
- `.opencode/plans/plan-010-design.md` (new: architect's design doc, 30-250 lines)
- `opencode.json` (modified: 3 inline strings replaced with `{file:...}` refs)
- `tests/test_agent_safety.py` (extended: +5 tests T-AS-6..T-AS-10)
- archive plan to completed/ subfolder after verification passes

## Out of scope

- **Plan-011** (project-specific SKILL.md files): separate plan
- **Plan-012** (per-agent variants + temperature/top_p/color): separate plan
- **Model name verification** (`opencode/minimax-m3-free`): separate plan or user clarification
- **All 13 agents to markdown** (plan-010 moves only 1 agent + 2 commands; the 12 subagents stay inline for now to keep scope tight)

## Notes

- The upstream markdown agent spec is documented at https://opencode.ai/docs/agents (the "Markdown" section). The upstream markdown command spec is at https://opencode.ai/docs/commands.
- The conductor's prompt is the largest single block in `opencode.json` (5 KB+). Moving it gives the biggest size win.
- After this plan, `opencode.json` shrinks by ~5 KB. The other 12 subagent prompts are 200-500 chars each; moving them all is mechanical but lower-value (do as a follow-up plan if desired).
- The pre-commit hook and verify-plan.py are unaffected by this change (they don't read agent prompts).
- The test runner is unaffected (tests read the JSON, not the markdown).

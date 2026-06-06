---
name: verify-plan-gate
description: Use when `python scripts/verify-plan.py` returns non-zero, or when the LLM is tempted to trust a subagent's "I did it" report. The 3-layer enforcement (conductor prompt step 8, reviewer subagent first action, /build command step 7.5, pre-commit hook) is non-negotiable. Invoke the canonical 5-step recovery: read failure, identify check, fix plan or code, re-run, archive. Avoid for verification of code-only changes that don't touch a plan file — those use `pytest`, not `verify-plan.py`.
---

# Verify-Plan Gate

This skill is the canonical reference for the 5 mechanical checks in `scripts/verify-plan.py` and the 3-layer enforcement that makes them non-skippable. The gate is the project's primary defense against "I built it but didn't actually verify it" failures.

## When to use

- `python scripts/verify-plan.py <plan>` returned non-zero — use the 5-step recovery.
- The LLM is about to write "build approved" to the work-log after a subagent's completion report — use this skill FIRST.
- A new layer of enforcement is being added to the conductor workflow.
- A reviewer subagent has finished its review — use this skill to confirm the verify-plan.py run was step 1 (not step 5).

## Process / Checklist

### The 5 mechanical checks in `scripts/verify-plan.py`

The script is at `scripts/verify-plan.py` (~245 lines, stdlib-only). It runs in 2 phases: 5 mechanical checks on the plan-file structure, then N command checks from the plan's `## Verification` section.

**Phase 1 (mechanical, always runs):**

1. **@-assignment check** — every task line in `## Tasks` must contain a `@agent` mention. Lines without one (e.g., "(assigned: me)") fail.
2. **@-mention position check** — the first `@agent` mention in a task line must have at least 10 characters of context after it. If `@conductor` is at the END of a line, the check fails. Always put `@agent` at the START of task lines.
3. **description length check** — the first 10 characters after every `@agent` mention must form a valid task description (not just whitespace, not a single character). A task like `- [ ] #5: @builder - x` (1 char after `@builder`) fails.
4. **verification coverage check** — `## Verification` must have at least as many `[x]` items as `## Tasks` has layers (Layer 1, Layer 2, ...). A plan with 4 layers and 3 verification items fails.
5. **cross-reference resolution check** — every path-like backtick string (e.g., `scripts/verify-plan.py`, `.opencode/agents/conductor.md`) must exist. Forward-references to future paths (e.g., `.opencode/plans/completed/plan-001.md` when the file isn't archived yet) fail. Bare backticked `verify-plan.py` (without `scripts/` prefix) also fails.

**Phase 2 (per-task verification, runs the commands):**

Each `- [x] #N: \`<runnable command>\`` line in `## Verification` is executed. The command must exit 0. Use the same `python -c "..."` one-liner pattern; the script handles quoting.

### The 5-step recovery when verify-plan.py fails

1. **Read the failure output** — the script prints the failing check name and a one-line explanation. Don't skip this.
2. **Identify which check failed** — the failure message contains the check name and (for Phase 1) a regex/test detail.
3. **Fix the plan file (or the underlying code)** — for Phase 1, the fix is in the plan file (add a `@agent`, move the mention to the start, expand the description, add a verification item, fix the path). For Phase 2, the fix may be in the code the plan was supposed to build.
4. **Re-run `verify-plan.py`** — until exit 0. Don't archive until exit 0.
5. **Archive the plan** — `Move-Item` the plan file (and any design doc) from `.opencode/plans/` to `.opencode/plans/completed/`. Then commit.

### The 3-layer enforcement (and a 4th on commits)

The gate is enforced at 4 levels. Skipping any one of them is a regression.

1. **Conductor prompt step 8** — the conductor's `14-step workflow` step 8 is "VERIFY PLAN (MANDATORY - cannot be skipped)". The prompt text says "DO NOT trust subagent reports" so the LLM knows to re-run.
2. **Reviewer subagent first action** — the `reviewer` agent's prompt has a "MECHANICAL VERIFICATION (MANDATORY — RUN THIS FIRST)" section before the qualitative checklist. The reviewer must run `verify-plan.py` and report the exit code BEFORE scoring the rubric.
3. **`/build` command step 7.5** — between VERIFY and ARCHIVE, the `/build` command has a hard gate: "MECHANICAL VERIFY (HARD GATE — CANNOT SKIP)". The archive step is blocked until the script exits 0.
4. **Pre-commit hook** — `.git/hooks/pre-commit` runs `verify-plan.py` against any staged plan files. A commit that touches an unverified plan is rejected.

The 4 layers are redundant by design. Layer 1 (LLM intent) is the weakest; layer 4 (filesystem hook) is the strongest. The project relies on layers 2-4 to catch the cases where layer 1 is ignored.

## Examples

### Example 1: failure on check 2 (mention position)

Plan had:
```markdown
- [ ] #5: build the agent (assigned: @builder)
```

Failure: `@builder` has only 1 character after it on the same line. Fix: move `@builder` to the start of the line:
```markdown
- [ ] @builder #5: build the agent
```

Source: plan-010 work-log — 4 plan-file bugs caught during the reviewer's L3 pass.

### Example 2: failure on check 5 (cross-reference)

Plan had:
```markdown
- See `.opencode/plans/completed/plan-001.md` for context
```

But `plan-001.md` hadn't been archived yet (it was still in `.opencode/plans/`). Fix: change the reference to `.opencode/plans/plan-001.md` (or move the file to completed/ first).

### Example 3: failure on Phase 2 (per-task command)

Plan had:
```markdown
- [x] #5: `python -c "import json; cfg=json.load(open('opencode.json')); assert 'command' in cfg"`
```

But the project had just moved commands to markdown (plan-010), so `cfg['command']` raises `KeyError`. Fix: change the verification to check the command block is ABSENT:
```python
assert 'command' not in cfg
```

### Example 4: a real caught bug (plan-007)

The first version of `verify-plan.py` had no `@-assignment` check. A subagent wrote a plan with `(assigned: @conductor)` in parens — the check would have caught this. The check was added in plan-007; the test file is `tests/test_verify_plan.py`.

## Plan-file pitfall patterns (Phase 2 commands)

These are recurring patterns that fool the Phase-2 command runner. Each one was caught in a real plan (plan-009, plan-010, plan-011, plan-012, plan-013); the fixes are mechanical.

### Pitfall A: multi-line Python inside `python -c "..."`

`python -c` does NOT support multi-line statements (no `if/for/with` blocks). The shell sees the literal newline and breaks the quoting.

```markdown
- WRONG:
- [x] #3: `python -c "import json; c=json.load(open('opencode.json')); 
    for a in readonly+impl:
        if 'jobs.md' not in c['agent'][a].get('prompt',''):
            missing.append(a)"`

- RIGHT (single-line list comprehension):
- [x] #3: `python -c "import json; c=json.load(open('opencode.json')); missing=[a for a in c['agent'] if 'jobs.md' not in c['agent'][a].get('prompt','')]; assert not missing"`
```

If the logic is too complex for a one-liner, write the script to a temp file and run it with `python <path>` instead of `python -c`.

### Pitfall B: forward-references to future files

Backticked paths are checked for existence at verify time. A reference to a file that WILL be created in L4 (the archive step) fails the check NOW.

```markdown
- WRONG (line 168):
- `.opencode/plans/completed/plan-013-live-progress-tracking.md` (archived)

- RIGHT (use prose, no backticks):
- Archived copies of the plan and design in `.opencode/plans/completed/` (created in L4)
```

The same pattern applies to:
- Future archive files (`.opencode/plans/completed/<plan>-*`)
- Future feature artifacts (`.opencode/jobs-archive.md` from a future plan)
- Any path that doesn't exist at the moment the plan is being verified

### Pitfall C: bare backticked paths without proper prefixes

The cross-reference resolver checks `workdir / <ref>`, so the path must be repo-root-relative AND must include all parent directories.

```markdown
- WRONG (bare, won't resolve):
- runs `verify-plan.py` FIRST              → workdir/verify-plan.py (doesn't exist)
- `todo.md` = high-level                   → workdir/todo.md (doesn't exist)
- `jobs.md` = fine-grained                 → workdir/jobs.md (doesn't exist)

- RIGHT (with proper prefix):
- runs `scripts/verify-plan.py` FIRST      → workdir/scripts/verify-plan.py ✓
- `.opencode/todo.md` = high-level         → workdir/.opencode/todo.md ✓
- `.opencode/jobs.md` = fine-grained       → workdir/.opencode/jobs.md ✓
```

Source: plan-013 L3 verify caught 8 of these in one pass; the fixes are mechanical (add `scripts/` or `.opencode/` prefix, or remove backticks).

### Pitfall D: self-referential `verify-plan.py` invocations

The recursion bug: the plan's own `## Verification` section contains a command that runs `verify-plan.py` against the SAME plan. The script tries to verify its own verifier and recurses infinitely (or hits the 300-second timeout).

```markdown
- WRONG:
- [x] #10: `python scripts/verify-plan.py .opencode/plans/plan-013-live-progress-tracking.md`

- RIGHT (non-recursive structural check):
- [x] #10: `python -c "import re; t=open('.opencode/plans/plan-013-live-progress-tracking.md', encoding='utf-8').read(); assert all(s in t for s in ['## Goal', '## Tasks', '## Verification', '## Deliverables'])"`
```

This was caught in plan-009, plan-010, plan-011, plan-012, and plan-013 — every plan in the current series. The fix is always the same: replace the recursive call with a static check that the plan has all required sections.

## Common pitfalls

- **Pitfall 1: "Subagent said 10/10 tests pass, I'll trust it"** — NO. The 3-layer enforcement exists because the LLM used to trust subagent reports. Re-run the tests yourself.
- **Pitfall 2: "I'll just `git --no-verify` past the pre-commit hook"** — this is acceptable for known hook bugs (e.g., the Windows hang), but the project treats `--no-verify` as a code smell. Use it sparingly and document the reason in the commit message.
- **Pitfall 3: "Verification command exited 1 but the result is correct"** — the script's check is mechanical; if the command fails, the verification has FAILED. Fix the command or the code; do not papering over the check.
- **Pitfall 4: "I forgot to re-run after the fix"** — common. The 5-step recovery is "re-run" → "if exit 0, archive". Don't skip re-run.
- **Pitfall 5: "The plan was approved-with-nits"** — the verify-plan-gate is mechanical; "approved-with-nits" is a qualitative concept. The verify script doesn't accept nits. Reject, fix, re-run.

## Reference: the 3-layer enforcement in 1 table

| Layer | Enforced at | Strength | Failure mode |
|---|---|---|---|
| 1 | Conductor prompt step 8 | LLM intent (weak) | LLM skips the step |
| 2 | Reviewer subagent first action | LLM intent (medium) | Reviewer skips the run |
| 3 | `/build` command step 7.5 | LLM intent (strong) | LLM edits the command to skip |
| 4 | Pre-commit hook | Filesystem (strongest) | `git --no-verify` (acceptable in emergencies only) |

## Reference: the recovery in 5 lines

```text
1. Read failure output
2. Identify check (1-5 in Phase 1, or per-task in Phase 2)
3. Fix plan file (Phase 1) or code (Phase 2)
4. Re-run `python scripts/verify-plan.py <plan>`
5. Archive (`Move-Item` to `.opencode/plans/completed/`) and commit
```

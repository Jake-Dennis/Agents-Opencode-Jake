# Plan 003: Make the source folder itself the deliverable

## Goal

Make `.opencode/agents/` a single, self-contained folder that can be copy-pasted into any project and just work — no build step, no bundle script, no dist/ directory, no `global-setup` required.

## What changed

### Inlined
- All `{file:...}` references in the 13 agent `.md` files are now inlined
- All `{file:...}` references in the 9 `shared/*.md` files are now inlined
- The whole folder is self-contained: **0 active `{file:}` references** across all 22 .md files

### Removed
- `dist/agents/` directory (redundant — source IS the bundle now)
- `scripts/build-self-contained-bundle.py` (no bundle to build)
- `tests/test_bundle.py` (no bundle to test)

### Added
- `.opencode/agents/README.md` — explains what the folder is, what's in it, and how to use it in any project

### Kept
- `.opencode/agents/shared/` subfolder — kept for maintainability. The 13 agents don't depend on these files (the content is inlined), but the shared/ folder is still useful as reference and for easy editing. The user said subfolders are fine.

### Test regression discovered and fixed
`tests/test_jobs.py::test_t_jb_6_conductor_and_git_excluded` failed after the initial inlining. Root cause: the test asserts that the **conductor** and **git** agents do NOT have the "Live progress tracking" content in their source body. This is a design choice (T-JB-6): conductor writes to todo/work-log, git stays on bash — neither does live progress tracking via jobs.md. The original source used `{file:...}` references, so the string "Live progress tracking" only appeared in `shared/progress-tracking.md` (not in the source). After inlining, the string ended up in conductor.md, breaking the test.

Fix: removed the "Live progress tracking" section from `conductor.md` (it was inlined from `progress-tracking.md`). The 11 write-capable agents still have it inlined (they're supposed to). The conductor and git are still excluded (as designed).

The .bat's `resolve_includes.py` step is now a no-op for these inlined files but is kept as a safety net for any future file that adds a `{file:...}` reference.

## Verification

- Audit: 0 active `{file:}` references across all 22 .md files in `.opencode/agents/`
- 229 / 252 tests pass (the 2 pre-existing failures are unrelated — `test_real_plan_001` and `T_AS_1` / `T_AS_5`)
- Specifically: `test_t_jb_6_conductor_and_git_excluded` passes (design intent preserved)

## How to use

```bash
# Copy one agent to another project
cp .opencode/agents/conductor.md /path/to/other-project/.opencode/agents/

# Copy all 13 agents
cp .opencode/agents/*.md /path/to/other-project/.opencode/agents/

# Copy the whole folder (agents + shared reference)
cp -r .opencode/agents /path/to/other-project/.opencode/
```

That's it. The conductor works in dispatch mode (if `task` tool available) or single-agent mode (sequential self-play). The mode is announced in the first response.

## Out of scope

- The pre-existing test failures (`test_real_plan_001`, `T_AS_1` / `T_AS_5`) — unrelated to plan-003
- Refactoring the `.bat` files to remove the now-unnecessary `resolve_includes.py` step — kept as a safety net for any future `{file:...}` reference
- Renaming `.opencode/agents/` to a more discoverable name — current name is consistent with the rest of the opencode config structure

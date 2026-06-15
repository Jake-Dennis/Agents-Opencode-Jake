# Plan 002: Operating mode — agents work in any project

## Goal

Make the agent set **fully portable**. The conductor detects its environment and operates in either **dispatch mode** (when a subagent tool is available) or **single-agent mode** (when it isn't). The user takes the agent bundle to any project, on any machine, in any AI client — the agents work without a `task` tool, without graphify, without the full opencode runtime.

Currently the install ships self-contained agent `.md` files (with `{file:}` includes inlined), but the prompts assume dispatch mode. When the user runs the agents in another project, the conductor tries to dispatch, finds no tool, and either rationalizes a fallback (the "well-scoped and small" problem) or fails to act at all. Both outcomes are bugs.

## Tasks

### Layer 1 — Conductor prompt rewrite (parallel, no deps)
- [ ] #1 - Add **"Detect operating mode"** as the first workflow step in `conductor.md`. The conductor checks its available tools and announces: "Dispatch tool detected" or "No dispatch tool detected, working in single-agent mode."
- [ ] #2 - Add **"Operating mode"** section explaining both modes. Dispatch mode is the default; single-agent mode is the fallback. Each mode describes the workflow, the boundaries, and the failure-mode language.
- [ ] #3 - Add **"Honest self-review"** subsection under single-agent mode. The conductor's self-review has known limits (same model that wrote the code, bias toward "looks good"). Mitigations: re-read the diff, look for usual-miss failure modes, run the tests, ask the user to spot-check large changes.
- [ ] #4 - Update the **Boundaries** section to be mode-aware. The "do not implement directly" / "do not write tests directly" / "do not review your own dispatches" rules are necessary in dispatch mode and necessarily violated in single-agent mode. The honesty rules apply in both modes.

### Layer 2 — Subagent prompts: self-mode note
- [ ] #5 - Add a one-line note to each of the 12 subagent `.md` files (after the line-1 consume-only framing): "If you are the conductor in single-agent mode reading this as a reference, follow the same workflow but execute the work yourself — don't try to dispatch a subagent that doesn't exist."

### Layer 3 — Bundle completeness (depends on Layer 1)
- [ ] #6 - Add `scripts/build-self-contained-bundle.py`: reads `.opencode/agents/*.md`, resolves all `{file:}` includes via the existing `resolve_includes.py`, and writes a `dist/agents/{name}.md` per agent. Each file is fully self-contained — copy one file, the agent works. Generates a `dist/agents/MANIFEST.md` listing which shared files were inlined into which agents.
- [ ] #7 - Wire the bundle script into `build-release.sh` / `build-release.bat` (or as a `Makefile` target) so releases include `dist/agents/`.
- [ ] #8 - Update `INSTALL.md` with a "Use in any project" section: copy `dist/agents/*.md` to the target project's agent directory, done. Works in any opencode build, any AI client, any env. No global-setup required.

### Layer 4 — Regression tests (depends on Layer 1, 3)
- [ ] #9 - Add `test_T_OM_1_*` ... `test_T_OM_5_*` tests in a new `tests/test_operating_mode.py` that verify the conductor.md has the operating-mode detection, both modes documented, honest self-review, and the boundaries are mode-aware.
- [ ] #10 - Add `test_T_BB_1_*` ... `test_T_BB_3_*` tests in a new `tests/test_bundle.py` that verify `build-self-contained-bundle.py` produces self-contained files (no remaining `{file:}` references) and a correct manifest.

## Verification
- [ ] #1 - `python -m pytest tests/test_operating_mode.py tests/test_bundle.py tests/test_graphify_protocol.py -v` all pass
- [ ] #2 - `python scripts/build-self-contained-bundle.py` produces `dist/agents/*.md` with no `{file:}` references
- [ ] #3 - Manual: copy `dist/agents/conductor.md` to a fresh directory, read it — it should be fully readable with no broken references
- [ ] #4 - `grep -r "do not implement code directly" .opencode/agents/conductor.md` confirms the boundary language is mode-aware
- [ ] #5 - `work-log.md` and `context.md` updated

## Out of scope
- Replacing `{file:}` include mechanism itself (it's working, the bundle is the answer for portability)
- Adding new agents or changing agent specialization
- Changing the dispatch mechanism in opencode itself
- Adding a fallback for missing graphify (operating mode handles it: skip graphify queries, work from text)

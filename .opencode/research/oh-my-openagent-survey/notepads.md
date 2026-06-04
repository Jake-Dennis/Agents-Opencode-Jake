# Notepads System in oh-my-openagent — Light Survey

Branch surveyed: `dev` (snapshot 2026-06-05). Sources: orchestration guide, README, AGENTS.md, CHANGELOG, issues #631, #1150, #1170, #1309, #1364, #1397, #2853, #2999, #3996, #4382, and commit `f313eb1`. Path is **webfetch-only**; no code was cloned.

---

## 1. Location

**Project root only.** Notepads live under the working directory, not the user home. The path has been **renamed mid-refactor**:

| Era | Path | Source |
|---|---|---|
| Docs (still shown) | `.sisyphus/notepads/{plan-name}/` | `docs/guide/orchestration.md` (Wisdom Accumulation section) |
| Recent code (May 2026) | `.omo/notepads/{plan-name}/` | CHANGELOG `f313eb1`: *"Notepad-write-guard wired and extended to `.omo/notepads`"* |

The repo `.gitignore` (`dev/.gitignore`) confirms both roots exist and both are gitignored (with rules/ exempted):

```
.omo/*
!.omo/rules/
!.omo/rules/**
.sisyphus/*
!.sisyphus/rules/
!.sisyphus/rules/**
```

> **Plan-name key.** The directory is keyed by the Prometheus plan name (e.g. `.sisyphus/notepads/lottery-go-to-ts-refactor/` — see issue #1150 and commit `44f057d`). One folder per plan; concurrent plans get their own subfolder.

---

## 2. The 5 Files (purpose)

Direct quote from `docs/guide/orchestration.md` → *Wisdom Accumulation* → *Notepad System*:

```
.sisyphus/notepads/{plan-name}/
├── learnings.md      # Patterns, conventions, successful approaches
├── decisions.md      # Architectural choices and rationales
├── issues.md         # Problems, blockers, gotchas encountered
├── verification.md   # Test results, validation outcomes
└── problems.md       # Unresolved issues, technical debt
```

| File | Purpose (from docs + observed use) |
|---|---|
| `learnings.md` | Distilled, reusable knowledge: patterns found, conventions, working approaches, reusable commands. **The file most other workers read.** |
| `decisions.md` | Architectural choices made during execution, with rationale and call-sites touched. |
| `issues.md` | Mid-flight blockers / gotchas encountered. The maintainer describes this as *"friction Atlas logs during execution"* (#1364). |
| `verification.md` | Concrete test results, build output, validation outcomes (e.g. `bun test` counts, lsp_diagnostics state). |
| `problems.md` | Items that were **not** resolved — left as technical debt or unknowns for follow-up. |

A real-world example dump from commit `44f057d` shows the timestamped, freeform format agents actually write:

```markdown
## [2026-05-20T15:04:52Z] Task 1 baseline
- Total tests: 7315
- Pass: 7312, Fail: 2, Skip: 1
- Build exit code: 0 (dist/ size: 13M, 1456 files)
- Anomalies observed: 2 pre-existing test failures in
  `src/features/opencode-skill-loader/skill-content.test.ts` …
```

The format is **not strictly schema-enforced**; agents write `[ISO-timestamp] Title` followed by bullets.

---

## 3. Who Writes

**Sisyphus-Junior** (the workhorse executor) is the primary writer. The default subagent prompt template injected via `delegate_task` (visible in issue #1150) tells it explicitly:

> **Notepad Location (for recording learnings)**
> NOTEPAD PATH: `.sisyphus/notepads/{plan-name}/`
>
> - `learnings.md`: Record patterns, conventions, successful approaches
> - `issues.md`: Record problems, blockers, gotchas encountered
> - `decisions.md`: Record architectural choices and rationales
> - `problems.md`: Record unresolved issues, technical debt
>
> You SHOULD append findings to notepad files after completing work.
> **IMPORTANT: Always APPEND to notepad files — never overwrite or use Edit tool.**

Best-effort map of which agent writes which file:

| Writer | When | Files touched |
|---|---|---|
| **Sisyphus-Junior** (via `task(category=...)`) | After completing each delegated subtask | All 5; especially `learnings.md`, `issues.md`, `decisions.md` |
| **Atlas** (orchestrator) | When it logs friction, workarounds, blockers (per issue #1364) | Mainly `issues.md`, `problems.md`, `verification.md` |
| **Prometheus** | No — Prometheus is `READ-ONLY`; it can only `create` markdown in `.omo/`, but the docs list it as a planning-time writer, not a notepad writer | n/a |

Note that the write is **prompt-instructed, not programmatically enforced**. The system does not auto-write; it relies on the subagent deciding to append. (See §6 — gaps.)

---

## 4. Who Reads

The orchestration guide states the *intent* clearly:

> **Wisdom Accumulation** — after each task:
> 1. Extract learnings from subagent's response
> 2. Categorize into: Conventions, Successes, Failures, Gotchas, Commands
> 3. **Pass forward to ALL subsequent subagents**
> (`docs/guide/orchestration.md` → *Wisdom Accumulation*)

| Reader | When |
|---|---|
| **Atlas (orchestrator)** | Between every delegated task — extracts a digest from the previous subagent's response and injects it into the next delegation prompt. |
| **Sisyphus-Junior (subagent)** | At task start, via the `<Work_Context>` block (`NOTEPAD PATH: .sisyphus/notepads/{plan-name}/`) — told to READ `learnings.md` before working, then APPEND at the end. |
| **Other subagents** (Oracle, Librarian, Explore) | Best-effort: only if explicitly given the notepad path in their delegation prompt. Most read-only workers do not touch notepads. |
| **External scripts / humans** | Manual review only. Discussion #2999: *"Are they meant to be persisted/committed for future work, unrelated to the original plan, or can I drop them?"* — maintainer has not answered, but the design is **plan-scoped and ephemeral** (see §5). |

There is **no automatic "feed me everything in `learnings.md`" hook** that injects the file into every session. The system reminder in the orchestrator prompt is what does the propagation.

---

## 5. Eviction, Size Limits, Lifetime

**No documented size limit, no rotation, no truncation.** Agents are told to **append-only**:

- Issue #1150 prompt: *"Always APPEND to notepad files — never overwrite or use Edit tool."*
- PR #4382 introduces a *separate* "durable notepad" in the ultrawork mode backed by `mktemp -t ulw-*.md` — but that is the in-session scratchpad, not the `.sisyphus/notepads/` system.

**Lifetime:**

| Scope | Behaviour |
|---|---|
| Within one plan | Persists for the lifetime of the plan execution. Survives `/start-work` resume via `boulder.json` (boulder re-opens the same plan folder). |
| Across worktrees | Not git-tracked; explicitly synced from worktree → main repo by `syncSisyphusStateFromWorktree()` (commit `19ab3b5`) before `git worktree remove`. |
| Across plans | **Isolated by `plan-name`.** A new plan gets a fresh subfolder; nothing is merged between plans. |
| Cross-session (user home) | **No.** `.sisyphus/` and `.omo/` are both project-local. There is no global notepad. |
| Long-term | Discussion #2999 explicitly says the directory is **safe to drop / not commit**. Maintainer's RFE #1397 proposes lifting valuable entries into `AGENTS.md` / `CLAUDE.md` via a PR, but **this is not yet implemented**. Until then, learnings are *transient within one plan* and *invisible to future plans*. |

The CHANGELOG line *"Notepad-write-guard wired and extended to `.omo/notepads`, preventing accidental overwrites in the new workspace layout"* confirms a hook exists that *guards* against overwrite — but it is a safety guard, not a size limit.

---

## 6. Honest Gaps

1. **No source file is publicly browsable** at the obvious path. `/src/features/notepads/index.ts` returns 404. The "notepad system" is mostly *prompt text + gitignore entries + a write-guard hook*, not a dedicated module in `src/features/` (the `src/features/` directory was inspected and contains 17+ feature modules — none named `notepads`).
2. **The path is mid-rename.** Docs say `.sisyphus/notepads/`, recent code says `.omo/notepads/`. Users running on `dev` will see both depending on which feature they hit. Plan names from older sessions are keyed under the old path.
3. **Propagation is prompt-driven, not data-driven.** The "extract → pass forward" loop runs only because Atlas' prompt tells it to. A weak/fast model for Atlas (e.g. `gpt-5.4-mini-fast`) may skip the synthesis step and the next subagent starts blind. (Issue #2897 documents this class of failure for parallel delegation in general.)
4. **The glob tool was broken for hidden dirs** in early 2026 (issue #631). Agents literally could not find their own notepads until PR #720 (`fix(glob): default hidden=true and follow=true`). On older versions the system is silently non-functional.
5. **No size / line / byte cap** is documented. A multi-day plan that loops the boulder-continuation hook will keep appending to all 5 files forever. A 116-line `learnings.md` in commit `44f057d` is evidence the files can grow into the hundreds of lines.
6. **No automated promotion to AGENTS.md.** RFE #1397 (RFC), issue #1364 (Session Debrief) and PR #4382 (durable notepad) all gesture at closing the loop, but as of the surveyed snapshot, **notepad content is dead-end data** unless a human reads it.
7. **Gitignored by design.** Users who commit their repo will *not* see the notepad diff. The dev branch's own `.gitignore` ignores it. Issue #2853 calls this out as a design choice: *"`.sisyphus/boulder.json` contains session IDs, active plan pointers, and runtime state that is inherently local… Committing it would create merge conflicts on every branch switch and pollute git history with ephemeral state."*

---

## 7. Sources (path → line/identifier)

- `docs/guide/orchestration.md` — *Wisdom Accumulation* section; "Notepad System" code block; agent inventory.
- `dev/.gitignore` — lines 2-6: `.omo/*` and `.sisyphus/*` ignore rules with `rules/` exception.
- `CHANGELOG.md` (commit `f313eb1`) — "Notepad-write-guard wired and extended to `.omo/notepads`".
- Issue #631 — glob tool excluding hidden directories; cites `src/agents/orchestrator-sisyphus.ts:975` and `:1329` as the notepad-read sites.
- Issue #1150 — full default subagent prompt showing the `Notepad Location` block and append-only rule.
- Issue #1309 — `<Work_Context>` block: `NOTEPAD PATH: .sisyphus/notepads/{plan-name}/`, `PLAN PATH: .sisyphus/plans/{plan-name}.md (READ ONLY)`.
- Issue #1364 — *"Since Atlas already logs execution friction and pain points into `.sisyphus/notepads`"*; motivates Session Debrief feature.
- Issue #1397 (RFE) — the "Automated Learning Capture System" RFC; the gap diagram: `Session Work → .sisyphus/notepads/ → [DEAD END]`.
- Issue #2853 — confirms `.sisyphus/` is gitignored by design; worktree-sync fix at commit `19ab3b5`.
- Discussion #2999 — user question: "are they meant to be persisted/committed for future work, unrelated to the original plan, or can I drop them?" — unanswered as of survey date.
- Commit `44f057d` — real-world `learnings.md` (116 lines) and `decisions.md` (19 lines) for the `package-layering-refactor` plan.
- PR #4382 — introduces a **separate** ultrawork "durable notepad" via `mktemp`; not the same as `.sisyphus/notepads/`.

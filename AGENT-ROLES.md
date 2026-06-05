# Agent Roles & Boundaries

> Canonical reference for the 13 agents in this project: which
> lifecycle phase each one owns, what it is allowed to do, and what
> is reserved for the conductor. See `.opencode/decisions/adr-004-agent-roles.md`
> for the rationale and the design alternatives.

## Lifecycle phases

The 13 agents are organized into eight lifecycle phases. Each
agent belongs to exactly one phase; the conductor dispatches by
phase and by task.

- **Orchestration** — `conductor` (the workflow owner)
- **Planning** — `planner`, `architect`
- **Implementation** — `builder`, `refactor`
- **Review** — `reviewer`, `tester`
- **Documentation** — `docs`
- **Operations** — `debugger`, `git`
- **Read-only search** — `explorer`
- **Specialized** — `security`, `perf`

## Agent roster

| Agent | Mode | Phase | Role | Can | Cannot | Owned by |
|-------|------|-------|------|-----|--------|----------|
| `conductor` | primary | Orchestration | Orchestrator. Routes every request through the 15-step workflow, dispatches subagents, maintains `todo.md`, `work-log.md`, plans, and ADRs, and is the only agent that commits, pushes, and archives plans. | Read and write the project; run the full default bash allow-list; dispatch any subagent via `@mention`; create, edit, and archive plans in `.opencode/plans/`; modify `opencode.json` and the installer manifest; run `global-setup.bat` and `setup.bat`. | Delegate the conductor-only actions (commit, push, archive, manifest edits, `opencode.json` edits, installer runs) to a subagent — those are reserved for the conductor. | Conductor |
| `planner` | primary | Planning | Read-only planner. Produces numbered, layered implementation plans; never edits files. | Read the project; query the graphify knowledge graph; output plan files in the conductor's plan format (the conductor saves them). | Edit any file (no `edit` permission); run bash (no `bash` permission); dispatch subagents. | Conductor |
| `architect` | subagent (`all`) | Planning | Read-only system designer. Produces data models, API contracts, component boundaries, and design rationale. | Read the project; query the graphify knowledge graph; output a design document in the format defined in its prompt. | Edit any file (no `edit` permission); run bash (no `bash` permission). | Conductor |
| `builder` | subagent (`all`) | Implementation | Code implementation. Writes new code and modifies existing code per the conductor's delegation. | Edit files; run bash; run the project's test suite to verify changes; add new dependencies only when the conductor has approved. | Modify `opencode.json`; archive plans; commit or push; run the installer scripts; change public APIs without asking. | Conductor |
| `refactor` | subagent (`all`) | Implementation | Code cleanup. Improves structure, removes duplication, renames for clarity — without changing behavior. | Edit files; ask before running bash (e.g. test suite); run tests to confirm behavior is preserved. | Change public APIs without asking; optimize prematurely; refactor and feature-change in the same change. | Conductor |
| `reviewer` | subagent (`all`) | Review | Strict code reviewer. Runs `verify-plan.py` first, then checks correctness, security, error handling, edge cases, type safety, performance, style, and testing. | Read the project; run `python scripts/verify-plan.py <plan-file>`; query graphify; output a structured review in the format defined in its prompt. | Edit any file (no `edit` permission); approve a plan when `verify-plan.py` exits non-zero. | Conductor |
| `tester` | subagent (`all`) | Review | Test writing. Writes unit, integration, and E2E tests; creates fixtures and mocks. | Edit files; run bash; run the project's test framework; mirror the source tree in the test tree (e.g. `src/foo.ts` → `tests/foo.test.ts`). | Modify production source files (use `@builder` for that); commit or push; archive plans. | Conductor |
| `docs` | subagent (`all`) | Documentation | Documentation specialist. Writes READMEs, API docs, inline comments, changelogs, and setup guides. | Edit files; follow the project's existing doc style; document *why* (rationale) in addition to *what*. | Modify production code (use `@builder` for that); commit or push; archive plans. | Conductor |
| `debugger` | subagent (`all`) | Operations | Bug diagnosis and fixing. Reproduces, isolates, fixes the root cause, and adds a regression test. | Edit files; run bash; read logs and stack traces; query graphify to trace related code paths. | Refactor unrelated code while debugging; commit or push; archive plans. | Conductor |
| `git` | subagent (`all`) | Operations | Git operations. Branches, commits, merges, rebases, and PRs with conventional-commit messages. | Run only `git *` bash commands (every other bash command is denied by its `permission` block); create and switch branches; resolve merge conflicts; view history and diffs. | Edit source files (no `edit` permission); run non-git bash; force-push unless explicitly asked; amend commits the conductor did not approve. | Conductor |
| `explorer` | subagent (`all`) | Read-only search | Fast codebase search. Glob, grep, file discovery, and code navigation. | Read the project; run bash; query the graphify knowledge graph for relationships; report findings with file paths and line numbers. | Edit any file (no `edit` permission). | Conductor |
| `security` | subagent (`all`) | Specialized | Security auditor. Scans for OWASP Top-10 issues, auth flaws, injection risks, vulnerable dependencies, and SSRF. | Read the project; ask before running bash (e.g. to query a CVE database or run a scanner); report findings in a severity-rated format. | Edit any file (no `edit` permission); auto-fix issues (the auditor reports; the conductor dispatches `@builder` to fix). | Conductor |
| `perf` | subagent (`all`) | Specialized | Performance optimization. Profiles, identifies bottlenecks, and applies minimal fixes with before/after measurements. | Edit files; run bash; read the project; profile with the project's available tools. | Sacrifice readability for performance without documenting the tradeoff; optimize without measuring first. | Conductor |

## Cross-cutting boundaries

**The conductor owns:** archiving plans (moving them to
`.opencode/plans/completed/`), committing, pushing, modifying
`opencode.json`, modifying the installer manifest
(`.opencode-jake-installed.json`), and running the installer
scripts (`global-setup.bat`, `setup.bat`, `uninstall-global.bat`).
These actions are reserved for the conductor because they are
irreversible from a subagent's perspective — once `@builder`
commits, `@git` cannot un-commit without a force-push, which the
conductor's prompt forbids.

**No subagent should:** commit, push, modify the manifest,
modify `opencode.json`, archive plans, or run the installer
scripts. Subagents have the `permission` blocks to make most of
these impossible (e.g. `@builder` has no manifest write path,
`@git` has `bash: { git *: allow, *: deny }`); the prose
boundaries in this doc are the second line of defense for cases
the `permission` block does not cover (e.g. `@builder` is
allowed to run bash but should still not archive its own plan).

**Any agent can:** read the project, query the graphify
knowledge graph, and dispatch other subagents via `@mention`
(the conductor dispatches the most, but a subagent can
`@mention` another subagent when its task is split into
parallel pieces — e.g. `@tester` can `@mention` `@explorer` to
find the right test file before writing).

**The `permission` block in `opencode.json` is the enforced
boundary.** This table is the human-readable comment for those
`permission` blocks. If the two disagree, the JSON wins (the
opencode CLI is the enforcer) and this table is a bug — file a
PR to bring them back in sync.

## How to extend

**Adding a new agent:**

1. Register the agent in `opencode.json` under the `agent` key.
   Include a `description`, a `mode` (`primary`, `all`, or
   `subagent`), a `permission` block, and a `prompt`.
2. Add a row to the table in this file. Include: the agent's
   name, mode, lifecycle phase, one-sentence role, the actions
   it can take (2–4 bullets), the actions it cannot take
   (1–3 bullets), and the lifecycle phase that owns it (almost
   always `Conductor`).
3. Run `python scripts/verify-plan.py` (or the pre-commit
   hook) to confirm the rest of the project still parses and
   that the opencode CLI still accepts the updated config.

**Changing a role boundary** (e.g. granting `@security` the
ability to apply a one-line config fix):

1. Update the `permission` block in `opencode.json` for the
   affected agent.
2. Update the agent's row in this table — both the `Can` and
   the `Cannot` columns, since they describe the same boundary
   in two surfaces.
3. Run `python scripts/verify-plan.py` to confirm the
   permission change is consistent with the rest of the config.

**Adding a new lifecycle phase** (e.g. introducing a
"Compliance" phase):

1. Update the lifecycle-phases list at the top of this file.
2. Add the agent's row to the table with the new phase.
3. Update the conductor's prompt (step 3, "Plan — Break into
   Dependency Layers") to mention the new phase so dispatch
   stays consistent.

## See also

- `AGENTS.md` — project onboarding and the conductor's
  15-step workflow.
- `opencode.json` — the 13-agent registry, the **enforced**
  source of truth for `permission` blocks.
- `.opencode/decisions/adr-004-agent-roles.md` — the rationale
  for this document and the alternatives that were considered.

# ADR-002: Global installer uses JSONC merge, not folder symlinks

- **Status:** Accepted (with the plan-003 extension to merge
  `command`/`mcp`/`provider`/`permission`/`enabled_providers`/`$schema`
  as well; see "Updated per-key policy" below and
  `.opencode/plans/plan-003-full-global-install.md` for the full design.)
- **Date:** 2026-06-04
- **Deciders:** Jake Dennis (conductor session), @builder (implementation)
- **Supersedes:** the "merge all agents into `~/.config/opencode/agents/`" strategy
  in `global-setup.bat` (pre-refactor)

## Context and Problem Statement

Pre-refactor, `global-setup.bat` produced a *plausible-looking* install that
failed in three concrete ways:

1. **Empty-source junction.** The repo's agent definitions live in
   `opencode.json` (per ADR-001, which consolidated away from
   `.opencode/agents/*.md`). The old installer ran
   `mklink /J %AGENTS_DIR%\Agents-Opencode-Jake %REPO_DIR%\.opencode\agents`,
   but `.opencode\agents\` is intentionally empty. The junction succeeded
   and pointed at nothing — the global config could not find a single agent.

2. **Missing skill junction.** The repo ships
   `.opencode\skills\graphify-agent-workflow\SKILL.md` so the `graphify` skill
   is available in any opencode project that includes our `AGENTS.md`. The
   old installer only ran the skill junction if the user had run the script
   on a *different* machine layout; on a fresh box the skill dir never
   existed in `%USERPROFILE%\.config\opencode\skills\`.

3. **No-op NOTE for an existing jsonc.** When the global `opencode.jsonc`
   already existed (the common case), the old installer skipped writing it
   and printed a `NOTE` block telling the user to add `skills.paths` and
   `instructions` by hand. Many users read "no error" as "done" and never
   edited the file, so the install did not take effect.

The three failure modes share a root cause: the installer was trying to
express the install as *filesystem operations* (junctions, file copies) when
the source of truth is the JSON config in the repo. Symlinks and copy-and-
paste fragments are not how opencode discovers agents — it reads
`opencode.json[ c ]`. We need to merge into the global config, not
decorate the filesystem.

## Decision Outcome

The global installer is split into two cooperating pieces:

* **`global-setup.bat` / `uninstall-global.bat`** (at the repo root) —
  orchestrate the workflow. They parse flags (`--unattended`, `--dry-run`,
  `--force` and their `GLOBAL_SETUP_*` env-var equivalents), resolve
  Python, create / remove junctions for the skill dir, and invoke the
  helper. The `.bat` is thin: it does not parse JSON, it does not edit
  `opencode.jsonc`, and it does not try to remember what it merged.

* **`.opencode/scripts/opencode_jsonc_merge.py`** (committed, stdlib-only,
  Python 3.10+) — does the actual merge. Exposes two modes:

  - `install --project <opencode.json> --global <opencode.jsonc>
     --manifest <path> [--force] [--dry-run]`
  - `remove --global <opencode.jsonc> --manifest <path> [--dry-run]`

  The helper is JSONC-tolerant (strips `/* */` block comments, `//` line
  comments, and trailing commas, with a context-aware state machine so
  `//` inside string literals like `"https://..."` is preserved). Writes
  are atomic (`<path>.tmp` + `os.replace`), JSON is `indent=2,
  ensure_ascii=False, sort_keys=True`, and a leading `// opencode-jake:
  installed <ts> from <project>` header marks the file as ours so a human
  opening the jsonc can see at a glance who touched it.

### Per-key merge policy

The helper applies this policy deterministically (table is the contract;
no inference, no surprises). Plan-003 (2026-06-04) extended the original
table to merge *all* the project's top-level keys, not just
`agent`/`skills`/`instructions`/scalars — the goal being "install
everything the project ships" so a `global-setup.bat` run makes the
project family fully available globally.

| Key | Install strategy | Uninstall strategy | Manifest tracking |
|---|---|---|---|
| `default_agent`, `model`, `small_model` | overwrite (project is authoritative) | DO NOT restore | `scalar_changes` |
| `$schema` | overwrite (project's schema URL) | DO NOT restore | none — single URL pointer |
| `skills.paths` | union + dedupe, case-insensitive | drop only entries we added | `skills_paths` |
| `instructions` | union + dedupe + auto-add repo `AGENTS.md` | drop only entries we added | `instructions` |
| `agent.<name>` | deep-merge; warn + skip on collision; `--force` to overwrite | delete only names we added | `agent_names` + `collisions` |
| `command.<name>` | deep-merge into `command`; project wins on per-name conflict | delete only names we added | `command_names: [string]` |
| `mcp.<name>` | deep-merge into `mcp`; project wins on per-name conflict | delete only names we added | `mcp_names: [string]` |
| `provider` | recursive deep-merge (top-level) | restore from snapshot | `provider_snapshot: object \| null` |
| `permission` | recursive deep-merge (top-level) | restore from snapshot | `permission_snapshot: object \| null` |
| `enabled_providers` | list union + dedupe | filter out items we added | `enabled_providers_added: [string]` |

**Why snapshot+restore for `provider` / `permission` but not the
scalars?** The scalars are single values; if a different project
overwrites them between installs, we cannot safely revert. The dicts
are bigger and a partial overwrite is more likely to leave the global
config in a broken state. Snapshotting the pre-install value lets us
return the global config to its exact pre-install state on uninstall.
Snapshots are deep-copied at install time, so a user's later manual
edits to those keys will not contaminate the snapshot (the snapshot is
taken *before* the deep-merge writes to `global_cfg`).

**FIRST-wins for snapshots on re-runs.** If `global-setup.bat` is run
twice, the second run's snapshot of `provider` would capture the
post-first-install value (which is the deep-merge result). We want the
*pre-FIRST-install* value as the snapshot, so on a later uninstall we
restore the user's original config. The manifest-merge logic for
re-runs therefore keeps the first run's snapshot and ignores
subsequent snapshots for the same key.

**No collision warnings for `command`/`mcp`/`provider`/`permission`.**
Unlike `agent.<name>`, these are not "registered subagents" — they
are project-family configuration. The project is authoritative for
project-family values. If the user has customized `command.setup-project`,
the project's value overwrites it silently on install (project wins
on deep-merge conflict). The user can `uninstall-global.bat` to revert,
or edit the global jsonc by hand to keep their custom version.

Two implicit additions to the union+dedupe lists make the install actually
*work*:

* `skills.paths` always gains the global skills dir
  (`<parent of opencode.jsonc>/skills`) so the installer's skill junction
  is reachable from the config.
* `instructions` always gains the absolute path to
  `<parent of opencode.json>/AGENTS.md` so the project's main `AGENTS.md`
  is loaded by opencode when this global config is active.

### Manifest for surgical uninstall

A successful install writes a manifest at
`%USERPROFILE%\.config\opencode\.opencode-jake-installed.json`:

```json
{
  "version": 2,
  "installed_at": "<iso-8601 utc>",
  "repo_dir": "<abs path to repo root>",
  "links": {
    "agent_junction": "<abs path to junction>",
    "skill_junction": "<abs path to junction>"
  },
  "added": {
    "agent_names":      ["conductor", "planner", ...],
    "collisions":       ["user_custom"],
    "instructions":     ["C:\\...\\AGENTS.md"],
    "skills_paths":     ["C:\\...\\.config\\opencode\\skills"],
    "scalar_changes":   {
      "default_agent": {"old": null, "new": "conductor"},
      "model":         {"old": null, "new": "opencode/minimax-m3-free"}
    },
    "command_names":          ["setup-project", "build"],
    "mcp_names":              ["graphify"],
    "enabled_providers_added": ["opencode"],
    "provider_snapshot":      { ... pre-install global_cfg["provider"] ... } | null,
    "permission_snapshot":    { ... pre-install global_cfg["permission"] ... } | null
  }
}
```

A `version: 1` manifest (pre-plan-003) is still loadable; the
plan-003 fields default to empty / null on read, and uninstall
silently no-ops on the missing fields.

Uninstall loads the manifest, removes exactly the agents we added (the
`collisions` list is left alone — those agents were never ours), and
removes the exact `skills.paths` and `instructions` entries we
contributed. It then unlinks the manifest.

**Scalars are NOT touched on remove.** The project is authoritative for
`default_agent`/`model`/`small_model` at install time, but another
project may have written its own scalar values into the global config
since install, and we cannot safely restore the user's previous value
because the `old` field in the manifest may already be stale. The user
can edit those three scalars by hand if they want to undo the overwrite.
The `added.scalar_changes` field in the manifest is kept for human
reference only. See `cmd_remove` in
`.opencode/scripts/opencode_jsonc_merge.py` for the full rationale, and
`test_remove_preserves_scalars` for the explicit assertion.

*The user's `opencode.jsonc` is never deleted* — the "Remove the entire
file" option from the old uninstaller is gone for good.

### Idempotency and rollback

* Re-running `global-setup.bat` is safe: scalars overwrite to the same
  value, `dedupe_union` keeps `skills.paths` and `instructions`
  duplicate-free, and pre-existing `agent.<name>` entries fall into the
  `collisions` list (warn + skip) unless `--force` is supplied.
* `uninstall-global.bat` is safe even if the manifest is missing: it
  falls back to junction removal only and prints a clear `[INFO]` so the
  user knows nothing was merged.
* Each junction removal checks `fsutil reparsepoint query` to confirm
  the target matches the install's recorded `repo_dir`. Junctions that
  point elsewhere are left alone (`--force` overrides).

## Consequences

### Positive

* The installer actually installs. After `global-setup.bat --unattended`,
  the global `opencode.jsonc` has all 13 agents, `default_agent`,
  `model`, `small_model`, `skills.paths`, and `instructions` pointing at
  the repo's `AGENTS.md`. `opencode agent list` exits 0.
* Idempotent. Re-running is a no-op for the data we already wrote, and
  warns (does not silently overwrite) on agents the user has added in
  the meantime.
* Safe uninstall. The manifest guarantees we only remove what we added.
  The user's other global customizations survive an `uninstall-global.bat`.
* Testable. The merge logic is a pure-Python module that the test suite
  can exercise in a `tmp_path` fixture with no real user config touched.
* Reversible. Reverting the ADR means reverting the commit, deleting the
  helper and the two `.bat` files, and restoring the previous
  `global-setup.bat` / `uninstall-global.bat` from git. The
  `.opencode-jake-installed.json` manifest is the only artifact on the
  user's machine; deleting it leaves the system in its pre-install
  state modulo the now-orphaned junctions, which the uninstall
  cleans up.

### Negative

* Python dependency. The helper requires `python` (3.10+) on `PATH`. We
  document this in the install banner and fall back gracefully (the
  `.bat` prints `[ERROR] Python not found...` and exits 5) so a missing
  Python is loud, not silent.
* More moving parts. The .bat is ~190 lines plus a ~700-line Python
  helper. The `.bat` is no longer self-contained; both must be kept in
  sync in the repo.
* Path normalization footgun. On Windows we fold separators to
  backslashes for display and use `os.path.normcase(os.path.normpath(...))`
  as the dedupe key, so a user who wrote `.opencode/skills` in their
  jsonc and the helper wrote `.opencode\skills` will not see duplicate
  entries after a second install.
* Edge case in JSONC tolerance. The state machine honors backslash
  escapes inside strings, so `"a\\\"b"` stays one token. Single-quoted
  strings are not legal JSON / JSONC and are not handled. None of the
  opencode-cli or our jsoncs use them.
* **Scalar changes are not reversible.** The manifest records the
  change in `added.scalar_changes` for human reference, but the
  uninstaller cannot apply it back without risking a clobber of another
  project's contribution. The user has to edit
  `default_agent`/`model`/`small_model` by hand if they want to undo the
  install-time overwrite.
* **Manifest grew slightly with plan-003.** Adding the snapshot fields
  for `provider` and `permission` makes the manifest a few hundred bytes
  larger per install. Acceptable trade-off for the safety net on
  uninstall.

### Reversibility

* The Python helper is committed, so a `git revert` removes the merge
  logic entirely. The two `.bat` files are also revertible individually.
* A user-installed manifest can be deleted manually; the next install
  re-creates it. If the user deletes the manifest and then runs
  `uninstall-global.bat`, the script falls back to junction removal
  only (the `opencode.jsonc` is left untouched, which is the
  conservative choice — the user can clean up the merged keys by hand
  or via `opencode`).

## Alternatives Considered

1. **Per-agent `.md` files (re-introducing them).**
   Rejected: contradicts ADR-001, which already chose JSON-only to
   eliminate the "two sources of truth" merge bug. Walking that back
   would also re-introduce the `command.template` vs `command.prompt`
   schema mismatch we already paid the price to fix.

2. **Symlink the whole `opencode.json` into the global config dir.**
   Rejected: opencode does not follow symlinks for the config path; it
   reads `<config dir>/opencode.jsonc` literally. We confirmed this
   during the static review. The right move is to merge JSON, not file
   the JSON from a symlinked path.

3. **Just print a `NOTE` (the pre-refactor status quo).**
   Rejected: this is the bug we are fixing. The old behavior masked a
   no-op install behind a success message, which is worse than an
   error.

4. **Use `jq` for the merge.**
   Rejected: `jq` is not installed by default on Windows. Requiring it
   would make the install more brittle than the Python dependency it
   replaces. Python is also already a hard dependency of the local
   `setup.bat`.

5. **Use `pyjson5` or a JSON5 parser library.**
   Rejected: adds a pip dependency. The JSONC subset we need (line
   comments, block comments, trailing commas) is small enough to
   handle with a ~30-line state machine in stdlib.

## Pros and Cons of the Options (re-listed for the record)

### Chosen: split .bat + Python helper with manifest

* Good: actually installs; idempotent; safe uninstall; testable.
* Good: Python is already a hard dependency elsewhere in the project.
* Bad: Python dependency at install time (already required for
  `setup.bat` and the conductor workflow, so not a new constraint).
* Bad: more files to keep in sync.

### Alternative: shell out to `jq` in the .bat

* Good: no new dependencies for users who already have `jq`.
* Bad: not on every Windows machine; Windows installer would have to
  pull `jq` from somewhere.
* Bad: harder to test (would need a `jq` shim in CI).
* Bad: `.bat` is doing string manipulation on JSON, which is the same
  class of bug we are trying to leave behind.

### Alternative: ship a per-user `opencode.json` template and have
opencode read it via a project-relative `OPENCODE_CONFIG` env var.

* Good: zero installer surface — users set one env var.
* Bad: opencode does not honor `OPENCODE_CONFIG` for the *global*
  config (only project-level overrides). The whole point of
  `global-setup.bat` is to install globally; this would not work.
* Bad: requires every user on the machine to set the env var
  separately.

## References

* `opencode.json` — the 13-agent source of truth that gets merged.
* `.opencode/scripts/opencode_jsonc_merge.py` — the helper, committed.
* `global-setup.bat`, `uninstall-global.bat` — the thin orchestrators.
* `.opencode/plans/plan-002-fix-global-setup.md` — the plan that
  diagnosed the three failure modes and proposed the split.
* `.opencode/plans/plan-003-full-global-install.md` — the plan that
  extended the merge helper to install `command`/`mcp`/`provider`/
  `permission`/`enabled_providers`/`$schema` and added snapshot-restore
  for `provider` and `permission`.
* `.opencode/decisions/adr-001-json-only-agents.md` — the prior
  decision that this ADR builds on (single source of truth in
  `opencode.json`).
* `tests/test_global_setup.py` (owned by @tester) — unit tests for
  the helper, all using `tmp_path`, no real user config touched.

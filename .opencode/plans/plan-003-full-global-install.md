# Plan 003: Make global install mirror the full project config

## Goal

The global installer currently merges only `agent.<name>`, `skills.paths`,
`instructions`, and the three scalars (`default_agent`, `model`,
`small_model`) into `~/.config/opencode/opencode.jsonc`. Every other
top-level key the project ships — `command`, `permission`, `mcp`,
`provider`, `enabled_providers`, `$schema` — is silently dropped on
install. As a result, after `global-setup.bat` the user has the 13 agents
and the slash commands `/setup-project` and `/build` are missing, the
permission policy from the project family is not in effect, and the MCP
servers (graphify) are not wired up.

This plan extends the merge helper to install **everything** the project
ships, with safe uninstall that restores the user's prior values.

## Background (why ADR-002 said "never touch" for these keys)

ADR-002 (2026-06-04) explicitly classified `$schema`, `enabled_providers`,
`provider`, `mcp`, `command`, `permission` as "never touch / preserved
as-is". The intent was defensive: the install was thought of as "register
the agents globally" and the other keys were treated as user-owned
configuration that the installer should leave alone.

That classification is wrong for this project family. The intent of the
global install is to make the *project family* available globally — the
same way `npm install -g` brings the CLI binaries. Users running
`global-setup.bat` expect the project's commands, MCPs, permission
policy, and provider config to be live everywhere. Dropping them is the
bug the user is reporting.

## Architecture

Extend the merge helper in `.opencode/scripts/opencode_jsonc_merge.py`
to handle six additional top-level keys, following the same
deep-merge-with-snapshot pattern that `agent.<name>` already uses.

### Updated per-key merge policy (supersedes ADR-002's table)

| Key | Install strategy | Uninstall strategy | Manifest tracking |
|---|---|---|---|
| `default_agent`, `model`, `small_model` | overwrite (project is authoritative) | DO NOT restore (existing policy) | `scalar_changes` (existing) |
| `$schema` | overwrite (project's schema URL) | DO NOT restore (no tracking) | none — it's a one-line URL pointer |
| `skills.paths` | union + dedupe, case-insensitive | drop only entries we added | `skills_paths` (existing) |
| `instructions` | union + dedupe + auto-add repo `AGENTS.md` | drop only entries we added | `instructions` (existing) |
| `agent.<name>` | deep-merge; warn + skip on collision; `--force` to overwrite | delete only names we added | `agent_names` + `collisions` (existing) |
| `command.<name>` | deep-merge into `command`; project wins on per-name conflict | delete only names we added | `command_names: [string]` (new) |
| `mcp.<name>` | deep-merge into `mcp`; project wins on per-name conflict | delete only names we added | `mcp_names: [string]` (new) |
| `provider` | recursive deep-merge into `provider` (top-level) | restore from snapshot | `provider_snapshot: object \| null` (new) |
| `permission` | recursive deep-merge into `permission` (top-level) | restore from snapshot | `permission_snapshot: object \| null` (new) |
| `enabled_providers` | list union + dedupe (string compare) | filter out items we added | `enabled_providers_added: [string]` (new) |

**Why snapshot+restore for `provider` and `permission` but not the
scalars?** The scalars are single values; if a different project overwrites
them between installs, we cannot safely revert. The dicts are bigger and
a partial overwrite is more likely to leave the global config in a broken
state. Snapshotting the pre-install value lets us return the global config
to its exact pre-install state on uninstall. Snapshots are deep-copied
at install time, so a user's later manual edits to those keys will not
contaminate the snapshot (the snapshot is taken *before* the deep-merge
writes to `global_cfg`).

**FIRST-wins for snapshots on re-runs.** If `global-setup.bat` is run
twice, the second run's snapshot of `provider` would capture the
post-first-install value (which is the deep-merge result). We want the
*pre-FIRST-install* value as the snapshot, so on a later uninstall we
restore the user's original config. The manifest-merge logic for
re-runs therefore keeps the first run's snapshot and ignores subsequent
snapshots for the same key.

**No collision warnings for `command`/`mcp`/`provider`/`permission`.**
Unlike `agent.<name>`, these are not "registered subagents" — they are
project-family configuration. The project is authoritative for project-
family values. If the user has customized `command.setup-project`, the
project's value overwrites it silently on install (project wins on
deep-merge conflict). The user can `uninstall-global.bat` to revert, or
edit the global jsonc by hand to keep their custom version.

### Manifest schema additions

The `added` block in
`%USERPROFILE%\.config\opencode\.opencode-jake-installed.json` gains
five new fields:

```json
{
  "added": {
    "agent_names":      [...],            // existing
    "collisions":       [...],            // existing
    "instructions":     [...],            // existing
    "skills_paths":     [...],            // existing
    "scalar_changes":   {...},            // existing
    "command_names":         ["setup-project", "build"],
    "mcp_names":             ["graphify"],
    "enabled_providers_added": ["opencode"],
    "provider_snapshot":     { ... pre-install global_cfg["provider"] ... } | null,
    "permission_snapshot":   { ... pre-install global_cfg["permission"] ... } | null
  }
}
```

`command_names` and `mcp_names` are unioned across re-runs (per-name
dedupe). `enabled_providers_added` is unioned (per-item dedupe).
`provider_snapshot` and `permission_snapshot` are FIRST-wins (the
earliest non-null snapshot is preserved).

## Tasks

### Layer 1 (parallel, no deps) — design

- [x] **#1** @architect — per-key policy table + manifest schema
  (above).

### Layer 2 (depends on L1) — implementation

- [ ] **#2** @builder — extend `cmd_install` in
  `.opencode/scripts/opencode_jsonc_merge.py`:
  - Snapshot `global_cfg.get("provider")` and
    `global_cfg.get("permission")` into a deep copy *before* the merge.
  - Snapshot `global_cfg.get("command")` and `global_cfg.get("mcp")` —
    but we only need the *names* for the manifest (the per-name
    tracking handles removal); we can record the names inline during
    the merge loop.
  - For each project key below, do the action and record the
    contribution in `added`:
    - `command` — `agents["command"] = deep_merge(global_cfg.get("command", {}), project["command"])`,
      then add every name in `project["command"]` to
      `added["command_names"]`.
    - `mcp` — same pattern as `command`, populating
      `added["mcp_names"]`.
    - `provider` — `global_cfg["provider"] = deep_merge(global_cfg.get("provider", {}), project["provider"])`,
      set `added["provider_snapshot"]` to the deep-copied pre-merge
      value (or `None` if the key was absent).
    - `permission` — same pattern as `provider`, populating
      `added["permission_snapshot"]`.
    - `enabled_providers` — `new = dedupe_union(global_cfg.get("enabled_providers", []), project["enabled_providers"])`,
      set `global_cfg["enabled_providers"] = new`, set
      `added["enabled_providers_added"]` to
      `_diff_added(old, new)`.
    - `$schema` — if present in project: `global_cfg["$schema"] = project["$schema"]`.
      No manifest tracking, no remove behavior.
  - Order matters: do the deep-merged dicts FIRST (so snapshots
    reflect pre-merge state), then the list union (so `_diff_added`
    has a clean `old`), then the simple overwrite last.
- [ ] **#3** @builder — extend the manifest **merge** logic
  (in the `if manifest_path.exists()` block of `cmd_install`):
  - Union `added["command_names"]` (per-name dedupe, preserve order).
  - Union `added["mcp_names"]` (same).
  - Union `added["enabled_providers_added"]` (same).
  - **FIRST-wins for snapshots**: if `prev_added.get("provider_snapshot")`
    is not `None`, keep it; else overwrite with the new value. Same
    for `permission_snapshot`.
  - Bump the `manifest` version from 1 to 2 (signals that the schema
    has these new optional fields; old manifests without the new
    fields still load correctly because the merge is permissive).
- [ ] **#4** @builder — extend `cmd_remove`:
  - For each name in `added.get("command_names", [])`, delete from
    `global_cfg["command"]`. If `command` is empty afterward, delete
    the key entirely.
  - Same for `added.get("mcp_names", [])` on `global_cfg["mcp"]`.
  - For `added.get("enabled_providers_added", [])`, filter out those
    items from `global_cfg["enabled_providers"]`. If empty, delete
    the key.
  - For `added.get("provider_snapshot")`: if non-null, restore
    `global_cfg["provider"] = snapshot`; else delete the key.
  - Same for `added.get("permission_snapshot")`.
  - Print a one-line summary for each restored/removed block.
- [ ] **#5** @builder — keep `cmd_remove`'s existing scalar restore
  behavior (DO NOT restore scalars — same as today).

### Layer 3 (depends on L2) — tests

- [ ] **#6** @tester — add tests to `tests/test_global_setup.py`:
  - `test_install_deep_merges_command_block` — project has
    `command: { "setup-project": {template: "..."} }`; global ends
    up with it; user's pre-existing `command.user-cmd` survives.
  - `test_install_command_overwrites_on_name_conflict` — project has
    `command.setup-project`; user also has `command.setup-project`;
    project's value wins (no warn, deep-merge b-wins).
  - `test_install_deep_merges_mcp_block` — same shape as command.
  - `test_install_deep_merges_provider_block` — recursive merge
    verifies nested `provider.opencode.options` survives the merge
    and user's other providers are preserved.
  - `test_install_deep_merges_permission_block` — recursive merge;
    user's existing permission rules survive; project's rules are
    added; conflicts at the leaf level are resolved in project's
    favor.
  - `test_install_unions_enabled_providers` — union+dedupe across
    two installs.
  - `test_install_overwrites_schema` — project's `$schema` wins.
  - `test_remove_surgically_drops_merged_command_names` — project-
    contributed command names are gone, user's survive.
  - `test_remove_surgically_drops_merged_mcp_names` — same shape.
  - `test_remove_filters_enabled_providers` — added items removed,
    user's items survive.
  - `test_remove_restores_provider_from_snapshot` — pre-install
    `provider` value is restored exactly, not the post-merge value.
  - `test_remove_restores_permission_from_snapshot` — same shape.
  - `test_remove_deletes_provider_key_if_no_snapshot` — when the
    key was absent pre-install, the key is deleted on remove.
  - `test_manifest_preserves_command_names_across_idempotent_reruns`
    — re-run unions, no dupes.
  - `test_manifest_first_wins_for_provider_snapshot` — first run's
    snapshot survives a second run, not the second run's snapshot.
  - All tests use the existing `tmp_path` fixture pattern, no real
    global config touched.

### Layer 4 (depends on L3) — review

- [ ] **#7** @reviewer — review the changes for:
  - Correctness of the deep-merge (project wins at every leaf).
  - Idempotency — running install twice produces the same global
    config.
  - Manifest round-trip — install + remove is a clean no-op for the
    user's pre-existing keys.
  - Snapshot deep-copy — mutating `global_cfg["provider"]` after
    the snapshot is taken must not bleed into the snapshot.
  - FIRST-wins for snapshots — verify the re-run logic with a
    test that proves the second run does not overwrite the first
    run's snapshot.
  - Edge case: project has empty `command: {}` (no contribution);
    manifest should not record an empty `command_names: []` as
    "we added zero commands" — verify the merge helper skips
    empty contributions.
  - Edge case: project's `enabled_providers` is missing; the
    existing global's `enabled_providers` survives untouched.
  - Run `python -m pytest tests/ -v` — full suite green.
  - Run `python scripts/verify-plan.py .opencode/plans/plan-003-...md`
    — exits 0.

### Layer 5 (depends on L4) — docs + ADR

- [ ] **#8** @docs — update `README.md` and
  `examples/integrate-into-your-project.md` to mention that the
  global install also brings commands (`/setup-project`, `/build`),
  MCPs (`graphify`), the permission policy, and the provider config.
- [ ] **#9** @docs — update ADR-002 to reflect the new policy:
  - Add a "Superseded by" note at the top pointing to plan-003.
  - Update the per-key policy table to match the new table above.
  - Add a "Consequences / negative" line for snapshots growing the
    manifest slightly.
  - Cross-link the plan-003 file.

### Layer 6 (depends on L5) — live run

- [ ] **#10** Conductor — run `python .opencode\scripts\opencode_jsonc_merge.py
  install --project opencode.json --global <real-global-jsonc>
  --manifest <real-manifest> --dry-run` and confirm the dry-run
  output lists the new blocks.
- [ ] **#11** Conductor — run the real installer
  (`global-setup.bat --unattended`) and verify the global
  `opencode.jsonc` now has `command`, `mcp`, `provider`, `permission`,
  `enabled_providers`, `$schema` in addition to the existing
  `agent`/`skills`/`instructions`/scalars.
- [ ] **#12** Conductor — open opencode TUI (or `opencode` CLI) and
  confirm `/setup-project` and `/build` are listed as available
  commands. Confirm `opencode agent list` still shows 13 agents.
- [ ] **#13** Conductor — re-run the installer to confirm
  idempotency (no duplicates in `command`, `mcp`, `enabled_providers`).
- [ ] **#14** Conductor — run `uninstall-global.bat --unattended`
  and verify the global config no longer has the project's `command`
  blocks, `mcp` blocks, `provider` block, `permission` block, and
  `enabled_providers` items, but the user's pre-existing values
  survive.

## Deliverables

- `.opencode/scripts/opencode_jsonc_merge.py` (extended; ~80 new lines)
- `tests/test_global_setup.py` (~15 new tests, ~250 new lines)
- `.opencode/decisions/adr-002-global-setup-merge-strategy.md` (updated)
- `README.md` (mention the new keys)
- `examples/integrate-into-your-project.md` (mention the new keys)
- This plan archived to `.opencode/plans/completed/plan-003-*.md`

## Verification

Static + dynamic checks (run from the repo root, exit 0 = pass):

- [ ] **#1** `.opencode/scripts/opencode_jsonc_merge.py` — file exists
- [ ] **#2** `python -c "import ast; ast.parse(open('.opencode/scripts/opencode_jsonc_merge.py', encoding='utf-8').read())"` — helper still parses
- [ ] **#3** `python -c "import ast; ast.parse(open('tests/test_global_setup.py', encoding='utf-8').read())"` — tests still parse
- [ ] **#4** `python -c "from pathlib import Path; t = Path('.opencode/scripts/opencode_jsonc_merge.py').read_text(encoding='utf-8'); assert 'command_names' in t; assert 'mcp_names' in t; assert 'provider_snapshot' in t; assert 'permission_snapshot' in t; assert 'enabled_providers_added' in t; print('OK')"` — new manifest fields are referenced
- [ ] **#5** `python -c "from pathlib import Path; t = Path('.opencode/scripts/opencode_jsonc_merge.py').read_text(encoding='utf-8'); assert 'global_cfg[\"provider\"] = deep_merge' in t; assert 'global_cfg[\"permission\"] = deep_merge' in t; assert 'project_command' in t; assert 'project_mcp' in t; assert 'project_provider' in t; assert 'project_permission' in t; assert 'project_ep' in t; assert 'global_cfg[\"$schema\"]' in t; print('OK')"` — new merge call sites exist (provider/permission use deep_merge; command/mcp use per-name direct assign per design)
- [ ] **#6** `python -m pytest tests/test_global_setup.py -v` — all merge-helper tests pass (30 original + 27 new = 57 total)
- [ ] **#7** `python -c "import json, subprocess; r = subprocess.run(['python','-m','pytest','tests/','-q','--ignore=tests/test_agents_runtime.py','--ignore=tests/test_agents_v2.py','--ignore=tests/test_setup.py','--ignore=tests/test_integration.py'], capture_output=True, text=True); assert r.returncode == 0, r.stdout + r.stderr; print('OK')"` — all in-scope unit tests pass (excludes tests that shell out to the `opencode` CLI, which has a pre-existing Bun-on-Windows segfault unrelated to this plan; see Risks)
- [ ] **#8** `.opencode/decisions/adr-002-global-setup-merge-strategy.md` — file exists
- [ ] **#9** `python -c "from pathlib import Path; t = Path('README.md').read_text(encoding='utf-8').lower(); assert 'command' in t and 'mcp' in t and 'permission' in t; print('OK')"` — README mentions the new globally-installed blocks
- [ ] **#10** `python .opencode/scripts/opencode_jsonc_merge.py install --project opencode.json --global .opencode/plans/completed/.tmp-global.jsonc --manifest .opencode/plans/completed/.tmp-manifest.json --dry-run` — exit 0
- [ ] **#11** `python -c "import json; cfg = json.load(open('opencode.json', encoding='utf-8')); missing = [k for k in ('command', 'permission', 'mcp', 'provider', 'enabled_providers') if k not in cfg]; missing += [k for k in cfg if k.startswith(chr(92)) and 'schema' in k]; assert not missing, f'missing or malformed: {missing}'; print('OK')"` — project's opencode.json has every top-level key we expect to install globally (`$schema` is checked separately because the bash `\$` escape does not survive into Python)

Live-state checks (after the patched installer is run on the user's real
machine; the merge helper handles all of these — no need to invoke the
`opencode` CLI directly since it has a Bun-on-Windows crash):

- [ ] **#12** Conductor — after real `global-setup.bat --unattended`:
  `python -c "import sys; sys.path.insert(0, '.opencode/scripts'); from opencode_jsonc_merge import load_jsonc; cfg = load_jsonc(r'%USERPROFILE%\.config\opencode\opencode.jsonc'); assert 'setup-project' in cfg.get('command', {}); assert 'build' in cfg.get('command', {}); assert 'graphify' in cfg.get('mcp', {}); assert 'opencode' in cfg.get('enabled_providers', []); assert 'opencode' in cfg.get('provider', {}); assert 'bash' in cfg.get('permission', {}); assert 'conductor' in cfg.get('agent', {}); print('OK')"` — global config has the new blocks AND the agents. Uses `load_jsonc` because the helper prepends a `// opencode-jake: ...` header.
- [ ] **#13** Conductor — `python -c "import sys; sys.path.insert(0, '.opencode/scripts'); from opencode_jsonc_merge import load_jsonc; cfg = load_jsonc(r'%USERPROFILE%\.config\opencode\opencode.jsonc'); assert len(cfg.get('agent', {})) == 13; print('OK')"` — global config has exactly 13 agents
- [ ] **#14** Conductor — `python -c "import sys; sys.path.insert(0, '.opencode/scripts'); from opencode_jsonc_merge import load_jsonc; cfg = load_jsonc(r'%USERPROFILE%\.config\opencode\opencode.jsonc'); cmds = set(cfg.get('command', {}).keys()); assert {'setup-project', 'build'}.issubset(cmds); print('OK')"` — global config has the project's slash commands (we check via jsonc content to avoid the opencode CLI Bun crash)
- [ ] **#15** Conductor — re-run `global-setup.bat --unattended`, confirm
  no duplicate command names / MCP names / providers by checking the
  jsonc content
- [ ] **#16** Conductor — run `uninstall-global.bat --unattended` and
  confirm global config no longer has the project's `command.setup-project`,
  `command.build`, `mcp.graphify`, or `enabled_providers` items

## Risks

- **Snapshot deep-copy bug.** A bug where the helper takes a shallow
  reference to `global_cfg["provider"]` instead of a deep copy would
  cause the snapshot to mutate as `global_cfg["provider"]` is later
  mutated. Caught by `test_remove_restores_provider_from_snapshot` if
  we explicitly mutate the global after the snapshot and check the
  snapshot is unaffected.
- **FIRST-wins logic for snapshots is easy to invert.** The manifest
  re-run merge is the trickiest part. A test that explicitly proves
  the second run's snapshot is ignored is the safety net.
- **MCP command paths in `mcp.graphify.command`.** The project's
  `mcp.graphify.command` is `["python3", "-m", "graphify.serve", ...]`.
  The `python3` binary is the MS Store stub on some Windows machines
  (per ADR-002 / plan-002). This is a pre-existing issue not caused
  by this plan. The install will faithfully copy the project's
  command; whether `graphify` actually starts is the user's env
  problem. Out of scope for this plan.
- **`$schema` overwrite is a behavior change.** Anyone with a custom
  `$schema` URL in their global config (unlikely, but possible) will
  see it overwritten. Documented in the ADR update; user can edit by
  hand.

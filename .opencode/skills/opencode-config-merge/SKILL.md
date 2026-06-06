---
name: opencode-config-merge
description: Use when running or troubleshooting the global-install / uninstall scripts (`global-setup.bat`, `setup.bat`, `uninstall-global.bat`), or when a per-key merge policy is questioned. Documents the per-key table (scalars overwrite, arrays union+dedupe, `agent.<name>` deep-merge with warning, `command.<name>`/`mcp.<name>` project-wins, `provider`/`permission` deep-merge+restore, `enabled_providers` union+filter, `$schema` overwrite) and the snapshot+restore semantic. Avoid for non-merge config edits — that is a manual edit to the global `opencode.jsonc`.
---

# OpenCode Config Merge

This skill is the canonical reference for how the project installers merge their `opencode.json` into the user's global `opencode.jsonc`. The merge logic lives in `.opencode/scripts/opencode_jsonc_merge.py` (~1100 lines, stdlib-only). ADR-002 is the design doc; this skill is the operational cheat sheet.

## When to use

- Running or troubleshooting `global-setup.bat` or `setup.bat` (the installers).
- Running or troubleshooting `uninstall-global.bat` (the uninstaller).
- Deciding "should the project overwrite the user's `command.<name>` block?" — the per-key table is the answer.
- Investigating a "the user's `provider` block disappeared after uninstall!" bug — the snapshot+restore semantic is the answer.

## Process / Checklist

### The per-key merge policy (the canonical table)

| Key | Merge behavior | On uninstall | Notes |
|---|---|---|---|
| `default_agent` | **overwrite** (project wins) | NOT restored (safety) | Scalar; non-restoration is by design (see ADR-002) |
| `model` | **overwrite** (project wins) | NOT restored | Scalar |
| `small_model` | **overwrite** (project wins) | NOT restored | Scalar |
| `$schema` | **overwrite** (project URL) | NOT restored | Scalar |
| `skills.paths` | **union + dedupe** (case-insensitive on Windows) | **removed** (project entries only) | User-added paths preserved |
| `instructions` | **union + dedupe** | **removed** (project entries only) | |
| `agent.<name>` | **deep-merge** with collision WARNING; `--force` overwrites | **removed** (project entries only) | Sub-keys like `steps`/`permission.task`/`prompt` merge per-name |
| `command.<name>` | **deep-merge per-name** (project wins, NO warning) | **removed** (project entries only) | Project-family config; user-custom version is overwritten without warning |
| `mcp.<name>` | **deep-merge per-name** (project wins, NO warning) | **removed** (project entries only) | |
| `provider` | **recursive deep-merge top-level**; project-wins on scalar sub-keys; arrays union+dedupe | **restored from snapshot** (or DELETED if snapshot was null) | The only block with snapshot+restore |
| `permission` | **recursive deep-merge top-level**; project-wins on scalar sub-keys | **restored from snapshot** (or DELETED if snapshot was null) | Same snapshot+restore semantic as `provider` |
| `enabled_providers` | **list union + dedupe** | **filtered** (project entries removed; user's other entries kept) | |

### The snapshot+restore semantic

For `provider` and `permission` ONLY, the installer:

1. **Install step 1:** deep-copy the user's PRE-MERGE `provider` (or `permission`) value into `added.provider_snapshot` (or `added.permission_snapshot`) in the manifest. If the user had no pre-existing value, set the snapshot to `null`.
2. **Install step 2:** apply the recursive deep-merge, writing the merged value to the global `opencode.jsonc`.
3. **Uninstall step 1:** read `added.provider_snapshot` from the manifest. If non-null, restore it verbatim. If null, DELETE the `provider` key from the global.

**Why snapshot+restore?** The project may have only partially owned `provider` (e.g., it merged in its own `provider.opencode` block but left the user's `provider.anthropic` block alone). On uninstall, the user's pre-existing state is exactly what they had before the install — no half-merged residue.

### The FIRST-wins rule on re-runs

If the installer is re-run on a global that already has the project installed (idempotent re-run), the install step:

1. Reads the previous manifest.
2. Checks if `added.provider_snapshot` (or `permission_snapshot`) is PRESENT in the previous manifest.
3. If PRESENT, does NOT re-take the snapshot (FIRST-wins; preserves the original pre-install value).
4. If ABSENT, takes a fresh snapshot (first-time install).

The manifest-merge step layers `prev_added` over `added` for snapshot keys, so the earliest snapshot wins across re-runs.

### The manifest v2 schema

The install manifest is at `%USERPROFILE%\.config\opencode\.opencode-jake-installed.json`:

```json
{
  "version": 2,
  "installed_at": "2026-06-04T09:30:00Z",
  "repo_dir": "C:\\Users\\Jake\\Documents\\GitHub\\Agents-Opencode-Jake",
  "added": {
    "scalars": {"default_agent": "conductor", "model": "opencode/minimax-m3-free", "small_model": "opencode/minimax-m3-free"},
    "agent_names": ["conductor", "planner", "builder", ...],
    "scalar_changes": {"default_agent": {"old": null, "new": "conductor"}, ...},
    "skills_paths": [".opencode/skills", "~/.config/opencode/skills"],
    "instructions": ["path/to/AGENTS.md"],
    "command_names": ["setup-project", "build"],
    "mcp_names": ["graphify"],
    "enabled_providers": ["opencode"],
    "provider_snapshot": null,
    "permission_snapshot": null
  }
}
```

Note: `provider_snapshot` and `permission_snapshot` are NOT pre-initialized. Their **presence** means "we took a snapshot"; their **absence** means "we never touched this block". A value of `null` (key present, value null) means "user had no pre-existing value, and the key on the global was deleted by the installer's deep-merge path or by us on uninstall".

## Examples

### Example 1: clean install (plan-002)

User's global has NO `provider` block. The installer:

1. Snapshots `null` (user had nothing).
2. Deep-merges project's `provider` block into global.
3. Writes manifest with `provider_snapshot: null`.

On uninstall, the `provider` key is DELETED from global (not restored, because snapshot was null). User is back to a clean state.

### Example 2: idempotent re-run

User re-runs `global-setup.bat` after the first install completed. The installer:

1. Reads manifest: `provider_snapshot: null` is PRESENT.
2. Does NOT re-take the snapshot (FIRST-wins).
3. Re-applies the deep-merge (no-op because it's already merged).
4. Manifest re-written with same `provider_snapshot: null`.

Verified: 0 changes to global; manifest stable across re-runs.

### Example 3: user had pre-existing `provider` (plan-003)

User's global has `provider.anthropic` with API key + custom model. The installer:

1. Snapshots the ENTIRE `provider` value (including `anthropic`) as `added.provider_snapshot`.
2. Deep-merges project's `provider.opencode` block; user's `provider.anthropic` is preserved (deep-merge is per-top-level-key, not whole-block).
3. Writes manifest with `provider_snapshot: <the pre-existing value>`.

On uninstall, the `provider` block is RESTORED to the pre-existing value verbatim. User's `anthropic` config survives the install/uninstall cycle.

### Example 4: collision on `agent.<name>`

User already has an agent named `builder` (from a different project). The installer:

1. Detects the collision when deep-merging `agent.builder`.
2. WITHOUT `--force`, the install SKIPS the agent (user's version wins). A warning is printed.
3. WITH `--force`, the install OVERWRITES the agent. A warning is printed.
4. The manifest's `added.agent_names` includes `builder` regardless (so uninstall will try to remove it; on a global that has a non-project `builder`, uninstall will NOT remove it — manifest is not authoritative for non-project agents).

## Common pitfalls

- **Pitfall 1: "I edited `opencode.jsonc` and re-ran install, my edits got overwritten"** — yes, that's the design. If you want your edits to survive, edit the project repo's `opencode.json` and commit. The installer always writes the project's version.
- **Pitfall 2: "I uninstalled and my `provider` block disappeared"** — this happens when the user's pre-existing `provider` was `null` (key absent). Uninstall deletes the key, returning the global to its pre-install state. To preserve a `provider` block, set it up BEFORE running install.
- **Pitfall 3: "I re-ran install and got a different manifest"** — the manifest is unioned with the previous manifest on every run. Re-running should be idempotent (0 changes). If it isn't, that's a bug in `opencode_jsonc_merge.py`; report it.
- **Pitfall 4: "The skill description says `command.<name>` project-wins, but my custom command survived"** — check whether the custom command's sub-keys are project-wins (scalars overwrite) or deep-merge (preserved). The per-key table has the answer.

## Reference: the snapshot+restore in 3 lines

```text
INSTALL:  snapshot = user.provider (or null)
          merge:    user.provider = deep_merge(user.provider, project.provider)
          manifest: added.provider_snapshot = snapshot

UNINSTALL: if added.provider_snapshot is present:
              user.provider = added.provider_snapshot
          else:
              delete user.provider
```

# Example: Add a custom agent

This walkthrough shows how to add a 14th agent (e.g., `@translator` for translation tasks) to your opencode.json.

## Steps

### 1. Choose a unique agent name

The name must be lowercase, no spaces, and not collide with built-in agents or the 13 existing ones.

```bash
$ grep -E '^\s+"[a-z]+":' opencode.json | head -20
  "conductor": ...
  "planner": ...
  ...
```

Pick something like `translator`, `formatter`, or `linter`.

### 2. Add the agent entry to `opencode.json`

Open `opencode.json` and add a new entry under `"agent"`:

```json
"agent": {
  "conductor": { ... },
  "planner": { ... },
  ...
  "translator": {
    "model": "opencode/minimax-m3-free",
    "fallback_model": "opencode/big-pickle",
    "description": "Translation specialist. Converts text between languages while preserving technical terms and code blocks. Reads source files, outputs translated files with same structure.",
    "mode": "all",
    "permission": {
      "edit": "allow",
      "read": "allow",
      "bash": "ask"
    },
    "prompt": "You are a translation specialist. ..."
  }
}
```

**Required fields:**
- `model` — provider/model string (must match the regex in `opencode.schema.json`)
- `fallback_model` — backup model when primary is unavailable
- `description` — ≥20 characters, used for routing
- `mode` — `"primary"` (Tab-switchable), `"subagent"` (@mention only), or `"all"` (both)
- `prompt` — ≥50 characters, the system prompt

### 3. Validate the config

```bash
python -m pytest tests/test_schema.py -v
```

All 4 schema tests must pass.

### 4. Test the new agent

```bash
# Direct CLI test
opencode run --agent translator "Translate 'hello world' to Spanish"

# Or via the test suite
python tests/test_agents_v2.py
# (Add a new EXPECTED entry in test_agents_v2.py for the new agent)
```

### 5. Re-run the knowledge graph

```bash
/graphify . --update
```

The new agent will appear in the graph and in the agent ecosystem community.

## Common pitfalls

- **Wrong mode:** If you set `"mode": "subagent"`, the agent won't be Tab-switchable and `opencode run --agent <name>` will fail. Use `"all"` unless you specifically want it hidden.
- **Missing permission block:** Without `permission`, the agent has no edit/read/bash access. The defaults are restrictive.
- **Prompt too short:** The schema requires `minLength: 50`. A one-line "You are a translator" won't validate.
- **Description too vague:** Routing depends on the description. "Does translation" is worse than "Translation specialist. Converts text between languages while preserving technical terms."

## See also

- `opencode.schema.json` — the full schema
- ADR-001 — why we use JSON-only agent definitions

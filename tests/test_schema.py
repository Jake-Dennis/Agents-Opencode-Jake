"""Validates opencode.json against opencode.schema.json.

Uses the session-scoped `cfg` and `schema` fixtures from conftest.py,
which parse the JSON files exactly once for the whole test run.
"""
import jsonschema


def test_opencode_json_validates_against_schema(cfg, schema):
    """The whole config must validate."""
    jsonschema.validate(cfg, schema)
    print(f"\n[OK] opencode.json validates against schema ({len(cfg['agent'])} agents)")


def test_default_agent_exists(cfg):
    """default_agent must reference an actual agent in the agent map."""
    assert cfg["default_agent"] in cfg["agent"], \
        f"default_agent {cfg['default_agent']!r} not in agent map"


def test_all_agents_have_consistent_models(cfg):
    """Every agent's model must match the top-level model (constraint)."""
    top = cfg["model"]
    for name, entry in cfg["agent"].items():
        assert entry["model"] == top, \
            f"agent.{name}.model ({entry['model']}) != top-level model ({top})"


def test_commands_use_template_not_prompt(cfg):
    """Regression: the `template` field is required, not `prompt`."""
    for cmd_name, cmd_cfg in cfg.get("command", {}).items():
        assert "template" in cmd_cfg, f"command {cmd_name!r} missing 'template' field"
        assert "prompt" not in cmd_cfg, f"command {cmd_name!r} has 'prompt' — should be 'template'"

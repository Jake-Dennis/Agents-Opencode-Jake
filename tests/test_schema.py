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


def test_all_agents_inherit_top_level_model(cfg):
    """If project sets a top-level model, agents that set an explicit model must match;
    if the project doesn't set one, global config applies and the test is vacuously true."""
    top = cfg.get("model")
    if top is None:
        return  # project doesn't override; global/user model applies
    for name, entry in cfg["agent"].items():
        if "model" in entry:
            assert entry["model"] == top, \
                f"agent.{name}.model ({entry['model']}) != top-level model ({top})"
    # Every agent should have a fallback_model that differs from the top-level model
    # (otherwise the fallback would never be used).
    for name, entry in cfg["agent"].items():
        if "fallback_model" in entry:
            assert entry["fallback_model"] != top, \
                f"agent.{name}.fallback_model ({entry['fallback_model']}) == top-level model ({top}); " \
                "fallback should be a different model to actually serve as fallback"


def test_commands_use_template_not_prompt(cfg):
    """Regression: the `template` field is required, not `prompt`."""
    for cmd_name, cmd_cfg in cfg.get("command", {}).items():
        assert "template" in cmd_cfg, f"command {cmd_name!r} missing 'template' field"
        assert "prompt" not in cmd_cfg, f"command {cmd_name!r} has 'prompt' — should be 'template'"

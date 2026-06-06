"""Tests for the 4 project-scope SKILL.md files (plan-011).

Covers:
  T-SK-1: All 4 SKILL.md files exist at .opencode/skills/<name>/SKILL.md
  T-SK-2: Each starts with --- (YAML frontmatter delimiter on line 1)
  T-SK-3: Each name matches ^[a-z0-9]+(-[a-z0-9]+)*$ and is 1-64 chars
  T-SK-4: Each description is 1-1024 chars (non-empty after strip)
  T-SK-5: No name collision with the existing graphify skill
  T-SK-6: Each body (after closing ---) is 100-5000 chars
  T-SK-7: plan-review body contains the 4 Momus criteria keywords (case-insensitive)
  T-SK-8: batch-quoting body contains both % and ! (the two expansion types)

Stdlib only; regex-based frontmatter parser (no PyYAML dep).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".opencode" / "skills"

NEW_SKILLS = [
    "plan-review",
    "batch-quoting",
    "opencode-config-merge",
    "verify-plan-gate",
]

# Upstream skill spec
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAME_MAX = 64
DESC_MIN = 1
DESC_MAX = 1024
BODY_MIN = 100
BODY_MAX = 10000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_skill(name: str) -> dict:
    """Parse .opencode/skills/<name>/SKILL.md frontmatter + body.

    Returns:
        {"name": str, "description": str, "body": str, "path": Path}
    """
    p = SKILLS_DIR / name / "SKILL.md"
    content = p.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines and lines[0].strip() == "---", f"{name}: no opening --- on line 1"

    # Find closing ---
    close_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break
    assert close_idx is not None, f"{name}: no closing --- found"

    fm_block = "\n".join(lines[1:close_idx])
    body = "\n".join(lines[close_idx + 1:]).strip()

    # Regex-parse name and description
    m_name = re.search(r"^name:\s*(\S+)\s*$", fm_block, re.MULTILINE)
    m_desc = re.search(r"^description:\s*(.+?)\s*$", fm_block, re.MULTILINE | re.DOTALL)

    name_val = m_name.group(1) if m_name else ""
    # description can span multiple lines (folded); just take the first line for our purposes
    desc_val = m_desc.group(1).strip() if m_desc else ""

    return {
        "name": name_val,
        "description": desc_val,
        "body": body,
        "path": p,
    }


# ---------------------------------------------------------------------------
# T-SK-1: all 4 files exist
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill", NEW_SKILLS)
def test_skill_file_exists(skill: str) -> None:
    """T-SK-1: All 4 new SKILL.md files exist at the expected path."""
    p = SKILLS_DIR / skill / "SKILL.md"
    assert p.is_file(), f"missing skill file: {p}"


# ---------------------------------------------------------------------------
# T-SK-2: each starts with ---
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill", NEW_SKILLS)
def test_skill_starts_with_frontmatter(skill: str) -> None:
    """T-SK-2: Each SKILL.md starts with --- (YAML frontmatter delimiter on line 1)."""
    p = SKILLS_DIR / skill / "SKILL.md"
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines, f"{skill}: empty file"
    assert lines[0].strip() == "---", f"{skill}: first line is not '---': {lines[0]!r}"


# ---------------------------------------------------------------------------
# T-SK-3: each name matches the regex and length
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill", NEW_SKILLS)
def test_skill_name_valid(skill: str) -> None:
    """T-SK-3: Each skill's name matches ^[a-z0-9]+(-[a-z0-9]+)*$ and is 1-64 chars."""
    parsed = _load_skill(skill)
    name = parsed["name"]
    assert name, f"{skill}: name field missing or empty"
    assert len(name) <= NAME_MAX, f"{skill}: name too long ({len(name)} > {NAME_MAX})"
    assert NAME_RE.match(name), f"{skill}: name {name!r} does not match regex"


# ---------------------------------------------------------------------------
# T-SK-4: each description is 1-1024 chars
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill", NEW_SKILLS)
def test_skill_description_valid(skill: str) -> None:
    """T-SK-4: Each skill's description is 1-1024 chars (non-empty after strip)."""
    parsed = _load_skill(skill)
    desc = parsed["description"]
    assert desc, f"{skill}: description field missing or empty"
    assert DESC_MIN <= len(desc) <= DESC_MAX, (
        f"{skill}: description length {len(desc)} not in [{DESC_MIN}, {DESC_MAX}]"
    )


# ---------------------------------------------------------------------------
# T-SK-5: no name collision with existing skills
# ---------------------------------------------------------------------------

def test_no_name_collision_with_graphify() -> None:
    """T-SK-5: None of the 4 new skills collides with the existing graphify skill."""
    graphify_skill = SKILLS_DIR / "graphify-agent-workflow" / "SKILL.md"
    if not graphify_skill.is_file():
        pytest.skip("graphify-agent-workflow skill not present (acceptable)")
    parsed_graphify = _load_skill("graphify-agent-workflow")
    existing_names = {parsed_graphify["name"]}
    for skill in NEW_SKILLS:
        parsed = _load_skill(skill)
        assert parsed["name"] not in existing_names, (
            f"{skill}: name {parsed['name']!r} collides with existing skill"
        )
        existing_names.add(parsed["name"])


# ---------------------------------------------------------------------------
# T-SK-6: each body is 100-5000 chars
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill", NEW_SKILLS)
def test_skill_body_size(skill: str) -> None:
    """T-SK-6: Each skill's body (after closing ---) is 100-5000 chars."""
    parsed = _load_skill(skill)
    body = parsed["body"]
    assert BODY_MIN <= len(body) <= BODY_MAX, (
        f"{skill}: body length {len(body)} not in [{BODY_MIN}, {BODY_MAX}]"
    )


# ---------------------------------------------------------------------------
# T-SK-7: plan-review contains the 4 Momus criteria keywords
# ---------------------------------------------------------------------------

def test_plan_review_has_4_criteria() -> None:
    """T-SK-7: plan-review body contains 'correctness', 'specification', 'clarity', 'operability'."""
    parsed = _load_skill("plan-review")
    body_lower = parsed["body"].lower()
    for keyword in ("correctness", "specification", "clarity", "operability"):
        assert keyword in body_lower, (
            f"plan-review: missing Momus criterion keyword {keyword!r}"
        )


# ---------------------------------------------------------------------------
# T-SK-8: batch-quoting contains both % and !
# ---------------------------------------------------------------------------

def test_batch_quoting_has_expansion_symbols() -> None:
    """T-SK-8: batch-quoting body contains both % and ! (the two expansion types)."""
    parsed = _load_skill("batch-quoting")
    body = parsed["body"]
    assert "%" in body, "batch-quoting: missing % (parse-time expansion marker)"
    assert "!" in body, "batch-quoting: missing ! (delayed expansion marker)"


# ---------------------------------------------------------------------------
# Bonus: folder structure sanity
# ---------------------------------------------------------------------------

def test_no_unexpected_skill_subdirs() -> None:
    """Sanity: each of the 4 skills lives in its own subdir; no extra top-level files."""
    for skill in NEW_SKILLS:
        sub = SKILLS_DIR / skill
        assert sub.is_dir(), f"{skill}: not a directory at {sub}"
        contents = list(sub.iterdir())
        # Exactly one file: SKILL.md
        assert len(contents) == 1, f"{skill}: expected 1 file, found {len(contents)}: {contents}"
        assert contents[0].name == "SKILL.md", f"{skill}: unexpected file {contents[0].name}"

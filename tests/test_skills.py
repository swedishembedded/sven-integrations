#!/usr/bin/env python3
"""Validate all SKILL.md files in skills/integrations/.

Checks:
- Every SKILL.md has valid YAML frontmatter
- description field is present and non-empty
- name field is present and uses integrations/ namespace
- version field is present and looks like semver
- Per-tool skills have sven.requires_bins with the correct binary
- No mention of forbidden strings
- Body content is non-empty

Run:
  python tests/test_skills.py
  pytest tests/test_skills.py -v
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
SKILLS_DIR = ROOT / "skills" / "integrations"

TOOL_BINARIES = {
    "gimp": "sven-integrations-gimp",
    "blender": "sven-integrations-blender",
    "inkscape": "sven-integrations-inkscape",
    "audacity": "sven-integrations-audacity",
    "libreoffice": "sven-integrations-libreoffice",
    "obs-studio": "sven-integrations-obs-studio",
    "kdenlive": "sven-integrations-kdenlive",
    "shotcut": "sven-integrations-shotcut",
    "zoom": "sven-integrations-zoom",
    "drawio": "sven-integrations-drawio",
    "mermaid": "sven-integrations-mermaid",
    "anygen": "sven-integrations-anygen",
    "comfyui": "sven-integrations-comfyui",
}

FORBIDDEN_STRINGS = [
    "cli-anything",
    "cli_anything",
]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")


def parse_skill_md(path: Path) -> tuple[dict, str]:
    """Parse a SKILL.md file and return (frontmatter_dict, body)."""
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: malformed frontmatter (no closing ---)")
    fm = yaml.safe_load(parts[1])
    body = parts[2].strip()
    return fm or {}, body


def find_all_skills() -> list[Path]:
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


def test_all_skills_exist():
    skills = find_all_skills()
    assert len(skills) >= 14, f"Expected at least 14 SKILL.md files, found {len(skills)}"
    parent = SKILLS_DIR / "SKILL.md"
    assert parent.exists(), f"Parent skill missing: {parent}"
    for tool in TOOL_BINARIES:
        tool_skill = SKILLS_DIR / tool / "SKILL.md"
        assert tool_skill.exists(), f"Tool skill missing: {tool_skill}"


def test_frontmatter_valid():
    for path in find_all_skills():
        fm, body = parse_skill_md(path)
        assert isinstance(fm, dict), f"{path}: frontmatter is not a dict"
        assert "description" in fm, f"{path}: missing 'description' field"
        assert fm["description"], f"{path}: 'description' is empty"
        assert "name" in fm, f"{path}: missing 'name' field"
        assert fm["name"], f"{path}: 'name' is empty"
        assert "version" in fm, f"{path}: missing 'version' field"
        assert SEMVER_RE.match(str(fm["version"])), \
            f"{path}: 'version' does not look like semver: {fm['version']}"
        assert body, f"{path}: body is empty"


def test_skill_names_use_integrations_namespace():
    """All skill names must use the 'integrations/' prefix or be 'integrations'."""
    for path in find_all_skills():
        fm, _ = parse_skill_md(path)
        name = fm.get("name", "")
        assert name == "integrations" or name.startswith("integrations/"), \
            f"{path}: name '{name}' must start with 'integrations/' or be 'integrations'"


def test_tool_skills_have_requires_bins():
    for tool, binary in TOOL_BINARIES.items():
        path = SKILLS_DIR / tool / "SKILL.md"
        if not path.exists():
            continue
        fm, _ = parse_skill_md(path)
        sven_meta = fm.get("sven", {}) or {}
        requires_bins = sven_meta.get("requires_bins", [])
        assert requires_bins, \
            f"{path}: sven.requires_bins is missing or empty"
        assert binary in requires_bins, \
            f"{path}: sven.requires_bins should include '{binary}', got {requires_bins}"


def test_no_forbidden_strings():
    for path in find_all_skills():
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_STRINGS:
            assert forbidden not in content, \
                f"{path}: contains forbidden string '{forbidden}'"


def test_parent_skill_no_requires_bins():
    path = SKILLS_DIR / "SKILL.md"
    fm, _ = parse_skill_md(path)
    sven_meta = fm.get("sven", {}) or {}
    requires_bins = sven_meta.get("requires_bins", [])
    assert not requires_bins, \
        f"Parent skill should not have requires_bins, got: {requires_bins}"


def test_skill_names_match_directory():
    for tool in TOOL_BINARIES:
        path = SKILLS_DIR / tool / "SKILL.md"
        if not path.exists():
            continue
        fm, _ = parse_skill_md(path)
        name = fm.get("name", "")
        assert f"integrations/{tool}" == name, \
            f"{path}: expected name 'integrations/{tool}', got '{name}'"


if __name__ == "__main__":
    tests = [
        test_all_skills_exist,
        test_frontmatter_valid,
        test_skill_names_use_integrations_namespace,
        test_tool_skills_have_requires_bins,
        test_no_forbidden_strings,
        test_parent_skill_no_requires_bins,
        test_skill_names_match_directory,
    ]
    failures = []
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failures.append(test.__name__)
        except Exception as e:
            print(f"  ERROR {test.__name__}: {e}")
            failures.append(test.__name__)

    print()
    if failures:
        print(f"FAILED: {len(failures)} test(s) failed")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print(f"All {len(tests)} skill validation tests passed.")

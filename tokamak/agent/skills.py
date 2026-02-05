"""Skills loader for agent capabilities."""

import re
from pathlib import Path


class SkillsLoader:
    """
    Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to
    perform certain tasks using available tools.
    """

    def __init__(self, workspace: Path):
        """
        Initialize skills loader.

        Args:
            workspace: Base directory containing skills/ subdirectory.
        """
        self.skills_dir = workspace / "skills"

    def list_skills(self) -> list[dict[str, str]]:
        """
        List all available skills.

        Returns:
            List of skill info dicts with 'name', 'description', 'path'.
        """
        skills = []

        if not self.skills_dir.exists():
            return skills

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    meta = self._parse_frontmatter(skill_file)
                    skills.append({
                        "name": meta.get("name", skill_dir.name),
                        "description": meta.get("description", skill_dir.name),
                        "path": str(skill_file),
                    })

        return skills

    def build_skills_summary(self) -> str:
        """
        Build XML summary of all skills for system prompt.

        Returns:
            XML-formatted skills summary, empty string if no skills.
        """
        skills = self.list_skills()
        if not skills:
            return ""

        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<skills>"]
        for s in skills:
            name = escape_xml(s["name"])
            desc = escape_xml(s["description"])
            path = s["path"]

            lines.append("  <skill>")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <path>{path}</path>")
            lines.append("  </skill>")
        lines.append("</skills>")

        return "\n".join(lines)

    def _parse_frontmatter(self, skill_file: Path) -> dict[str, str]:
        """
        Parse YAML frontmatter from skill file.

        Simple regex-based parsing without external dependencies.

        Args:
            skill_file: Path to SKILL.md file.

        Returns:
            Dict with frontmatter values (name, description).
        """
        try:
            content = skill_file.read_text(encoding="utf-8")
        except Exception:
            return {}

        if not content.startswith("---"):
            return {}

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}

        metadata = {}
        for line in match.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"\'')

        return metadata

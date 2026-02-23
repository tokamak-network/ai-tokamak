"""Skills loader for agent capabilities."""

import json
import os
import re
import shutil
from pathlib import Path

# Default builtin skills directory (relative to this file)
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillsLoader:
    """
    Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to
    perform certain tasks using available tools.

    Supports:
    - Workspace skills: project-specific skills in workspace/skills/
    - Builtin skills: framework-provided skills in tokamak/skills/
    - Requirements checking: bins (CLI tools), env (environment variables)
    - Metadata: emoji, install instructions, always-load flag
    """

    def __init__(
        self,
        workspace: Path,
        builtin_skills_dir: Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ):
        """
        Initialize skills loader.

        Args:
            workspace: Base directory containing skills/ subdirectory.
            builtin_skills_dir: Directory for built-in skills. Defaults to tokamak/skills/.
            env_overrides: Override values for environment variable checks.
                          Key is env var name, value is the value to use instead of os.environ.
        """
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
        self.env_overrides = env_overrides or {}

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        """
        List all available skills.

        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.

        Returns:
            List of skill info dicts with 'name', 'description', 'path', 'source'.
        """
        skills = []

        # Workspace skills (highest priority)
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        meta = self._parse_frontmatter(skill_file)
                        skills.append(
                            {
                                "name": meta.get("name", skill_dir.name),
                                "description": meta.get("description", skill_dir.name),
                                "path": str(skill_file),
                                "source": "workspace",
                            }
                        )

        # Built-in skills
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        meta = self._parse_frontmatter(skill_file)
                        skill_name = meta.get("name", skill_dir.name)
                        # Don't override workspace skills
                        if not any(s["name"] == skill_name for s in skills):
                            skills.append(
                                {
                                    "name": skill_name,
                                    "description": meta.get("description", skill_dir.name),
                                    "path": str(skill_file),
                                    "source": "builtin",
                                }
                            )

        # Filter by requirements
        if filter_unavailable:
            return [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
        return skills

    def load_skill(self, name: str) -> str | None:
        """
        Load a skill by name.

        Args:
            name: Skill name (from frontmatter or directory name).

        Returns:
            Skill content or None if not found.
        """
        # Check workspace first
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        meta = self._parse_frontmatter(skill_file)
                        if meta.get("name", skill_dir.name) == name:
                            return skill_file.read_text(encoding="utf-8")

        # Check built-in
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        meta = self._parse_frontmatter(skill_file)
                        if meta.get("name", skill_dir.name) == name:
                            return skill_file.read_text(encoding="utf-8")

        return None

    def load_skill_content(self, name: str) -> str | None:
        """
        Load skill content without frontmatter.

        Args:
            name: Skill name.

        Returns:
            Skill content (stripped of frontmatter) or None.
        """
        content = self.load_skill(name)
        if content:
            return self._strip_frontmatter(content)
        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        Load specific skills for inclusion in agent context.

        Args:
            skill_names: List of skill names to load.

        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill_content(name)
            if content:
                parts.append(f"### Skill: {name}\n\n{content}")

        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skills_summary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).

        This is used for progressive loading - the agent can read the full
        skill content using read_file when needed.

        Returns:
            XML-formatted skills summary.
        """
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""

        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            desc = escape_xml(s["description"])
            path = s["path"]
            skill_meta = self._get_skill_meta(s["name"])
            available = self._check_requirements(skill_meta)

            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")

            # Show missing requirements for unavailable skills
            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")

            lines.append("  </skill>")
        lines.append("</skills>")

        return "\n".join(lines)

    def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        result = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_nanobot_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result

    def get_skill_metadata(self, name: str) -> dict | None:
        """
        Get metadata from a skill's frontmatter.

        Args:
            name: Skill name.

        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content:
            return None

        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip("\"'")
                return metadata

        return None

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
                metadata[key.strip()] = value.strip().strip("\"'")

        return metadata

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end() :].strip()
        return content

    def _parse_nanobot_metadata(self, raw: str) -> dict:
        """Parse nanobot metadata JSON from frontmatter."""
        try:
            data = json.loads(raw)
            return data.get("nanobot", {}) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_skill_meta(self, name: str) -> dict:
        """Get nanobot metadata for a skill (requires, always, etc.)."""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_nanobot_metadata(meta.get("metadata", ""))

    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars, env_set)."""
        requires = skill_meta.get("requires", {})

        # Check binary requirements
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False

        # Check environment variable existence (with override support)
        for env in requires.get("env", []):
            value = self.env_overrides.get(env, os.environ.get(env))
            if not value:
                return False

        # Check environment variable is set to specific value
        for env, value in requires.get("env_set", {}).items():
            if os.environ.get(env) != value:
                return False

        return True

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        """Get a description of missing requirements."""
        missing = []
        requires = skill_meta.get("requires", {})

        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")

        for env in requires.get("env", []):
            value = self.env_overrides.get(env, os.environ.get(env))
            if not value:
                missing.append(f"ENV: {env}")

        for env, value in requires.get("env_set", {}).items():
            if os.environ.get(env) != value:
                missing.append(f"ENV {env}={value}")

        return ", ".join(missing)

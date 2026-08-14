import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None  # Fallback to simple parser if yaml package is not installed


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    instructions: str = ""
    file_path: str = ""


class SkillsLoader:
    """
    Scans and loads markdown skill definitions from disk, matching user queries
    against triggers to dynamically pull skills and tools into context.
    """

    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            # Default to project_root/skills
            backend_dir = Path(__file__).resolve().parent.parent.parent
            self.skills_dir = backend_dir.parent / "skills"
        self._skills_cache: dict[str, Skill] = {}
        self.load_skills()

    def load_skills(self) -> dict[str, Skill]:
        """
        Scan skills directory and parse all markdown skill files.
        """
        self._skills_cache.clear()
        if not self.skills_dir.exists() or not self.skills_dir.is_dir():
            return self._skills_cache

        for file_path in self.skills_dir.glob("*.md"):
            try:
                skill = self._parse_skill_file(file_path)
                if skill:
                    self._skills_cache[skill.name] = skill
            except Exception as e:
                pass

        return self._skills_cache

    def _parse_skill_file(self, file_path: Path) -> Optional[Skill]:
        content = file_path.read_text(encoding="utf-8")
        
        # Parse YAML frontmatter between `---`
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not frontmatter_match:
            # Simple header fallback
            return None

        frontmatter_raw = frontmatter_match.group(1)
        instructions = frontmatter_match.group(2).strip()

        meta: dict[str, Any] = {}
        if yaml:
            meta = yaml.safe_load(frontmatter_raw) or {}
        else:
            # Minimal custom parser for name, description, triggers, tools
            lines = frontmatter_raw.splitlines()
            current_list_key = None
            for line in lines:
                line_stripped = line.strip()
                if line_stripped.startswith("- ") and current_list_key:
                    meta.setdefault(current_list_key, []).append(line_stripped[2:].strip())
                elif ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if v:
                        meta[k] = v
                        current_list_key = None
                    else:
                        meta[k] = []
                        current_list_key = k

        name = meta.get("name", file_path.stem)
        description = meta.get("description", "")
        triggers = meta.get("triggers", [])
        tools = meta.get("tools", [])

        return Skill(
            name=name,
            description=description,
            triggers=triggers if isinstance(triggers, list) else [str(triggers)],
            tools=tools if isinstance(tools, list) else [str(tools)],
            instructions=instructions,
            file_path=str(file_path)
        )

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "triggers": s.triggers,
                "tools": s.tools,
                "file_path": s.file_path
            }
            for s in self._skills_cache.values()
        ]

    def match_skills(self, user_message: str) -> list[Skill]:
        """
        Evaluate user message against skill triggers and return matched skills.
        """
        matched: list[Skill] = []
        msg_lower = user_message.lower()

        for skill in self._skills_cache.values():
            for trigger in skill.triggers:
                if trigger.lower() in msg_lower:
                    matched.append(skill)
                    break

        return matched

    def build_skill_prompt_injection(self, active_skills: list[Skill]) -> str:
        """
        Construct a concise system prompt injection for the active skills.
        """
        if not active_skills:
            return ""

        sections = []
        for s in active_skills:
            sections.append(f"### Skill Active: {s.name}\n{s.instructions}")

        return "\n\n" + "\n\n".join(sections)

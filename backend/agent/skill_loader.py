from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and return (metadata_dict, body_markdown)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    body = text[m.end():]
    return fm, body


@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path
    status: str = "discovered"
    metadata: dict[str, str] = field(default_factory=dict)
    scripts: list[str] = field(default_factory=list)
    doc_content: str | None = None


class SkillLoader:
    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.catalog: dict[str, SkillMeta] = {}

    @property
    def loaded_skills(self) -> list[SkillMeta]:
        return list(self.catalog.values())

    def discover(self) -> list[SkillMeta]:
        """Scan skill dirs, parse ONLY frontmatter (name + description).
        Also record which script files exist for reference."""
        self.catalog.clear()

        if not self.skills_dir.exists():
            logger.info("Skills directory not found: %s", self.skills_dir)
            return []

        for skill_path in sorted(self.skills_dir.iterdir()):
            if not skill_path.is_dir():
                continue
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                raw = skill_md.read_text(encoding="utf-8")
                fm, _body = _parse_frontmatter(raw)
                name = fm.get("name", skill_path.name)
                description = fm.get("description", "")
                metadata = fm.get("metadata", {}) or {}
                if isinstance(metadata, dict):
                    metadata = {str(k): str(v) for k, v in metadata.items()}
                else:
                    metadata = {}

                scripts_dir = skill_path / "scripts"
                script_files = []
                if scripts_dir.exists():
                    script_files = [f.name for f in sorted(scripts_dir.glob("*.py"))]

                self.catalog[name] = SkillMeta(
                    name=name,
                    description=description,
                    path=skill_path,
                    status="discovered",
                    metadata=metadata,
                    scripts=script_files,
                )
            except Exception as e:
                logger.warning("Failed to discover skill '%s': %s", skill_path.name, e)

        logger.info(
            "Discovered %d skill(s): %s",
            len(self.catalog),
            list(self.catalog.keys()),
        )
        return list(self.catalog.values())

    def get_skill_doc(self, name: str) -> str | None:
        """Load SKILL.md body on demand (progressive disclosure Level 2)."""
        skill = self.catalog.get(name)
        if skill is None:
            return None
        if skill.doc_content is None:
            skill_md = skill.path / "SKILL.md"
            if skill_md.exists():
                raw = skill_md.read_text(encoding="utf-8")
                _fm, body = _parse_frontmatter(raw)
                skill.doc_content = body.strip()
        return skill.doc_content

    def get_skill_reference(self, name: str, ref_path: str) -> str | None:
        """Load a reference/asset file on demand (Level 3)."""
        skill = self.catalog.get(name)
        if skill is None:
            return None
        file_path = skill.path / ref_path
        if not file_path.exists() or not file_path.is_file():
            return None
        if not file_path.resolve().is_relative_to(skill.path.resolve()):
            return None
        return file_path.read_text(encoding="utf-8")


_loader = SkillLoader()


def get_skill_loader() -> SkillLoader:
    return _loader

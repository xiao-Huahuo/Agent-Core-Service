"""
Skill indexing and routing service.

Usage:
Scan built-in skills from resources/skills and user skills from the active
knowledge library .agents/skills directory. The service keeps no long-lived
cache; callers can rescan by listing skills after login or knowledge-root
changes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import BACKGROUND_SUMMARY_TASK, LLMTaskScheduler
from agent_service.services.settings_service import SettingsService

SKILL_BODY_MAX_CHARS = 8000
SKILL_ROUTER_MAX_SKILLS = 3


@dataclass(frozen=True, slots=True)
class SkillRecord:
    skill_id: str
    name: str
    description: str
    source: str
    path: Path
    enabled: bool
    metadata: dict[str, Any]
    has_scripts: bool
    has_references: bool
    has_assets: bool

    def to_dict(self, *, include_body: bool = False) -> dict[str, Any]:
        payload = {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "path": str(self.path),
            "enabled": self.enabled,
            "metadata": self.metadata,
            "has_scripts": self.has_scripts,
            "has_references": self.has_references,
            "has_assets": self.has_assets,
        }
        if include_body:
            payload["body"] = self.path.read_text(encoding="utf-8")[:SKILL_BODY_MAX_CHARS]
        return payload


class SkillService:
    """Scan, configure, create, and route Agent skills."""

    def __init__(self, *, config: AgentConfig, settings_service: SettingsService) -> None:
        self.config = config
        self.settings_service = settings_service
        self.builtin_root = config.storage.project_root / "resources" / "skills"

    def list_skills(self, *, user_id: str) -> list[dict[str, Any]]:
        """Return all discoverable skills for the user and active knowledge library."""

        disabled = self._read_disabled_skill_ids(user_id=user_id)
        records = [
            *self._scan_root(root=self.builtin_root, source="builtin", disabled=disabled),
            *self._scan_root(root=self._user_skill_root(user_id=user_id), source="user", disabled=disabled),
        ]
        return [record.to_dict() for record in sorted(records, key=lambda item: (item.source, item.name.lower()))]

    def get_enabled_skill_index(self, *, user_id: str) -> list[dict[str, str]]:
        """Return compact index information injected into the Agent context."""

        return [
            {
                "skill_id": str(skill["skill_id"]),
                "name": str(skill["name"]),
                "description": str(skill.get("description") or ""),
                "source": str(skill["source"]),
            }
            for skill in self.list_skills(user_id=user_id)
            if skill.get("enabled")
        ]

    def read_skill_body(self, *, user_id: str, skill_ref: str) -> dict[str, Any] | None:
        """Return one enabled skill and its SKILL.md body by id, name, or folder name."""

        normalized_ref = str(skill_ref or "").strip().lower()
        if not normalized_ref:
            return None
        for skill in self.list_skills(user_id=user_id):
            candidates = {
                str(skill.get("skill_id") or "").lower(),
                str(skill.get("name") or "").lower(),
                Path(str(skill.get("path") or "")).parent.name.lower(),
            }
            if normalized_ref not in candidates:
                continue
            if not skill.get("enabled"):
                result = dict(skill)
                result["disabled"] = True
                return result
            return self._with_body(skill)
        return None

    def route_skills(
        self,
        *,
        user_id: str,
        prompt: str,
        llm_config: dict[str, Any] | None,
        task_scheduler: LLMTaskScheduler | None,
    ) -> list[dict[str, Any]]:
        """Select up to three enabled skills for the current user input."""

        skills = [skill for skill in self.list_skills(user_id=user_id) if skill.get("enabled")]
        if not skills:
            return []
        selected_ids = self._route_with_small_model(
            prompt=prompt,
            skills=skills,
            llm_config=llm_config,
            task_scheduler=task_scheduler,
        )
        if not selected_ids:
            selected_ids = self._route_by_keywords(prompt=prompt, skills=skills)
        by_id = {str(skill["skill_id"]): skill for skill in skills}
        by_name = {str(skill["name"]).lower(): skill for skill in skills}
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_id in selected_ids:
            key = str(raw_id).strip()
            skill = by_id.get(key) or by_name.get(key.lower())
            if not skill or skill["skill_id"] in seen:
                continue
            seen.add(str(skill["skill_id"]))
            selected.append(self._with_body(skill))
            if len(selected) >= SKILL_ROUTER_MAX_SKILLS:
                break
        return selected

    def set_skill_enabled(self, *, user_id: str, skill_id: str, enabled: bool) -> dict[str, Any]:
        """Persist enabled state for one skill in the user's active knowledge library."""

        config_path = self._user_config_path(user_id=user_id)
        payload = self._read_user_config(config_path)
        disabled = set(str(item) for item in payload.get("disabled_skill_ids", []))
        if enabled:
            disabled.discard(skill_id)
        else:
            disabled.add(skill_id)
        payload["disabled_skill_ids"] = sorted(disabled)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"skill_id": skill_id, "enabled": enabled}

    def create_user_skill(self, *, user_id: str, name: str, description: str, body: str = "") -> dict[str, Any]:
        """Create a user-level skill under the active knowledge library."""

        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Skill name is required")
        root = self._user_skill_root(user_id=user_id)
        root.mkdir(parents=True, exist_ok=True)
        slug = self._slugify(clean_name)
        skill_dir = root / slug
        counter = 2
        while skill_dir.exists():
            skill_dir = root / f"{slug}-{counter}"
            counter += 1
        skill_dir.mkdir(parents=True, exist_ok=False)
        content = (
            "---\n"
            f"name: {clean_name}\n"
            f"description: {description.strip()}\n"
            "---\n\n"
            f"{body.strip()}\n"
        )
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(content, encoding="utf-8")
        record = self._read_skill(skill_path=skill_path, source="user", disabled=set())
        if record is None:
            raise ValueError("Created skill could not be read")
        return record.to_dict(include_body=True)

    def spec_text(self) -> str:
        """Return a concise Skill authoring specification for the UI."""

        return (
            "Skill must be an independent directory with a required SKILL.md file. "
            "The recommended structure is SKILL.md plus optional references/, scripts/, assets/, and templates/. "
            "SKILL.md should start with YAML frontmatter containing name and description. "
            "The body should describe when to use the skill, required workflow, and which local files to read next. "
            "This project follows the OpenAI Skill style as the main standard and accepts Anthropic-style optional fields."
        )

    def _route_with_small_model(
        self,
        *,
        prompt: str,
        skills: Sequence[dict[str, Any]],
        llm_config: dict[str, Any] | None,
        task_scheduler: LLMTaskScheduler | None,
    ) -> list[str]:
        if task_scheduler is None or not llm_config:
            return []
        api_key = self._normalize(llm_config.get("small_api_key")) or self._normalize(llm_config.get("api_key"))
        base_url = self._normalize(llm_config.get("small_base_url")) or self._normalize(llm_config.get("base_url"))
        model_name = self._normalize(llm_config.get("small_model_name")) or self._normalize(llm_config.get("model_name"))
        if not api_key or not model_name:
            return []
        catalog = "\n".join(
            f"- skill_id: {skill['skill_id']}\n  name: {skill['name']}\n  description: {skill.get('description') or ''}"
            for skill in skills
        )
        messages = [
            SystemMessage(
                content=(
                    "You are a skill router. Select at most 3 skills useful for the user input. "
                    "Return strict JSON only: {\"skills\":[\"skill_id\"]}. Return an empty list if none match."
                )
            ),
            HumanMessage(content=f"User input:\n{prompt}\n\nAvailable skills:\n{catalog}"),
        ]
        try:
            response = task_scheduler.invoke_chat(
                task_type=BACKGROUND_SUMMARY_TASK,
                messages=messages,
                tool_names=[],
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                small_api_key=api_key,
                small_base_url=base_url,
                small_model_name=model_name,
            )
            text = str(getattr(response, "content", "") or "")
            parsed = json.loads(self._strip_json_fence(text))
            selected = parsed.get("skills")
            if isinstance(selected, list):
                return [str(item) for item in selected[:SKILL_ROUTER_MAX_SKILLS]]
        except Exception:
            return []
        return []

    def _route_by_keywords(self, *, prompt: str, skills: Sequence[dict[str, Any]]) -> list[str]:
        text = prompt.lower()
        scored: list[tuple[int, str]] = []
        for skill in skills:
            name = str(skill.get("name") or "").lower()
            description = str(skill.get("description") or "").lower()
            score = 0
            if name and name in text:
                score += 8
            for token in self._tokens(name) + self._tokens(description):
                if len(token) >= 2 and token in text:
                    score += 1
            if score > 0:
                scored.append((score, str(skill["skill_id"])))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [skill_id for _, skill_id in scored[:SKILL_ROUTER_MAX_SKILLS]]

    def _scan_root(self, *, root: Path, source: str, disabled: set[str]) -> list[SkillRecord]:
        if not root.exists() or not root.is_dir():
            return []
        records: list[SkillRecord] = []
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir():
                continue
            record = self._read_skill(skill_path=child / "SKILL.md", source=source, disabled=disabled)
            if record is not None:
                records.append(record)
        return records

    def _read_skill(self, *, skill_path: Path, source: str, disabled: set[str]) -> SkillRecord | None:
        if not skill_path.exists() or not skill_path.is_file():
            return None
        text = skill_path.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(text)
        name = str(metadata.get("name") or skill_path.parent.name).strip()
        description = str(metadata.get("description") or "").strip()
        skill_id = f"{source}:{skill_path.parent.name}"
        skill_dir = skill_path.parent
        return SkillRecord(
            skill_id=skill_id,
            name=name,
            description=description,
            source=source,
            path=skill_path,
            enabled=skill_id not in disabled,
            metadata=metadata,
            has_scripts=(skill_dir / "scripts").is_dir(),
            has_references=(skill_dir / "references").is_dir(),
            has_assets=(skill_dir / "assets").is_dir(),
        )

    @staticmethod
    def _parse_frontmatter(text: str) -> dict[str, Any]:
        if not text.startswith("---"):
            return {}
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}
        metadata: dict[str, Any] = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            raw_value = value.strip().strip('"').strip("'")
            if not key:
                continue
            if raw_value.lower() in {"true", "false"}:
                metadata[key] = raw_value.lower() == "true"
            elif raw_value.startswith("[") and raw_value.endswith("]"):
                metadata[key] = [item.strip().strip('"').strip("'") for item in raw_value[1:-1].split(",") if item.strip()]
            else:
                metadata[key] = raw_value
        return metadata

    def _with_body(self, skill: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(skill["path"]))
        payload = dict(skill)
        payload["body"] = path.read_text(encoding="utf-8")[:SKILL_BODY_MAX_CHARS]
        return payload

    def _read_disabled_skill_ids(self, *, user_id: str) -> set[str]:
        payload = self._read_user_config(self._user_config_path(user_id=user_id))
        return set(str(item) for item in payload.get("disabled_skill_ids", []))

    @staticmethod
    def _read_user_config(config_path: Path) -> dict[str, Any]:
        if not config_path.exists():
            return {}
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _user_skill_root(self, *, user_id: str) -> Path:
        return self._active_knowledge_dir(user_id=user_id) / ".agents" / "skills"

    def _user_config_path(self, *, user_id: str) -> Path:
        return self._active_knowledge_dir(user_id=user_id) / ".agents" / "skills_config.json"

    def _active_knowledge_dir(self, *, user_id: str) -> Path:
        library = self.settings_service.get_active_knowledge_library(user_id=user_id)
        path = str(library.get("knowledge_dir") or "").strip()
        if path:
            return Path(path)
        profile = self.settings_service.ensure_user_profile(user_id)
        fallback = profile.get("knowledge_dir") or self.config.storage.knowledge_dir
        return Path(str(fallback))

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
        return slug or "skill"

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [token for token in re.split(r"[^0-9a-zA-Z_\u4e00-\u9fff]+", text.lower()) if token]

    @staticmethod
    def _normalize(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _strip_json_fence(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
            stripped = re.sub(r"```$", "", stripped).strip()
        return stripped

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
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import BACKGROUND_SUMMARY_TASK, LLMTaskScheduler
from agent_service.services.settings.service import SettingsService

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

    def to_dict(self, *, include_body: bool = False, body_max_chars: int | None = None) -> dict[str, Any]:
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
            payload["body"] = self.path.read_text(encoding="utf-8")[:body_max_chars]
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
        """Return compact index information for management views and explicit listing."""

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

    def select_skill_candidates(
        self,
        *,
        user_id: str,
        prompt: str,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """Return a small prompt-matched skill index for the current Agent turn."""

        skills = [skill for skill in self.list_skills(user_id=user_id) if skill.get("enabled")]
        ranked = self._rank_skills_by_prompt(prompt=prompt, skills=skills)
        candidates: list[dict[str, str]] = []
        candidate_limit = self.config.limits.skill_router_candidate_limit if limit is None else limit
        for _, skill in ranked[: max(0, candidate_limit)]:
            candidates.append(self._to_compact_index(skill))
        return candidates

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
        candidate_skills: Sequence[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Select up to three enabled skills for the current user input."""

        skills = self._resolve_route_candidates(user_id=user_id, prompt=prompt, candidate_skills=candidate_skills)
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
            if len(selected) >= self.config.limits.skill_router_max_skills:
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
        return record.to_dict(
            include_body=True,
            body_max_chars=self.config.limits.skill_body_max_chars,
        )

    def update_user_skill(
        self,
        *,
        user_id: str,
        skill_id: str,
        name: str | None = None,
        description: str | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        """更新用户 Skill 的 SKILL.md；内置 Skill 不允许修改。"""

        skill_path = self._require_user_skill_path(user_id=user_id, skill_id=skill_id)
        current = skill_path.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(current)
        current_body = self._body_without_frontmatter(current)
        next_name = str(name if name is not None else metadata.get("name") or skill_path.parent.name).strip()
        next_description = str(description if description is not None else metadata.get("description") or "").strip()
        next_body = str(body if body is not None else current_body).strip()
        if not next_name:
            raise ValueError("Skill name is required")
        skill_path.write_text(
            f"---\nname: {next_name}\ndescription: {next_description}\n---\n\n{next_body}\n",
            encoding="utf-8",
        )
        record = self._read_skill(skill_path=skill_path, source="user", disabled=self._read_disabled_skill_ids(user_id=user_id))
        if record is None:
            raise ValueError("Updated skill could not be read")
        return record.to_dict(
            include_body=True,
            body_max_chars=self.config.limits.skill_body_max_chars,
        )

    def delete_user_skill(self, *, user_id: str, skill_id: str) -> dict[str, Any]:
        """删除用户 Skill 目录，并清理其禁用配置项。"""

        skill_path = self._require_user_skill_path(user_id=user_id, skill_id=skill_id)
        skill_dir = skill_path.parent.resolve()
        root = self._user_skill_root(user_id=user_id).resolve()
        if skill_dir.parent != root:
            raise ValueError("skill path escapes user skill root")
        shutil.rmtree(skill_dir)
        config_path = self._user_config_path(user_id=user_id)
        payload = self._read_user_config(config_path)
        disabled = {str(item) for item in payload.get("disabled_skill_ids", [])}
        if skill_id in disabled:
            disabled.discard(skill_id)
            payload["disabled_skill_ids"] = sorted(disabled)
            config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"skill_id": skill_id, "deleted": True}

    def validate_user_skill(self, *, user_id: str, skill_id: str) -> dict[str, Any]:
        """校验用户 Skill 的目录、frontmatter 和正文是否可被路由器读取。"""

        skill_path = self._require_user_skill_path(user_id=user_id, skill_id=skill_id)
        text = skill_path.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(text)
        errors: list[str] = []
        if not text.startswith("---"):
            errors.append("SKILL.md 缺少 YAML frontmatter")
        if not str(metadata.get("name") or "").strip():
            errors.append("frontmatter 缺少 name")
        if not str(metadata.get("description") or "").strip():
            errors.append("frontmatter 缺少 description")
        if not self._body_without_frontmatter(text).strip():
            errors.append("Skill 正文为空")
        record = self._read_skill(skill_path=skill_path, source="user", disabled=set())
        if record is None:
            errors.append("Skill 无法被索引器读取")
        return {"skill_id": skill_id, "valid": not errors, "errors": errors}

    def test_user_skill(self, *, user_id: str, skill_id: str, prompt: str) -> dict[str, Any]:
        """以真实关键词路由器测试指定 Skill 是否能响应给定用户提示。"""

        validation = self.validate_user_skill(user_id=user_id, skill_id=skill_id)
        skills = [skill for skill in self.list_skills(user_id=user_id) if str(skill.get("skill_id")) == skill_id]
        ranked = self._rank_skills_by_prompt(prompt=prompt, skills=skills)
        return {
            **validation,
            "prompt": prompt,
            "matched": bool(ranked),
            "score": ranked[0][0] if ranked else 0,
        }

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
        system_prompt = self.config.prompts.skill_router_system_prompt.format(
            max_skills=self.config.limits.skill_router_max_skills
        )
        messages = [
            SystemMessage(content=system_prompt),
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
                return [str(item) for item in selected[:self.config.limits.skill_router_max_skills]]
        except Exception:
            return []
        return []

    def _route_by_keywords(self, *, prompt: str, skills: Sequence[dict[str, Any]]) -> list[str]:
        ranked = self._rank_skills_by_prompt(prompt=prompt, skills=skills)
        return [
            str(skill["skill_id"])
            for _, skill in ranked[:self.config.limits.skill_router_max_skills]
        ]

    def _resolve_route_candidates(
        self,
        *,
        user_id: str,
        prompt: str,
        candidate_skills: Sequence[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        if candidate_skills:
            candidate_ids = {str(skill.get("skill_id") or "") for skill in candidate_skills}
            return [
                skill
                for skill in self.list_skills(user_id=user_id)
                if skill.get("enabled") and str(skill.get("skill_id") or "") in candidate_ids
            ]
        skills = [skill for skill in self.list_skills(user_id=user_id) if skill.get("enabled")]
        return [
            skill
            for _, skill in self._rank_skills_by_prompt(prompt=prompt, skills=skills)[
                :self.config.limits.skill_router_candidate_limit
            ]
        ]

    def _rank_skills_by_prompt(
        self,
        *,
        prompt: str,
        skills: Sequence[dict[str, Any]],
    ) -> list[tuple[int, dict[str, Any]]]:
        text = prompt.lower()
        prompt_tokens = set(self._tokens(text))
        scored: list[tuple[int, dict[str, Any]]] = []
        for skill in skills:
            searchable = self._searchable_skill_text(skill).lower()
            score = 0
            name = str(skill.get("name") or "").lower()
            if name and name in text:
                score += 12
            for token in self._tokens(searchable):
                if len(token) < 2:
                    continue
                if token in prompt_tokens:
                    score += 3
                elif token in text:
                    score += 1
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda item: (-item[0], str(item[1].get("source") or ""), str(item[1].get("name") or "").lower()))
        return scored

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
        payload["body"] = path.read_text(encoding="utf-8")[:self.config.limits.skill_body_max_chars]
        return payload

    @staticmethod
    def _to_compact_index(skill: dict[str, Any]) -> dict[str, str]:
        description = str(skill.get("description") or "")
        max_chars = self.config.limits.skill_index_description_max_chars
        if len(description) > max_chars:
            description = description[:max_chars].rstrip() + "..."
        return {
            "skill_id": str(skill["skill_id"]),
            "name": str(skill["name"]),
            "description": description,
            "source": str(skill["source"]),
        }

    @staticmethod
    def _searchable_skill_text(skill: dict[str, Any]) -> str:
        metadata = skill.get("metadata") if isinstance(skill.get("metadata"), dict) else {}
        parts = [
            str(skill.get("skill_id") or ""),
            str(skill.get("name") or ""),
            str(skill.get("description") or ""),
        ]
        for key in ("keywords", "triggers", "aliases", "tags"):
            value = metadata.get(key)
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
            elif value:
                parts.append(str(value))
        return " ".join(parts)

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

    def _require_user_skill_path(self, *, user_id: str, skill_id: str) -> Path:
        """解析并验证 user:* Skill 的受管 SKILL.md 路径。"""

        normalized = str(skill_id or "").strip()
        if not normalized.startswith("user:"):
            raise ValueError("only user skills can be modified")
        folder = normalized.split(":", 1)[1]
        root = self._user_skill_root(user_id=user_id).resolve()
        skill_path = (root / folder / "SKILL.md").resolve()
        if skill_path.parent.parent != root or not skill_path.is_file():
            raise ValueError("user skill not found")
        return skill_path

    @staticmethod
    def _body_without_frontmatter(text: str) -> str:
        """移除首段 YAML frontmatter 并返回 Skill 正文。"""

        if not text.startswith("---"):
            return text
        parts = text.split("---", 2)
        return parts[2].lstrip() if len(parts) == 3 else ""

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
        """拆分英文词，并为连续中文补充二元词以支持自然句子匹配。"""

        raw_tokens = [token for token in re.split(r"[^0-9a-zA-Z_\u4e00-\u9fff]+", text.lower()) if token]
        tokens = list(raw_tokens)
        for token in raw_tokens:
            if len(token) > 2 and re.fullmatch(r"[\u4e00-\u9fff]+", token):
                tokens.extend(token[index:index + 2] for index in range(len(token) - 1))
        return tokens

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

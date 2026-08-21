"""
Knowledge-library component file service.

Usage:
Lists and creates Vue SFC or standalone HTML files below the active user's
<knowledge_dir>/.mw/components directory. Tags are represented by direct child
directories, so component business data has no database or manifest copy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.services.settings_service import SettingsService

COMPONENT_TAGS = (
    "buttons",
    "checkboxes",
    "toggle switches",
    "cards",
    "loaders",
    "inputs",
    "radio buttons",
    "forms",
    "patterns",
    "tooltips",
    "any",
)
COMPONENTS_DIRECTORY_NAME = ".mw/components"
SUPPORTED_COMPONENT_SUFFIXES = {".vue", ".html", ".htm"}


class ComponentLibraryService:
    """Manage component files inside each user's active knowledge library."""

    def __init__(self, *, settings_service: SettingsService, legacy_engine: Engine | None = None) -> None:
        """Retain the active-library resolver and optional one-time legacy source."""

        self.settings_service = settings_service
        self.legacy_engine = legacy_engine
        self.limits = getattr(getattr(settings_service, "config", None), "limits", DEFAULT_BUSINESS_LIMITS)

    def list_components(self, *, user_id: str, tag: str = "any") -> dict[str, object]:
        """Read supported UTF-8 source files from the active components directory."""

        normalized_user_id = self._require_user_id(user_id)
        normalized_tag = self._require_tag(tag)
        components_root = self._components_root(user_id=normalized_user_id)
        self._migrate_legacy_components(user_id=normalized_user_id)
        if not components_root.is_dir():
            return {"components": [], "tags": list(COMPONENT_TAGS)}

        components: list[dict[str, object]] = []
        for path in sorted(components_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED_COMPONENT_SUFFIXES:
                continue
            relative_path = path.relative_to(components_root)
            component_tag = self._tag_from_relative_path(relative_path)
            if normalized_tag != "any" and component_tag != normalized_tag:
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if (
                not source.strip()
                or len(source) > self.limits.component_source_max_length
            ):
                continue
            components.append(
                self._file_to_dict(
                    path=path,
                    relative_path=relative_path,
                    user_id=normalized_user_id,
                    tag=component_tag,
                    source=source,
                )
            )
        components.sort(key=lambda component: str(component["title"]).casefold())
        return {"components": components, "tags": list(COMPONENT_TAGS)}

    def create_component(
        self,
        *,
        user_id: str,
        source: str,
        tag: str,
        filename: str = "",
    ) -> dict[str, object]:
        """Validate and atomically write one component source file."""

        normalized_user_id = self._require_user_id(user_id)
        normalized_tag = self._require_tag(tag)
        normalized_source = str(source or "").strip()
        if not normalized_source:
            raise ValueError("component source is required")
        if len(normalized_source) > self.limits.component_source_max_length:
            raise ValueError("component source is too large")

        source_format = "vue" if "<template" in normalized_source.casefold() else "html"
        safe_filename = self._safe_filename(filename=filename, source_format=source_format)
        tag_dir = self._components_root(user_id=normalized_user_id) / normalized_tag
        tag_dir.mkdir(parents=True, exist_ok=True)
        target = self._unique_path(directory=tag_dir, filename=safe_filename)
        temp_path = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            temp_path.write_text(normalized_source, encoding="utf-8", newline="\n")
            temp_path.replace(target)
        finally:
            temp_path.unlink(missing_ok=True)

        relative_path = target.relative_to(self._components_root(user_id=normalized_user_id))
        return {
            "component": self._file_to_dict(
                path=target,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=normalized_tag,
                source=normalized_source,
            )
        }

    def rename_component(self, *, user_id: str, component_id: str, title: str) -> dict[str, object]:
        """Move one canonical component file while retaining tag, source, and suffix."""

        normalized_user_id = self._require_user_id(user_id)
        components_root = self._components_root(user_id=normalized_user_id)
        source_path = self._component_path(components_root=components_root, component_id=component_id)
        raw_title = str(title or "").strip()
        supplied_suffix = Path(raw_title).suffix.casefold()
        title_stem = Path(raw_title).stem if supplied_suffix in SUPPORTED_COMPONENT_SUFFIXES else raw_title
        safe_filename = self._safe_filename(
            filename=f"{title_stem}{source_path.suffix.casefold()}",
            source_format="vue" if source_path.suffix.casefold() == ".vue" else "html",
        )
        target = source_path.with_name(safe_filename)
        if target != source_path:
            target = self._unique_path(directory=source_path.parent, filename=safe_filename)
            source_path.replace(target)
        relative_path = target.relative_to(components_root)
        source = target.read_text(encoding="utf-8")
        return {
            "component": self._file_to_dict(
                path=target,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=self._tag_from_relative_path(relative_path),
                source=source,
            )
        }

    def get_component(self, *, user_id: str, component_id: str) -> dict[str, object]:
        """读取一个组件的完整源码与元数据。"""

        normalized_user_id = self._require_user_id(user_id)
        root = self._components_root(user_id=normalized_user_id)
        path = self._component_path(components_root=root, component_id=component_id)
        relative_path = path.relative_to(root)
        return {
            "component": self._file_to_dict(
                path=path,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=self._tag_from_relative_path(relative_path),
                source=path.read_text(encoding="utf-8"),
            )
        }

    def update_component(
        self,
        *,
        user_id: str,
        component_id: str,
        source: str | None = None,
        tag: str | None = None,
        title: str | None = None,
    ) -> dict[str, object]:
        """增量更新组件源码、分类或标题，并保持单文件规范存储。"""

        normalized_user_id = self._require_user_id(user_id)
        root = self._components_root(user_id=normalized_user_id)
        path = self._component_path(components_root=root, component_id=component_id)
        next_source = path.read_text(encoding="utf-8") if source is None else str(source).strip()
        if not next_source:
            raise ValueError("component source is required")
        if len(next_source) > self.limits.component_source_max_length:
            raise ValueError("component source is too large")
        next_tag = self._tag_from_relative_path(path.relative_to(root)) if tag is None else self._require_tag(tag)
        next_title = path.stem if title is None else str(title).strip()
        if not next_title:
            raise ValueError("component title is required")
        suffix = path.suffix.casefold()
        filename = self._safe_filename(
            filename=f"{Path(next_title).stem}{suffix}",
            source_format="vue" if suffix == ".vue" else "html",
        )
        target_dir = root / next_tag
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        if target.resolve() != path.resolve() and target.exists():
            target = self._unique_path(directory=target_dir, filename=filename)
        temp_path = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            temp_path.write_text(next_source, encoding="utf-8", newline="\n")
            temp_path.replace(target)
            if target.resolve() != path.resolve():
                path.unlink()
        finally:
            temp_path.unlink(missing_ok=True)
        relative_path = target.relative_to(root)
        return {
            "component": self._file_to_dict(
                path=target,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=next_tag,
                source=next_source,
            )
        }

    def delete_component(self, *, user_id: str, component_id: str) -> dict[str, object]:
        """删除一个用户组件文件并返回稳定标识。"""

        normalized_user_id = self._require_user_id(user_id)
        root = self._components_root(user_id=normalized_user_id)
        path = self._component_path(components_root=root, component_id=component_id)
        path.unlink()
        return {"component_id": component_id, "deleted": True}

    def validate_component(self, *, user_id: str, component_id: str) -> dict[str, object]:
        """校验持久化组件的格式、大小及 Vue/HTML 基本结构。"""

        payload = self.get_component(user_id=user_id, component_id=component_id)
        component = dict(payload["component"])
        source = str(component.get("source") or "")
        source_format = str(component.get("source_format") or "")
        errors: list[str] = []
        if not source.strip():
            errors.append("组件源码为空")
        if len(source) > self.limits.component_source_max_length:
            errors.append("组件源码超过大小限制")
        if source_format == "vue":
            if not re.search(r"<template(?:\s[^>]*)?>", source, flags=re.IGNORECASE):
                errors.append("Vue SFC 缺少 <template>")
            if not re.search(r"</template\s*>", source, flags=re.IGNORECASE):
                errors.append("Vue SFC 缺少 </template>")
        elif not re.search(r"<[^>]+>", source):
            errors.append("HTML 组件不包含有效标签")
        return {"component_id": component_id, "valid": not errors, "errors": errors}

    def _migrate_legacy_components(self, *, user_id: str) -> None:
        """Move obsolete SQLite source rows to files, deleting rows only after success."""

        if self.legacy_engine is None or not inspect(self.legacy_engine).has_table("component_library_items"):
            return
        with self.legacy_engine.begin() as connection:
            records = connection.execute(
                text(
                    "SELECT component_id, title, tag, source_format, source "
                    "FROM component_library_items WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            ).mappings().all()
            migrated_ids: list[str] = []
            for record in records:
                source = str(record["source"] or "")
                if not source.strip() or len(source) > self.limits.component_source_max_length:
                    continue
                tag = str(record["tag"] or "any").casefold()
                if tag not in COMPONENT_TAGS:
                    tag = "any"
                suffix = ".vue" if str(record["source_format"] or "").casefold() == "vue" else ".html"
                title = Path(str(record["title"] or "component")).name or "component"
                try:
                    self.create_component(
                        user_id=user_id,
                        source=source,
                        tag=tag,
                        filename=f"{title}{suffix}",
                    )
                except (OSError, ValueError):
                    continue
                migrated_ids.append(str(record["component_id"]))
            for component_id in migrated_ids:
                connection.execute(
                    text("DELETE FROM component_library_items WHERE component_id = :component_id"),
                    {"component_id": component_id},
                )

    def _components_root(self, *, user_id: str) -> Path:
        """Resolve the application-managed directory below the active knowledge root."""

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        knowledge_root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        components_root = (knowledge_root / COMPONENTS_DIRECTORY_NAME).resolve()
        legacy_root = (knowledge_root / "components").resolve()
        if legacy_root.is_dir() and legacy_root != components_root:
            components_root.mkdir(parents=True, exist_ok=True)
            for child in legacy_root.iterdir():
                destination = components_root / child.name
                if destination.exists():
                    raise ValueError(f"managed components already contain: {child.name}")
            for child in legacy_root.iterdir():
                shutil.move(str(child), str(components_root / child.name))
        return components_root

    @staticmethod
    def _component_path(*, components_root: Path, component_id: str) -> Path:
        """Resolve one existing supported component without permitting path escape."""

        raw_component_id = str(component_id or "").strip()
        if not raw_component_id or "\\" in raw_component_id:
            raise ValueError("component_id is invalid")
        candidate = (components_root / raw_component_id).resolve()
        try:
            candidate.relative_to(components_root)
        except ValueError as exc:
            raise ValueError("component_id is invalid") from exc
        if not candidate.is_file() or candidate.suffix.casefold() not in SUPPORTED_COMPONENT_SUFFIXES:
            raise FileNotFoundError("component not found")
        return candidate

    @staticmethod
    def _file_to_dict(
        *,
        path: Path,
        relative_path: Path,
        user_id: str,
        tag: str,
        source: str,
    ) -> dict[str, Any]:
        """Serialize one source file into the shared REST/gRPC/UI item shape."""

        stat = path.stat()
        return {
            "component_id": relative_path.as_posix(),
            "user_id": user_id,
            "title": path.stem,
            "tag": tag,
            "source_format": "vue" if path.suffix.casefold() == ".vue" else "html",
            "source": source,
            "builtin": False,
            "created_at": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    def _safe_filename(self, *, filename: str, source_format: str) -> str:
        """Return a safe supported basename or generate one for pasted source."""

        raw_name = str(filename or "").strip()
        if raw_name and (Path(raw_name).name != raw_name or "/" in raw_name or "\\" in raw_name):
            raise ValueError("component file name must not contain a directory")
        if not raw_name:
            suffix = ".vue" if source_format == "vue" else ".html"
            return f"component-{uuid4().hex[:self.limits.checksum_short_chars]}{suffix}"
        suffix = Path(raw_name).suffix.casefold()
        if suffix not in SUPPORTED_COMPONENT_SUFFIXES:
            raise ValueError("supported component file extensions are .vue, .html, and .htm")
        safe_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", Path(raw_name).stem).strip(" .")
        if not safe_stem:
            raise ValueError("component file name is required")
        return f"{safe_stem[:self.limits.component_filename_max_length]}{suffix}"

    @staticmethod
    def _unique_path(*, directory: Path, filename: str) -> Path:
        """Avoid overwriting an existing component by adding a numeric suffix."""

        candidate = directory / filename
        if not candidate.exists():
            return candidate
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        index = 2
        while True:
            candidate = directory / f"{stem}-{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    @staticmethod
    def _tag_from_relative_path(relative_path: Path) -> str:
        """Infer the single tag from the first directory below components."""

        first = relative_path.parts[0].casefold() if len(relative_path.parts) > 1 else "any"
        return first if first in COMPONENT_TAGS else "any"

    @staticmethod
    def _require_user_id(user_id: str) -> str:
        """Reject anonymous filesystem access."""

        normalized = str(user_id or "").strip()
        if not normalized:
            raise ValueError("user_id is required")
        return normalized

    @staticmethod
    def _require_tag(tag: str) -> str:
        """Return a supported lowercase tag or raise a domain validation error."""

        normalized = str(tag or "").strip().casefold()
        if normalized not in COMPONENT_TAGS:
            raise ValueError(f"unsupported component tag: {tag}")
        return normalized

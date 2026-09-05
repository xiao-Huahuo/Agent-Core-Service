"""
Knowledge-library component file service.

Usage:
Lists and creates Vue SFC, standalone HTML, and raw drawing-script files below
the active user's <knowledge_dir>/.mw/components directory. Drawing language
and optional cover relationships use the component metadata database table.
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
from sqlmodel import Session, select

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.models.component_library import ComponentLibraryMetadata
from agent_service.models.library import LibraryAsset
from agent_service.models.session import utc_now
from agent_service.services.settings.service import SettingsService

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
    "drawing scripts",
    "any",
)
COMPONENTS_DIRECTORY_NAME = ".mw/components"
DRAWING_SCRIPT_TAG = "drawing scripts"
SCRIPT_COMPONENT_SUFFIX = ".script"
SUPPORTED_COMPONENT_SUFFIXES = {".vue", ".html", ".htm", SCRIPT_COMPONENT_SUFFIX}


class ComponentLibraryService:
    """Manage component files inside each user's active knowledge library."""

    def __init__(self, *, settings_service: SettingsService, legacy_engine: Engine | None = None) -> None:
        """Retain the active-library resolver and optional one-time legacy source."""

        self.settings_service = settings_service
        self.legacy_engine = legacy_engine
        self.engine = legacy_engine
        self.limits = getattr(getattr(settings_service, "config", None), "limits", DEFAULT_BUSINESS_LIMITS)

    def list_components(self, *, user_id: str, tag: str = "any") -> dict[str, object]:
        """Read supported UTF-8 source files from the active components directory."""

        normalized_user_id = self._require_user_id(user_id)
        normalized_tag = self._require_tag(tag)
        components_root = self._components_root(user_id=normalized_user_id)
        self._migrate_legacy_components(user_id=normalized_user_id)
        if not components_root.is_dir():
            return {"components": [], "tags": list(COMPONENT_TAGS)}
        drawing_metadata = self._drawing_metadata_by_component(user_id=normalized_user_id)

        components: list[dict[str, object]] = []
        for path in sorted(components_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED_COMPONENT_SUFFIXES:
                continue
            relative_path = path.relative_to(components_root)
            component_tag = self._tag_from_relative_path(relative_path)
            if path.suffix.casefold() == SCRIPT_COMPONENT_SUFFIX and component_tag != DRAWING_SCRIPT_TAG:
                continue
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
            metadata, asset = drawing_metadata.get(relative_path.as_posix(), (None, None))
            if path.suffix.casefold() == SCRIPT_COMPONENT_SUFFIX and metadata is None:
                continue
            components.append(self._file_to_dict(
                path=path,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=component_tag,
                source=source,
                metadata=metadata,
                cover_asset=asset,
            ))
        components.sort(key=lambda component: str(component["title"]).casefold())
        return {"components": components, "tags": list(COMPONENT_TAGS)}

    def create_component(
        self,
        *,
        user_id: str,
        source: str,
        tag: str,
        filename: str = "",
        script_language: str = "",
        cover_asset_id: str = "",
    ) -> dict[str, object]:
        """Validate and atomically write one component source file."""

        normalized_user_id = self._require_user_id(user_id)
        normalized_tag = self._require_tag(tag)
        normalized_source = str(source or "").strip()
        if not normalized_source:
            raise ValueError("component source is required")
        if len(normalized_source) > self.limits.component_source_max_length:
            raise ValueError("component source is too large")

        source_format = "script" if normalized_tag == DRAWING_SCRIPT_TAG else (
            "vue" if "<template" in normalized_source.casefold() else "html"
        )
        normalized_language = self._require_script_language(script_language) if source_format == "script" else ""
        if source_format != "script" and (str(script_language).strip() or str(cover_asset_id).strip()):
            raise ValueError("script metadata is only supported for drawing scripts")
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
        metadata = None
        cover_asset = None
        if source_format == "script":
            try:
                metadata, cover_asset = self._create_drawing_metadata(
                    user_id=normalized_user_id,
                    component_id=relative_path.as_posix(),
                    script_language=normalized_language,
                    cover_asset_id=str(cover_asset_id or "").strip(),
                )
            except Exception:
                target.unlink(missing_ok=True)
                raise
        return {
            "component": self._file_to_dict(
                path=target,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=normalized_tag,
                source=normalized_source,
                metadata=metadata,
                cover_asset=cover_asset,
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
            source_format=self._source_format(source_path),
        )
        target = source_path.with_name(safe_filename)
        if target != source_path:
            target = self._unique_path(directory=source_path.parent, filename=safe_filename)
            source_path.replace(target)
        relative_path = target.relative_to(components_root)
        if target.suffix.casefold() == SCRIPT_COMPONENT_SUFFIX:
            try:
                self._update_drawing_metadata(
                    user_id=normalized_user_id,
                    component_id=component_id,
                    next_component_id=relative_path.as_posix(),
                )
            except Exception:
                if target != source_path:
                    target.replace(source_path)
                raise
        source = target.read_text(encoding="utf-8")
        metadata, asset = self._drawing_metadata_by_component(user_id=normalized_user_id).get(
            relative_path.as_posix(), (None, None),
        )
        return {
            "component": self._file_to_dict(
                path=target,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=self._tag_from_relative_path(relative_path),
                source=source,
                metadata=metadata,
                cover_asset=asset,
            )
        }

    def get_component(self, *, user_id: str, component_id: str) -> dict[str, object]:
        """读取一个组件的完整源码与元数据。"""

        normalized_user_id = self._require_user_id(user_id)
        root = self._components_root(user_id=normalized_user_id)
        path = self._component_path(components_root=root, component_id=component_id)
        relative_path = path.relative_to(root)
        metadata, asset = self._drawing_metadata_by_component(user_id=normalized_user_id).get(
            relative_path.as_posix(), (None, None),
        )
        return {
            "component": self._file_to_dict(
                path=path,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=self._tag_from_relative_path(relative_path),
                source=path.read_text(encoding="utf-8"),
                metadata=metadata,
                cover_asset=asset,
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
        script_language: str | None = None,
        cover_asset_id: str | None = None,
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
        is_script = path.suffix.casefold() == SCRIPT_COMPONENT_SUFFIX
        if is_script != (next_tag == DRAWING_SCRIPT_TAG):
            raise ValueError("drawing scripts cannot be converted to or from preview components")
        if not is_script and (script_language is not None or cover_asset_id is not None):
            raise ValueError("script metadata is only supported for drawing scripts")
        next_title = path.stem if title is None else str(title).strip()
        if not next_title:
            raise ValueError("component title is required")
        suffix = path.suffix.casefold()
        filename = self._safe_filename(
            filename=f"{Path(next_title).stem}{suffix}",
            source_format=self._source_format(path),
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
        metadata = None
        asset = None
        if is_script:
            metadata, asset = self._update_drawing_metadata(
                user_id=normalized_user_id,
                component_id=component_id,
                next_component_id=relative_path.as_posix(),
                script_language=script_language,
                cover_asset_id=cover_asset_id,
            )
        return {
            "component": self._file_to_dict(
                path=target,
                relative_path=relative_path,
                user_id=normalized_user_id,
                tag=next_tag,
                source=next_source,
                metadata=metadata,
                cover_asset=asset,
            )
        }

    def delete_component(self, *, user_id: str, component_id: str) -> dict[str, object]:
        """删除一个用户组件文件并返回稳定标识。"""

        normalized_user_id = self._require_user_id(user_id)
        root = self._components_root(user_id=normalized_user_id)
        path = self._component_path(components_root=root, component_id=component_id)
        path.unlink()
        if path.suffix.casefold() == SCRIPT_COMPONENT_SUFFIX:
            self._delete_drawing_metadata(user_id=normalized_user_id, component_id=component_id)
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
        if source_format == "script":
            if not str(component.get("script_language") or "").strip():
                errors.append("绘图脚本缺少脚本语言")
        elif source_format == "vue":
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
        metadata: ComponentLibraryMetadata | None = None,
        cover_asset: LibraryAsset | None = None,
    ) -> dict[str, Any]:
        """Serialize one source file into the shared REST/gRPC/UI item shape."""

        stat = path.stat()
        return {
            "component_id": relative_path.as_posix(),
            "user_id": user_id,
            "title": path.stem,
            "tag": tag,
            "source_format": ComponentLibraryService._source_format(path),
            "source": source,
            "builtin": False,
            "script_language": metadata.script_language if metadata else "",
            "cover_asset_id": metadata.cover_asset_id if metadata else "",
            "cover_asset": ComponentLibraryService._serialize_cover_asset(cover_asset),
            "created_at": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    def _drawing_metadata_by_component(
        self,
        *,
        user_id: str,
    ) -> dict[str, tuple[ComponentLibraryMetadata, LibraryAsset | None]]:
        """Load drawing metadata and cover assets for the active knowledge library."""

        if self.engine is None or not inspect(self.engine).has_table("component_library_metadata"):
            return {}
        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        library_id = str(dict(profile["active_knowledge_library"])["library_id"])
        with Session(self.engine, expire_on_commit=False) as db:
            records = list(db.exec(select(ComponentLibraryMetadata).where(
                ComponentLibraryMetadata.user_id == user_id,
                ComponentLibraryMetadata.library_id == library_id,
            )).all())
            assets = {
                asset_id: db.get(LibraryAsset, asset_id)
                for asset_id in {record.cover_asset_id for record in records if record.cover_asset_id}
            }
            return {
                record.component_id: (record, assets.get(record.cover_asset_id))
                for record in records
            }

    def _create_drawing_metadata(
        self,
        *,
        user_id: str,
        component_id: str,
        script_language: str,
        cover_asset_id: str,
    ) -> tuple[ComponentLibraryMetadata, LibraryAsset | None]:
        """Persist required drawing language and validate an optional owned cover asset."""

        if self.engine is None:
            raise RuntimeError("component metadata database is unavailable")
        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        library_id = str(dict(profile["active_knowledge_library"])["library_id"])
        with Session(self.engine, expire_on_commit=False) as db:
            asset = self._owned_cover_asset(
                db=db,
                user_id=user_id,
                library_id=library_id,
                cover_asset_id=cover_asset_id,
            )
            record = ComponentLibraryMetadata(
                metadata_id=f"component-meta-{uuid4().hex}",
                user_id=user_id,
                library_id=library_id,
                component_id=component_id,
                script_language=script_language,
                cover_asset_id=cover_asset_id,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record, asset

    def _update_drawing_metadata(
        self,
        *,
        user_id: str,
        component_id: str,
        next_component_id: str,
        script_language: str | None = None,
        cover_asset_id: str | None = None,
    ) -> tuple[ComponentLibraryMetadata, LibraryAsset | None]:
        """Move or edit one drawing metadata row together with its canonical source file."""

        if self.engine is None:
            raise RuntimeError("component metadata database is unavailable")
        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        library_id = str(dict(profile["active_knowledge_library"])["library_id"])
        with Session(self.engine, expire_on_commit=False) as db:
            record = db.exec(select(ComponentLibraryMetadata).where(
                ComponentLibraryMetadata.user_id == user_id,
                ComponentLibraryMetadata.library_id == library_id,
                ComponentLibraryMetadata.component_id == component_id,
            )).one_or_none()
            if record is None:
                raise ValueError("drawing script metadata is missing")
            next_cover_id = record.cover_asset_id if cover_asset_id is None else str(cover_asset_id).strip()
            asset = self._owned_cover_asset(
                db=db,
                user_id=user_id,
                library_id=library_id,
                cover_asset_id=next_cover_id,
            )
            record.component_id = next_component_id
            if script_language is not None:
                record.script_language = self._require_script_language(script_language)
            record.cover_asset_id = next_cover_id
            record.updated_at = utc_now()
            db.add(record)
            db.commit()
            db.refresh(record)
            return record, asset

    def _delete_drawing_metadata(self, *, user_id: str, component_id: str) -> None:
        """Delete the metadata row after its drawing source file is removed."""

        if self.engine is None:
            return
        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        library_id = str(dict(profile["active_knowledge_library"])["library_id"])
        with Session(self.engine) as db:
            record = db.exec(select(ComponentLibraryMetadata).where(
                ComponentLibraryMetadata.user_id == user_id,
                ComponentLibraryMetadata.library_id == library_id,
                ComponentLibraryMetadata.component_id == component_id,
            )).one_or_none()
            if record is not None:
                db.delete(record)
                db.commit()

    @staticmethod
    def _owned_cover_asset(
        *,
        db: Session,
        user_id: str,
        library_id: str,
        cover_asset_id: str,
    ) -> LibraryAsset | None:
        """Return an optional cover only when it belongs to the same user and library."""

        if not cover_asset_id:
            return None
        asset = db.get(LibraryAsset, cover_asset_id)
        if asset is None or asset.user_id != user_id or asset.library_id != library_id:
            raise ValueError("cover asset does not belong to the active knowledge library")
        return asset

    @staticmethod
    def _serialize_cover_asset(asset: LibraryAsset | None) -> dict[str, Any] | None:
        """Return the existing library cover shape consumed by both library card domains."""

        if asset is None:
            return None
        return {
            "asset_id": asset.asset_id,
            "mime_type": asset.mime_type,
            "file_name": asset.file_name,
            "url": f"/library/assets/{asset.user_id}/{Path(asset.storage_path).name}",
            "width": asset.width,
            "height": asset.height,
            "size": asset.size,
            "created_at": asset.created_at.isoformat(),
        }

    @staticmethod
    def _source_format(path: Path) -> str:
        """Map a canonical suffix to the front-end renderer contract."""

        suffix = path.suffix.casefold()
        if suffix == SCRIPT_COMPONENT_SUFFIX:
            return "script"
        return "vue" if suffix == ".vue" else "html"

    def _safe_filename(self, *, filename: str, source_format: str) -> str:
        """Return a safe supported basename or generate one for pasted source."""

        raw_name = str(filename or "").strip()
        if raw_name and (Path(raw_name).name != raw_name or "/" in raw_name or "\\" in raw_name):
            raise ValueError("component file name must not contain a directory")
        if not raw_name:
            suffix = SCRIPT_COMPONENT_SUFFIX if source_format == "script" else (
                ".vue" if source_format == "vue" else ".html"
            )
            return f"component-{uuid4().hex[:self.limits.checksum_short_chars]}{suffix}"
        suffix = Path(raw_name).suffix.casefold()
        if suffix not in SUPPORTED_COMPONENT_SUFFIXES:
            raise ValueError("supported component file extensions are .vue, .html, .htm, and .script")
        if (source_format == "script") != (suffix == SCRIPT_COMPONENT_SUFFIX):
            raise ValueError(".script files are reserved for drawing scripts")
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

    def _require_script_language(self, script_language: str) -> str:
        """Require a bounded user-defined drawing-script language label."""

        normalized = str(script_language or "").strip()
        if not normalized:
            raise ValueError("script language is required for drawing scripts")
        if len(normalized) > self.limits.medium_name_max_length:
            raise ValueError("script language is too long")
        return normalized

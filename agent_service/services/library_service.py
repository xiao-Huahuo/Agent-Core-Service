"""
图书馆虚拟编目服务。

功能说明:
本服务负责图书馆页面的虚拟资源管理,并把虚拟集锦/图书结构投影到当前知识库
的图书馆存储目录。集锦维护真实文件夹,图书维护真实文件路径。

使用说明:
由 REST 层注入 user_id 后调用。创建图书时可引用知识库相对路径、网页 URL 或
外部路径;创建集锦时只生成虚拟 collection 记录。
"""

from __future__ import annotations

import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session, SQLModel, col, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.library import LibraryAsset, LibraryItem, LibraryItemTag, LibraryTag
from agent_service.services.knowledge_graph_service import KnowledgeGraphService
from agent_service.services.knowledge_library_service import KnowledgeLibraryService
from agent_service.services.settings_service import SettingsService


BOOK_ITEM_TYPE = "book"
COLLECTION_ITEM_TYPE = "collection"
CONTENT_KNOWLEDGE_FILE = "knowledge_file"
CONTENT_WEB_URL = "web_url"
CONTENT_EXTERNAL_FILE = "external_file"
COVER_MODES = {"icon", "image", "description", "source_image", "title"}


class LibraryService:
    """
    图书馆虚拟编目服务。

    config: 全局配置。
    settings_service: 用于获取用户当前 active 知识库。
    knowledge_library_service: 用于复用真实文件路径解析和节点状态。
    knowledge_graph_service: 用于读取真实文件图谱状态。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        settings_service: SettingsService,
        knowledge_library_service: KnowledgeLibraryService,
        knowledge_graph_service: KnowledgeGraphService,
    ) -> None:
        """保存依赖并确保图书馆表存在。"""

        self.config = config
        self.settings_service = settings_service
        self.knowledge_library_service = knowledge_library_service
        self.knowledge_graph_service = knowledge_graph_service
        self.engine = settings_service.engine
        SQLModel.metadata.create_all(self.engine)
        self._ensure_library_schema()

    def _ensure_library_schema(self) -> None:
        """确保旧库中的图书馆表具备真实投影路径字段。"""

        from sqlalchemy import inspect as sa_inspect
        try:
            inspector = sa_inspect(self.engine)
            columns = [column["name"] for column in inspector.get_columns("library_items")]
            with Session(self.engine) as db:
                if "storage_path" not in columns:
                    db.execute(text("ALTER TABLE library_items ADD COLUMN storage_path VARCHAR(2048) NOT NULL DEFAULT ''"))
                db.commit()
        except Exception:
            pass

    def list_items(
        self,
        *,
        user_id: str,
        parent_id: str = "",
        query: str = "",
        tag: str = "",
        content_type: str = "",
        sort: str = "updated_at",
        direction: str = "desc",
    ) -> dict[str, Any]:
        """
        列出当前 active 知识库下的图书馆条目。

        parent_id: 虚拟集锦 ID,为空时表示图书馆根层。
        query: 匹配图书馆假名、描述和真实文件名。
        tag: 标签名精确匹配。
        content_type: knowledge_file/web_url/external_file/collection 过滤。
        sort: title/source_mtime/updated_at/created_at/sort_order。
        direction: asc 或 desc。
        """

        context = self._context(user_id=user_id)
        normalized_parent_id = parent_id.strip()
        normalized_query = query.strip().lower()
        normalized_tag = tag.strip()
        normalized_content_type = content_type.strip()
        with Session(self.engine) as db:
            self._sync_collection_storage_dirs(db=db, context=context)
            statement = (
                select(LibraryItem)
                .where(LibraryItem.user_id == context["user_id"])
                .where(LibraryItem.library_id == context["library_id"])
                .where(LibraryItem.parent_id == normalized_parent_id)
            )
            if normalized_content_type:
                if normalized_content_type == COLLECTION_ITEM_TYPE:
                    statement = statement.where(LibraryItem.item_type == COLLECTION_ITEM_TYPE)
                else:
                    statement = statement.where(LibraryItem.content_type == normalized_content_type)
            items = list(db.exec(statement).all())
            if normalized_tag:
                item_ids = self._item_ids_for_tag(
                    db=db,
                    user_id=context["user_id"],
                    library_id=context["library_id"],
                    tag_name=normalized_tag,
                )
                items = [item for item in items if item.item_id in item_ids]
            if normalized_query:
                items = [
                    item
                    for item in items
                    if normalized_query in item.title.lower()
                    or normalized_query in item.description.lower()
                    or normalized_query in item.source_name.lower()
                    or normalized_query in item.source_path.lower()
                    or normalized_query in item.source_url.lower()
                ]
            tags_by_item = self._tags_by_item(db=db, items=items)
            child_counts = self._child_counts(db=db, items=items)
            assets = self._assets_by_id(db=db, items=items)
            enriched = [
                self._serialize_item(
                    item=item,
                    context=context,
                    tags=tags_by_item.get(item.item_id, []),
                    child_count=child_counts.get(item.item_id, 0),
                    asset=assets.get(item.cover_asset_id),
                )
                for item in items
            ]
        return {
            "items": self._sort_items(enriched, sort=sort, direction=direction),
            "parent": self.get_item(user_id=user_id, item_id=normalized_parent_id)["item"] if normalized_parent_id else None,
            "breadcrumbs": self.build_breadcrumbs(user_id=user_id, item_id=normalized_parent_id),
        }

    def list_tags(self, *, user_id: str) -> dict[str, Any]:
        """列出当前 active 知识库的所有图书馆标签。"""

        context = self._context(user_id=user_id)
        with Session(self.engine) as db:
            tags = list(
                db.exec(
                    select(LibraryTag)
                    .where(LibraryTag.user_id == context["user_id"])
                    .where(LibraryTag.library_id == context["library_id"])
                    .order_by(LibraryTag.name.asc())
                ).all()
            )
        return {"tags": [{"tag_id": tag.tag_id, "name": tag.name} for tag in tags]}

    def get_item(self, *, user_id: str, item_id: str) -> dict[str, Any]:
        """读取一个图书馆条目。"""

        if not item_id:
            return {"item": None}
        context = self._context(user_id=user_id)
        with Session(self.engine) as db:
            item = self._get_owned_item(db=db, context=context, item_id=item_id)
            tags = self._tags_by_item(db=db, items=[item]).get(item.item_id, [])
            child_count = self._child_counts(db=db, items=[item]).get(item.item_id, 0)
            asset = self._assets_by_id(db=db, items=[item]).get(item.cover_asset_id)
            return {
                "item": self._serialize_item(
                    item=item,
                    context=context,
                    tags=tags,
                    child_count=child_count,
                    asset=asset,
                )
            }

    def build_breadcrumbs(self, *, user_id: str, item_id: str) -> list[dict[str, str]]:
        """构建虚拟集锦面包屑。"""

        if not item_id:
            return []
        context = self._context(user_id=user_id)
        breadcrumbs: list[dict[str, str]] = []
        with Session(self.engine) as db:
            current_id = item_id
            visited: set[str] = set()
            while current_id and current_id not in visited:
                visited.add(current_id)
                item = self._get_owned_item(db=db, context=context, item_id=current_id)
                breadcrumbs.append({"item_id": item.item_id, "title": self._display_title(item)})
                current_id = item.parent_id
        breadcrumbs.reverse()
        return breadcrumbs

    def create_collection(
        self,
        *,
        user_id: str,
        parent_id: str = "",
        title: str = "",
        description: str = "",
        cover_mode: str = "icon",
        cover_asset_id: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """创建虚拟集锦。"""

        context = self._context(user_id=user_id)
        now = self._now()
        with Session(self.engine) as db:
            self._validate_parent(db=db, context=context, parent_id=parent_id)
            storage_path = self._create_collection_storage_path(
                db=db,
                context=context,
                parent_id=parent_id.strip(),
                title=title,
            )
            item = LibraryItem(
                item_id=self._new_id("lib"),
                user_id=context["user_id"],
                library_id=context["library_id"],
                parent_id=parent_id.strip(),
                item_type=COLLECTION_ITEM_TYPE,
                content_type=COLLECTION_ITEM_TYPE,
                title=title.strip(),
                description=description.strip(),
                storage_path=storage_path,
                cover_mode=self._normalize_cover_mode(cover_mode),
                cover_asset_id=cover_asset_id.strip(),
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            db.commit()
            self._replace_tags(db=db, context=context, item_id=item.item_id, tag_names=tags or [])
            db.refresh(item)
            return self.get_item(user_id=user_id, item_id=item.item_id)

    def create_item(
        self,
        *,
        user_id: str,
        parent_id: str = "",
        content_type: str = CONTENT_KNOWLEDGE_FILE,
        source_path: str = "",
        source_url: str = "",
        title: str = "",
        description: str = "",
        cover_mode: str = "icon",
        cover_asset_id: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """创建虚拟图书条目。"""

        context = self._context(user_id=user_id)
        normalized_content_type = self._normalize_content_type(content_type)
        normalized_source_path = source_path.strip().replace("\\", "/").strip("/")
        normalized_source_url = source_url.strip()
        if normalized_content_type == CONTENT_KNOWLEDGE_FILE and not normalized_source_path:
            raise ValueError("source_path is required for knowledge_file item")
        if normalized_content_type == CONTENT_WEB_URL and not normalized_source_url:
            raise ValueError("source_url is required for web_url item")
        source_meta = self._source_metadata(context=context, content_type=normalized_content_type, source_path=normalized_source_path, source_url=normalized_source_url)
        now = self._now()
        with Session(self.engine) as db:
            self._validate_parent(db=db, context=context, parent_id=parent_id)
            storage_path = ""
            if normalized_content_type == CONTENT_KNOWLEDGE_FILE:
                normalized_source_path = self._move_book_file_to_parent_storage(
                    db=db,
                    context=context,
                    parent_id=parent_id.strip(),
                    source_path=normalized_source_path,
                    title=title,
                )
                storage_path = normalized_source_path
                source_meta = self._source_metadata(
                    context=context,
                    content_type=normalized_content_type,
                    source_path=normalized_source_path,
                    source_url=normalized_source_url,
                )
            item = LibraryItem(
                item_id=self._new_id("lib"),
                user_id=context["user_id"],
                library_id=context["library_id"],
                parent_id=parent_id.strip(),
                item_type=BOOK_ITEM_TYPE,
                content_type=normalized_content_type,
                title=title.strip(),
                description=description.strip(),
                storage_path=storage_path,
                source_path=normalized_source_path,
                source_url=normalized_source_url,
                source_name=source_meta["source_name"],
                source_mime=source_meta["source_mime"],
                source_size=source_meta["source_size"],
                source_mtime=source_meta["source_mtime"],
                cover_mode=self._normalize_cover_mode(cover_mode),
                cover_asset_id=cover_asset_id.strip(),
                index_status=source_meta["index_status"],
                graph_status=source_meta["graph_status"],
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            db.commit()
            self._replace_tags(db=db, context=context, item_id=item.item_id, tag_names=tags or [])
            db.refresh(item)
            return self.get_item(user_id=user_id, item_id=item.item_id)

    def update_item(self, *, user_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """更新图书馆条目的虚拟元数据。"""

        context = self._context(user_id=user_id)
        with Session(self.engine) as db:
            item = self._get_owned_item(db=db, context=context, item_id=item_id)
            next_parent_id = item.parent_id
            next_title = item.title
            if "parent_id" in payload:
                next_parent_id = str(payload.get("parent_id") or "").strip()
                self._validate_move(db=db, context=context, item=item, parent_id=next_parent_id)
            if "title" in payload:
                next_title = str(payload.get("title") or "").strip()
            if item.item_type == COLLECTION_ITEM_TYPE and (next_parent_id != item.parent_id or next_title != item.title):
                self._move_collection_storage(
                    db=db,
                    context=context,
                    item=item,
                    parent_id=next_parent_id,
                    title=next_title,
                )
            elif item.item_type == BOOK_ITEM_TYPE and (next_parent_id != item.parent_id or next_title != item.title):
                self._move_book_storage(
                    db=db,
                    context=context,
                    item=item,
                    parent_id=next_parent_id,
                    title=next_title,
                )
            item.parent_id = next_parent_id
            item.title = next_title
            if "description" in payload:
                item.description = str(payload.get("description") or "").strip()
            if "cover_mode" in payload:
                item.cover_mode = self._normalize_cover_mode(str(payload.get("cover_mode") or "icon"))
            if "cover_asset_id" in payload:
                item.cover_asset_id = str(payload.get("cover_asset_id") or "").strip()
            if "sort_order" in payload:
                item.sort_order = int(payload.get("sort_order") or 0)
            item.updated_at = self._now()
            db.add(item)
            if "tags" in payload:
                tag_values = payload.get("tags") if isinstance(payload.get("tags"), list) else []
                self._replace_tags(db=db, context=context, item_id=item.item_id, tag_names=[str(tag) for tag in tag_values])
            db.commit()
        return self.get_item(user_id=user_id, item_id=item_id)

    def delete_item(self, *, user_id: str, item_id: str) -> dict[str, Any]:
        """移出图书馆。删除集锦时递归删除其虚拟子项,不删除任何真实文件。"""

        context = self._context(user_id=user_id)
        with Session(self.engine) as db:
            item = self._get_owned_item(db=db, context=context, item_id=item_id)
            item_ids = self._collect_descendant_ids(db=db, context=context, root_id=item.item_id)
            for target_id in item_ids:
                for link in db.exec(select(LibraryItemTag).where(LibraryItemTag.item_id == target_id)).all():
                    db.delete(link)
                target = db.get(LibraryItem, target_id)
                if target is not None:
                    db.delete(target)
            db.commit()
        return {"ok": True, "deleted_item_ids": item_ids}

    def upload_cover(self, *, user_id: str, filename: str, content: bytes, mime_type: str = "") -> dict[str, Any]:
        """保存上传封面到 runtime/assets/library 并创建资产记录。"""

        if not content:
            raise ValueError("cover content is empty")
        context = self._context(user_id=user_id)
        asset_id = self._new_id("asset")
        safe_suffix = Path(filename or "cover").suffix.lower()[:16] or ".bin"
        target_dir = self.config.storage.assets_dir / "library" / context["user_id"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = (target_dir / f"{asset_id}{safe_suffix}").resolve()
        target_path.write_bytes(content)
        detected_mime = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        width = 0
        height = 0
        try:
            from PIL import Image

            with Image.open(target_path) as image:
                width, height = image.size
        except Exception:
            pass
        asset = LibraryAsset(
            asset_id=asset_id,
            user_id=context["user_id"],
            library_id=context["library_id"],
            asset_type="cover",
            mime_type=detected_mime,
            file_name=filename or target_path.name,
            storage_path=str(target_path),
            width=width,
            height=height,
            size=len(content),
        )
        with Session(self.engine) as db:
            db.add(asset)
            db.commit()
            db.refresh(asset)
        return {"asset": self._serialize_asset(asset)}

    def _context(self, *, user_id: str) -> dict[str, Any]:
        """读取当前用户 active 知识库上下文。"""

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        return {
            "user_id": str(profile["user_id"]),
            "library_id": str(active_library["library_id"]),
            "knowledge_dir": Path(str(active_library["knowledge_dir"])).expanduser().resolve(),
            "library_storage_dir": str(active_library.get("library_storage_dir") or "library"),
        }

    def _source_metadata(self, *, context: dict[str, Any], content_type: str, source_path: str, source_url: str) -> dict[str, Any]:
        """读取真实内容的展示元数据。"""

        if content_type == CONTENT_WEB_URL:
            source_name = source_url.rstrip("/").split("/")[-1] or source_url
            return {
                "source_name": source_name[:512],
                "source_mime": "text/html",
                "source_size": 0,
                "source_mtime": "",
                "index_status": "",
                "graph_status": "",
            }
        if content_type == CONTENT_EXTERNAL_FILE:
            path = Path(source_path).expanduser()
            source_name = path.name or source_path
            return {
                "source_name": source_name,
                "source_mime": mimetypes.guess_type(source_name)[0] or "",
                "source_size": path.stat().st_size if path.exists() and path.is_file() else 0,
                "source_mtime": self._mtime(path) if path.exists() else "",
                "index_status": "",
                "graph_status": "",
            }
        root = Path(context["knowledge_dir"])
        source_file = (root / source_path).resolve()
        if not self._is_relative_to(source_file, root):
            raise ValueError("source_path escapes active knowledge library")
        source_name = source_file.name or source_path
        graph_status = self._graph_status(context=context, source_path=source_path)
        return {
            "source_name": source_name,
            "source_mime": mimetypes.guess_type(source_name)[0] or "",
            "source_size": source_file.stat().st_size if source_file.exists() and source_file.is_file() else 0,
            "source_mtime": self._mtime(source_file) if source_file.exists() else "",
            "index_status": self._index_status(context=context, source_path=source_path, exists=source_file.exists()),
            "graph_status": graph_status,
        }

    def _serialize_item(
        self,
        *,
        item: LibraryItem,
        context: dict[str, Any],
        tags: list[str],
        child_count: int,
        asset: LibraryAsset | None,
    ) -> dict[str, Any]:
        """转换图书馆条目为前端 DTO。"""

        source_meta = self._source_metadata(
            context=context,
            content_type=item.content_type,
            source_path=item.source_path,
            source_url=item.source_url,
        ) if item.item_type == BOOK_ITEM_TYPE else {
            "source_name": "",
            "source_mime": "",
            "source_size": 0,
            "source_mtime": "",
            "index_status": "",
            "graph_status": "",
        }
        cover_asset = self._serialize_asset(asset) if asset else None
        return {
            "item_id": item.item_id,
            "user_id": item.user_id,
            "library_id": item.library_id,
            "parent_id": item.parent_id,
            "item_type": item.item_type,
            "content_type": item.content_type,
            "title": item.title,
            "display_title": self._display_title(item),
            "description": item.description,
            "storage_path": item.storage_path,
            "source_path": item.source_path,
            "source_url": item.source_url,
            "source_name": source_meta["source_name"] or item.source_name,
            "source_mime": source_meta["source_mime"] or item.source_mime,
            "source_size": source_meta["source_size"] or item.source_size,
            "source_mtime": source_meta["source_mtime"] or item.source_mtime,
            "source_exists": self._source_exists(context=context, item=item),
            "cover_mode": item.cover_mode,
            "cover_asset_id": item.cover_asset_id,
            "cover_asset": cover_asset,
            "sort_order": item.sort_order,
            "index_status": source_meta["index_status"] or item.index_status,
            "graph_status": source_meta["graph_status"] or item.graph_status,
            "tags": tags,
            "child_count": child_count,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }

    def _serialize_asset(self, asset: LibraryAsset) -> dict[str, Any]:
        """转换封面资产为前端 DTO。"""

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

    def _replace_tags(self, *, db: Session, context: dict[str, Any], item_id: str, tag_names: list[str]) -> None:
        """替换一个条目的所有标签。"""

        for link in db.exec(select(LibraryItemTag).where(LibraryItemTag.item_id == item_id)).all():
            db.delete(link)
        normalized_names = []
        seen = set()
        for raw_name in tag_names:
            name = raw_name.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            normalized_names.append(name)
        for name in normalized_names:
            tag = self._ensure_tag(db=db, context=context, name=name)
            db.add(LibraryItemTag(item_id=item_id, tag_id=tag.tag_id))
        db.commit()

    def _ensure_tag(self, *, db: Session, context: dict[str, Any], name: str) -> LibraryTag:
        """按名称获取或创建标签。"""

        tag = db.exec(
            select(LibraryTag)
            .where(LibraryTag.user_id == context["user_id"])
            .where(LibraryTag.library_id == context["library_id"])
            .where(LibraryTag.name == name)
        ).first()
        if tag is not None:
            return tag
        tag = LibraryTag(
            tag_id=self._new_id("tag"),
            user_id=context["user_id"],
            library_id=context["library_id"],
            name=name,
        )
        db.add(tag)
        db.commit()
        db.refresh(tag)
        return tag

    def _tags_by_item(self, *, db: Session, items: list[LibraryItem]) -> dict[str, list[str]]:
        """按 item_id 聚合标签名。"""

        result = {item.item_id: [] for item in items}
        if not items:
            return result
        item_ids = [item.item_id for item in items]
        links = list(db.exec(select(LibraryItemTag).where(col(LibraryItemTag.item_id).in_(item_ids))).all())
        if not links:
            return result
        tags = {
            tag.tag_id: tag.name
            for tag in db.exec(select(LibraryTag).where(col(LibraryTag.tag_id).in_([link.tag_id for link in links]))).all()
        }
        for link in links:
            name = tags.get(link.tag_id)
            if name:
                result.setdefault(link.item_id, []).append(name)
        return result

    def _item_ids_for_tag(self, *, db: Session, user_id: str, library_id: str, tag_name: str) -> set[str]:
        """查找具有指定标签名的条目 ID。"""

        tag = db.exec(
            select(LibraryTag)
            .where(LibraryTag.user_id == user_id)
            .where(LibraryTag.library_id == library_id)
            .where(LibraryTag.name == tag_name)
        ).first()
        if tag is None:
            return set()
        return {link.item_id for link in db.exec(select(LibraryItemTag).where(LibraryItemTag.tag_id == tag.tag_id)).all()}

    def _child_counts(self, *, db: Session, items: list[LibraryItem]) -> dict[str, int]:
        """统计集锦直接子项数量。"""

        result = {item.item_id: 0 for item in items}
        for item in items:
            if item.item_type == COLLECTION_ITEM_TYPE:
                result[item.item_id] = len(
                    list(
                        db.exec(
                            select(LibraryItem)
                            .where(LibraryItem.user_id == item.user_id)
                            .where(LibraryItem.library_id == item.library_id)
                            .where(LibraryItem.parent_id == item.item_id)
                        ).all()
                    )
                )
        return result

    def _assets_by_id(self, *, db: Session, items: list[LibraryItem]) -> dict[str, LibraryAsset]:
        """读取条目引用的封面资产。"""

        asset_ids = [item.cover_asset_id for item in items if item.cover_asset_id]
        if not asset_ids:
            return {}
        return {
            asset.asset_id: asset
            for asset in db.exec(select(LibraryAsset).where(col(LibraryAsset.asset_id).in_(asset_ids))).all()
        }

    def _validate_parent(self, *, db: Session, context: dict[str, Any], parent_id: str) -> None:
        """校验 parent_id 指向当前库中的集锦。"""

        normalized_parent_id = parent_id.strip()
        if not normalized_parent_id:
            return
        parent = self._get_owned_item(db=db, context=context, item_id=normalized_parent_id)
        if parent.item_type != COLLECTION_ITEM_TYPE:
            raise ValueError("parent_id must point to a collection")

    def _validate_move(self, *, db: Session, context: dict[str, Any], item: LibraryItem, parent_id: str) -> None:
        """校验虚拟移动不会形成循环。"""

        self._validate_parent(db=db, context=context, parent_id=parent_id)
        if not parent_id:
            return
        if item.item_id == parent_id:
            raise ValueError("collection cannot move into itself")
        current_id = parent_id
        while current_id:
            parent = self._get_owned_item(db=db, context=context, item_id=current_id)
            if parent.parent_id == item.item_id:
                raise ValueError("collection cannot move into its descendant")
            current_id = parent.parent_id

    def _collect_descendant_ids(self, *, db: Session, context: dict[str, Any], root_id: str) -> list[str]:
        """收集条目及其虚拟子孙 ID。"""

        result = [root_id]
        children = list(
            db.exec(
                select(LibraryItem)
                .where(LibraryItem.user_id == context["user_id"])
                .where(LibraryItem.library_id == context["library_id"])
                .where(LibraryItem.parent_id == root_id)
            ).all()
        )
        for child in children:
            result.extend(self._collect_descendant_ids(db=db, context=context, root_id=child.item_id))
        return result

    def _get_owned_item(self, *, db: Session, context: dict[str, Any], item_id: str) -> LibraryItem:
        """读取当前用户当前库中的条目。"""

        item = db.get(LibraryItem, item_id)
        if item is None or item.user_id != context["user_id"] or item.library_id != context["library_id"]:
            raise ValueError("library item not found")
        return item

    def _sort_items(self, items: list[dict[str, Any]], *, sort: str, direction: str) -> list[dict[str, Any]]:
        """按前端筛选条件排序。"""

        reverse = direction != "asc"
        key_map = {
            "title": lambda item: str(item.get("display_title") or "").lower(),
            "source_name": lambda item: str(item.get("source_name") or "").lower(),
            "source_mtime": lambda item: str(item.get("source_mtime") or ""),
            "created_at": lambda item: str(item.get("created_at") or ""),
            "sort_order": lambda item: int(item.get("sort_order") or 0),
            "updated_at": lambda item: str(item.get("updated_at") or ""),
        }
        key_fn = key_map.get(sort, key_map["updated_at"])
        return sorted(items, key=key_fn, reverse=reverse)

    @staticmethod
    def _display_title(item: LibraryItem) -> str:
        """计算图书馆展示标题。"""

        if item.title.strip():
            return item.title.strip()
        if item.item_type == COLLECTION_ITEM_TYPE:
            return "未命名集锦"
        date_text = item.created_at.strftime("%Y-%m-%d")
        return f"图书馆资料{date_text}"

    @staticmethod
    def _normalize_cover_mode(value: str) -> str:
        """规范化封面模式。"""

        normalized = value.strip() or "icon"
        return normalized if normalized in COVER_MODES else "icon"

    @staticmethod
    def _normalize_content_type(value: str) -> str:
        """规范化真实内容类型。"""

        normalized = value.strip() or CONTENT_KNOWLEDGE_FILE
        if normalized not in {CONTENT_KNOWLEDGE_FILE, CONTENT_WEB_URL, CONTENT_EXTERNAL_FILE}:
            raise ValueError("unsupported content_type")
        return normalized

    @staticmethod
    def _source_exists(*, context: dict[str, Any], item: LibraryItem) -> bool:
        """判断条目引用的真实内容是否存在或有效。"""

        if item.item_type == COLLECTION_ITEM_TYPE:
            if not item.storage_path:
                return True
            root = Path(context["knowledge_dir"])
            return (root / item.storage_path).resolve().is_dir()
        if item.content_type == CONTENT_WEB_URL:
            return bool(item.source_url)
        if item.content_type == CONTENT_EXTERNAL_FILE:
            return Path(item.source_path).expanduser().exists()
        root = Path(context["knowledge_dir"])
        return (root / item.source_path).resolve().exists()

    def _library_root_relative(self, *, context: dict[str, Any]) -> str:
        """返回图书馆真实存储根目录相对路径。"""

        value = str(context.get("library_storage_dir") or "library").strip().replace("\\", "/").strip("/")
        return value or "library"

    def _library_root_path(self, *, context: dict[str, Any]) -> Path:
        """返回图书馆真实存储根目录绝对路径。"""

        root = Path(context["knowledge_dir"])
        path = (root / self._library_root_relative(context=context)).resolve()
        if not self._is_relative_to(path, root):
            raise ValueError("library storage path escapes active knowledge library")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _create_collection_storage_path(
        self,
        *,
        db: Session,
        context: dict[str, Any],
        parent_id: str,
        title: str,
    ) -> str:
        """为新集锦创建真实文件夹并返回知识库相对路径。"""

        parent_dir = self._parent_storage_dir(db=db, context=context, parent_id=parent_id)
        folder_name = self._safe_path_segment(title) or "未命名集锦"
        target_dir = self._unique_child_path(target_dir=parent_dir, preferred_name=folder_name)
        target_dir.mkdir(parents=True, exist_ok=True)
        return self._relative_to_knowledge_root(context=context, path=target_dir)

    def _move_collection_storage(
        self,
        *,
        db: Session,
        context: dict[str, Any],
        item: LibraryItem,
        parent_id: str,
        title: str,
    ) -> None:
        """移动或重命名集锦真实文件夹并重写子孙条目的路径前缀。"""

        old_relative = self._collection_storage_relative(db=db, context=context, item=item)
        old_dir = self._absolute_knowledge_path(context=context, relative_path=old_relative)
        parent_dir = self._parent_storage_dir(db=db, context=context, parent_id=parent_id)
        folder_name = self._safe_path_segment(title) or "未命名集锦"
        target_dir = (parent_dir / folder_name).resolve()
        if target_dir != old_dir:
            target_dir = self._unique_child_path(target_dir=parent_dir, preferred_name=folder_name)
            if old_dir.exists():
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_dir), str(target_dir))
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
        new_relative = self._relative_to_knowledge_root(context=context, path=target_dir)
        self._rewrite_descendant_storage_paths(
            db=db,
            context=context,
            root_item=item,
            old_prefix=old_relative,
            new_prefix=new_relative,
        )
        item.storage_path = new_relative

    def _move_book_storage(
        self,
        *,
        db: Session,
        context: dict[str, Any],
        item: LibraryItem,
        parent_id: str,
        title: str,
    ) -> None:
        """移动 knowledge_file 图书真实文件并更新 source_path/storage_path。"""

        if item.content_type != CONTENT_KNOWLEDGE_FILE or not item.source_path:
            return
        next_path = self._move_book_file_to_parent_storage(
            db=db,
            context=context,
            parent_id=parent_id,
            source_path=item.source_path,
            title=title,
        )
        item.source_path = next_path
        item.storage_path = next_path

    def _move_book_file_to_parent_storage(
        self,
        *,
        db: Session,
        context: dict[str, Any],
        parent_id: str,
        source_path: str,
        title: str,
    ) -> str:
        """把图书真实文件移动到目标集锦文件夹并返回新相对路径。"""

        source_relative = source_path.strip().replace("\\", "/").strip("/")
        source_file = self._absolute_knowledge_path(context=context, relative_path=source_relative)
        if not source_file.exists() or not source_file.is_file():
            return source_relative
        target_dir = self._parent_storage_dir(db=db, context=context, parent_id=parent_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_name = self._book_file_name(title=title, fallback_name=source_file.name)
        target_file = (target_dir / target_name).resolve()
        if target_file == source_file:
            return self._relative_to_knowledge_root(context=context, path=source_file)
        if target_file.exists():
            target_file = self._unique_child_path(target_dir=target_dir, preferred_name=target_name)
        shutil.move(str(source_file), str(target_file))
        return self._relative_to_knowledge_root(context=context, path=target_file)

    def _parent_storage_dir(self, *, db: Session, context: dict[str, Any], parent_id: str) -> Path:
        """返回虚拟父集锦对应的真实目录;根层返回图书馆存储根目录。"""

        normalized_parent_id = parent_id.strip()
        if not normalized_parent_id:
            return self._library_root_path(context=context)
        parent = self._get_owned_item(db=db, context=context, item_id=normalized_parent_id)
        if parent.item_type != COLLECTION_ITEM_TYPE:
            raise ValueError("parent_id must point to a collection")
        relative = self._collection_storage_relative(db=db, context=context, item=parent)
        folder = self._absolute_knowledge_path(context=context, relative_path=relative)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _collection_storage_relative(self, *, db: Session, context: dict[str, Any], item: LibraryItem) -> str:
        """返回集锦真实文件夹相对路径;旧数据缺失时补建。"""

        if item.storage_path.strip():
            return item.storage_path.strip().replace("\\", "/").strip("/")
        relative = self._create_collection_storage_path(
            db=db,
            context=context,
            parent_id=item.parent_id,
            title=item.title,
        )
        item.storage_path = relative
        db.add(item)
        return relative

    def _rewrite_descendant_storage_paths(
        self,
        *,
        db: Session,
        context: dict[str, Any],
        root_item: LibraryItem,
        old_prefix: str,
        new_prefix: str,
    ) -> None:
        """集锦目录移动后同步子孙集锦和图书的相对路径前缀。"""

        old_value = old_prefix.strip("/")
        new_value = new_prefix.strip("/")
        if not old_value or old_value == new_value:
            return
        for item_id in self._collect_descendant_ids(db=db, context=context, root_id=root_item.item_id):
            if item_id == root_item.item_id:
                continue
            child = db.get(LibraryItem, item_id)
            if child is None:
                continue
            if child.storage_path.startswith(f"{old_value}/"):
                child.storage_path = f"{new_value}/{child.storage_path[len(old_value) + 1:]}"
            if child.content_type == CONTENT_KNOWLEDGE_FILE and child.source_path.startswith(f"{old_value}/"):
                child.source_path = f"{new_value}/{child.source_path[len(old_value) + 1:]}"
            child.updated_at = self._now()
            db.add(child)

    def _sync_collection_storage_dirs(self, *, db: Session, context: dict[str, Any]) -> None:
        """刷新列表时确保虚拟集锦的真实文件夹存在,但不删除缺失图书条目。"""

        statement = (
            select(LibraryItem)
            .where(LibraryItem.user_id == context["user_id"])
            .where(LibraryItem.library_id == context["library_id"])
            .where(LibraryItem.item_type == COLLECTION_ITEM_TYPE)
        )
        changed = False
        for item in db.exec(statement).all():
            had_storage_path = bool(item.storage_path.strip())
            relative = self._collection_storage_relative(db=db, context=context, item=item)
            if not had_storage_path and item.storage_path:
                changed = True
            folder = self._absolute_knowledge_path(context=context, relative_path=relative)
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
                changed = True
        if changed:
            db.commit()

    def _absolute_knowledge_path(self, *, context: dict[str, Any], relative_path: str) -> Path:
        """将知识库相对路径转换为绝对路径并防止越界。"""

        root = Path(context["knowledge_dir"])
        path = (root / relative_path.strip().replace("\\", "/").strip("/")).resolve()
        if not self._is_relative_to(path, root):
            raise ValueError("library storage path escapes active knowledge library")
        return path

    def _relative_to_knowledge_root(self, *, context: dict[str, Any], path: Path) -> str:
        """将绝对路径转换为当前知识库相对路径。"""

        root = Path(context["knowledge_dir"]).resolve()
        resolved = path.resolve()
        if not self._is_relative_to(resolved, root):
            raise ValueError("library storage path escapes active knowledge library")
        return resolved.relative_to(root).as_posix()

    def _book_file_name(self, *, title: str, fallback_name: str) -> str:
        """根据标题生成真实文件名,保留原文件扩展名并清理非法字符。"""

        fallback = Path(fallback_name).name or "untitled"
        suffix = Path(fallback).suffix
        stem = self._safe_path_segment(title) or Path(fallback).stem or "untitled"
        return f"{stem}{suffix}"

    @staticmethod
    def _safe_path_segment(value: str) -> str:
        """将标题转换为可用路径段,移除 Windows 非法字符并压缩空白。"""

        cleaned = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in value.strip())
        cleaned = " ".join(cleaned.split()).strip(" .")
        return cleaned[:96]

    def _unique_child_path(self, *, target_dir: Path, preferred_name: str) -> Path:
        """在目录内生成不冲突的子路径,使用 `名称 (1)` 去重。"""

        safe_name = self._safe_path_segment(preferred_name) or "untitled"
        candidate = (target_dir / safe_name).resolve()
        if not candidate.exists():
            return candidate
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        for index in range(1, 10_000):
            next_candidate = (target_dir / f"{stem} ({index}){suffix}").resolve()
            if not next_candidate.exists():
                return next_candidate
        raise ValueError("unable to allocate unique library storage path")

    @staticmethod
    def _mtime(path: Path) -> str:
        """返回文件修改时间 ISO 字符串。"""

        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

    @staticmethod
    def _now() -> datetime:
        """返回当前 UTC 时间。"""

        return datetime.now(timezone.utc)

    @staticmethod
    def _new_id(prefix: str) -> str:
        """生成数据库主键。"""

        return f"{prefix}_{uuid4().hex[:16]}"

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        """兼容旧 Python 的 Path.is_relative_to。"""

        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _index_status(self, *, context: dict[str, Any], source_path: str, exists: bool) -> str:
        """读取真实文件入库状态,失败时返回 missing/unknown。"""

        if not exists:
            return "missing"
        try:
            nodes = self.knowledge_library_service.list_files(user_id=context["user_id"])
            flat = self._flatten_nodes(nodes)
            node = next((item for item in flat if item.get("path") == source_path), None)
            return str((node or {}).get("indexStatus") or "")
        except Exception:
            return ""

    def _graph_status(self, *, context: dict[str, Any], source_path: str) -> str:
        """读取真实文件图谱状态。"""

        try:
            statuses = self.knowledge_graph_service.list_document_statuses(
                user_id=context["user_id"],
                library_id=context["library_id"],
            )
            return str(statuses.get(source_path) or "")
        except Exception:
            return ""

    def _flatten_nodes(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """展开知识库文件树。"""

        result: list[dict[str, Any]] = []
        for node in nodes:
            result.append(node)
            children = node.get("children")
            if isinstance(children, list):
                result.extend(self._flatten_nodes(children))
        return result

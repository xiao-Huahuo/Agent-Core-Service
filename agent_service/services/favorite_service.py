"""
Favorite business service.

功能说明:
本服务负责用户收藏的数据库持久化、查询、去重和删除。收藏是业务数据,统一走
SQLite 表,不允许降级为浏览器存储或文件型临时存储。

使用说明:
REST 层注入 `FavoriteService` 后调用本服务。调用方需要显式传入 user_id、
target_type、target_id 和可选 library_id。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

import agent_service.models  # noqa: F401
from agent_service.models.favorite import FavoriteRecord
from agent_service.schemas.favorite import FavoriteCreate, FavoriteOut, FavoriteTargetType


VALID_TARGET_TYPES = {"knowledge_path", "library_item", "component", "session", "smart_form_row"}


class FavoriteService:
    """
    收藏业务服务。

    engine: SQLAlchemy Engine,通常复用 settings_service.engine。
    create_tables: 是否确保收藏表存在。
    """

    def __init__(self, *, engine: Engine, create_tables: bool = True) -> None:
        """保存数据库引擎并按需创建收藏表。"""

        self.engine = engine
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def list_favorites(
        self,
        *,
        user_id: str,
        target_type: FavoriteTargetType | str | None = None,
        library_id: str | None = None,
    ) -> list[FavoriteOut]:
        """
        查询用户收藏。

        target_type: 可选目标类型过滤。
        library_id: 可选知识库作用域过滤;传 None 时不过滤知识库。
        """

        normalized_user_id = self._required(user_id, "user_id")
        statement = select(FavoriteRecord).where(FavoriteRecord.user_id == normalized_user_id)
        if target_type:
            normalized_type = self._normalize_target_type(str(target_type))
            statement = statement.where(FavoriteRecord.target_type == normalized_type)
        if library_id is not None:
            statement = statement.where(FavoriteRecord.library_id == library_id.strip())
        statement = statement.order_by(FavoriteRecord.created_at.desc())
        with Session(self.engine) as db:
            return [self._to_out(record) for record in db.exec(statement).all()]

    def add_favorite(self, payload: FavoriteCreate) -> FavoriteOut:
        """
        创建收藏;如果同一目标已收藏,直接返回已有记录。

        payload: 收藏创建 DTO。
        """

        normalized_user_id = self._required(payload.user_id, "user_id")
        normalized_type = self._normalize_target_type(payload.target_type)
        normalized_target_id = self._required(payload.target_id, "target_id")
        normalized_library_id = payload.library_id.strip()
        with Session(self.engine) as db:
            existing = self._find(
                db=db,
                user_id=normalized_user_id,
                library_id=normalized_library_id,
                target_type=normalized_type,
                target_id=normalized_target_id,
            )
            if existing is not None:
                return self._to_out(existing)
            record = FavoriteRecord(
                favorite_id=self.generate_favorite_id(),
                user_id=normalized_user_id,
                library_id=normalized_library_id,
                target_type=normalized_type,
                target_id=normalized_target_id,
                created_at=self._utc_now(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_out(record)

    def delete_favorite(
        self,
        *,
        user_id: str,
        target_type: FavoriteTargetType | str,
        target_id: str,
        library_id: str = "",
    ) -> bool:
        """
        删除指定收藏。

        返回 True 表示找到并删除,False 表示原本不存在。
        """

        normalized_user_id = self._required(user_id, "user_id")
        normalized_type = self._normalize_target_type(str(target_type))
        normalized_target_id = self._required(target_id, "target_id")
        normalized_library_id = library_id.strip()
        with Session(self.engine) as db:
            record = self._find(
                db=db,
                user_id=normalized_user_id,
                library_id=normalized_library_id,
                target_type=normalized_type,
                target_id=normalized_target_id,
            )
            if record is None:
                return False
            db.delete(record)
            db.commit()
            return True

    @staticmethod
    def generate_favorite_id() -> str:
        """生成收藏 ID。"""

        return f"fav_{uuid4().hex}"

    @staticmethod
    def _utc_now() -> datetime:
        """返回当前 UTC 时间。"""

        return datetime.now(timezone.utc)

    @staticmethod
    def _required(value: str, field_name: str) -> str:
        """校验并规范化必填字符串字段。"""

        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    def _normalize_target_type(value: str) -> FavoriteTargetType:
        """校验收藏目标类型。"""

        normalized = value.strip()
        if normalized not in VALID_TARGET_TYPES:
            raise ValueError("target_type must be knowledge_path, library_item, component, session, or smart_form_row")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _to_out(record: FavoriteRecord) -> FavoriteOut:
        """将数据库记录转换为 API DTO。"""

        return FavoriteOut(
            favorite_id=record.favorite_id,
            user_id=record.user_id,
            library_id=record.library_id,
            target_type=record.target_type,  # type: ignore[arg-type]
            target_id=record.target_id,
            created_at=record.created_at,
        )

    @staticmethod
    def _find(
        *,
        db: Session,
        user_id: str,
        library_id: str,
        target_type: str,
        target_id: str,
    ) -> FavoriteRecord | None:
        """查找一个用户在指定作用域下的单个收藏。"""

        return db.exec(
            select(FavoriteRecord)
            .where(FavoriteRecord.user_id == user_id)
            .where(FavoriteRecord.library_id == library_id)
            .where(FavoriteRecord.target_type == target_type)
            .where(FavoriteRecord.target_id == target_id)
        ).first()

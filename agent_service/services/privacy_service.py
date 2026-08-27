"""Privacy business service.

Usage:
REST and gRPC adapters call this service to list, add, or remove privacy flags.
All state is persisted in SQLite through PrivacyRecord.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

import agent_service.models  # noqa: F401
from agent_service.models.privacy import PrivacyRecord
from agent_service.schemas.privacy import PrivacyCreate, PrivacyOut, PrivacyTargetType


VALID_TARGET_TYPES = {"knowledge_path", "library_item", "smart_form_row"}


class PrivacyService:
    """Persist and query privacy flags scoped by user and knowledge library."""

    def __init__(self, *, engine: Engine, create_tables: bool = True) -> None:
        """Save the shared database engine and ensure the privacy table exists."""

        self.engine = engine
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def list_privacy(
        self,
        *,
        user_id: str,
        target_type: PrivacyTargetType | str | None = None,
        library_id: str | None = None,
    ) -> list[PrivacyOut]:
        """List privacy flags, optionally filtering by target type and library."""

        statement = select(PrivacyRecord).where(PrivacyRecord.user_id == self._required(user_id, "user_id"))
        if target_type:
            statement = statement.where(PrivacyRecord.target_type == self._normalize_target_type(str(target_type)))
        if library_id is not None:
            statement = statement.where(PrivacyRecord.library_id == library_id.strip())
        statement = statement.order_by(PrivacyRecord.created_at.desc())
        with Session(self.engine) as db:
            return [self._to_out(record) for record in db.exec(statement).all()]

    def add_privacy(self, payload: PrivacyCreate) -> PrivacyOut:
        """Create a privacy flag, returning the existing record on duplicates."""

        user_id = self._required(payload.user_id, "user_id")
        target_type = self._normalize_target_type(str(payload.target_type))
        target_id = self._required(payload.target_id, "target_id")
        library_id = payload.library_id.strip()
        with Session(self.engine) as db:
            existing = self._find(db, user_id, library_id, target_type, target_id)
            if existing is not None:
                return self._to_out(existing)
            record = PrivacyRecord(
                privacy_id=f"privacy_{uuid4().hex}",
                user_id=user_id,
                library_id=library_id,
                target_type=target_type,
                target_id=target_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_out(record)

    def delete_privacy(
        self,
        *,
        user_id: str,
        target_type: PrivacyTargetType | str,
        target_id: str,
        library_id: str = "",
    ) -> bool:
        """Delete a privacy flag and report whether a record existed."""

        user_id = self._required(user_id, "user_id")
        target_type = self._normalize_target_type(str(target_type))
        target_id = self._required(target_id, "target_id")
        with Session(self.engine) as db:
            record = self._find(db, user_id, library_id.strip(), target_type, target_id)
            if record is None:
                return False
            db.delete(record)
            db.commit()
            return True

    @staticmethod
    def _required(value: str, field_name: str) -> str:
        """Normalize and validate a required string."""

        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    def _normalize_target_type(value: str) -> PrivacyTargetType:
        """Restrict privacy to supported persisted UI target types."""

        normalized = value.strip()
        if normalized not in VALID_TARGET_TYPES:
            raise ValueError("target_type must be knowledge_path, library_item, or smart_form_row")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _find(db: Session, user_id: str, library_id: str, target_type: str, target_id: str) -> PrivacyRecord | None:
        """Find one privacy record by its unique business key."""

        return db.exec(
            select(PrivacyRecord)
            .where(PrivacyRecord.user_id == user_id)
            .where(PrivacyRecord.library_id == library_id)
            .where(PrivacyRecord.target_type == target_type)
            .where(PrivacyRecord.target_id == target_id)
        ).first()

    @staticmethod
    def _to_out(record: PrivacyRecord) -> PrivacyOut:
        """Convert the database record to the public DTO."""

        return PrivacyOut(
            privacy_id=record.privacy_id,
            user_id=record.user_id,
            library_id=record.library_id,
            target_type=record.target_type,  # type: ignore[arg-type]
            target_id=record.target_id,
            created_at=record.created_at,
        )

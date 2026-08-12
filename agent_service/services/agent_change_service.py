"""
Durable Agent patch tracking and guarded undo service.

The service records exact text replacements per Agent run.  It deliberately
works on the edited file content, rather than repository-wide Git output, so a
turn summary and its undo action cannot absorb unrelated workspace changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.agent_change import AgentChangeSnapshotRecord
from agent_service.services.knowledge_library_service import KnowledgeLibraryService


class AgentChangeService:
    """Store one Agent-run patch list and safely reverse completed snapshots."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        knowledge_library_service: KnowledgeLibraryService,
        engine: Engine | None = None,
        create_tables: bool = True,
    ) -> None:
        """Initialize persistent storage and the active knowledge-file service."""

        self.knowledge_library_service = knowledge_library_service
        self.engine = engine or create_engine(f"sqlite:///{config.storage.sqlite_path}", pool_pre_ping=True)
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def start_run(self, *, user_id: str, session_id: str, run_id: str) -> None:
        """Create the durable empty snapshot for an Agent run if it is absent."""

        with Session(self.engine) as db_session:
            existing = db_session.exec(
                select(AgentChangeSnapshotRecord).where(AgentChangeSnapshotRecord.run_id == run_id)
            ).first()
            if existing is not None:
                return
            db_session.add(
                AgentChangeSnapshotRecord(
                    snapshot_id=f"change_{uuid4().hex}",
                    user_id=user_id,
                    session_id=session_id,
                    run_id=run_id,
                )
            )
            db_session.commit()

    def record_edit(
        self,
        *,
        user_id: str,
        run_id: str,
        path: str,
        before: str | None,
        after: str,
    ) -> dict[str, int]:
        """Append one text edit and return its added/deleted line counts."""

        additions, deletions = _line_change_counts(before, after)
        with Session(self.engine) as db_session:
            record = db_session.exec(
                select(AgentChangeSnapshotRecord).where(AgentChangeSnapshotRecord.run_id == run_id)
            ).first()
            if record is None or record.user_id != user_id or record.is_finalized:
                raise ValueError("change snapshot is unavailable")
            edits = _decode_edits(record.edits_json)
            edits.append({"path": path, "before": before, "after": after, "additions": additions, "deletions": deletions})
            record.edits_json = json.dumps(edits, ensure_ascii=False)
            record.additions += additions
            record.deletions += deletions
            db_session.add(record)
            db_session.commit()
        return {"additions": additions, "deletions": deletions}

    def finalize_run(self, *, run_id: str) -> dict[str, Any] | None:
        """Freeze a completed run and return its public summary when it changed files."""

        with Session(self.engine) as db_session:
            record = db_session.exec(
                select(AgentChangeSnapshotRecord).where(AgentChangeSnapshotRecord.run_id == run_id)
            ).first()
            if record is None:
                return None
            record.is_finalized = True
            record.finalized_at = datetime.now(timezone.utc)
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return self._public_record(record) if record.additions or record.deletions else None

    def latest_for_session(self, *, session_id: str) -> dict[str, Any] | None:
        """Return the latest finalized snapshot for one session."""

        statement = (
            select(AgentChangeSnapshotRecord)
            .where(AgentChangeSnapshotRecord.session_id == session_id)
            .where(AgentChangeSnapshotRecord.is_finalized == True)  # noqa: E712
            .order_by(AgentChangeSnapshotRecord.created_at.desc())
        )
        with Session(self.engine) as db_session:
            record = db_session.exec(statement).first()
            return self._public_record(record) if record is not None else None

    def current_for_run(self, *, run_id: str) -> dict[str, Any] | None:
        """Return the current unfinalized-or-finalized snapshot for live UI updates."""

        with Session(self.engine) as db_session:
            record = db_session.exec(
                select(AgentChangeSnapshotRecord).where(AgentChangeSnapshotRecord.run_id == run_id)
            ).first()
            return self._public_record(record) if record is not None and (record.additions or record.deletions) else None

    def undo_snapshot(self, *, snapshot_id: str, user_id: str) -> dict[str, Any]:
        """Undo a snapshot only when every target still matches its saved result."""

        with Session(self.engine) as db_session:
            record = db_session.get(AgentChangeSnapshotRecord, snapshot_id)
            if record is None or record.user_id != user_id:
                raise ValueError("change snapshot not found")
            if record.is_undone:
                raise ValueError("change snapshot has already been undone")
            edits = _decode_edits(record.edits_json)
            for edit in reversed(edits):
                current = self.knowledge_library_service.read_file(user_id=user_id, path=str(edit["path"]))["content"]
                if current != edit["after"]:
                    raise ValueError(f"file changed after this turn: {edit['path']}")
            for edit in reversed(edits):
                if edit.get("before") is None:
                    self.knowledge_library_service.delete_path(user_id=user_id, path=str(edit["path"]))
                else:
                    self.knowledge_library_service.write_file(
                        user_id=user_id,
                        path=str(edit["path"]),
                        content=str(edit["before"]),
                    )
            record.is_undone = True
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return self._public_record(record)

    @staticmethod
    def _public_record(record: AgentChangeSnapshotRecord) -> dict[str, Any]:
        """Convert a database record to the response shape consumed by the UI."""

        edits = _decode_edits(record.edits_json)
        return {
            "snapshot_id": record.snapshot_id,
            "session_id": record.session_id,
            "run_id": record.run_id,
            "additions": record.additions,
            "deletions": record.deletions,
            "is_undone": record.is_undone,
            "created_at": record.created_at.isoformat(),
            "files": _file_summaries(edits),
            "edits": edits,
        }


def _decode_edits(value: str) -> list[dict[str, Any]]:
    """Decode valid persisted edit arrays without exposing malformed database data."""

    try:
        decoded = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    return [item for item in decoded if isinstance(item, dict)] if isinstance(decoded, list) else []


def _line_change_counts(before: str | None, after: str) -> tuple[int, int]:
    """Return compact line statistics for one whole-file replacement."""

    import difflib

    additions = deletions = 0
    for line in difflib.ndiff((before or "").splitlines(), after.splitlines()):
        additions += line.startswith("+ ")
        deletions += line.startswith("- ")
    return additions, deletions


def _file_summaries(edits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate edit statistics by file while retaining each patch for the detail drawer."""

    grouped: dict[str, dict[str, Any]] = {}
    for edit in edits:
        path = str(edit.get("path") or "")
        entry = grouped.setdefault(path, {"path": path, "additions": 0, "deletions": 0, "edits": []})
        entry["additions"] += int(edit.get("additions") or 0)
        entry["deletions"] += int(edit.get("deletions") or 0)
        entry["edits"].append(edit)
    return list(grouped.values())

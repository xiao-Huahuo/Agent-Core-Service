"""
Token usage persistence and aggregation service.

Usage:
The service extracts model-call token usage from assistant message trace
metadata into `agent_token_usage`, then serves per-call, time-bucket, and
session-total statistics for the dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.message import MessageRecord
from agent_service.models.session import SessionRecord
from agent_service.models.token_usage import TokenUsageRecord


INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "10m": 600,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "3h": 10800,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
    "3d": 259200,
    "10d": 864000,
    "15d": 1296000,
}
SUPPORTED_INTERVALS = tuple([*INTERVAL_SECONDS.keys(), "month"])
MODEL_TIERS = {"large", "small"}
DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")
NON_SESSION_TOKEN_SOURCE = "__non_session__"


class TokenUsageService:
    """
    Token usage business service.

    config: Global application config used to resolve the SQLite database path.
    engine: Optional engine for tests or dependency injection.
    create_tables: Whether to create missing SQLModel tables.
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        engine: Engine | None = None,
        create_tables: bool = True,
    ) -> None:
        """Initialize the SQLite engine and create the token usage table."""

        self.config = config
        self.engine = engine or create_engine(f"sqlite:///{config.storage.sqlite_path}", pool_pre_ping=True)
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def record_message_token_usage(self, message: MessageRecord) -> int:
        """
        Extract and persist token usage events from one message.

        message: Newly created or backfilled message record.
        Returns the number of newly inserted token usage rows.
        """

        records = self._records_from_message(message)
        if not records:
            return 0
        inserted = 0
        with Session(self.engine) as db_session:
            for record in records:
                if db_session.get(TokenUsageRecord, record.token_usage_id) is not None:
                    continue
                db_session.add(record)
                inserted += 1
            db_session.commit()
        return inserted

    def record_llm_response_token_usage(
        self,
        *,
        user_id: str,
        response: Any,
        node: str,
        event: str,
        model_tier: str,
        session_id: str | None = None,
        source_id: str | None = None,
        created_at: datetime | None = None,
    ) -> int:
        """
        Persist token usage for model calls that are not assistant messages.

        user_id: Owner of the background model call.
        response: LangChain message returned by the scheduler.
        node/event: Logical source shown in per-call charts.
        model_tier: `large` or `small`.
        session_id: Optional real session id. Omit for non-session background calls.
        source_id: Optional deterministic source id used for traceability.
        created_at: Optional event time; defaults to now.
        """

        if model_tier not in MODEL_TIERS:
            return 0
        usage = self._normalize_response_usage(response)
        if usage["total_tokens"] <= 0:
            return 0
        source = source_id or f"runtime_{uuid4().hex}"
        record = TokenUsageRecord(
            token_usage_id=f"tok_runtime_{uuid4().hex}",
            user_id=user_id,
            session_id=session_id or NON_SESSION_TOKEN_SOURCE,
            message_id=source[:64] or NON_SESSION_TOKEN_SOURCE,
            node=node[:64],
            event=event[:96],
            model_tier=model_tier,
            model_name=self._response_model_name(response),
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            total_tokens=usage["total_tokens"],
            created_at=created_at or datetime.now(timezone.utc),
        )
        with Session(self.engine) as db_session:
            db_session.add(record)
            db_session.commit()
        return 1

    def backfill_user(self, *, user_id: str, session_id: str | None = None) -> int:
        """
        Backfill token usage events from existing assistant messages.

        user_id: User whose messages should be scanned.
        session_id: Optional session filter.
        """

        statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .where(MessageRecord.role == "assistant")
            .order_by(MessageRecord.created_at.asc())
        )
        if session_id:
            statement = statement.where(MessageRecord.session_id == session_id)
        inserted = 0
        with Session(self.engine) as db_session:
            messages = list(db_session.exec(statement).all())
        for message in messages:
            inserted += self.record_message_token_usage(message)
        return inserted

    def get_dashboard_stats(
        self,
        *,
        user_id: str,
        session_id: str | None = None,
        interval: str = "5m",
        limit: int = 120,
        lookback_hours: int | None = None,
        session_sort: str = "time",
    ) -> dict[str, Any]:
        """
        Return token usage stats for dashboard cards.

        The response contains per-call rows, uniform time buckets, and session
        totals. Existing message trace metadata is backfilled before querying.

        lookback_hours: Filter bucket data to the last N hours. None means no filter.
        session_sort: Session total sort strategy: 'time' (default) or 'tokens'.
        """

        interval_key = interval if interval in SUPPORTED_INTERVALS else "5m"
        self.backfill_user(user_id=user_id, session_id=session_id)
        records = self._list_records(
            user_id=user_id,
            session_id=session_id,
            limit=max(1, min(limit, 500)),
            include_non_session=True,
        )
        all_user_records = self._list_records(user_id=user_id, session_id=None, limit=5000)
        return {
            "interval": interval_key,
            "calls": [self._serialize_record(record) for record in records],
            "buckets": self._build_buckets(all_user_records, interval_key, lookback_hours=lookback_hours),
            "sessions": self._build_session_totals(user_id=user_id, sort_by=session_sort),
        }

    def _list_records(
        self,
        *,
        user_id: str,
        session_id: str | None,
        limit: int,
        include_non_session: bool = False,
    ) -> list[TokenUsageRecord]:
        """List token usage records in ascending time order."""

        statement = (
            select(TokenUsageRecord)
            .where(TokenUsageRecord.user_id == user_id)
            .where(TokenUsageRecord.model_tier.in_(MODEL_TIERS))
            .order_by(TokenUsageRecord.created_at.desc(), TokenUsageRecord.token_usage_id.desc())
            .limit(limit)
        )
        if session_id and include_non_session:
            statement = statement.where(
                or_(
                    TokenUsageRecord.session_id == session_id,
                    TokenUsageRecord.session_id == NON_SESSION_TOKEN_SOURCE,
                )
            )
        elif session_id:
            statement = statement.where(TokenUsageRecord.session_id == session_id)
        with Session(self.engine) as db_session:
            rows = list(db_session.exec(statement).all())
        rows.reverse()
        return rows

    def _build_buckets(
        self, records: list[TokenUsageRecord], interval: str, *, lookback_hours: int | None = None
    ) -> list[dict[str, Any]]:
        """Aggregate token usage into uniform time buckets."""

        if lookback_hours:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=lookback_hours)
            records = [r for r in records if r.created_at >= cutoff]
        buckets: dict[str, dict[str, Any]] = {}
        for record in records:
            key, label, start = self._bucket_key(record.created_at, interval)
            bucket = buckets.setdefault(
                key,
                {
                    "bucket": key,
                    "label": label,
                    "start_at": start.isoformat(),
                    "large_tokens": 0,
                    "small_tokens": 0,
                    "total_tokens": 0,
                    "call_count": 0,
                },
            )
            if record.model_tier == "large":
                bucket["large_tokens"] += record.total_tokens
            elif record.model_tier == "small":
                bucket["small_tokens"] += record.total_tokens
            bucket["total_tokens"] += record.total_tokens
            bucket["call_count"] += 1
        if not buckets:
            return []
        starts = sorted(datetime.fromisoformat(item["start_at"]) for item in buckets.values())
        return [
            buckets.get(key) or self._empty_bucket(key, label, start)
            for key, label, start in self._iter_bucket_range(starts[0], starts[-1], interval)
        ]

    def _build_session_totals(self, *, user_id: str, sort_by: str = "time") -> list[dict[str, Any]]:
        """Aggregate token totals by session for the given user.

        sort_by: 'time' sorts by updated_at descending; 'tokens' by total_tokens descending.
        """

        sessions: dict[str, dict[str, Any]] = {}
        with Session(self.engine) as db_session:
            session_records = list(
                db_session.exec(
                    select(SessionRecord)
                    .where(SessionRecord.user_id == user_id)
                    .order_by(SessionRecord.updated_at.desc())
                ).all()
            )
            usage_records = list(
                db_session.exec(
                    select(TokenUsageRecord)
                    .where(TokenUsageRecord.user_id == user_id)
                    .where(TokenUsageRecord.session_id != NON_SESSION_TOKEN_SOURCE)
                    .where(TokenUsageRecord.model_tier.in_(MODEL_TIERS))
                ).all()
            )
        for session in session_records:
            sessions[session.session_id] = {
                "session_id": session.session_id,
                "session_name": session.session_name,
                "large_tokens": 0,
                "small_tokens": 0,
                "total_tokens": 0,
                "call_count": 0,
                "updated_at": session.updated_at.isoformat(),
            }
        for record in usage_records:
            item = sessions.setdefault(
                record.session_id,
                {
                    "session_id": record.session_id,
                    "session_name": record.session_id,
                    "large_tokens": 0,
                    "small_tokens": 0,
                    "total_tokens": 0,
                    "call_count": 0,
                    "updated_at": record.created_at.isoformat(),
                },
            )
            if record.model_tier == "large":
                item["large_tokens"] += record.total_tokens
            elif record.model_tier == "small":
                item["small_tokens"] += record.total_tokens
            item["total_tokens"] += record.total_tokens
            item["call_count"] += 1
        if sort_by == "tokens":
            return sorted(sessions.values(), key=lambda item: item["total_tokens"], reverse=True)
        return sorted(sessions.values(), key=lambda item: item["updated_at"], reverse=True)

    def _records_from_message(self, message: MessageRecord) -> list[TokenUsageRecord]:
        """Convert one message's trace metadata into token usage records."""

        metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
        traces = metadata.get("trace")
        if not isinstance(traces, list):
            return []
        records: list[TokenUsageRecord] = []
        for index, trace in enumerate(traces):
            if not isinstance(trace, dict):
                continue
            usage = self._normalize_usage(trace.get("token_usage"))
            if usage["total_tokens"] <= 0:
                continue
            model_tier = self._model_tier_for_trace(trace)
            if model_tier not in MODEL_TIERS:
                continue
            records.append(
                TokenUsageRecord(
                    token_usage_id=f"tok_{message.message_id}_{index}",
                    user_id=message.user_id,
                    session_id=message.session_id,
                    message_id=message.message_id,
                    node=str(trace.get("node") or ""),
                    event=str(trace.get("event") or ""),
                    model_tier=model_tier,
                    model_name=str(trace.get("model_name") or ""),
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_tokens=usage["total_tokens"],
                    created_at=self._trace_datetime(trace.get("ts")) or message.created_at,
                )
            )
        return records

    @staticmethod
    def _serialize_record(record: TokenUsageRecord) -> dict[str, Any]:
        """Serialize a token usage record for REST responses."""

        return {
            "token_usage_id": record.token_usage_id,
            "session_id": record.session_id,
            "message_id": record.message_id,
            "node": record.node,
            "event": record.event,
            "model_tier": record.model_tier,
            "model_name": record.model_name,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "total_tokens": record.total_tokens,
            "created_at": record.created_at.isoformat(),
        }

    @staticmethod
    def _normalize_usage(value: Any) -> dict[str, int]:
        """Normalize OpenAI-compatible token usage field names."""

        if not isinstance(value, dict):
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        input_tokens = int(value.get("input_tokens") or value.get("prompt_tokens") or 0)
        output_tokens = int(value.get("output_tokens") or value.get("completion_tokens") or 0)
        total_tokens = int(value.get("total_tokens") or input_tokens + output_tokens or 0)
        if input_tokens <= 0 and output_tokens <= 0 and total_tokens > 0:
            input_tokens = total_tokens
        return {
            "input_tokens": max(input_tokens, 0),
            "output_tokens": max(output_tokens, 0),
            "total_tokens": max(total_tokens, 0),
        }

    @classmethod
    def _normalize_response_usage(cls, response: Any) -> dict[str, int]:
        """Extract token usage from common LangChain response metadata shapes."""

        usage_metadata = getattr(response, "usage_metadata", None)
        usage = cls._normalize_usage(usage_metadata)
        if usage["total_tokens"] > 0:
            return usage
        response_metadata = getattr(response, "response_metadata", None)
        if isinstance(response_metadata, dict):
            for key in ("token_usage", "usage", "usage_metadata"):
                usage = cls._normalize_usage(response_metadata.get(key))
                if usage["total_tokens"] > 0:
                    return usage
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    @staticmethod
    def _response_model_name(response: Any) -> str:
        """Read the provider model name from a LangChain response when present."""

        response_metadata = getattr(response, "response_metadata", None)
        if isinstance(response_metadata, dict):
            for key in ("model_name", "model", "model_id"):
                value = response_metadata.get(key)
                if value:
                    return str(value)[:128]
        return ""

    @staticmethod
    def _model_tier_for_trace(trace: dict[str, Any]) -> str:
        """Infer large/small model pool from trace metadata."""

        tier = trace.get("model_tier")
        if tier in MODEL_TIERS:
            return str(tier)
        node = str(trace.get("node") or "")
        if node in {"compress", "planner", "observation", "summary"}:
            return "small"
        if node in {"agent", "agent_simple"}:
            return "large" if tier == "large" else "large" if node == "agent" else "small"
        return "runtime"

    @staticmethod
    def _trace_datetime(value: Any) -> datetime | None:
        """Convert a trace timestamp to UTC datetime when possible."""

        if not isinstance(value, int | float):
            return None
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _bucket_key(value: datetime, interval: str) -> tuple[str, str, datetime]:
        """Return stable bucket key, label, and start time."""

        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(DISPLAY_TIMEZONE)
        if interval == "month":
            start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start.strftime("%Y-%m"), start.strftime("%Y-%m"), start
        seconds = INTERVAL_SECONDS.get(interval, INTERVAL_SECONDS["5m"])
        if seconds >= 86400:
            days = max(seconds // 86400, 1)
            local_midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            bucket_ordinal = local_midnight.toordinal() - (local_midnight.toordinal() % days)
            start = datetime.fromordinal(bucket_ordinal).replace(tzinfo=DISPLAY_TIMEZONE)
            label = start.strftime("%Y-%m-%d")
            return start.isoformat(), label, start
        minute_of_day = dt.hour * 60 + dt.minute
        bucket_minutes = max(seconds // 60, 1)
        floored_minutes = minute_of_day - (minute_of_day % bucket_minutes)
        start = dt.replace(hour=floored_minutes // 60, minute=floored_minutes % 60, second=0, microsecond=0)
        label = start.strftime("%m-%d %H:%M") if seconds < 86400 else start.strftime("%Y-%m-%d")
        return start.isoformat(), label, start

    @staticmethod
    def _empty_bucket(key: str, label: str, start: datetime) -> dict[str, Any]:
        """Build a zero-value bucket used to keep chart ticks evenly spaced."""

        return {
            "bucket": key,
            "label": label,
            "start_at": start.isoformat(),
            "large_tokens": 0,
            "small_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
        }

    @classmethod
    def _iter_bucket_range(
        cls,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> list[tuple[str, str, datetime]]:
        """Yield every bucket boundary between two local bucket start times."""

        if interval == "month":
            cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            result: list[tuple[str, str, datetime]] = []
            while cursor <= end:
                result.append((cursor.strftime("%Y-%m"), cursor.strftime("%Y-%m"), cursor))
                year = cursor.year + (1 if cursor.month == 12 else 0)
                month = 1 if cursor.month == 12 else cursor.month + 1
                cursor = cursor.replace(year=year, month=month)
            return result
        seconds = INTERVAL_SECONDS.get(interval, INTERVAL_SECONDS["5m"])
        step = timedelta(seconds=seconds)
        cursor = start
        result = []
        while cursor <= end:
            key, label, bucket_start = cls._bucket_key(cursor, interval)
            result.append((key, label, bucket_start))
            cursor += step
        return result

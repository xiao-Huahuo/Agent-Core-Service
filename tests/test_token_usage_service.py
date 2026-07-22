"""
Token usage service tests.

Usage:
Verifies persisted token usage extraction from message traces and the dashboard
aggregation contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.models.session import SessionRecord
from agent_service.models.token_usage import TokenUsageRecord
from agent_service.schemas.message import MessageCreate
from agent_service.services.message_service import MessageService
from agent_service.services.token_usage_service import NON_SESSION_TOKEN_SOURCE, TokenUsageService


def test_message_create_persists_token_usage_and_dashboard_stats() -> None:
    """Assistant trace token usage should be persisted and aggregated by the backend."""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(SessionRecord(session_id="sess_a", user_id="u1", session_name="A"))
        db_session.add(SessionRecord(session_id="sess_b", user_id="u1", session_name="B"))
        db_session.commit()
    message_service = MessageService(config=config, engine=engine, create_tables=False)

    message_service.create_message(
        MessageCreate(
            session_id="sess_a",
            user_id="u1",
            role="assistant",
            content="done",
            metadata_json={
                "trace": [
                    {
                        "node": "agent",
                        "event": "model_response",
                        "model_tier": "large",
                        "model_name": "large-model",
                        "token_usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                    },
                    {
                        "node": "planner",
                        "event": "strategy_generated",
                        "model_tier": "small",
                        "model_name": "small-model",
                        "token_usage": {"total_tokens": 30},
                    },
                    {
                        "node": "safety_output",
                        "event": "passed",
                        "model_tier": "runtime",
                        "token_usage": {"total_tokens": 999},
                    },
                ]
            },
        )
    )
    message_service.create_message(
        MessageCreate(
            session_id="sess_b",
            user_id="u1",
            role="assistant",
            content="done",
            metadata_json={
                "trace": [
                    {
                        "node": "agent",
                        "event": "model_response",
                        "model_tier": "large",
                        "token_usage": {"total_tokens": 50},
                    }
                ]
            },
        )
    )

    service = TokenUsageService(config=config, engine=engine, create_tables=False)
    stats = service.get_dashboard_stats(user_id="u1", session_id="sess_a", interval="1h", limit=20)

    assert [item["total_tokens"] for item in stats["calls"]] == [120, 30]
    assert stats["buckets"][0]["large_tokens"] == 170
    assert stats["buckets"][0]["small_tokens"] == 30
    session_totals = {item["session_id"]: item for item in stats["sessions"]}
    assert session_totals["sess_a"]["total_tokens"] == 150
    assert session_totals["sess_b"]["total_tokens"] == 50


def test_time_buckets_use_local_time_and_fill_empty_ticks() -> None:
    """Time buckets should use display timezone labels and zero-fill gaps."""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = TokenUsageService(config=config, engine=engine, create_tables=False)
    records = [
        TokenUsageRecord(
            token_usage_id="tok_a",
            user_id="u1",
            session_id="sess_a",
            message_id="msg_a",
            model_tier="large",
            total_tokens=10,
            created_at=datetime(2026, 7, 22, 8, 4, 20, tzinfo=timezone.utc),
        ),
        TokenUsageRecord(
            token_usage_id="tok_b",
            user_id="u1",
            session_id="sess_a",
            message_id="msg_b",
            model_tier="small",
            total_tokens=20,
            created_at=datetime(2026, 7, 22, 8, 7, 5, tzinfo=timezone.utc),
        ),
    ]

    buckets = service._build_buckets(records, "1m")

    assert [bucket["label"] for bucket in buckets] == [
        "07-22 16:04",
        "07-22 16:05",
        "07-22 16:06",
        "07-22 16:07",
    ]
    assert [bucket["total_tokens"] for bucket in buckets] == [10, 0, 0, 20]
    assert buckets[0]["start_at"].endswith("+08:00")


def test_non_session_model_calls_are_excluded_from_session_totals() -> None:
    """Background LLM calls should affect call/bucket charts but not session totals."""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(SessionRecord(session_id="sess_a", user_id="u1", session_name="A"))
        db_session.commit()
    service = TokenUsageService(config=config, engine=engine, create_tables=False)

    service.record_llm_response_token_usage(
        user_id="u1",
        session_id=None,
        response=SimpleNamespace(
            usage_metadata={"input_tokens": 40, "output_tokens": 6, "total_tokens": 46},
            response_metadata={"model_name": "small-model"},
        ),
        node="knowledge_graph",
        event="section_extracted",
        model_tier="small",
        source_id="kg_doc_sec",
        created_at=datetime(2026, 7, 22, 8, 7, tzinfo=timezone.utc),
    )

    stats = service.get_dashboard_stats(user_id="u1", session_id="sess_a", interval="1m", limit=20)

    assert stats["calls"][0]["session_id"] == NON_SESSION_TOKEN_SOURCE
    assert stats["calls"][0]["node"] == "knowledge_graph"
    assert stats["calls"][0]["total_tokens"] == 46
    assert stats["buckets"][0]["small_tokens"] == 46
    assert stats["sessions"][0]["session_id"] == "sess_a"
    assert stats["sessions"][0]["total_tokens"] == 0

"""
AgentService 核心功能测试脚本。

功能说明:
本文件用于测试 `agent_service.agent_core` 的基础行为。测试不请求真实大模型,
而是通过假图对象和假的图结构验证 `AgentCore` 的初始化、流式输出包装和
Mermaid 图生成逻辑。

使用说明:
在项目根目录执行 `python -m pytest tests/test_agent_core_service.py`。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from sqlmodel import SQLModel, create_engine

from agent_service.agent_core import AgentCore
from agent_service.agent_core.agent_core import _extract_friendly_error
from agent_service.agent_core.nodes.compress import CompressNode
from agent_service.agent_core.nodes.model_decision import get_user_llm_overrides
from agent_service.agent_core.nodes.summary import SummaryNode
from agent_service.agent_core.nodes.tool_call import ToolCallNode
from agent_service.core.agent_config import AgentConfig
from agent_service.models.longterm_memory_spec import LongTermMemorySpec
from agent_service.models.message import MessageRecord
from agent_service.models.session import SessionRecord
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecOut
from agent_service.schemas.message import MessageCreate
from agent_service.schemas.message import MessageOut
from agent_service.schemas.session import SessionOut
from agent_service.scripts.download_model import MODEL_MARKER_FILE
from agent_service.scripts.download_model import PADDLEOCR_MARKER_FILE
from agent_service.scripts.download_model import ensure_paddleocr_models
from agent_service.scripts.draw_agent_graph import build_mermaid
from agent_service.scripts.download_model import is_model_available
from agent_service.scripts.download_model import model_target_dir
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.memory_resolver import MemoryFact
from agent_service.services.memory.memory_resolver import MemoryResolver
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService
from agent_service.services.message_service import MessageService
from agent_service.services.safety import SafetyService
from agent_service.services.session_service import SessionService
from agent_service.services.settings_service import SettingsService
from agent_service.tools import ToolExecutor, ToolRegistry, clear_tool_runtime, set_tool_runtime
from agent_service.tools.runtime_context import get_tool_citation_map


TEST_TEMP_DIR = Path(__file__).resolve().parents[1] / "runtime" / "test_tmp"


class FakeCompiledGraph:
    """
    测试用假编译图。

    updates: 模拟 LangGraph `stream(..., stream_mode="updates")` 产生的节点更新。
    graph_data: 模拟 `CompiledStateGraph.get_graph()` 返回的真实图结构数据。
    """

    def __init__(self, updates: list[dict[str, Any]] | None = None) -> None:
        """创建包含固定节点、固定边和可控流式输出的假图。"""

        self.updates = updates or []
        self.stream_inputs: list[dict[str, Any]] = []
        self.graph_data = SimpleNamespace(
            nodes={
                "__start__": object(),
                "agent": object(),
                "summary": object(),
                "__end__": object(),
            },
            edges=[
                SimpleNamespace(source="__start__", target="agent", conditional=False),
                SimpleNamespace(source="agent", target="summary", conditional=True),
                SimpleNamespace(source="summary", target="__end__", conditional=False),
            ],
        )

    def stream(self, *args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        """返回预设的 LangGraph 节点更新列表。"""

        if args:
            self.stream_inputs.append(args[0])
        return self.updates

    def get_graph(self) -> Any:
        """返回预设图结构,供 Mermaid 绘图脚本读取。"""

        return self.graph_data


class FakeEmbeddingProvider:
    """
    测试用假 Embedding 提供者。

    dimension: 输出向量维度。
    """

    def __init__(self, *, dimension: int = 3) -> None:
        """保存固定向量维度。"""

        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """根据文本长度生成稳定假向量。"""

        return [[float(len(text) + index) for index in range(self.dimension)] for text in texts]


class FakeSummaryService:
    """
    测试用假摘要服务。

    calls: 记录被异步调用的 user_id 和 session_id。
    """

    def __init__(self) -> None:
        """初始化调用记录。"""

        self.calls: list[tuple[str, str]] = []

    def summarize_session(self, *, user_id: str, session_id: str) -> str:
        """记录摘要调用并返回固定摘要。"""

        self.calls.append((user_id, session_id))
        return "测试摘要"


def make_test_config() -> AgentConfig:
    """
    创建测试用配置。
    """

    TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(TEST_TEMP_DIR),
                "base_data_dir": str(TEST_TEMP_DIR / "runtime"),
            },
            "model": {
                "model_name": "test-model",
                "api_key": "test-key",
                "base_url": "https://example.com/v1",
            },
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )


def test_agent_core_init_generates_mermaid_graph() -> None:
    """验证 AgentCore 初始化时会根据实际图结构生成 Mermaid 文件。"""

    config = make_test_config()
    agent = AgentCore(config=config, graph=FakeCompiledGraph())

    assert agent.graph_diagram_path == TEST_TEMP_DIR / "agent_graph.mmd"
    assert agent.graph_diagram_path.exists()
    assert 'agent["agent"]' in agent.graph_diagram_path.read_text(encoding="utf-8")


def test_agent_core_stream_run_wraps_graph_updates() -> None:
    """验证 AgentCore 会把图节点更新包装为 SSE 风格字符串。"""

    config = make_test_config()
    fake_graph = FakeCompiledGraph(
        updates=[
            {
                "agent": {
                    "messages": [AIMessage(content="测试回复")],
                    "trace": [{"node": "agent", "event": "model_response"}],
                }
            }
        ]
    )
    agent = AgentCore(config=config, graph=fake_graph)

    chunks = list(agent.stream_run(prompt="你好", user_id="u1", session_id="s1"))

    assert "测试回复" in str(chunks[0])
    assert chunks[0].get("node") == "agent"


def test_agent_core_run_once_returns_structured_result() -> None:
    """验证 AgentCore.run_once 会返回最终输出、事件列表和原始流式数据。"""

    config = make_test_config()
    fake_graph = FakeCompiledGraph(
        updates=[
            {
                "agent": {
                    "messages": [AIMessage(content="最终回复")],
                    "trace": [{"node": "agent", "event": "model_response"}],
                }
            }
        ]
    )
    agent = AgentCore(config=config, graph=fake_graph)

    result = agent.run_once(prompt="你好", user_id="u1", session_id="s1")

    assert result["final_output"] == "最终回复"
    assert result["events"][0]["node"] == "agent"


def test_agent_core_run_session_prompt_uses_context_and_persists_messages() -> None:
    """验证 session 正式入口会加载历史上下文并保存本轮新增消息。"""

    config = AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(TEST_TEMP_DIR),
                "base_data_dir": str(TEST_TEMP_DIR / "runtime"),
            },
            "memory": {"max_context_messages": 2},
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    message_service = MessageService(config=config, engine=engine, create_tables=False)
    empty_snapshot = SimpleNamespace(post_rerank_results=[])
    retrieval_service = SimpleNamespace(
        retrieve_long_term_memory_with_debug=lambda **_kwargs: empty_snapshot,
        get_latest_session_summary=lambda **_kwargs: None,
        retrieve_knowledge_with_debug=lambda **_kwargs: empty_snapshot,
        get_latest_important_fact_summary=lambda **_kwargs: None,
        serialize_debug_snapshot=lambda _snapshot: {},
        warmup=lambda: None,
    )
    context_builder = ContextBuilder(
        config=config,
        message_service=message_service,
        retrieval_service=retrieval_service,
    )
    message_service.create_message(
        MessageCreate(
            session_id="sess_formal",
            user_id="user_1",
            role="user",
            content="上一轮关键词是 blue-river",
        )
    )
    fake_graph = FakeCompiledGraph(
        updates=[
            {
                "agent": {
                    "messages": [AIMessage(content="blue-river")],
                    "trace": [{"node": "agent", "event": "model_response"}],
                }
            }
        ]
    )
    agent = AgentCore(
        config=config,
        graph=fake_graph,
        message_service=message_service,
        context_builder=context_builder,
    )

    result = agent.run_session_prompt(
        prompt="关键词是什么?",
        user_id="user_1",
        session_id="sess_formal",
        reference="引用中的关键词是 blue-river",
    )
    saved_messages = message_service.list_recent_messages(user_id="user_1", session_id="sess_formal", limit=10)

    assert result["final_output"] == "blue-river"
    assert isinstance(fake_graph.stream_inputs[0]["messages"][0], SystemMessage)
    assert fake_graph.stream_inputs[0]["messages"][1].content == "上一轮关键词是 blue-river"
    assert "引用中的关键词是 blue-river" in fake_graph.stream_inputs[0]["messages"][-1].content
    assert "关键词是什么?" in fake_graph.stream_inputs[0]["messages"][-1].content
    assert {message.role for message in saved_messages} == {"user", "system", "assistant"}
    assert saved_messages[-2].metadata_json["reference"] == "引用中的关键词是 blue-river"
    assert saved_messages[-1].content == "blue-river"


def test_agent_core_build_human_readable_process() -> None:
    """验证 AgentCore 可以把结构化事件转换为给人阅读的执行过程。"""

    events = [
        {"node": "agent", "content": "", "tool_calls": [{"name": "get_current_time"}], "trace": []},
        {"node": "action", "content": "hello", "tool_calls": [], "trace": []},
        {"node": "agent", "content": "最终回复", "tool_calls": [], "trace": []},
    ]

    process = AgentCore.build_human_readable_process(events)

    assert process[0] == "1. 模型决定调用工具: get_current_time"
    assert process[-1] == "3. 模型生成最终回复。"


def test_build_mermaid_uses_actual_graph_edges() -> None:
    """验证 Mermaid 文本来自图结构中的真实节点和边。"""

    mermaid = build_mermaid(FakeCompiledGraph())

    assert "flowchart TD" in mermaid
    assert 'internal_start["START"]' in mermaid
    assert 'agent["agent"]' in mermaid
    assert 'agent -. "conditional" .-> summary' in mermaid


def test_session_out_converts_from_session_record() -> None:
    """验证 Session 数据库模型可以转换为输出 DTO。"""

    record = SessionRecord(
        session_id="sess_test",
        user_id="user_1",
        session_name="测试会话",
    )

    output = SessionOut.from_record(record)

    assert output.session_id == "sess_test"
    assert output.user_id == "user_1"
    assert output.session_name == "测试会话"


def test_message_record_links_to_session_and_converts_to_out() -> None:
    """验证 Message 通过 session_id 关联 Session,并可转换为输出 DTO。"""

    session = SessionRecord(
        session_id="sess_message",
        user_id="user_1",
        session_name="消息会话",
    )
    message = MessageRecord(
        message_id="msg_1",
        session_id=session.session_id,
        user_id=session.user_id,
        role="assistant",
        content="需要调用工具",
        tool_calls_json=[{"name": "get_current_time", "args": {"timezone_name": "Asia/Shanghai"}}],
        metadata_json={"node": "agent"},
    )

    output = MessageOut.from_record(message)

    assert message.session_id == session.session_id
    assert output.message_id == "msg_1"
    assert output.tool_calls_json[0]["name"] == "get_current_time"
    assert output.metadata_json["node"] == "agent"


def test_longterm_memory_spec_converts_to_out_with_source_metadata() -> None:
    """验证统一长期记忆结构可以承载 Memory/Knowledge 共同需要的溯源和时效字段。"""

    memory = LongTermMemorySpec(
        memory_id="mem_1",
        user_id="user_1",
        session_id="sess_message",
        tag="Memory",
        memory_type="session_summary",
        content="用户正在设计 AgentService 的记忆系统。",
        source_type="session_messages",
        source_id="sess_message",
        source_range_json={"message_ids": ["msg_1", "msg_2"]},
        metadata_json={"facts": ["Message 是 Session 的原始事件日志。"]},
        confidence=0.9,
        importance=0.8,
        authority=0.6,
        embedding_model="test-embedding",
        embedding_vector_json=[0.1, 0.2, 0.3],
    )

    output = LongTermMemorySpecOut.from_record(memory)

    assert output.tag == "Memory"
    assert output.memory_type == "session_summary"
    assert output.source_range_json["message_ids"] == ["msg_1", "msg_2"]
    assert output.embedding_vector_json == [0.1, 0.2, 0.3]


def test_longterm_memory_service_creates_memory_with_embedding_json() -> None:
    """验证长期记忆服务可以保存摘要或知识库向量 JSON。"""

    config = make_test_config()
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = LongTermMemoryService(config=config, engine=engine, create_tables=False)

    memory = service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_1",
            tag="Memory",
            memory_type="session_summary",
            content="用户希望构建 RAG 记忆系统。",
            source_type="session_messages",
            source_id="sess_1",
            embedding_model="fake",
            embedding_vector_json=[1.0, 2.0, 3.0],
        )
    )

    assert memory.content == "用户希望构建 RAG 记忆系统。"
    assert memory.embedding_vector_json == [1.0, 2.0, 3.0]


def test_knowledge_ingestion_chunks_embeds_and_stores_files() -> None:
    """验证知识库入库服务会把本地文件切片、Embedding 并写入统一长期记忆。"""

    from agent_service.services.memory.rag.frontmatter_document import StructuredKnowledgeDocument, StructuredKnowledgeSection

    frontmatter_dir = TEST_TEMP_DIR / "knowledge_ingestion"
    frontmatter_dir.mkdir(parents=True, exist_ok=True)
    doc = StructuredKnowledgeDocument(
        document_id="demo_doc",
        source_type="text",
        source_path=str(frontmatter_dir / "demo.txt"),
        source_uri=str(frontmatter_dir / "demo.txt"),
        source_hash="demo_hash",
        title="demo",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        sections=[
            StructuredKnowledgeSection(
                section_id="sec_0000",
                heading="demo",
                title_path=["demo"],
                content="第一段知识。" * 80,
                start_char=0,
                end_char=len("第一段知识。" * 80),
            )
        ],
    )
    json_path = frontmatter_dir / "demo.json"
    json_path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False), encoding="utf-8")
    config = AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(TEST_TEMP_DIR),
                "base_data_dir": str(TEST_TEMP_DIR / "runtime"),
                "frontmatter_dir": str(frontmatter_dir),
            },
            "memory": {"chunk_size": 120, "chunk_overlap": 20, "knowledge_hash_lock_enabled": True},
            "model": {"embedding_model_name": "fake-embedding"},
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    embedding_service = EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=4))
    ingestion_service = KnowledgeIngestionService(
        config=config,
        embedding_service=embedding_service,
        memory_service=memory_service,
    )

    result = ingestion_service.ingest_frontmatter_dir()

    assert result.files_seen == 1
    assert result.files_ingested == 1
    assert result.chunks_created > 1
    assert memory_service.has_source_hash(
        source_hash="demo_hash",
        memory_type="knowledge_chunk",
    )


def test_summary_node_schedules_async_summary() -> None:
    """验证 summary 节点会异步触发会话摘要服务。"""

    config = make_test_config()
    summary_service = FakeSummaryService()
    node = SummaryNode(config=config, summary_service=summary_service)

    result = node({"messages": [HumanMessage(content="你好")], "user_id": "u1", "session_id": "s1", "trace": []})
    node.pending_tasks[-1].join(timeout=2)

    assert result["trace"][0]["event"] == "summary_scheduled"
    assert result["trace"][0]["mode"] == "scheduler_queue"
    assert summary_service.calls == [("u1", "s1")]


def test_session_service_generates_session_id() -> None:
    """验证 SessionService 生成的会话 ID 使用统一前缀。"""

    session_id = SessionService.generate_session_id()

    assert session_id.startswith("sess_")
    assert len(session_id) == 37


def test_message_service_lists_recent_messages_by_session_window() -> None:
    """验证 MessageService 只返回同一 session 的最近 N 条未摘要消息。"""

    config = make_test_config()
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=config, engine=engine, create_tables=False)

    for index in range(3):
        service.create_message(
            MessageCreate(
                session_id="sess_a",
                user_id="user_1",
                role="user",
                content=f"a-{index}",
            )
        )
    service.create_message(
        MessageCreate(
            session_id="sess_b",
            user_id="user_1",
            role="user",
            content="b-0",
        )
    )

    messages = service.list_recent_messages(user_id="user_1", session_id="sess_a", limit=2)

    assert len(messages) == 2
    assert {message.content for message in messages} == {"a-1", "a-2"}


def test_message_service_lists_complete_user_history_across_sessions() -> None:
    """验证观测面板可以读取同一用户跨 session 的完整消息历史。"""

    config = make_test_config()
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=config, engine=engine, create_tables=False)

    for session_id, content in (("sess_a", "a-0"), ("sess_b", "b-0")):
        service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id="user_1",
                role="user",
                content=content,
            )
        )
    service.create_message(
        MessageCreate(
            session_id="sess_other",
            user_id="user_2",
            role="user",
            content="other-user",
        )
    )

    messages = service.list_user_messages(user_id="user_1")

    assert [message.session_id for message in messages] == ["sess_a", "sess_b"]
    assert [message.content for message in messages] == ["a-0", "b-0"]


def test_message_service_limits_observability_history_by_recent_user_turns() -> None:
    """验证观测历史按最近用户轮次截取,并保留对应 RAG 与 assistant 记录。"""

    config = make_test_config()
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=config, engine=engine, create_tables=False)

    for index, session_id in enumerate(("sess_a", "sess_b", "sess_a"), start=1):
        service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id="user_1",
                role="system",
                content=f"rag-{index}",
                metadata_json={"rag_metrics": {"fill_rate": index * 10}},
            )
        )
        service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id="user_1",
                role="user",
                content=f"user-{index}",
            )
        )
        service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id="user_1",
                role="assistant",
                content=f"assistant-{index}",
                metadata_json={"node": "agent", "trace": [{"duration_ms": index * 100}]},
            )
        )

    def fail_if_complete_history_is_loaded(**_kwargs: Any) -> list[Any]:
        """有限范围查询不得先物化用户的完整消息历史。"""

        raise AssertionError("bounded observability query loaded complete history")

    service.list_user_messages = fail_if_complete_history_is_loaded  # type: ignore[method-assign]
    messages = service.list_user_observability_messages(user_id="user_1", turn_limit=2)

    contents = [message.content for message in messages]
    assert set(contents) == {
        "rag-2",
        "user-2",
        "assistant-2",
        "rag-3",
        "user-3",
        "assistant-3",
    }
    assert contents.index("rag-2") < contents.index("user-2") < contents.index("assistant-2")
    assert contents.index("rag-3") < contents.index("user-3") < contents.index("assistant-3")


def test_message_service_compacts_observability_trace_payload() -> None:
    """验证观测接口移除曲线计算不需要的 trace 大字段。"""

    metadata = MessageService.compact_observability_metadata(
        {
            "node": "action",
            "rag_metrics": {"fill_rate": 50},
            "trace": [
                {
                    "node": "action",
                    "event": "tool_call_end",
                    "duration_ms": 120,
                    "tool_name": "read_knowledge_file",
                    "result_count": 1,
                    "raw_content": "very large tool response",
                    "human_readable": "工具执行完成",
                }
            ],
            "context_messages": ["very large context"],
        }
    )

    assert metadata == {
        "node": "action",
        "rag_metrics": {"fill_rate": 50},
        "trace": [
            {
                "node": "action",
                "event": "tool_call_end",
                "duration_ms": 120,
                "tool_name": "read_knowledge_file",
                "result_count": 1,
            }
        ],
    }


def test_context_builder_appends_current_prompt_and_converts_roles() -> None:
    """验证 ContextBuilder 会转换历史消息并把当前 prompt 追加到最后。"""

    config = AgentConfig.load_config(
        {"memory": {"max_context_messages": 4}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=config, engine=engine, create_tables=False)
    retrieval_service = SimpleNamespace(
        retrieve_long_term_memory_with_debug=lambda **_kwargs: SimpleNamespace(post_rerank_results=[]),
        get_latest_session_summary=lambda **_kwargs: None,
        retrieve_knowledge_with_debug=lambda **_kwargs: SimpleNamespace(post_rerank_results=[]),
        get_latest_important_fact_summary=lambda **_kwargs: None,
        serialize_debug_snapshot=lambda _snapshot: {},
    )
    builder = ContextBuilder(config=config, message_service=service, retrieval_service=retrieval_service)
    service.create_message(MessageCreate(session_id="sess_ctx", user_id="user_1", role="system", content="系统提示"))
    service.create_message(MessageCreate(session_id="sess_ctx", user_id="user_1", role="user", content="你好"))
    service.create_message(
        MessageCreate(
            session_id="sess_ctx",
            user_id="user_1",
            role="assistant",
            content="",
            tool_calls_json=[{"id": "call_1", "name": "get_current_time", "args": {"timezone_name": "UTC"}}],
        )
    )
    service.create_message(
        MessageCreate(
            session_id="sess_ctx",
            user_id="user_1",
            role="tool",
            content="hello",
            tool_call_id="call_1",
        )
    )

    messages = builder.build_messages(user_id="user_1", session_id="sess_ctx", current_prompt="继续")

    assert isinstance(messages[0], SystemMessage)
    assert any(isinstance(message, HumanMessage) and message.content == "你好" for message in messages)
    assert isinstance(messages[-1], HumanMessage)
    assert messages[-1].content == "继续"


def test_context_builder_passes_user_id_to_automatic_knowledge_retrieval() -> None:
    """验证自动知识库召回使用当前用户范围,而不是默认 system 知识库。"""

    config = AgentConfig.load_config(
        {"memory": {"max_context_messages": 4}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=config, engine=engine, create_tables=False)
    empty_snapshot = SimpleNamespace(post_rerank_results=[])
    knowledge_calls: list[dict[str, Any]] = []

    def retrieve_knowledge_with_debug(**kwargs: Any) -> Any:
        """记录自动知识库召回参数。"""

        knowledge_calls.append(kwargs)
        return empty_snapshot

    retrieval_service = SimpleNamespace(
        retrieve_long_term_memory_with_debug=lambda **_kwargs: empty_snapshot,
        get_latest_session_summary=lambda **_kwargs: None,
        retrieve_knowledge_with_debug=retrieve_knowledge_with_debug,
        get_latest_important_fact_summary=lambda **_kwargs: None,
        serialize_debug_snapshot=lambda _snapshot: {},
    )
    builder = ContextBuilder(config=config, message_service=service, retrieval_service=retrieval_service)

    builder.build_messages(user_id="user_1", session_id="sess_scope", current_prompt="查找知识库内容")

    assert knowledge_calls == [
        {
            "query": "查找知识库内容",
            "user_id": "user_1",
            "top_k": config.memory.rerank_top_k,
        }
    ]


def test_context_builder_keeps_references_in_history_and_compressed_current_prompt() -> None:
    """引用应随历史恢复,并在当前上下文触发压缩后仍进入最终 HumanMessage。"""

    config = AgentConfig.load_config(
        {
            "memory": {
                "max_context_messages": 4,
                "summary_trigger_tokens": 5,
                "context_compression_tail_messages": 2,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=config, engine=engine, create_tables=False)
    empty_snapshot = SimpleNamespace(post_rerank_results=[])
    retrieval_service = SimpleNamespace(
        retrieve_long_term_memory_with_debug=lambda **_kwargs: empty_snapshot,
        retrieve_knowledge_with_debug=lambda **_kwargs: empty_snapshot,
        get_latest_session_summary=lambda **_kwargs: None,
        get_latest_important_fact_summary=lambda **_kwargs: None,
        serialize_debug_snapshot=lambda _snapshot: {},
    )
    builder = ContextBuilder(config=config, message_service=service, retrieval_service=retrieval_service)
    service.create_message(
        MessageCreate(
            session_id="sess_reference",
            user_id="user_1",
            role="user",
            content="历史问题",
            metadata_json={"reference": "历史引用材料"},
        )
    )

    messages = builder.build_messages(
        user_id="user_1",
        session_id="sess_reference",
        current_prompt="当前问题",
        reference="当前引用材料",
    )

    human_contents = [str(message.content) for message in messages if isinstance(message, HumanMessage)]
    assert any("历史引用材料" in content and "历史问题" in content for content in human_contents)
    assert "当前引用材料" in str(messages[-1].content)
    assert "当前问题" in str(messages[-1].content)


def test_context_builder_drops_incomplete_assistant_tool_call_history() -> None:
    """验证当历史 assistant.tool_calls 缺少 ToolMessage 对应时,ContextBuilder 会自动将该消息对移除"""

    config = AgentConfig.load_config(
        {"memory": {"max_context_messages": 4}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=config, engine=engine, create_tables=False)
    retrieval_service = SimpleNamespace(
        retrieve_long_term_memory_with_debug=lambda **_kwargs: SimpleNamespace(post_rerank_results=[]),
        get_latest_session_summary=lambda **_kwargs: None,
        retrieve_knowledge_with_debug=lambda **_kwargs: SimpleNamespace(post_rerank_results=[]),
        get_latest_important_fact_summary=lambda **_kwargs: None,
        serialize_debug_snapshot=lambda _snapshot: {},
    )
    builder = ContextBuilder(config=config, message_service=service, retrieval_service=retrieval_service)
    service.create_message(
        MessageCreate(
            session_id="sess_tool_gap",
            user_id="user_1",
            role="assistant",
            content="",
            tool_calls_json=[
                {"id": "call_knowledge_0", "name": "get_knowledge_context", "args": {"query": "测试"}}
            ],
        )
    )
    service.create_message(
        MessageCreate(
            session_id="sess_tool_gap",
            user_id="user_1",
            role="user",
            content="历史已经查询完毕，这里没有工具可执行。",
        )
    )

    messages = builder.build_messages(
        user_id="user_1",
        session_id="sess_tool_gap",
        current_prompt="现在城市的人口是什么?",
    )

    assert messages[-1].content == "现在城市的人口是什么?"


def test_retrieval_service_returns_ranked_memory_and_knowledge() -> None:
    """验证统一检索服务可以从 JSON 向量回退路径召回长期记忆和知识库片段。"""

    config = AgentConfig.load_config(
        {"memory": {"rerank_top_k": 2, "score_threshold": 0.0}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_recall",
            tag="Memory",
            memory_type="session_summary",
            content="项目代号是 stone-cat,负责模块是 SummaryNode。",
            source_type="session_messages",
            source_id="sess_recall",
            authority=0.8,
            embedding_model="fake",
            embedding_vector_json=[10.0, 11.0, 12.0],
        )
    )
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="system",
            session_id=None,
            tag="Knowledge",
            memory_type="knowledge_chunk",
            content="海洋酸化会影响贝类和珊瑚的钙化过程。",
            source_type="knowledge_file",
            source_id="ocean.txt",
            source_uri="resources/knowledge/ocean.txt",
            authority=0.7,
            embedding_model="fake",
            embedding_vector_json=[10.0, 11.0, 12.0],
        )
    )
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3)),
        memory_service=memory_service,
    )

    memories = retrieval_service.retrieve_long_term_memory(
        query="项目代号和负责模块是什么",
        user_id="user_1",
        session_id="sess_recall",
    )
    knowledge = retrieval_service.retrieve_knowledge(query="海洋酸化影响什么")

    assert memories[0].memory.content.startswith("项目代号是 stone-cat")
    assert knowledge[0].memory.source_uri == "resources/knowledge/ocean.txt"


def test_retrieval_service_handles_sqlite_naive_valid_until() -> None:
    """验证 SQLite 读回无时区 valid_until 时,长期记忆检索不会抛出时区比较异常。"""

    config = AgentConfig.load_config(
        {"memory": {"rerank_top_k": 1, "score_threshold": 0.0}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_time",
            tag="Memory",
            memory_type="session_summary",
            content="项目代号是 stone-cat。",
            source_type="session_messages",
            source_id="sess_time",
            valid_until=datetime.now(timezone.utc) + timedelta(days=1),
            embedding_model="fake",
            embedding_vector_json=[7.0, 8.0, 9.0],
        )
    )
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3)),
        memory_service=memory_service,
    )

    memories = retrieval_service.retrieve_long_term_memory(
        query="项目代号是什么",
        user_id="user_1",
        session_id="sess_time",
    )

    assert len(memories) == 1
    assert memories[0].memory.content == "项目代号是 stone-cat。"


def test_context_builder_includes_retrieved_memory_context() -> None:
    """验证上下文构建器会把长期记忆和知识库召回结果插入系统上下文。"""

    config = AgentConfig.load_config(
        {"memory": {"max_context_messages": 2, "rerank_top_k": 1, "score_threshold": 0.0}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    message_service = MessageService(config=config, engine=engine, create_tables=False)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_ctx",
            tag="Memory",
            memory_type="session_summary",
            content="项目代号是 stone-cat。",
            source_type="session_messages",
            embedding_model="fake",
            embedding_vector_json=[8.0, 9.0, 10.0],
        )
    )
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3)),
        memory_service=memory_service,
    )
    builder = ContextBuilder(config=config, message_service=message_service, retrieval_service=retrieval_service)
    message_service.create_message(MessageCreate(session_id="sess_ctx", user_id="user_1", role="user", content="你好"))

    messages = builder.build_messages(user_id="user_1", session_id="sess_ctx", current_prompt="项目代号是什么")

    assert isinstance(messages[0], SystemMessage)
    assert "get_long_term_memory" in messages[0].content


def test_context_builder_uses_important_fact_summary_when_budget_is_exceeded() -> None:
    """验证上下文接近 token 上限时,构建器会保留重要事实摘要并裁剪历史消息。"""

    config = AgentConfig.load_config(
        {
            "memory": {
                "max_context_messages": 6,
                "summary_trigger_tokens": 5,
                "context_compression_tail_messages": 2,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    message_service = MessageService(config=config, engine=engine, create_tables=False)
    for index in range(4):
        message_service.create_message(
            MessageCreate(
                session_id="sess_budget",
                user_id="user_1",
                role="user",
                content=f"历史消息-{index}",
            )
        )
    retrieval_service = SimpleNamespace(
        retrieve_long_term_memory_with_debug=lambda **_kwargs: SimpleNamespace(post_rerank_results=[]),
        get_latest_session_summary=lambda **_kwargs: None,
        retrieve_knowledge_with_debug=lambda **_kwargs: SimpleNamespace(post_rerank_results=[]),
        get_latest_important_fact_summary=lambda **_kwargs: SimpleNamespace(
            final_score=1.0,
            memory=SimpleNamespace(content="当前项目代号为3333333, 1111111 和 2222222 均已失效。"),
        ),
        serialize_debug_snapshot=lambda _snapshot: {},
    )
    builder = ContextBuilder(config=config, message_service=message_service, retrieval_service=retrieval_service)

    messages = builder.build_messages(
        user_id="user_1",
        session_id="sess_budget",
        current_prompt="当前项目代号是什么",
    )

    assert isinstance(messages[0], SystemMessage)
    assert "重要事实摘要" in messages[0].content
    assert "3333333" in messages[0].content
    history_messages = [message for message in messages[1:-1] if isinstance(message, HumanMessage)]
    assert len(history_messages) == 2


def test_compress_node_replaces_messages_after_context_overflow() -> None:
    """验证 compress 节点会生成重要事实摘要并替换当前工作消息。"""

    config = AgentConfig.load_config(
        {
            "memory": {
                "summary_trigger_tokens": 5,
                "context_compression_tail_messages": 2,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    fake_summary_service = SimpleNamespace(
        summarize_text=lambda **_kwargs: "当前项目代号为3333333, 旧值1111111和2222222均已失效。",
        build_hash=lambda *parts: "|".join(parts),
    )
    persisted: list[str] = []
    fake_summary_service.persist_summary_memory = lambda **kwargs: persisted.append(kwargs["summary_text"]) or None
    node = CompressNode(config=config, summary_service=fake_summary_service)
    state = {
        "messages": [
            SystemMessage(content="很长的系统提示,需要压缩。"),
            HumanMessage(content="当前项目代号已经从2222222改成3333333。"),
            AIMessage(content="我已记住当前项目代号。"),
            HumanMessage(content="现在请告诉我当前项目代号是什么。"),
        ],
        "user_id": "u1",
        "session_id": "s1",
        "trace": [],
    }

    result = node(state)

    assert isinstance(result["messages"][0], RemoveMessage)
    assert isinstance(result["messages"][1], SystemMessage)
    assert "3333333" in result["messages"][1].content
    assert persisted == ["当前项目代号为3333333, 旧值1111111和2222222均已失效。"]


def test_extract_friendly_error_explains_rate_limit_and_connection_errors() -> None:
    """验证模型错误不会再被展示成裸的 Connection error。"""

    rate_limit_message = _extract_friendly_error('HTTP/1.1 429 Too Many Requests: {"error":"rate_limit"}')
    connection_message = _extract_friendly_error("Connection error.")

    assert "429" in rate_limit_message
    assert "限流" in rate_limit_message
    assert connection_message != "Connection error."
    assert "模型服务连接失败" in connection_message


def test_get_user_llm_overrides_falls_back_small_config_to_primary_config() -> None:
    """验证 state 中 small key 为空时会回退到主模型 key,避免 small-tier 空凭证。"""

    api_key, base_url, small_api_key, small_base_url = get_user_llm_overrides(
        {
            "user_id": "u1",
            "llm_config": {
                "api_key": "primary-key",
                "base_url": "https://primary.example.com/v1",
                "small_api_key": "",
                "small_base_url": "",
            },
        }
    )

    assert api_key == "primary-key"
    assert base_url == "https://primary.example.com/v1"
    assert small_api_key == "primary-key"
    assert small_base_url == "https://primary.example.com/v1"


def test_memory_resolver_prefers_rule_based_known_fact_over_llm_output() -> None:
    """验证已知事实键优先使用规则抽取结果,避免 LLM 旧值覆盖当前值。"""

    config = AgentConfig.load_config(
        {
            "model": {"model_name": "test-model", "api_key": "test-key", "base_url": "https://example.com/v1"},
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    resolver = MemoryResolver(
        config=config,
        memory_service=memory_service,
        embedding_service=EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3)),
    )
    resolver._extract_facts_via_model = lambda summary: [
        MemoryFact(
            namespace="project",
            key="project_code",
            value="1111111",
            category="single_value",
        )
    ]

    facts = resolver.extract_facts("当前项目代号已更新为2222222。")

    assert len(facts) == 1
    assert facts[0].key == "project_code"
    assert facts[0].value == "2222222"


def test_memory_resolver_marks_latest_project_code_as_active_after_multiple_updates() -> None:
    """验证项目代号连续三次更新后,只有最新值保留为 active。"""

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "test-model",
                "api_key": "test-key",
                "base_url": "https://example.com/v1",
                "embedding_model_name": "fake-embedding",
            },
            "memory": {"score_threshold": 0.0},
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    embedding_service = EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3))
    resolver = MemoryResolver(
        config=config,
        memory_service=memory_service,
        embedding_service=embedding_service,
    )
    resolver._extract_facts_via_model = lambda summary: []

    def write_summary(session_id: str, content: str) -> None:
        summary_memory = memory_service.create_memory(
            LongTermMemorySpecCreate(
                user_id="user_1",
                session_id=session_id,
                tag="Memory",
                memory_type="session_summary",
                content=content,
                source_type="session_messages",
                source_id=session_id,
                embedding_model="fake-embedding",
                embedding_vector_json=[1.0, 2.0, 3.0],
            )
        )
        resolver.resolve_summary(
            user_id="user_1",
            session_id=session_id,
            summary_memory=summary_memory,
        )

    write_summary("sess_1", "当前项目代号为1111111。")
    write_summary("sess_2", "当前项目代号已更新为2222222。")
    write_summary("sess_3", "当前项目代号已从2222222更改为3333333。")

    active_facts = memory_service.list_active_fact_memories(
        user_id="user_1",
        namespace="project",
        key="project_code",
    )
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=embedding_service,
        memory_service=memory_service,
    )
    retrieved = retrieval_service.retrieve_long_term_memory(
        query="当前项目代号是什么",
        user_id="user_1",
        session_id="sess_final",
        top_k=3,
    )

    assert len(active_facts) == 1
    assert active_facts[0].content == "当前项目代号为3333333。"
    assert retrieved[0].memory.content == "当前项目代号为3333333。"


def test_builtin_memory_tools_use_runtime_context() -> None:
    """验证 builtin 记忆工具可以通过运行时上下文访问统一检索服务。"""

    config = AgentConfig.load_config(
        {"memory": {"score_threshold": 0.0}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_tool",
            tag="Memory",
            memory_type="session_summary",
            content="用户偏好直接给出结论。",
            source_type="session_messages",
            embedding_model="fake",
            embedding_vector_json=[6.0, 7.0, 8.0],
        )
    )
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="system",
            session_id=None,
            tag="Knowledge",
            memory_type="knowledge_chunk",
            content="珊瑚礁会支持渔业和海岸防护。",
            source_type="knowledge_file",
            source_uri="resources/knowledge/coral.txt",
            embedding_model="fake",
            embedding_vector_json=[6.0, 7.0, 8.0],
        )
    )
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3)),
        memory_service=memory_service,
    )
    set_tool_runtime(
        config=config,
        user_id="user_1",
        session_id="sess_tool",
        retrieval_service=retrieval_service,
    )
    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())

    memory_result = executor.execute("get_long_term_memory", {"query": "用户偏好是什么", "top_k": 1})
    knowledge_result = executor.execute("get_knowledge_context", {"query": "珊瑚礁有什么作用", "top_k": 1})
    citation_map = get_tool_citation_map()
    clear_tool_runtime()

    assert "用户偏好直接给出结论" in memory_result
    assert "[K1]" in knowledge_result
    assert "珊瑚礁会支持渔业和海岸防护" in knowledge_result
    assert citation_map["K1"]["source_uri"] == "resources/knowledge/coral.txt"
    assert "珊瑚礁会支持渔业和海岸防护" in citation_map["K1"]["content"]


def test_agent_core_filters_citations_to_used_anchors() -> None:
    citation_map = {
        "1": {"source_uri": "knowledge/a.md", "content": "A"},
        "2": {"source_uri": "knowledge/b.md", "content": "B"},
        "K1": {"source_uri": "knowledge/tool.md", "content": "K"},
    }

    metadata = AgentCore._build_citation_metadata(
        "最终回答只使用自动来源 [1] 和工具来源 [K1]。",
        citation_map,
    )

    assert metadata["used_citations"] == ["1", "K1"]
    assert set(metadata["citation_map"].keys()) == {"1", "K1"}


def test_agent_core_falls_back_to_adopted_tool_citations_without_anchors() -> None:
    citation_map = {
        "K1": {
            "source_uri": "knowledge/read.md",
            "content": "Read file content",
            "source": "tool",
            "adopted_by_default": True,
        },
        "K2": {
            "source_uri": "knowledge/search.md",
            "content": "Search candidate",
            "source": "tool",
        },
    }

    metadata = AgentCore._build_citation_metadata("最终回答总结了已读取文件，但模型漏写了引用编号。", citation_map)

    assert metadata["used_citations"] == ["K1"]
    assert set(metadata["citation_map"].keys()) == {"K1"}


def test_agent_core_inserts_missing_citation_anchors_inline_for_adopted_sources() -> None:
    content = AgentCore._insert_missing_citation_anchors_inline(
        "Documents:\n- read.md: contains the project summary\n- unrelated.md: search candidate only",
        {
            "K1": {
                "source_uri": "knowledge/read.md",
                "content": "Read file content",
                "adopted_by_default": True,
            },
            "K2": {
                "source_uri": "knowledge/search.md",
                "content": "Search candidate",
            },
        },
    )
    unchanged = AgentCore._insert_missing_citation_anchors_inline(
        "Answer already has citation [K1].",
        {
            "K1": {
                "source_uri": "knowledge/read.md",
                "content": "Read file content",
                "adopted_by_default": True,
            },
        },
    )

    assert "- read.md: contains the project summary [K1]" in content
    assert "[K2]" not in content
    assert "\n\n来源:" not in content
    assert unchanged == "Answer already has citation [K1]."


def test_agent_core_inserts_citations_into_realistic_knowledge_overview_rows() -> None:
    content = (
        "主题 | 文件 | 来源\n"
        "**气候变化证据** | 01_climate_change_nasa.md | NASA\n"
        "**生物多样性** | 01_biodiversity_ipbes.txt | IPBES\n"
        "**太阳能光伏** | special/03_solar_pv_iea.txt | IEA\n"
        "\n"
        "整体来看，这些资料覆盖气候、生态和能源。"
    )
    citation_map = {
        "K1": {
            "source_uri": "1/3/01_climate_change_nasa.md",
            "content": "# 气候变化证据概览\nNASA content",
            "adopted_by_default": True,
        },
        "K2": {
            "source_uri": "1/3/01_biodiversity_ipbes.txt",
            "content": "# 生物多样性\nIPBES content",
            "adopted_by_default": True,
        },
        "K3": {
            "source_uri": "1/3/special/03_solar_pv_iea.txt",
            "content": "# 太阳能光伏\nIEA content",
            "adopted_by_default": True,
        },
    }

    result = AgentCore._insert_missing_citation_anchors_inline(content, citation_map)

    assert "01_climate_change_nasa.md | NASA [K1]" in result
    assert "01_biodiversity_ipbes.txt | IPBES [K2]" in result
    assert "special/03_solar_pv_iea.txt | IEA [K3]" in result
    assert "\n\n来源:" not in result


def test_agent_core_drops_unmapped_citation_anchors() -> None:
    content = AgentCore._drop_unmapped_citation_anchors(
        "使用了有效来源 [1]，但不存在的来源 [K9] 应该被移除。",
        {"1": {"source_uri": "knowledge/a.md", "content": "A"}},
    )
    empty_map_content = AgentCore._drop_unmapped_citation_anchors("没有合法来源时 [1] 也应移除。", {})

    assert "[1]" in content
    assert "[K9]" not in content
    assert "[1]" not in empty_map_content


def test_read_knowledge_file_registers_tool_citation(monkeypatch: Any) -> None:
    class FakeKnowledgeService:
        def read_file(self, *, user_id: str, path: str) -> dict[str, Any]:
            assert user_id == "user_1"
            assert path == "notes/a.md"
            return {
                "path": "notes/a.md",
                "content": "Alpha content from a knowledge file.",
            }

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    monkeypatch.setattr(
        "agent_service.tools.builtin._build_knowledge_service",
        lambda: FakeKnowledgeService(),
    )
    set_tool_runtime(
        config=config,
        user_id="user_1",
        session_id="sess_tool",
        retrieval_service=object(),
        memory_service=object(),
        embedding_service=object(),
    )
    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())

    result = executor.execute("read_knowledge_file", {"path": "notes/a.md"})
    citation_map = get_tool_citation_map()
    clear_tool_runtime()

    assert "Citation ID: [K1]" in result
    assert "Alpha content from a knowledge file." in result
    assert citation_map["K1"]["source_uri"] == "notes/a.md"
    assert citation_map["K1"]["content"] == "Alpha content from a knowledge file."
    assert citation_map["K1"]["adopted_by_default"] is True


def test_web_search_registers_network_citations(monkeypatch: Any) -> None:
    class FakeSettingsService:
        def get_web_search_config(self, *, user_id: str) -> dict[str, Any]:
            assert user_id == "user_1"
            return {"web_search_enabled": True, "proxy_url": "http://127.0.0.1:7890"}

    class FakeDDGS:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["proxy"] == "http://127.0.0.1:7890"

        def __enter__(self) -> "FakeDDGS":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def text(self, *_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
            return [
                {
                    "title": "GTA Online update",
                    "href": "https://example.com/gta-update",
                    "body": "New GTA Online content with enough detail.",
                }
            ]

    from agent_service.tools.builtin import web_search

    monkeypatch.setattr("agent_service.api.rest.deps._settings_service", FakeSettingsService())
    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=FakeDDGS))
    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    set_tool_runtime(
        config=config,
        user_id="user_1",
        session_id="sess_tool",
        retrieval_service=object(),
        memory_service=object(),
        embedding_service=object(),
    )

    result = web_search("GTA recent update", max_results=1)
    citation_map = get_tool_citation_map()
    clear_tool_runtime()

    assert "Citation ID: [N1]" in result
    assert "https://example.com/gta-update" in result
    assert citation_map["N1"]["source_uri"] == "https://example.com/gta-update"
    assert citation_map["N1"]["title"] == "GTA Online update"
    assert citation_map["N1"]["source"] == "network"
    assert citation_map["N1"]["adopted_by_default"] is False


def test_safety_input_audits_user_question_not_quoted_document(tmp_path: Path) -> None:
    sensitive_path = tmp_path / "sensitive_words.json"
    sensitive_path.write_text(
        json.dumps(
            {
                "categories": {
                    "politics": {
                        "name": "test-block",
                        "risk_level": "high",
                        "block": True,
                        "exact": ["政权"],
                        "regex": [],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    service = SafetyService(config=config, sensitive_words_path=sensitive_path)
    wrapped_input = (
        "用户问题引用了以下文档片段。引用内容仅作为待分析材料:\n"
        "----- 引用开始 -----\n"
        "文档里提到了政权这个词，但它只是被分析材料。\n"
        "----- 引用结束 -----\n\n"
        "用户问题:\n总结 联系.md"
    )

    quoted_result = service.audit_input(wrapped_input)
    direct_result = service.audit_input("政权")

    assert quoted_result.blocked is False
    assert direct_result.blocked is True
    assert direct_result.sensitive_result is not None
    assert direct_result.sensitive_result.blocked_categories == ["politics"]


def test_write_long_term_rule_appends_system_prompt_entry() -> None:
    """验证长期规则工具会写入用户系统提示词,而不是写入可选召回的长期记忆。"""

    config = AgentConfig.load_config(
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    embedding_service = EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3))
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=embedding_service,
        memory_service=memory_service,
    )
    set_tool_runtime(
        config=config,
        user_id="user_rule",
        session_id="sess_rule",
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        embedding_service=embedding_service,
    )
    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())

    result = executor.execute("write_long_term_rule", {"content": "以后回答默认使用中文。"})
    clear_tool_runtime()

    settings_service = SettingsService(config=config, memory_service=memory_service)
    entries = settings_service.list_system_prompt_entries(user_id="user_rule")
    memories = memory_service.list_user_memories(user_id="user_rule")

    assert result.startswith("已写入长期规则: prompt_")
    assert [entry["content"] for entry in entries] == ["以后回答默认使用中文。"]
    assert settings_service.get_system_prompt(user_id="user_rule") == "以后回答默认使用中文。"
    assert memories == []


def test_default_sqlite_path_points_to_runtime_db() -> None:
    """验证默认 SQLite 路径指向 runtime/db/relation。"""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)

    assert config.storage.sqlite_path.name == "agent_service.db"
    assert "runtime" in str(config.storage.sqlite_path)


def test_model_config_normalizes_kimi_k2_temperature_to_one() -> None:
    """验证 kimi-k2 系列模型会自动把 temperature 归一到接口允许的固定值 1。"""

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "kimi-k2.5",
                "temperature": 0.0,
                "small_model_name": "kimi-k2.5",
                "small_model_temperature": 0.0,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )

    assert config.model.resolve_primary_temperature() == 0.6
    assert config.model.resolve_primary_temperature(0.3) == 0.6
    assert config.model.resolve_small_temperature() == 0.6


def test_db_init_creates_sqlite_and_chroma_dirs() -> None:
    """验证数据库初始化脚本会创建 SQLite 文件和 ChromaDB 目录。"""

    from agent_service.scripts.db_init import initialize_database

    config = AgentConfig.load_config(load_env=False, ensure_directories=True, ensure_models=False)
    initialize_database(config=config)

    assert config.storage.sqlite_path.exists()
    assert config.storage.chroma_persist_dir.exists()


def test_storage_sqlite_path_can_be_overridden() -> None:
    """验证 SQLite 路径和 ChromaDB 目录可以通过 overrides 自定义。"""

    config = AgentConfig.load_config(
        {"storage": {"sqlite_path": "/tmp/test_agent.db", "chroma_persist_dir": "/tmp/test_chroma"}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )

    assert config.storage.sqlite_path.name == "test_agent.db"
    assert config.storage.chroma_persist_dir.name == "test_chroma"


def test_download_model_resolves_safe_target_dir_and_checks_completeness() -> None:
    """验证下载脚本会使用模型名子目录,并要求模型文件完整。"""

    target_dir = model_target_dir("BAAI/bge-small-zh-v1.5", TEST_TEMP_DIR / "models" / "embedding")
    import shutil
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    assert target_dir.name == "BAAI__bge-small-zh-v1.5"
    assert not is_model_available(target_dir)

    (target_dir / MODEL_MARKER_FILE).write_text("BAAI/bge-small-zh-v1.5", encoding="utf-8")
    (target_dir / "config.json").write_text("{}", encoding="utf-8")
    (target_dir / "model.safetensors").write_text("", encoding="utf-8")
    (target_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

    assert is_model_available(target_dir)


def test_paddleocr_model_prepare_initializes_pipeline(tmp_path: Path, monkeypatch: Any) -> None:
    """验证 PaddleOCR 模型预热会初始化 pipeline 并写入完成标记。"""

    calls: list[dict[str, Any]] = []

    class FakePaddleOCR:
        def __init__(self, **kwargs: Any) -> None:
            """记录 PaddleOCR 初始化参数。"""

            calls.append(kwargs)

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))
    target_dir = tmp_path / "models" / "paddleocr"

    ensure_paddleocr_models(
        paddleocr_model_dir=target_dir,
        language="ch",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        device="cpu",
    )

    assert calls[0]["lang"] == "ch"
    assert calls[0]["text_detection_model_name"] == "PP-OCRv5_mobile_det"
    assert calls[0]["text_recognition_model_name"] == "PP-OCRv5_mobile_rec"
    assert (target_dir / PADDLEOCR_MARKER_FILE).exists()


def test_ocr_paddle_env_overrides_are_loaded(monkeypatch: Any) -> None:
    """验证 PaddleOCR 配置集中通过 AgentConfig 环境变量读取。"""

    monkeypatch.setenv("AGENT_PADDLEOCR_MODEL_DIR", "runtime/custom-paddleocr")
    monkeypatch.setenv("AGENT_OCR_LANGUAGE", "ch")
    monkeypatch.setenv("AGENT_PADDLEOCR_DET_MODEL_NAME", "PP-OCRv5_server_det")
    monkeypatch.setenv("AGENT_PADDLEOCR_REC_MODEL_NAME", "PP-OCRv5_server_rec")
    monkeypatch.setenv("AGENT_PADDLEOCR_DEVICE", "cpu")

    config = AgentConfig.load_config(load_env=True, ensure_directories=False, ensure_models=False)

    assert config.storage.paddleocr_model_dir.name == "custom-paddleocr"
    assert config.ocr.language == "ch"
    assert config.ocr.text_detection_model_name == "PP-OCRv5_server_det"
    assert config.ocr.text_recognition_model_name == "PP-OCRv5_server_rec"
    assert config.ocr.device == "cpu"


def test_agent_core_init_checks_local_models(monkeypatch: Any) -> None:
    """验证 AgentCore 初始化时会强制触发本地模型检查。"""

    config = make_test_config()
    calls: list[AgentConfig] = []

    def fake_ensure_local_models(self: AgentConfig) -> None:
        """记录 AgentCore 是否调用了模型检查入口。"""

        calls.append(self)

    monkeypatch.setattr(AgentConfig, "ensure_local_models", fake_ensure_local_models)

    AgentCore(config=config, graph=FakeCompiledGraph())

    assert calls == [config]


def test_tool_registry_exports_builtin_langchain_tools() -> None:
    """验证工具注册表会把内置工具转换为 LLM 可绑定的 LangChain 工具。"""

    registry = ToolRegistry.with_builtin_tools()
    tools = registry.to_langchain_tools()

    tool_names = {tool.name for tool in tools}
    assert registry.get("get_current_time") is not None
    assert tool_names >= {
        "get_knowledge_context",
        "get_long_term_memory",
        "write_long_term_rule",
        "get_current_time",
        "search_knowledge",
        "list_knowledge_files",
    }
    assert tool_names.isdisjoint({
        "calculate",
        "echo_text",
        "generate_uuid",
        "get_current_utc_time",
        "json_parse",
        "json_pick",
        "list_builtin_tools",
        "text_stats",
        "update_exploration_state",
    })


def test_tool_executor_runs_builtin_tool() -> None:
    """验证工具执行器可以根据工具名称和参数执行内置工具。"""

    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())

    result = executor.execute("get_current_time", {"timezone_name": "UTC"})

    assert "T" in result


def test_tool_call_node_uses_project_executor() -> None:
    """验证 action 节点会通过项目工具执行器执行模型返回的 tool_calls。"""

    config = make_test_config()
    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())
    node = ToolCallNode(config=config, tool_executor=executor)
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_time", "name": "get_current_time", "args": {"timezone_name": "UTC"}}],
            )
        ],
        "user_id": "u1",
        "session_id": "s1",
        "trace": [],
    }

    result = node(state)

    assert "T" in result["messages"][0].content
    assert result["trace"][0]["event"] == "tool_call_start"
    assert result["trace"][0]["tool_name"] == "get_current_time"


def test_tool_call_node_counts_knowledge_search_results() -> None:
    """知识库搜索输出不是纯编号列表时,也应能统计召回条目数。"""

    content = "=== 内容匹配 ===\n  [K1] 崩铁.md\n  [K2] docs/区别.md\n\n=== 语义匹配 ===\n  docs/联系.md"

    assert ToolCallNode._count_results(content) == 2

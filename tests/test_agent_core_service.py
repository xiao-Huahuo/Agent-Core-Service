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
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlmodel import SQLModel, create_engine

from agent_service.agent_core import AgentCore
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
from agent_service.scripts.db_init import build_admin_dsn
from agent_service.scripts.download_model import MODEL_MARKER_FILE
from agent_service.scripts.draw_agent_graph import build_mermaid
from agent_service.scripts.download_model import is_model_available
from agent_service.scripts.download_model import model_target_dir
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService
from agent_service.services.message_service import MessageService
from agent_service.services.session_service import SessionService
from agent_service.tools import ToolExecutor, ToolRegistry, clear_tool_runtime, set_tool_runtime


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
            "storage": {"project_root": str(TEST_TEMP_DIR), "base_data_dir": str(TEST_TEMP_DIR / "runtime")},
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

    assert chunks[0].startswith("data: ")
    assert "测试回复" in chunks[0]
    assert chunks[-1] == "data: [DONE]\n\n"


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
    assert result["chunks"][-1] == "data: [DONE]\n\n"


def test_agent_core_run_session_prompt_uses_context_and_persists_messages() -> None:
    """验证 session 正式入口会加载历史上下文并保存本轮新增消息。"""

    config = AgentConfig.load_config(
        {"memory": {"max_context_messages": 2}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    message_service = MessageService(config=config, engine=engine, create_tables=False)
    context_builder = ContextBuilder(config=config, message_service=message_service)
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

    result = agent.run_session_prompt(prompt="关键词是什么?", user_id="user_1", session_id="sess_formal")
    saved_messages = message_service.list_recent_messages(user_id="user_1", session_id="sess_formal", limit=10)

    assert result["final_output"] == "blue-river"
    assert fake_graph.stream_inputs[0]["messages"][0].content == "上一轮关键词是 blue-river"
    assert fake_graph.stream_inputs[0]["messages"][-1].content == "关键词是什么?"
    assert [message.role for message in saved_messages] == ["user", "user", "assistant"]
    assert saved_messages[-1].content == "blue-river"


def test_agent_core_build_human_readable_process() -> None:
    """验证 AgentCore 可以把结构化事件转换为给人阅读的执行过程。"""

    events = [
        {"node": "agent", "content": "", "tool_calls": [{"name": "echo_text"}], "trace": []},
        {"node": "action", "content": "hello", "tool_calls": [], "trace": []},
        {"node": "agent", "content": "最终回复", "tool_calls": [], "trace": []},
    ]

    process = AgentCore.build_human_readable_process(events)

    assert process[0] == "1. 模型决定调用工具: echo_text"
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

    knowledge_dir = TEST_TEMP_DIR / "knowledge_ingestion"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "demo.txt").write_text("第一段知识。" * 80, encoding="utf-8")
    config = AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(TEST_TEMP_DIR),
                "base_data_dir": str(TEST_TEMP_DIR / "runtime"),
                "knowledge_dir": str(knowledge_dir),
            },
            "memory": {"chunk_size": 120, "chunk_overlap": 20},
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

    result = ingestion_service.ingest_knowledge_dir()

    assert result.files_seen == 1
    assert result.files_ingested == 1
    assert result.chunks_created > 1
    assert memory_service.has_source_hash(
        source_hash=KnowledgeIngestionService._hash_file(knowledge_dir / "demo.txt"),
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

    assert [message.content for message in messages] == ["a-1", "a-2"]


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
    builder = ContextBuilder(config=config, message_service=service)
    service.create_message(MessageCreate(session_id="sess_ctx", user_id="user_1", role="system", content="系统提示"))
    service.create_message(MessageCreate(session_id="sess_ctx", user_id="user_1", role="user", content="你好"))
    service.create_message(
        MessageCreate(
            session_id="sess_ctx",
            user_id="user_1",
            role="assistant",
            content="",
            tool_calls_json=[{"id": "call_1", "name": "echo_text", "args": {"text": "hello"}}],
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
    assert isinstance(messages[1], HumanMessage)
    assert isinstance(messages[2], AIMessage)
    assert isinstance(messages[3], ToolMessage)
    assert isinstance(messages[-1], HumanMessage)
    assert messages[-1].content == "继续"


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
    assert "长期记忆召回" in messages[0].content
    assert "stone-cat" in messages[0].content


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
    clear_tool_runtime()

    assert "用户偏好直接给出结论" in memory_result
    assert "珊瑚礁会支持渔业和海岸防护" in knowledge_result


def test_default_relational_dsn_uses_psycopg_driver() -> None:
    """验证默认 PostgreSQL DSN 与 psycopg3 依赖保持一致。"""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)

    assert config.storage.relational_dsn.startswith("postgresql+psycopg://")


def test_db_init_builds_admin_dsn_from_target_dsn() -> None:
    """验证数据库初始化脚本可以从业务库 DSN 派生管理库 DSN。"""

    admin_dsn = build_admin_dsn(
        target_dsn="postgresql+psycopg://postgres:1111@localhost:5432/agent_service"
    )

    assert admin_dsn == "postgresql+psycopg://postgres:1111@localhost:5432/postgres"


def test_storage_dsn_can_be_built_from_password_field() -> None:
    """验证默认 DSN 可以从独立数据库密码字段组装。"""

    config = AgentConfig.load_config(
        {"storage": {"relational_db_password": "1111", "vector_db_password": "2222"}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )

    assert config.storage.relational_dsn == "postgresql+psycopg://postgres:1111@localhost:5432/agent_service"
    assert config.storage.vector_dsn == "postgresql+psycopg://postgres:2222@localhost:5432/agent_service"


def test_download_model_resolves_safe_target_dir_and_checks_completeness() -> None:
    """验证下载脚本会使用模型名子目录,并要求模型文件完整。"""

    target_dir = model_target_dir("BAAI/bge-small-zh-v1.5", TEST_TEMP_DIR / "models" / "embedding")
    target_dir.mkdir(parents=True, exist_ok=True)

    assert target_dir.name == "BAAI__bge-small-zh-v1.5"
    assert not is_model_available(target_dir)

    (target_dir / MODEL_MARKER_FILE).write_text("BAAI/bge-small-zh-v1.5", encoding="utf-8")
    (target_dir / "config.json").write_text("{}", encoding="utf-8")
    (target_dir / "model.safetensors").write_text("", encoding="utf-8")
    (target_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

    assert is_model_available(target_dir)


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

    assert registry.get("echo_text") is not None
    assert {tool.name for tool in tools} >= {
        "calculate",
        "echo_text",
        "generate_uuid",
        "get_knowledge_context",
        "get_long_term_memory",
        "get_current_time",
        "get_current_utc_time",
        "json_parse",
        "json_pick",
        "list_builtin_tools",
        "text_stats",
    }


def test_tool_executor_runs_builtin_tool() -> None:
    """验证工具执行器可以根据工具名称和参数执行内置工具。"""

    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())

    result = executor.execute("echo_text", {"text": "hello"})

    assert result == "hello"


def test_tool_executor_runs_general_builtin_tools() -> None:
    """验证常用内置工具可以通过统一执行器执行。"""

    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())

    uuid_value = executor.execute("generate_uuid")
    calculate_value = executor.execute("calculate", {"expression": "(1 + 2) * 3"})
    json_value = executor.execute("json_pick", {"json_text": '{"user": {"name": "Ada"}}', "path": "user.name"})
    text_stats_value = json.loads(executor.execute("text_stats", {"text": "hello\nworld"}))

    assert str(UUID(uuid_value)) == uuid_value
    assert calculate_value == "9"
    assert json_value == '"Ada"'
    assert text_stats_value["lines"] == 2


def test_calculate_rejects_unsafe_expression() -> None:
    """验证计算工具不会执行函数调用等非白名单表达式。"""

    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())

    result = executor.execute("calculate", {"expression": "__import__('os').system('echo bad')"})

    assert result.startswith("计算失败:")


def test_tool_call_node_uses_project_executor() -> None:
    """验证 action 节点会通过项目工具执行器执行模型返回的 tool_calls。"""

    config = make_test_config()
    executor = ToolExecutor(registry=ToolRegistry.with_builtin_tools())
    node = ToolCallNode(config=config, tool_executor=executor)
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_echo", "name": "echo_text", "args": {"text": "node-ok"}}],
            )
        ],
        "user_id": "u1",
        "session_id": "s1",
        "trace": [],
    }

    result = node(state)

    assert result["messages"][0].content == "node-ok"
    assert result["trace"][0]["executor"] == "project_tool_executor"

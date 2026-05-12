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

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage

from agent_service.agent_core import AgentCore
from agent_service.agent_core.nodes.tool_call import ToolCallNode
from agent_service.core.agent_config import AgentConfig
from agent_service.models.session import SessionRecord
from agent_service.schemas.session import SessionOut
from agent_service.scripts.draw_agent_graph import build_mermaid
from agent_service.services.session_service import SessionService
from agent_service.tools import ToolExecutor, ToolRegistry


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

    def stream(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        """返回预设的 LangGraph 节点更新列表。"""

        return self.updates

    def get_graph(self) -> Any:
        """返回预设图结构,供 Mermaid 绘图脚本读取。"""

        return self.graph_data


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


def test_session_service_generates_session_id() -> None:
    """验证 SessionService 生成的会话 ID 使用统一前缀。"""

    session_id = SessionService.generate_session_id()

    assert session_id.startswith("sess_")
    assert len(session_id) == 37


def test_default_relational_dsn_uses_psycopg_driver() -> None:
    """验证默认 PostgreSQL DSN 与 psycopg3 依赖保持一致。"""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)

    assert config.storage.relational_dsn.startswith("postgresql+psycopg://")


def test_tool_registry_exports_builtin_langchain_tools() -> None:
    """验证工具注册表会把内置工具转换为 LLM 可绑定的 LangChain 工具。"""

    registry = ToolRegistry.with_builtin_tools()
    tools = registry.to_langchain_tools()

    assert registry.get("echo_text") is not None
    assert {tool.name for tool in tools} >= {
        "calculate",
        "echo_text",
        "generate_uuid",
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

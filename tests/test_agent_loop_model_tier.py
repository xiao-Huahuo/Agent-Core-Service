from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent_service.agent_core.agent_core import AgentCore
from agent_service.agent_core.graph import AgentGraphBuilder
from agent_service.agent_core.nodes.model_decision import ModelDecisionNode
from agent_service.agent_core.nodes.observation import ObservationNode
from agent_service.agent_core.nodes.planner import PlannerNode
from agent_service.agent_core.nodes.tool_call import ToolCallNode
from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import SMALL_MODEL_TIER
from agent_service.tools.builtin import list_available_tools
from agent_service.tools.runtime_context import clear_tool_runtime, set_tool_runtime


class _FakeScheduler:
    def __init__(self, response_content: str) -> None:
        self.response_content = response_content
        self.calls: list[dict] = []

    def invoke_chat(self, **kwargs):
        self.calls.append(kwargs)
        return AIMessage(content=self.response_content)


class _FakeRegistry:
    def get(self, _name: str):
        return None


class _FakeToolExecutor:
    def __init__(self) -> None:
        self.registry = _FakeRegistry()
        self.calls: list[tuple[str, dict]] = []

    def execute(self, name: str, arguments: dict) -> str:
        self.calls.append((name, arguments))
        return f"executed {name}"


def test_planner_uses_small_model_tier() -> None:
    scheduler = _FakeScheduler(
        '{"covered": [], "suggested": ["检查知识库"], "sufficient": false, "hint": "先检索相关资料"}'
    )
    node = PlannerNode(config=AgentConfig(), task_scheduler=scheduler)

    result = node(
        {
            "messages": [HumanMessage(content="帮我分析这个项目")],
            "user_id": "u1",
            "session_id": "s1",
            "trace": [],
            "plan": None,
            "observation_decision": "",
            "llm_config": {},
        }
    )

    assert result["plan"]["hint"] == "先检索相关资料"
    assert scheduler.calls[0]["model_tier"] == SMALL_MODEL_TIER


def test_observation_uses_small_model_tier() -> None:
    scheduler = _FakeScheduler("信息充足，可以回答。[answer]")
    node = ObservationNode(config=AgentConfig(), task_scheduler=scheduler)

    result = node(
        {
            "messages": [
                HumanMessage(content="查一下知识库"),
                AIMessage(content="", tool_calls=[{"id": "call_1", "name": "search_knowledge", "args": {}}]),
                ToolMessage(content="找到 2 条结果", tool_call_id="call_1"),
            ],
            "user_id": "u1",
            "session_id": "s1",
            "trace": [],
            "plan": None,
            "observation_decision": "",
            "llm_config": {},
        }
    )

    assert result["observation_decision"] == "answer"
    assert result["messages"] == []
    assert scheduler.calls[0]["model_tier"] == SMALL_MODEL_TIER


def test_model_boundary_drops_orphaned_tool_messages_before_request() -> None:
    """每次调用模型前都必须移除没有紧邻 tool_calls 的孤立工具结果。"""

    system_message = SystemMessage(content="system")
    orphan = ToolMessage(content="[FILE] leaked.md", tool_call_id="missing_call")

    prepared = ModelDecisionNode._prepare_messages_for_llm(
        system_message,
        [HumanMessage(content="列出文件"), orphan],
    )

    assert orphan not in prepared


def test_model_boundary_keeps_complete_tool_call_pair() -> None:
    """统一边界过滤不得破坏完整的 assistant tool_calls 与 ToolMessage 对。"""

    system_message = SystemMessage(content="system")
    assistant = AIMessage(content="", tool_calls=[{"id": "call_1", "name": "list_knowledge_files", "args": {}}])
    result = ToolMessage(content="[FILE] a.md", tool_call_id="call_1")

    prepared = ModelDecisionNode._prepare_messages_for_llm(
        system_message,
        [HumanMessage(content="列出文件"), assistant, result],
    )

    assert prepared[-2:] == [assistant, result]


def test_observation_respects_continue_after_long_exploration() -> None:
    """观察节点不得因固定观察次数或工具结果数量强制结束探索。"""

    scheduler = _FakeScheduler(
        '{"decision":"continue","reason":"need more","next_action":"continue reading","confidence":0.4}'
    )
    node = ObservationNode(config=AgentConfig(), task_scheduler=scheduler)
    traces = [
        {"node": "observation", "event": "observation_complete", "decision": "continue"}
        for _ in range(5)
    ]
    traces.extend(
        {"node": "action", "event": "tool_call_end"}
        for _ in range(18)
    )

    result = node(
        {
            "messages": [
                HumanMessage(content="完成复杂分析"),
                AIMessage(content="", tool_calls=[{"id": "call_1", "name": "search_knowledge", "args": {}}]),
                ToolMessage(content="找到 2 条结果", tool_call_id="call_1"),
            ],
            "user_id": "u1",
            "session_id": "s1",
            "trace": traces,
            "plan": None,
            "observation_decision": "",
            "llm_config": {},
        }
    )

    assert result["observation_decision"] == "continue"
    assert result["messages"] == []


def test_simple_answer_mode_only_matches_short_non_tool_prompt() -> None:
    assert AgentCore._should_use_simple_answer_mode(prompt="你好")
    assert AgentCore._should_use_simple_answer_mode(prompt="你是谁?")
    assert not AgentCore._should_use_simple_answer_mode(prompt="搜索知识库里的文件")
    assert not AgentCore._should_use_simple_answer_mode(prompt="你好", reference="引用内容")
    assert AgentCore._resolve_agent_loop_mode_fallback(agent_mode="deep", prompt="复杂问题") == "plan"
    assert AgentCore._resolve_agent_loop_mode_fallback(agent_mode="auto", prompt="你有哪些工具") == "react"
    assert AgentCore._resolve_agent_loop_mode_fallback(agent_mode="auto", prompt="读取一下当前文档") == "react"
    assert AgentCore._resolve_agent_loop_mode_fallback(agent_mode="auto", prompt="帮我设计一个多步骤的实现方案") == "plan"
    assert AgentCore._resolve_agent_loop_mode_fallback(agent_mode="auto", prompt="分析这个项目的架构并给出优化计划") == "plan"


def test_auto_agent_loop_mode_uses_small_model_router() -> None:
    scheduler = _FakeScheduler('{"mode":"react","reason":"需要最新信息"}')
    agent = AgentCore(config=AgentConfig(), tools=[], task_scheduler=scheduler)

    mode = agent._resolve_agent_loop_mode(
        agent_mode="auto",
        prompt="GTA最近出了什么新内容吗?",
        user_id="u1",
    )

    assert mode == "react"
    assert scheduler.calls[0]["model_tier"] == SMALL_MODEL_TIER
    assert scheduler.calls[0]["tool_names"] == []
    router_prompt = scheduler.calls[0]["messages"][0].content
    assert "你自己能力足够" in router_prompt
    assert "不要选择 simple,至少选择 react" in router_prompt


def test_auto_agent_loop_mode_falls_back_when_router_output_is_invalid() -> None:
    scheduler = _FakeScheduler("not json")
    agent = AgentCore(config=AgentConfig(), tools=[], task_scheduler=scheduler)

    mode = agent._resolve_agent_loop_mode(
        agent_mode="auto",
        prompt="你好",
        user_id="u1",
    )

    assert mode == "simple"


def test_react_graph_skips_planner_and_observation_nodes() -> None:
    builder = AgentGraphBuilder(config=AgentConfig(), tools=[], safety_service=None)

    react_graph = builder.build(mode="react")
    node_names = set(react_graph.get_graph().nodes)

    assert "agent" in node_names
    assert "action" in node_names
    assert "planner" not in node_names
    assert "observation" not in node_names


def test_plan_graph_keeps_planner_and_observation_nodes() -> None:
    builder = AgentGraphBuilder(config=AgentConfig(), tools=[], safety_service=None)

    plan_graph = builder.build(mode="plan")
    node_names = set(plan_graph.get_graph().nodes)

    assert "agent" in node_names
    assert "action" in node_names
    assert "planner" in node_names
    assert "observation" in node_names


def test_observation_parses_structured_decisions() -> None:
    parsed = ObservationNode._parse_decision(
        '{"decision":"retry","reason":"empty result","next_action":"retry with a broader query","confidence":0.8}'
    )

    assert parsed["decision"] == "retry"
    assert parsed["reason"] == "empty result"
    assert parsed["next_action"] == "retry with a broader query"
    assert parsed["confidence"] == 0.8


def test_plan_graph_routes_after_observation_decision() -> None:
    builder = AgentGraphBuilder(config=AgentConfig(), tools=[], safety_service=None)

    assert builder._route_after_observation({"observation_decision": "continue"}) == "planner"
    assert builder._route_after_observation({"observation_decision": "compress"}) == "compress"
    assert builder._route_after_observation({"observation_decision": "answer"}) == "agent"
    assert builder._route_after_observation({"observation_decision": "retry"}) == "agent"
    assert builder._route_after_observation({"observation_decision": "abandon"}) == "agent"


def test_planner_parses_sub_question_state() -> None:
    parsed = PlannerNode._parse_plan(
        '{"covered":["a"],"suggested":["b"],"sub_questions":["q1","q2"],'
        '"current_index":9,"status":"running","sufficient":false,"hint":"handle q2"}'
    )

    assert parsed is not None
    assert parsed["sub_questions"] == ["q1", "q2"]
    assert parsed["current_index"] == 1
    assert parsed["status"] == "running"
    assert parsed["sufficient"] is False


def test_internal_planner_and_observation_content_is_not_streamed_to_chat() -> None:
    planner_payload = AgentCore._build_stream_payload(
        node_name="planner",
        state_update={"messages": [AIMessage(content='{"hint":"internal plan"}')], "trace": []},
    )
    observation_payload = AgentCore._build_stream_payload(
        node_name="observation",
        state_update={"messages": [AIMessage(content="Observation decision=continue.")], "trace": []},
    )
    action_payload = AgentCore._build_stream_payload(
        node_name="action",
        state_update={"messages": [ToolMessage(content="large file content", tool_call_id="call_1")], "trace": []},
    )

    assert planner_payload["content"] == ""
    assert observation_payload["content"] == ""
    assert action_payload["content"] == ""


def test_tool_call_node_defers_excessive_parallel_tool_calls() -> None:
    executor = _FakeToolExecutor()
    node = ToolCallNode(config=AgentConfig(), tool_executor=executor)
    tool_calls = [
        {"id": f"call_{index}", "name": "read_knowledge_file", "args": {"path": f"file_{index}.md"}}
        for index in range(6)
    ]

    result = node(
        {
            "messages": [AIMessage(content="", tool_calls=tool_calls)],
            "user_id": "u1",
            "session_id": "s1",
            "trace": [],
            "plan": None,
            "observation_decision": "",
            "llm_config": {},
        }
    )

    assert len(executor.calls) == 4
    assert len(result["messages"]) == 6
    assert result["trace"][-1]["event"] == "tool_call_deferred"


def test_model_decision_compacts_tool_messages_before_llm_call() -> None:
    system = SystemMessage(content="system")
    messages = [
        HumanMessage(content="read file"),
        AIMessage(content="", tool_calls=[{"id": "call_1", "name": "read_knowledge_file", "args": {}}]),
        ToolMessage(content="x" * 2000, tool_call_id="call_1"),
    ]

    prepared = ModelDecisionNode._prepare_messages_for_llm(system, messages)

    assert prepared[0] is system
    assert isinstance(prepared[-1], ToolMessage)
    assert prepared[-1].tool_call_id == "call_1"
    assert len(str(prepared[-1].content)) < 1200
    assert "工具返回内容已压缩" in str(prepared[-1].content)


def test_model_decision_keeps_recent_terminal_results_large_enough_for_directory_analysis() -> None:
    system = SystemMessage(content="system")
    messages = [
        HumanMessage(content="调查知识库"),
        AIMessage(content="", tool_calls=[{"id": "call_1", "name": "run_terminal_command", "args": {}}]),
        ToolMessage(content="x" * 7000, tool_call_id="call_1", name="run_terminal_command"),
    ]

    prepared = ModelDecisionNode._prepare_messages_for_llm(system, messages)

    assert isinstance(prepared[-1], ToolMessage)
    assert len(str(prepared[-1].content)) > 6000
    assert "6000" in str(prepared[-1].content)


def test_list_available_tools_returns_full_tool_catalog() -> None:
    set_tool_runtime(config=AgentConfig(), user_id="u1", session_id="s1")
    try:
        result = list_available_tools()
    finally:
        clear_tool_runtime()

    assert "list_available_tools" in result
    assert "web_search" in result
    assert "show_markdown_html" in result
    assert "download_file" in result
    assert "create_task_list" in result


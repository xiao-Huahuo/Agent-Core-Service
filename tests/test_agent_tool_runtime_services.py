"""Agent 工具业务服务注入回归测试。

功能说明：
验证 SSE 工作线程中的工具从 ToolRuntimeState 获取应用服务，不再依赖无法跨线程传播的
REST 请求 ContextVar。
"""

import json
from pathlib import Path
from types import SimpleNamespace

from agent_service.core.agent_config import AgentConfig
from agent_service.tools import ToolRegistry
from agent_service.tools.builtin import business_ops, git, knowledge_ops, library, smart_forms
from agent_service.tools.runtime_context import clear_tool_runtime, set_tool_runtime


def test_tool_service_factories_use_thread_local_runtime_services() -> None:
    """所有曾经读取 REST dependencies 的工具域都应解析到显式注入实例。"""

    services = {
        "git": object(),
        "library": object(),
        "skill": object(),
        "knowledge_library": object(),
        "knowledge_graph": object(),
        "smart_form": object(),
        "structured_generation": object(),
    }
    set_tool_runtime(
        config=AgentConfig(),
        user_id="u1",
        session_id="s1",
        retrieval_service=SimpleNamespace(),
        memory_service=SimpleNamespace(engine=None),
        embedding_service=SimpleNamespace(),
        tool_services=services,
    )
    try:
        assert git._get_git_service() is services["git"]
        assert library._get_library_service() is services["library"]
        assert business_ops._service("skill") is services["skill"]
        assert knowledge_ops._knowledge_service() is services["knowledge_library"]
        assert knowledge_ops._graph_service() is services["knowledge_graph"]
        assert smart_forms._smart_form_service() is services["smart_form"]
        assert smart_forms._generation_service() is services["structured_generation"]
    finally:
        clear_tool_runtime()


def test_live_api_case_catalog_covers_every_registered_tool_once() -> None:
    """真实 API case 清单必须与正式原生注册表一一对应。"""

    cases = json.loads(
        (Path(__file__).with_name("live_agent_api_tool_cases.json")).read_text(encoding="utf-8")
    )
    names = [str(case["tool"]) for case in cases]

    assert len(names) == len(set(names))
    assert set(names) == set(ToolRegistry.with_builtin_tools().definitions)

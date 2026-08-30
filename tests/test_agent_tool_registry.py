"""
Agent 工具注册表观测测试。

功能说明:
验证 AgentCore 暴露给 REST/gRPC/前端观测页的工具列表来自最终工具注册表。
"""

from agent_service.agent_core import AgentCore
from agent_service.core.agent_config import AgentConfig
from agent_service.tools import ToolExecutor, ToolRegistry
from agent_service.tools.runtime_context import clear_tool_runtime, get_tool_citation_map, set_tool_runtime


class _UnifiedSearchStub:
    """记录 Agent 工具参数并返回四个正式来源各一条结果。"""

    def __init__(self) -> None:
        """初始化最近一次四库检索调用。"""

        self.call: dict[str, object] = {}

    def search(self, **kwargs: object) -> dict[str, object]:
        """返回与 UnifiedSearchService 相同的最小结果契约。"""

        self.call = kwargs
        results = [
            {
                "id": f"{source}-1",
                "source": source,
                "title": title,
                "snippet": f"{title} 的命中片段",
                "locator": locator,
                "matched_modes": ["fulltext"],
                "score": 0.8,
                "item": {},
            }
            for source, title, locator in (
                ("files", "文件结果", "docs/result.md"),
                ("library", "图书结果", "图书馆"),
                ("components", "组件结果", "cards/ResultCard.vue"),
                ("literature", "文献结果", "paper.pdf"),
            )
        ]
        return {"results": results, "total": len(results)}


def test_agent_core_lists_registered_tools_from_final_registry() -> None:
    """工具观测快照应包含最终注册表中的工具基础信息。"""

    agent = AgentCore.__new__(AgentCore)
    agent.tool_registry = ToolRegistry.with_builtin_tools()
    agent.tools = []

    payload = agent.list_registered_tools()
    search_tool = next(tool for tool in payload["tools"] if tool["name"] == "search_knowledge")

    assert payload["tool_count"] == len(agent.tool_registry.definitions)
    assert search_tool["display_name"] == "四库联合搜索"
    assert search_tool["argument_count"] >= 1
    assert "properties" in search_tool["args_schema"]


def test_search_knowledge_tool_reuses_four_library_service() -> None:
    """Agent 搜索必须调用页面同源的四库服务并返回四类结果。"""

    service = _UnifiedSearchStub()
    set_tool_runtime(
        config=AgentConfig(),
        user_id="u1",
        session_id="s1",
        retrieval_service=object(),
        memory_service=object(),
        embedding_service=object(),
        unified_search_service=service,
    )
    try:
        result = ToolExecutor(registry=ToolRegistry.with_builtin_tools()).execute(
            "search_knowledge",
            {
                "query": "检索词",
                "sources": ["files", "library", "components", "literature"],
                "fulltext": True,
                "semantic": True,
            },
        )
        citation_map = get_tool_citation_map()
    finally:
        clear_tool_runtime()

    assert service.call == {
        "user_id": "u1",
        "query": "检索词",
        "sources": {"files", "library", "components", "literature"},
        "fulltext": True,
        "semantic": True,
    }
    assert "四库联合搜索共 4 条结果" in result
    assert "引用需要挂载的结果编号" in result
    assert all(label in result for label in ("文件库", "图书馆", "组件库", "文献库"))
    assert citation_map["K1"]["search_result"]["source"] == "files"
    assert citation_map["K4"]["search_result"]["source"] == "literature"


def test_current_time_tool_is_not_registered() -> None:
    """用户提问自带时间后，Agent 不应再暴露重复的当前时间工具。"""

    registry = ToolRegistry.with_builtin_tools()

    assert registry.get("get_current_time") is None

"""
MCP 工具注册集成测试。
功能说明:
本文文件验证 MCP 工具能通过 `ToolRegistry.with_builtin_tools(config=...)` 与原生工具共同注册,
并且能够经由现有 `ToolExecutor` 同步执行。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from agent_service.core.agent_config import AgentConfig
from agent_service.tools import ToolExecutor, ToolRegistry
from agent_service.tools.mcp.registry import MCPToolRegistryAdapter


def build_test_config() -> AgentConfig:
    """构建一份最小测试配置,避免触发真实模型下载和目录初始化副作用。"""

    return AgentConfig.load_config(
        {
            "mcp": {
                "enabled": True,
                "tool_name_prefix": "mcp",
                "servers": [
                    {
                        "server_id": "demo-server",
                        "command": "python",
                        "args": ["-m", "demo_server"],
                    }
                ],
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )


def test_tool_registry_registers_builtin_and_mcp_tools(monkeypatch: Any) -> None:
    """验证 MCP 工具会与原生工具一起注册到统一 ToolRegistry。"""

    async def fake_discover_server_tools(
        self: MCPToolRegistryAdapter,
        _server_config: Any,
    ) -> list[Any]:
        return [
            SimpleNamespace(
                name="echo_remote",
                description="远程回显",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "回显文本"}},
                    "required": ["text"],
                },
            )
        ]

    monkeypatch.setattr(
        MCPToolRegistryAdapter,
        "_discover_server_tools",
        fake_discover_server_tools,
    )
    config = build_test_config()

    registry = ToolRegistry.with_builtin_tools(config=config)

    assert registry.get("echo_text") is not None
    registered_tool = registry.get("mcp__demo_server__echo_remote")
    assert registered_tool is not None
    assert "demo_server" in registered_tool.description


def test_tool_executor_executes_registered_mcp_tool(monkeypatch: Any) -> None:
    """验证注册后的 MCP 工具能通过现有同步 ToolExecutor 执行。"""

    async def fake_discover_server_tools(
        self: MCPToolRegistryAdapter,
        _server_config: Any,
    ) -> list[Any]:
        return [
            SimpleNamespace(
                name="echo_remote",
                description="远程回显",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        ]

    async def fake_call_tool_async(
        self: MCPToolRegistryAdapter,
        *,
        server_config: Any,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        return SimpleNamespace(
            text=f"{server_config.server_id}:{tool_name}:{arguments['text']}",
            content=[],
            structured_content={"ok": True},
            is_error=False,
        )

    monkeypatch.setattr(
        MCPToolRegistryAdapter,
        "_discover_server_tools",
        fake_discover_server_tools,
    )
    monkeypatch.setattr(
        MCPToolRegistryAdapter,
        "_call_tool_async",
        fake_call_tool_async,
    )
    config = build_test_config()
    registry = ToolRegistry.with_builtin_tools(config=config)
    executor = ToolExecutor(registry=registry)

    result = executor.execute("mcp__demo_server__echo_remote", {"text": "hello"})

    assert result == "demo_server:echo_remote:hello"

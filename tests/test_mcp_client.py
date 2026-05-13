"""
MCP 客户端测试脚本。

功能说明:
本文件用于验证 `agent_service.mcp.client` 第一版最小异步客户端的核心行为:

1. 能在假 SDK 环境下建立连接并完成初始化
2. 能读取工具列表
3. 能调用工具并把结果规范化为统一结构

使用说明:
在项目根目录执行 `python -m pytest tests/test_mcp_client.py`。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from agent_service.tools.mcp.client import MCPClient, MCPServerConfig


class FakeAsyncContextManager:
    """测试用异步上下文管理器。"""

    def __init__(self, value: Any) -> None:
        """保存进入上下文时返回的值。"""

        self.value = value

    async def __aenter__(self) -> Any:
        """进入异步上下文时返回预设值。"""

        return self.value

    async def __aexit__(self, *_exc_info: object) -> None:
        """退出异步上下文时不做额外处理。"""

        return None


class FakeClientSession:
    """测试用假 MCP Session。"""

    def __init__(self, read_stream: Any, write_stream: Any) -> None:
        """记录底层读写流。"""

        self.read_stream = read_stream
        self.write_stream = write_stream
        self.initialized = False

    async def __aenter__(self) -> "FakeClientSession":
        """进入异步上下文时返回自身。"""

        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """退出异步上下文时不做额外处理。"""

        return None

    async def initialize(self) -> None:
        """模拟 MCP initialize。"""

        self.initialized = True

    async def list_tools(self) -> Any:
        """返回固定工具列表。"""

        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="echo_text",
                    description="回显文本",
                    inputSchema={"type": "object", "properties": {"text": {"type": "string"}}},
                )
            ]
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """返回固定工具调用结果。"""

        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text=f"{name}:{arguments.get('text', '')}")
            ],
            structuredContent={"name": name, "arguments": arguments},
            isError=False,
        )


def build_fake_sdk() -> Any:
    """构造测试用假 MCP SDK。"""

    class FakeStdioServerParameters:
        """测试用 stdio server 参数对象。"""

        def __init__(self, **kwargs: Any) -> None:
            """保存传入的 server 参数。"""

            self.kwargs = kwargs

    def fake_stdio_client(_server_parameters: Any) -> FakeAsyncContextManager:
        """返回假的 stdio client 上下文。"""

        return FakeAsyncContextManager(("read-stream", "write-stream"))

    return SimpleNamespace(
        ClientSession=FakeClientSession,
        StdioServerParameters=FakeStdioServerParameters,
        stdio_client=fake_stdio_client,
    )


def test_mcp_client_lists_tools(monkeypatch: Any) -> None:
    """验证 MCPClient 能建立连接并读取工具列表。"""

    client = MCPClient(config=MCPServerConfig(command="python", args=["-m", "fake_server"]))
    monkeypatch.setattr(client, "_import_mcp_sdk", lambda: build_fake_sdk())

    async def run_case() -> None:
        async with client:
            tools = await client.list_tools()
            assert client.is_connected is True
            assert len(tools) == 1
            assert tools[0].name == "echo_text"
            assert tools[0].description == "回显文本"

    asyncio.run(run_case())
    assert client.is_connected is False


def test_mcp_client_call_tool_normalizes_text_result(monkeypatch: Any) -> None:
    """验证 MCPClient 会把工具返回结果规范化为统一文本与结构化内容。"""

    client = MCPClient(config=MCPServerConfig(command="python", args=["-m", "fake_server"]))
    monkeypatch.setattr(client, "_import_mcp_sdk", lambda: build_fake_sdk())

    async def run_case() -> None:
        async with client:
            result = await client.call_tool("echo_text", {"text": "hello"})
            assert result.tool_name == "echo_text"
            assert result.text == "echo_text:hello"
            assert result.structured_content["arguments"]["text"] == "hello"
            assert result.is_error is False

    asyncio.run(run_case())

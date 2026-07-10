"""
MCP 工具注册适配模块。
功能说明:
本文文件负责把外部 MCP Server 暴露的工具发现出来,并转换为项目现有
`BuiltinToolDefinition` 兼容结构,从而与原生 builtin tools 共同注册到 `ToolRegistry`。
实现策略:
1. 启动阶段按配置连接每个启用的 MCP Server。
2. 拉取工具清单并为每个工具生成带前缀的稳定工具名。
3. 将 MCP 工具包装为同步 Python callable,供现有 ToolExecutor 直接执行。

使用说明:
`ToolRegistry.with_builtin_tools(config=...)` 会在启用 `config.mcp.enabled` 时调用本模块,
自动将 MCP 工具与原生工具一起注册给 Agent 使用。
"""

from __future__ import annotations

import asyncio
import json
import queue
import re
from dataclasses import dataclass
import threading
from typing import Any

from agent_service.core.agent_config import AgentConfig
from agent_service.tools.builtin import BuiltinToolDefinition
from agent_service.tools.mcp.client import (
    MCPClient,
    MCPServerConfig as MCPClientServerConfig,
    MCPToolInfo,
)


@dataclass(frozen=True, slots=True)
class MCPRegisteredTool:
    """
    MCP 工具注册信息。
    registered_name: 注册到 Agent 工具链中的最终工具名。
    source_tool_name: MCP Server 原始工具名。
    server_id: 来源 MCP Server 的稳定标识。
    description: 包含来源 server 信息的工具描述。
    args_schema: 归一化后的 JSON Schema。
    """

    registered_name: str
    source_tool_name: str
    server_id: str
    description: str
    args_schema: dict[str, Any]


class MCPToolRegistryAdapter:
    """
    MCP 工具注册适配器。
    config: 全局配置对象,其中 `config.mcp` 定义启用开关、工具名前缀和 server 列表。
    """

    def __init__(self, *, config: AgentConfig) -> None:
        """保存配置对象,供后续发现和调用 MCP 工具时复用。"""

        self.config = config

    def build_tool_definitions(self) -> list[BuiltinToolDefinition]:
        """
        构建全部 MCP 工具定义。
        返回值中的每一项都兼容现有 `BuiltinToolDefinition`,可直接注册到 ToolRegistry。
        """

        if not self.config.mcp.enabled:
            return []
        definitions: list[BuiltinToolDefinition] = []
        for server_entry in self.config.mcp.servers:
            if not server_entry.get("enabled", True):
                continue
            server_config = self._build_server_config(server_entry)
            registered_tools = self._discover_registered_tools(server_config)
            for registered_tool in registered_tools:
                definitions.append(
                    BuiltinToolDefinition(
                        name=registered_tool.registered_name,
                        description=registered_tool.description,
                        args_schema=registered_tool.args_schema,
                        function=self._build_sync_tool_callable(
                            server_config=server_config,
                            source_tool_name=registered_tool.source_tool_name,
                        ),
                    )
                )
        return definitions

    def _discover_registered_tools(self, server_config: MCPRuntimeServerConfig) -> list[MCPRegisteredTool]:
        """连接指定 MCP Server,拉取工具列表并转换为可注册的元数据结构。"""

        tools = self._run_async(self._discover_server_tools(server_config))
        return [
            MCPRegisteredTool(
                registered_name=self._build_registered_tool_name(
                    server_id=server_config.server_id,
                    tool_name=tool.name,
                ),
                source_tool_name=tool.name,
                server_id=server_config.server_id,
                description=self._build_registered_description(
                    server_id=server_config.server_id,
                    tool=tool,
                ),
                args_schema=self._normalize_input_schema(tool.input_schema),
            )
            for tool in tools
        ]

    async def _discover_server_tools(self, server_config: MCPRuntimeServerConfig) -> list[MCPToolInfo]:
        """异步连接单个 MCP Server 并拉取工具清单。"""

        client = MCPClient(config=server_config.to_client_config())
        async with client:
            return await client.list_tools()

    def _build_sync_tool_callable(
        self,
        *,
        server_config: MCPRuntimeServerConfig,
        source_tool_name: str,
    ) -> Any:
        """为单个 MCP 工具构建同步包装函数,以兼容当前同步 ToolExecutor。"""

        def _invoke_mcp_tool(**arguments: Any) -> str:
            return self._call_tool_sync(
                server_config=server_config,
                tool_name=source_tool_name,
                arguments=arguments,
            )

        return _invoke_mcp_tool

    def _call_tool_sync(
        self,
        *,
        server_config: MCPRuntimeServerConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """同步调用指定 MCP 工具并将返回值归一化为字符串。"""

        result = self._run_async(
            self._call_tool_async(
                server_config=server_config,
                tool_name=tool_name,
                arguments=arguments,
            )
        )
        payload = self._format_tool_result(result)
        if result.is_error:
            raise RuntimeError(payload)
        return payload

    async def _call_tool_async(
        self,
        *,
        server_config: MCPRuntimeServerConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """异步连接 MCP Server 并执行单个工具调用。"""

        client = MCPClient(config=server_config.to_client_config())
        async with client:
            return await client.call_tool(tool_name, arguments)

    @staticmethod
    def _format_tool_result(result: Any) -> str:
        """
        将 MCP 调用结果转换为统一文本。
        优先返回文本,其次返回结构化内容,最后兜底返回原始 content。
        """

        if result.text:
            return result.text
        if result.structured_content is not None:
            return json.dumps(result.structured_content, ensure_ascii=False, indent=2)
        if result.content:
            serialized_content = []
            for item in result.content:
                if isinstance(item, dict):
                    serialized_content.append(item)
                    continue
                serialized_content.append(
                    {
                        key: value
                        for key, value in vars(item).items()
                        if not key.startswith("_")
                    }
                )
            return json.dumps(serialized_content, ensure_ascii=False, indent=2)
        return ""

    def _build_server_config(self, server_entry: dict[str, Any]) -> "MCPRuntimeServerConfig":
        """将配置文件中的单条 server 字典转换为带校验的运行时配置对象。"""

        raw_server_id = str(server_entry.get("server_id", "")).strip()
        if not raw_server_id:
            raise ValueError("MCP server 配置缺少必填字段 server_id。")
        command = str(server_entry.get("command", "")).strip()
        if not command:
            raise ValueError(f"MCP server {raw_server_id} 配置缺少必填字段 command。")
        args = server_entry.get("args", [])
        env = server_entry.get("env")
        if args is None:
            args = []
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError(f"MCP server {raw_server_id} 的 args 必须是字符串列表。")
        if env is not None and (
            not isinstance(env, dict)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in env.items())
        ):
            raise ValueError(f"MCP server {raw_server_id} 的 env 必须是字符串字典。")
        encoding = str(server_entry.get("encoding", "utf-8")).strip() or "utf-8"
        return MCPRuntimeServerConfig(
            server_id=self._sanitize_identifier(raw_server_id),
            command=command,
            args=list(args),
            env=dict(env) if env is not None else None,
            encoding=encoding,
        )

    def _build_registered_tool_name(self, *, server_id: str, tool_name: str) -> str:
        """生成带前缀和 server 隔离的最终工具名,避免与原生工具或其他 server 冲突。"""

        prefix = self._sanitize_identifier(self.config.mcp.tool_name_prefix) or "mcp"
        return f"{prefix}__{server_id}__{self._sanitize_identifier(tool_name)}"

    @staticmethod
    def _build_registered_description(*, server_id: str, tool: MCPToolInfo) -> str:
        """为 MCP 工具补充来源 server 信息,方便模型理解工具来源。"""

        base_description = tool.description.strip() or f"MCP tool {tool.name}"
        return f"{base_description} (source: MCP server {server_id}, tool {tool.name})"

    @staticmethod
    def _normalize_input_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
        """将 MCP 工具的输入 schema 归一化为当前 ToolRegistry 可消费的 object schema。"""

        if not isinstance(input_schema, dict):
            return {"type": "object", "properties": {}, "required": []}
        schema_type = input_schema.get("type", "object")
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        if schema_type != "object" or not isinstance(properties, dict):
            return {"type": "object", "properties": {}, "required": []}
        if not isinstance(required, list):
            required = []
        return {
            "type": "object",
            "properties": properties,
            "required": [item for item in required if isinstance(item, str)],
        }

    @staticmethod
    def _sanitize_identifier(value: str) -> str:
        """将 server_id 或 tool_name 归一化为稳定的工具标识片段。"""

        normalized = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized.lower() or "tool"

    @staticmethod
    def _run_async(coro: Any) -> Any:
        """
        在当前同步工具链中运行异步 MCP 发现或调用逻辑。
        若当前线程已存在运行中的事件循环,则切换到临时线程执行,避免 `asyncio.run()` 冲突。
        """

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

        def _thread_main() -> None:
            try:
                result_queue.put((True, asyncio.run(coro)))
            except Exception as exc:  # noqa: BLE001
                result_queue.put((False, exc))

        worker = threading.Thread(target=_thread_main, daemon=True, name="mcp-sync-bridge")
        worker.start()
        worker.join()
        success, payload = result_queue.get()
        if success:
            return payload
        raise payload


@dataclass(frozen=True, slots=True)
class MCPRuntimeServerConfig:
    """
    MCP Server 运行时配置。
    server_id: 在 Agent 内部用于注册工具名前缀隔离的稳定 server 标识。
    command: 启动 MCP Server 的命令。
    args: 启动命令参数列表。
    env: 可选环境变量覆盖。
    encoding: stdio 编码。
    """

    server_id: str
    command: str
    args: list[str]
    env: dict[str, str] | None
    encoding: str = "utf-8"

    def to_client_config(self) -> Any:
        """转换为底层 `MCPClient` 需要的连接配置对象。"""

        return MCPClientServerConfig(
            command=self.command,
            args=self.args,
            env=self.env,
            encoding=self.encoding,
        )

"""
MCP 工具适配包。
功能说明:
本包集中导出 MCP 异步 client 与 MCP 工具注册适配器,供 ToolRegistry 和调试脚本复用。
"""

from agent_service.tools.mcp.client import MCPCallResult, MCPClient, MCPServerConfig, MCPToolInfo
from agent_service.tools.mcp.registry import MCPRuntimeServerConfig, MCPToolRegistryAdapter

__all__ = [
    "MCPCallResult",
    "MCPClient",
    "MCPServerConfig",
    "MCPToolInfo",
    "MCPRuntimeServerConfig",
    "MCPToolRegistryAdapter",
]

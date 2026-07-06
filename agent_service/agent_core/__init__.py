"""
Agent 核心包导出模块。

功能说明:
本文件对外导出 `AgentCore`,调用方可以通过 `agent_service.agent_core`
直接导入核心入口类。

使用说明:
from agent_service.agent_core import AgentCore
"""

from agent_service.agent_core.agent_core import AgentCore

__all__ = ["AgentCore"]

"""全部内置工具的领域化 package 与兼容导出入口。

调用方继续使用 ``agent_service.tools.builtin`` 导入工具定义和函数；实际实现按
agent、terminal、utility、memory、knowledge、web、tasks、library、git 等职责存放。
"""

from agent_service.tools.builtin.builtin import BuiltinToolDefinition
from agent_service.tools.builtin.agent import *  # noqa: F403
from agent_service.tools.builtin.terminal import *  # noqa: F403
from agent_service.tools.builtin.utility import *  # noqa: F403
from agent_service.tools.builtin.memory import *  # noqa: F403
from agent_service.tools.builtin.knowledge import *  # noqa: F403
from agent_service.tools.builtin.web import *  # noqa: F403
from agent_service.tools.builtin.tasks import *  # noqa: F403
from agent_service.tools.builtin.library import *  # noqa: F403
from agent_service.tools.builtin.git import *  # noqa: F403
from agent_service.tools.builtin.business_ops import *  # noqa: F403
from agent_service.tools.builtin.knowledge_ops import *  # noqa: F403
from agent_service.tools.builtin.smart_forms import *  # noqa: F403
from agent_service.tools.builtin.knowledge import _build_knowledge_service
from agent_service.tools.definitions import (
    BUILTIN_TOOL_DEFINITIONS,
    FILE_TOOL_DEFINITIONS,
    KNOWLEDGE_TOOL_DEFINITIONS,
    MEMORY_TOOL_DEFINITIONS,
    TODO_TOOL_DEFINITIONS,
    UTILITY_TOOL_DEFINITIONS,
)

__all__ = [
    "BUILTIN_TOOL_DEFINITIONS",
    "FILE_TOOL_DEFINITIONS",
    "KNOWLEDGE_TOOL_DEFINITIONS",
    "MEMORY_TOOL_DEFINITIONS",
    "TODO_TOOL_DEFINITIONS",
    "UTILITY_TOOL_DEFINITIONS",
    "BuiltinToolDefinition",
]

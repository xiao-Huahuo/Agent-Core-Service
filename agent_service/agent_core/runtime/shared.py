"""AgentCore runtime 模块共享的模式常量。

这些常量从原 AgentCore 模块原样迁移；AgentCore 继续重导出它们以保持兼容。
"""

AGENT_LOOP_AUTO = "auto"
AGENT_LOOP_SIMPLE = "simple"
AGENT_LOOP_REACT = "react"
AGENT_LOOP_PLAN = "plan"
AGENT_LOOP_DEEP_ALIAS = "deep"
AGENT_LOOP_MODES = {
    AGENT_LOOP_AUTO,
    AGENT_LOOP_SIMPLE,
    AGENT_LOOP_REACT,
    AGENT_LOOP_PLAN,
    AGENT_LOOP_DEEP_ALIAS,
}

"""Agent runtime 的 token 用量提取适配。

保持现有 ModelDecisionNode 提取规则为唯一实现，runtime 只提供稳定入口。
"""

from __future__ import annotations

from typing import Any

from agent_service.agent_core.nodes.model_decision import extract_token_usage as _extract_token_usage


def extract_token_usage(message: Any) -> dict[str, int]:
    """按现有规则从 LangChain message 提取输入、输出和总 token。"""

    return _extract_token_usage(message)

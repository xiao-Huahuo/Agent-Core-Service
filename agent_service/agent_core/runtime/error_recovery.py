"""Agent runtime 的用户可见错误归一化。

本模块从 AgentCore 提取既有模型错误分类，不改变错误文案和降级规则。
"""

from __future__ import annotations

import re


def extract_friendly_error(error_message: str) -> str:
    """把模型安全、限流、凭证、超时和连接错误转换为原有友好文案。"""

    lower = error_message.lower()
    if "content_filter" in lower:
        match = re.search(r"'message':\s*'([^']+)'", error_message) or re.search(
            r'"message":\s*"([^"]+)"',
            error_message,
        )
        detail = match.group(1) if match else "请求因内容安全策略被拦截"
        return f"内容安全拦截: {detail}"
    if "429" in lower or "too many requests" in lower or "rate_limit" in lower or "rate limit" in lower:
        return "模型服务限流(429 Too Many Requests),请稍后重试;如果频繁出现,请切换模型或配置独立的小模型 API Key。"
    if "missing api key" in lower or (
        "api key" in lower and ("missing" in lower or "not found" in lower or "empty" in lower)
    ):
        return "模型 API Key 未配置或未传入,请在设置页检查主模型和小模型 API Key。"
    if "timeout" in lower:
        return "请求超时,请稍后重试"
    if "connection error" in lower or "connection reset" in lower or "connection aborted" in lower:
        return "模型服务连接失败,请检查网络、代理、Base URL 和 API Key;如果服务端刚返回过 429,通常是限流导致的连接中断。"
    return error_message.split("\n")[0].strip()

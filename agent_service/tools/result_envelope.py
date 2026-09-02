"""工具结果结构化信封。

工具正文仍作为正式 ToolMessage 完整保存；本模块生成供 Agent、Planner、
Observation 和 Debug 共用的确定性状态、摘要与续读引用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolResultEnvelope:
    """一次工具调用的结构化结果元数据。"""

    tool_call_id: str
    tool_name: str
    status: str
    summary: str
    content_ref: str
    content_type: str = "text/plain"
    key_facts: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """返回可持久化和跨进程序列化的字典。"""

        return {
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "summary": self.summary,
            "content_ref": self.content_ref,
            "content_type": self.content_type,
            "key_facts": list(self.key_facts),
            "error": self.error,
            "continuation": {"supported": True, "method": "read_tool_result"},
        }


def build_tool_result_envelope(
    *,
    tool_call_id: str,
    tool_name: str,
    content: str,
    failed: bool,
) -> ToolResultEnvelope:
    """从工具确定性输出构造状态与关键事实，不调用额外 LLM。"""

    status = "error" if failed else "success"
    summary = f"工具 {tool_name} 执行失败。" if failed else f"工具 {tool_name} 已完成。"
    key_facts: list[str] = []
    content_type = "text/plain"
    if tool_name == "run_terminal_command":
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict):
            content_type = "application/json"
            segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
            failed_segments = [item for item in segments if isinstance(item, dict) and item.get("returncode") not in {0, None}]
            status = "error" if failed or failed_segments else "success"
            key_facts.extend([
                f"segments={len(segments)}",
                f"failed_segments={len(failed_segments)}",
                f"truncated={bool(payload.get('truncated'))}",
            ])
            summary = (
                f"终端执行失败：{len(failed_segments)}/{len(segments)} 个命令段失败。"
                if status == "error"
                else f"终端执行完成：{len(segments)} 个命令段成功。"
            )
    return ToolResultEnvelope(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        status=status,
        summary=summary,
        content_ref=f"tool-result://{tool_call_id}",
        content_type=content_type,
        key_facts=tuple(key_facts),
        error=summary if failed else None,
    )


def render_tool_result_context(message: Any) -> str:
    """把 ToolMessage 渲染为 Planner/Observation 共用的结构化执行账本。"""

    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    envelope = additional_kwargs.get("tool_result")
    if isinstance(envelope, dict):
        payload = {}
        for key in ("tool_name", "status", "summary", "key_facts", "error", "content_ref"):
            value = envelope.get(key)
            if value is not None and value != "" and value != []:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    tool_call_id = str(getattr(message, "tool_call_id", "") or "")
    content = str(getattr(message, "content", "") or "")
    failed = "失败" in content or "error" in content.casefold()
    return json.dumps({
        "tool_name": str(getattr(message, "name", "") or "unknown"),
        "status": "error" if failed else "unknown",
        "summary": "旧工具结果缺少结构化信封，请按 content_ref 续读。",
        "content_ref": f"tool-result://{tool_call_id}",
    }, ensure_ascii=False, sort_keys=True)

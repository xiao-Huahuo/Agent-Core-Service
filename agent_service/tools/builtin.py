"""
内置工具定义模块。

功能说明:
本文件只负责书写项目自带的小工具函数,不负责工具注册和工具执行。工具注册由
`tool_registry.py` 完成,工具执行由 `executor.py` 完成。

使用说明:
新增内置工具时,在本文件中书写普通 Python 函数,并在 `BUILTIN_TOOL_DEFINITIONS`
中登记工具名称、描述、参数说明和函数对象。
"""

from __future__ import annotations

import ast
import json
import operator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_service.tools.runtime_context import get_tool_runtime
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate


ToolFunction = Callable[..., str]


@dataclass(frozen=True, slots=True)
class BuiltinToolDefinition:
    """
    内置工具定义。

    name: 工具名称,需要和 LLM tool_call 中的 name 匹配。
    description: 工具用途说明,会暴露给 LLM 作为工具选择依据。
    args_schema: 工具参数 JSON Schema,用于生成 LangChain StructuredTool。
    function: 实际执行的 Python 函数。
    """

    name: str
    description: str
    args_schema: dict[str, Any]
    function: ToolFunction


def get_current_utc_time() -> str:
    """
    获取当前 UTC 时间。

    返回值: ISO 8601 格式 UTC 时间字符串。
    """

    return datetime.now(timezone.utc).isoformat()


def get_current_time(timezone_name: str = "UTC") -> str:
    """
    获取指定时区的当前时间。

    timezone_name: IANA 时区名称,例如 `UTC`、`Asia/Shanghai`、`America/New_York`。
    """

    normalized_timezone_name = timezone_name or "UTC"
    try:
        target_timezone = ZoneInfo(normalized_timezone_name)
    except ZoneInfoNotFoundError:
        return f"未知时区: {normalized_timezone_name}"
    return datetime.now(target_timezone).isoformat()


def echo_text(text: str) -> str:
    """
    原样返回输入文本。

    text: 需要回显的文本。
    """

    return text


def generate_uuid() -> str:
    """
    生成随机 UUID。

    返回值: UUID4 字符串,可用于临时任务 ID、调试 ID 或幂等标识。
    """

    return str(uuid4())


def calculate(expression: str) -> str:
    """
    安全计算基础数学表达式。

    expression: 只允许数字、括号、加减乘除、取模、幂和一元正负号。
    """

    try:
        result = _evaluate_math_expression(ast.parse(expression, mode="eval").body)
    except Exception as exc:
        return f"计算失败: {exc}"
    return str(result)


def json_parse(json_text: str) -> str:
    """
    解析 JSON 字符串并返回格式化结果。

    json_text: 需要解析的 JSON 字符串。
    """

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return f"JSON 解析失败: 第 {exc.lineno} 行第 {exc.colno} 列: {exc.msg}"
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def json_pick(json_text: str, path: str) -> str:
    """
    从 JSON 字符串中按简单路径取值。

    json_text: 需要读取的 JSON 字符串。
    path: 点分路径,例如 `user.name` 或 `items.0.title`。
    """

    try:
        current_value: Any = json.loads(json_text)
        for segment in path.split("."):
            if isinstance(current_value, list):
                current_value = current_value[int(segment)]
            elif isinstance(current_value, dict):
                current_value = current_value[segment]
            else:
                return f"路径 {path} 在 {segment} 处无法继续读取。"
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        return f"JSON 取值失败: {exc}"
    return json.dumps(current_value, ensure_ascii=False)


def text_stats(text: str) -> str:
    """
    统计文本基础信息。

    text: 需要统计的文本。
    """

    stats = {
        "characters": len(text),
        "non_whitespace_characters": len("".join(text.split())),
        "lines": 0 if text == "" else text.count("\n") + 1,
        "words": len(text.split()),
        "rough_tokens": max(1, len(text) // 4) if text else 0,
    }
    return json.dumps(stats, ensure_ascii=False)


def list_builtin_tools() -> str:
    """
    列出当前注册的内置工具定义。

    返回值: 工具名称和描述的 JSON 字符串。
    """

    tools = [
        {"name": definition.name, "description": definition.description}
        for definition in BUILTIN_TOOL_DEFINITIONS
    ]
    return json.dumps(tools, ensure_ascii=False, indent=2)


def get_long_term_memory(query: str, top_k: int = 3) -> str:
    """
    检索当前用户的长期摘要记忆。

    query: 检索查询文本。
    top_k: 最多返回多少条结果。
    """

    runtime = get_tool_runtime()
    results = runtime.retrieval_service.retrieve_long_term_memory(
        query=query,
        user_id=runtime.user_id,
        session_id=runtime.session_id,
        top_k=top_k,
    )
    payload = [
        {
            "memory_id": item.memory.memory_id,
            "tag": item.memory.tag,
            "memory_type": item.memory.memory_type,
            "content": item.memory.content,
            "score": round(item.final_score, 4),
            "source_uri": item.memory.source_uri,
            "valid_from": item.memory.valid_from.isoformat(),
            "valid_until": item.memory.valid_until.isoformat() if item.memory.valid_until else None,
            "authority": item.memory.authority,
        }
        for item in results
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def get_knowledge_context(query: str, top_k: int = 3) -> str:
    """
    检索知识库相关片段。

    query: 检索查询文本。
    top_k: 最多返回多少条结果。
    """

    runtime = get_tool_runtime()
    results = runtime.retrieval_service.retrieve_knowledge(query=query, top_k=top_k)
    payload = [
        {
            "memory_id": item.memory.memory_id,
            "tag": item.memory.tag,
            "memory_type": item.memory.memory_type,
            "content": item.memory.content,
            "score": round(item.final_score, 4),
            "source_uri": item.memory.source_uri,
            "valid_from": item.memory.valid_from.isoformat(),
            "valid_until": item.memory.valid_until.isoformat() if item.memory.valid_until else None,
            "authority": item.memory.authority,
        }
        for item in results
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_long_term_memory(
    content: str,
    memory_type: str = "important_fact_summary",
    importance: float = 0.5,
    authority: float = 0.5,
) -> str:
    """
    向当前用户的长期记忆中写入一条记录,包含向量化后可被后续对话检索召回。

    content: 需要记忆的内容。
    memory_type: 记忆子类型,默认 important_fact_summary。可选值与检索优先级相关。
    importance: 重要性(0~1),默认 0.5。
    authority: 权威性(0~1),默认 0.5。
    """

    runtime = get_tool_runtime()
    embedding = runtime.embedding_service.embed_text(content) if runtime.embedding_service else []
    now = datetime.now(timezone.utc)
    create_dto = LongTermMemorySpecCreate(
        user_id=runtime.user_id,
        session_id=runtime.session_id,
        tag=runtime.config.constants.memory_tag,
        memory_type=memory_type,
        content=content,
        source_type="manual_write",
        source_id=None,
        source_uri="manual",
        confidence=1.0,
        importance=importance,
        authority=authority,
        embedding_model=runtime.config.model.embedding_model_name or None,
        embedding_vector_json=embedding,
        metadata_json={
            "fact_status": "active",
            "fact": {"namespace": "general", "key": memory_type, "value": content},
        },
    )

    memory = runtime.memory_service.create_memory(create_dto)

    result = {
        "memory_id": memory.memory_id,
        "content": content,
        "memory_type": memory.memory_type,
        "importance": memory.importance,
        "status": "created",
    }
    return json.dumps(result, ensure_ascii=False)


def _evaluate_math_expression(node: ast.AST) -> int | float:
    """
    递归计算经过 AST 白名单校验的数学表达式。

    node: `ast.parse(..., mode="eval").body` 返回的表达式节点。
    """

    binary_operators: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    unary_operators: dict[type[ast.unaryop], Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in binary_operators:
        left_value = _evaluate_math_expression(node.left)
        right_value = _evaluate_math_expression(node.right)
        return binary_operators[type(node.op)](left_value, right_value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in unary_operators:
        return unary_operators[type(node.op)](_evaluate_math_expression(node.operand))
    raise ValueError("表达式包含不允许的内容。")


BUILTIN_TOOL_DEFINITIONS = [
    BuiltinToolDefinition(
        name="get_current_utc_time",
        description="获取当前 UTC 时间。当用户询问当前时间或需要时间戳时使用。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=get_current_utc_time,
    ),
    BuiltinToolDefinition(
        name="get_current_time",
        description="获取指定 IANA 时区的当前时间。默认使用 UTC。",
        args_schema={
            "type": "object",
            "properties": {
                "timezone_name": {
                    "type": "string",
                    "description": "IANA 时区名称,例如 UTC、Asia/Shanghai。",
                }
            },
            "required": [],
        },
        function=get_current_time,
    ),
    BuiltinToolDefinition(
        name="echo_text",
        description="原样返回输入文本。用于测试工具调用链路是否正常。",
        args_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "需要原样返回的文本。",
                }
            },
            "required": ["text"],
        },
        function=echo_text,
    ),
    BuiltinToolDefinition(
        name="generate_uuid",
        description="生成随机 UUID4 字符串,用于临时标识或调试标识。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=generate_uuid,
    ),
    BuiltinToolDefinition(
        name="calculate",
        description="安全计算基础数学表达式,只支持数字和基础算术运算。",
        args_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式,例如 (1 + 2) * 3。",
                }
            },
            "required": ["expression"],
        },
        function=calculate,
    ),
    BuiltinToolDefinition(
        name="json_parse",
        description="解析 JSON 字符串,返回格式化 JSON 或错误位置。",
        args_schema={
            "type": "object",
            "properties": {
                "json_text": {
                    "type": "string",
                    "description": "需要解析的 JSON 字符串。",
                }
            },
            "required": ["json_text"],
        },
        function=json_parse,
    ),
    BuiltinToolDefinition(
        name="json_pick",
        description="从 JSON 字符串中按点分路径读取字段值。",
        args_schema={
            "type": "object",
            "properties": {
                "json_text": {
                    "type": "string",
                    "description": "需要读取的 JSON 字符串。",
                },
                "path": {
                    "type": "string",
                    "description": "点分路径,例如 user.name 或 items.0.title。",
                },
            },
            "required": ["json_text", "path"],
        },
        function=json_pick,
    ),
    BuiltinToolDefinition(
        name="text_stats",
        description="统计文本字符数、非空白字符数、行数、词数和粗略 token 数。",
        args_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "需要统计的文本。",
                }
            },
            "required": ["text"],
        },
        function=text_stats,
    ),
    BuiltinToolDefinition(
        name="list_builtin_tools",
        description="列出当前注册的全部内置工具名称和描述。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=list_builtin_tools,
    ),
    BuiltinToolDefinition(
        name="get_long_term_memory",
        description="检索当前用户在长期记忆中的相关摘要信息,用于跨轮对话回忆项目目标、约束、偏好和历史事实。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要检索的记忆查询文本。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "最多返回多少条结果,默认 3。",
                },
            },
            "required": ["query"],
        },
        function=get_long_term_memory,
    ),
    BuiltinToolDefinition(
        name="get_knowledge_context",
        description="检索知识库中的相关片段,用于回答事实性、说明性和文档型问题。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要检索的知识查询文本。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "最多返回多少条结果,默认 3。",
                },
            },
            "required": ["query"],
        },
        function=get_knowledge_context,
    ),
    BuiltinToolDefinition(
        name="write_long_term_memory",
        description="向当前用户的长期记忆中写入一条记录,包含向量化后可被后续对话检索召回。可用于手动存储重要信息、项目代号、用户偏好等需要跨会话持久化的内容。",
        args_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "需要记忆的内容,建议简洁完整,以便后续检索。",
                },
                "memory_type": {
                    "type": "string",
                    "description": "记忆子类型,默认 important_fact_summary。一般无需修改。",
                },
                "importance": {
                    "type": "number",
                    "description": "重要性(0~1),默认 0.5。0~0.3 为低,0.4~0.6 为中,0.7~1.0 为高。",
                },
                "authority": {
                    "type": "number",
                    "description": "权威性(0~1),默认 0.5。",
                },
            },
            "required": ["content"],
        },
        function=write_long_term_memory,
    ),
]

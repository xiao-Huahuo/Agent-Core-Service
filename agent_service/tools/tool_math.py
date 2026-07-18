"""
内置数学工具辅助模块。

功能说明:
本文件提供安全数学表达式求值逻辑,只允许数字和基础算术 AST 节点,避免 `builtin.py`
继续堆积低层 helper。

使用说明:
`builtin.calculate()` 调用 `evaluate_math_expression(expression)` 并把异常转换为工具返回文本。
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import Any


def evaluate_math_expression(expression: str) -> int | float:
    """计算经过 AST 白名单校验的数学表达式。"""

    return _evaluate_math_node(ast.parse(expression, mode="eval").body)


def _evaluate_math_node(node: ast.AST) -> int | float:
    """递归计算单个数学表达式 AST 节点。"""

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
        left_value = _evaluate_math_node(node.left)
        right_value = _evaluate_math_node(node.right)
        return binary_operators[type(node.op)](left_value, right_value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in unary_operators:
        return unary_operators[type(node.op)](_evaluate_math_node(node.operand))
    raise ValueError("表达式包含不允许的内容。")

"""AgentConfig 业务硬限制集中化验收测试。

使用说明:
本文件验证每个配置字段都有用途说明、BusinessLimitsConfig 支持显式覆盖和环境
变量覆盖,并防止后续新增未说明用途的配置字段。
"""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass
from pathlib import Path

from agent_service.core.agent_config import AgentConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_every_nested_config_field_has_a_documented_purpose() -> None:
    """AgentConfig 每条常量配置都必须在所属配置类文档中备注用途。"""

    undocumented: list[str] = []
    for value in vars(AgentConfig).values():
        if not isinstance(value, type) or not is_dataclass(value):
            continue
        class_doc = value.__doc__ or ""
        for config_field in fields(value):
            if f"{config_field.name}:" not in class_doc:
                undocumented.append(f"{value.__name__}.{config_field.name}")

    assert undocumented == []


def test_business_limits_support_explicit_overrides() -> None:
    """业务硬限制应通过 AgentConfig overrides 统一覆盖。"""

    config = AgentConfig.load_config(
        {
            "limits": {
                "agent_max_tool_calls_per_turn": 9,
                "graph_max_node_limit": 4321,
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )

    assert config.limits.agent_max_tool_calls_per_turn == 9
    assert config.limits.graph_max_node_limit == 4321


def test_business_limits_support_generic_environment_overrides(monkeypatch) -> None:
    """AGENT_LIMIT_<字段名> 应覆盖任意业务限制字段并保持字段类型。"""

    monkeypatch.setenv("AGENT_LIMIT_WEB_SEARCH_RETRY_COUNT", "7")
    monkeypatch.setenv("AGENT_LIMIT_AGENT_STREAM_QUEUE_POLL_SECONDS", "0.75")
    config = AgentConfig.load_config(
        load_env=True,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )

    assert config.limits.web_search_retry_count == 7
    assert config.limits.agent_stream_queue_poll_seconds == 0.75


def test_validation_layers_do_not_embed_numeric_limits() -> None:
    """数据库、DTO 与 REST 参数校验不得重新写入数值字面量。"""

    validation_keywords = {"min_length", "max_length", "ge", "gt", "le", "lt"}
    violations: list[str] = []
    paths = [
        *sorted((PROJECT_ROOT / "agent_service" / "models").glob("*.py")),
        *sorted((PROJECT_ROOT / "agent_service" / "schemas").glob("*.py")),
        *sorted((PROJECT_ROOT / "agent_service" / "api" / "rest").glob("*.py")),
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg in validation_keywords
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, int | float)
                ):
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT).as_posix()}:{keyword.value.lineno}:"
                        f"{keyword.arg}={keyword.value.value}"
                    )

    assert violations == []

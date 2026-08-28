"""导出固定 fake graph 的 Agent 流式事件契约快照。

用法：在项目根目录执行 ``python -m tests.contracts.export_agent_stream``。
脚本禁止模型下载和真实推理，只验证 AgentCore 把 LangGraph 更新转换成稳定事件的
现有行为。
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent_service.agent_core.agent_core import AgentCore
from agent_service.core.agent_config import AgentConfig
from tests.contracts.common import write_snapshot


class FixedGraph:
    """返回固定节点更新的最小 LangGraph 测试替身。"""

    def __init__(self) -> None:
        """创建稳定的节点更新和图结构。"""

        self.updates = [
            {
                "agent": {
                    "messages": [AIMessage(content="契约测试回复")],
                    "trace": [{"node": "agent", "event": "model_response"}],
                }
            }
        ]
        self.graph_data = SimpleNamespace(
            nodes={"__start__": object(), "agent": object(), "__end__": object()},
            edges=[
                SimpleNamespace(source="__start__", target="agent", conditional=False),
                SimpleNamespace(source="agent", target="__end__", conditional=False),
            ],
        )

    def stream(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        """返回固定的流式节点更新。"""

        return self.updates

    def get_graph(self) -> Any:
        """返回绘图所需的固定图结构。"""

        return self.graph_data


def _normalize(value: Any) -> Any:
    """替换事件中的运行时随机值，同时保留字段集合和事件顺序。"""

    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"run_id", "timestamp", "ts", "started_at", "completed_at"}:
                normalized[key] = f"<{key}>"
            elif key.endswith("duration_ms"):
                normalized[key] = "<duration_ms>"
            else:
                normalized[key] = _normalize(item)
        return normalized
    return value


def _build_config(project_root: Path) -> AgentConfig:
    """构造不创建目录、不下载模型的隔离配置。"""

    return AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(project_root),
                "base_data_dir": str(project_root / "runtime"),
            },
            "model": {"model_name": "contract-model"},
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )


def main() -> int:
    """运行固定流并写入规范化事件快照。"""

    with TemporaryDirectory(prefix="metaweave-contract-") as temporary_directory:
        config = _build_config(Path(temporary_directory))
        with patch.object(AgentConfig, "ensure_local_models", return_value=None):
            agent = AgentCore(config=config, graph=FixedGraph())
            events = list(agent.stream_run(prompt="契约测试", user_id="contract-user", session_id="contract-session"))
            agent.close()
    write_snapshot("agent_stream.json", _normalize(events))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

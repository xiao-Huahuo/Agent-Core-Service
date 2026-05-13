"""
Agent Mermaid 流程图生成脚本。

功能说明:
本文件负责从实际编译后的 LangGraph 图中读取节点和边,生成 Mermaid 流程图文本。
如果本机安装了 Mermaid CLI(`mmdc`),脚本会进一步把 Mermaid 文本渲染为 SVG。
脚本不再维护任何手写节点坐标或硬编码图结构,图内容完全来自 `compiled_graph.get_graph()`。

使用说明:
`AgentCore.__init__()` 会自动调用 `draw_agent_graph()` 并在项目根目录生成
`agent_graph.mmd`;如果检测到 `mmdc`,还会生成 `agent_graph.svg`。
也可以手动执行:

python -m agent_service.scripts.draw_agent_graph --output D:/Projects/Python/AgentService/agent_graph.mmd
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


MERMAID_HEADER = "flowchart TD"


def draw_agent_graph(compiled_graph: Any, output_path: Path | str, *, branch_labels: dict[tuple[str, str], str] | None = None) -> Path:
    """
    从实际编译后的 LangGraph 图读取节点和边,生成 Mermaid 文件并尽量渲染 SVG。

    compiled_graph: LangGraph 编译后的图对象,通常是 `CompiledStateGraph`。
    output_path: Mermaid 输出路径;如果传入 `.svg`,会自动改为同名 `.mmd` 作为源文件。
    branch_labels: 条件边的 (source, target) → 描述映射,来自 AgentGraphBuilder.branch_labels。
    """

    resolved_output_path = Path(output_path).expanduser().resolve()
    mermaid_path = _resolve_mermaid_path(resolved_output_path)
    mermaid_path.parent.mkdir(parents=True, exist_ok=True)
    mermaid_path.write_text(build_mermaid(compiled_graph, branch_labels=branch_labels), encoding="utf-8")
    _render_svg_if_available(mermaid_path=mermaid_path, requested_output_path=resolved_output_path)
    return mermaid_path


def build_mermaid(compiled_graph: Any, *, branch_labels: dict[tuple[str, str], str] | None = None) -> str:
    """
    把实际编译后的 LangGraph 图转换为 Mermaid flowchart 文本。

    compiled_graph: LangGraph 编译后的图对象,通常是 `CompiledStateGraph`。
    branch_labels: 条件边的 (source, target) → 描述映射,来自 AgentGraphBuilder.branch_labels。
    """

    graph_data = compiled_graph.get_graph()
    node_lines = [_build_node_line(str(node_id)) for node_id in graph_data.nodes.keys()]
    edge_lines = [_build_edge_line(edge, branch_labels=branch_labels) for edge in graph_data.edges]
    return "\n".join([MERMAID_HEADER, *node_lines, *edge_lines, ""])


def _resolve_mermaid_path(output_path: Path) -> Path:
    """
    根据用户传入路径确定 Mermaid 源文件路径。

    output_path: 用户要求的输出路径。
    """

    if output_path.suffix.lower() == ".svg":
        return output_path.with_suffix(".mmd")
    return output_path


def _render_svg_if_available(*, mermaid_path: Path, requested_output_path: Path) -> Path | None:
    """
    如果本机安装了 Mermaid CLI,则把 Mermaid 文件渲染为 SVG。

    mermaid_path: Mermaid 源文件路径。
    requested_output_path: 用户传入的原始输出路径,用于决定 SVG 输出位置。
    """

    mmdc_path = shutil.which("mmdc")
    if not mmdc_path:
        return None

    svg_path = requested_output_path if requested_output_path.suffix.lower() == ".svg" else mermaid_path.with_suffix(".svg")
    subprocess.run(
        [mmdc_path, "-i", str(mermaid_path), "-o", str(svg_path)],
        check=True,
    )
    return svg_path


def _build_node_line(node_id: str) -> str:
    """
    构造 Mermaid 节点声明。

    node_id: LangGraph 图中的原始节点 ID。
    """

    mermaid_id = _to_mermaid_id(node_id)
    label = _format_node_label(node_id)
    return f'    {mermaid_id}["{label}"]'


def _build_edge_line(edge: Any, *, branch_labels: dict[tuple[str, str], str] | None = None) -> str:
    """
    构造 Mermaid 边声明。

    edge: LangGraph `get_graph().edges` 中的边对象。
    branch_labels: 条件边的 (source, target) → 描述映射,来自 AgentGraphBuilder.branch_labels。
    """

    source = _to_mermaid_id(str(edge.source))
    target = _to_mermaid_id(str(edge.target))
    if edge.conditional:
        label = "conditional"
        if branch_labels:
            label = branch_labels.get((str(edge.source), str(edge.target)), "conditional")
        return f'    {source} -. "{label}" .-> {target}'
    return f"    {source} --> {target}"


def _to_mermaid_id(node_id: str) -> str:
    """
    将 LangGraph 节点 ID 转换为 Mermaid 可用的节点 ID。

    node_id: LangGraph 图中的原始节点 ID。
    """

    if node_id == "__start__":
        return "internal_start"
    if node_id == "__end__":
        return "internal_end"
    sanitized_id = re.sub(r"\W+", "_", node_id)
    if sanitized_id and sanitized_id[0].isdigit():
        return f"node_{sanitized_id}"
    return sanitized_id


def _format_node_label(node_id: str) -> str:
    """
    将 LangGraph 节点 ID 转换为 Mermaid 节点显示名。

    node_id: LangGraph 图中的原始节点 ID。
    """

    if node_id == "__start__":
        return "START"
    if node_id == "__end__":
        return "END"
    return node_id


def main() -> None:
    """命令行入口,用于根据当前 AgentCore 图编排手动生成 Mermaid 图。"""

    parser = argparse.ArgumentParser(description="Draw current AgentCore LangGraph as Mermaid.")
    parser.add_argument("--output", required=True, help="Mermaid output path, or SVG path when mmdc is installed.")
    args = parser.parse_args()

    from agent_service.agent_core.graph import AgentGraphBuilder
    from agent_service.core.agent_config import AgentConfig

    config = AgentConfig.load_config(ensure_models=False)
    builder = AgentGraphBuilder(config=config)
    compiled_graph = builder.build()
    draw_agent_graph(compiled_graph=compiled_graph, output_path=args.output, branch_labels=builder.branch_labels)


if __name__ == "__main__":
    main()

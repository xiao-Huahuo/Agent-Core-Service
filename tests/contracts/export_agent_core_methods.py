"""导出 AgentCore 方法到 runtime 职责的迁移清单骨架。

用法：``python -m tests.contracts.export_agent_core_methods``。脚本只解析源码并输出
方法名、行区间和长度，不修改生产文件。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path


def main() -> int:
    """解析 AgentCore 类并写入稳定 JSON 清单。"""

    project_root = Path(__file__).resolve().parents[2]
    source_path = project_root / "agent_service" / "agent_core" / "agent_core.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    agent_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AgentCore"
    )
    methods = [
        {
            "name": node.name,
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "line_count": (node.end_lineno or node.lineno) - node.lineno + 1,
            "target_runtime": "pending",
            "status": "pending",
        }
        for node in agent_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    output = project_root / "docs" / "acceptance" / "backend_maintenance" / "manifests" / "agent_core_methods.json"
    output.write_text(json.dumps(methods, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output.relative_to(project_root)} methods={len(methods)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

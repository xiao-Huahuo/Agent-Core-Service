"""导出后端结构重构所需的五份完整迁移清单。

用法：在项目根目录执行 ``python -m tests.contracts.export_manifests``。
脚本只读取 Python 源码和 protobuf 描述，不修改生产代码；结果写入
``docs/acceptance/backend_maintenance/manifests``，供各阶段逐项勾验。
"""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = PROJECT_ROOT / "agent_service" / "services"
OUTPUT_ROOT = PROJECT_ROOT / "docs" / "acceptance" / "backend_maintenance" / "manifests"
PYTHON_FILES = sorted(
    [PROJECT_ROOT / "main.py"]
    + list((PROJECT_ROOT / "agent_service").rglob("*.py"))
    + list((PROJECT_ROOT / "tests").rglob("*.py"))
)


def _module_name(path: Path) -> str:
    """把项目内 Python 路径转换成点分模块名。"""

    return ".".join(path.relative_to(PROJECT_ROOT).with_suffix("").parts)


@lru_cache(maxsize=None)
def _parse(path: Path) -> ast.Module:
    """以 UTF-8 读取并解析一个 Python 模块。"""

    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _public_symbols(path: Path) -> list[dict[str, Any]]:
    """返回模块中的公开函数、类及公开方法。"""

    symbols: list[dict[str, Any]] = []
    for node in _parse(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            symbols.append({"kind": "function", "name": node.name, "line": node.lineno})
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            methods = [
                {"name": child.name, "line": child.lineno}
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_")
            ]
            symbols.append({"kind": "class", "name": node.name, "line": node.lineno, "methods": methods})
    return symbols


def _target_service_path(path: Path) -> str:
    """根据根级 Service 模块角色给出无冲突的目标领域路径。"""

    stem = path.stem
    suffix_roles = (("_scheduler", "scheduler"), ("_tracking", "tracking"), ("_service", "service"))
    for suffix, role in suffix_roles:
        if stem.endswith(suffix):
            domain = stem[: -len(suffix)]
            return f"agent_service/services/{domain}/{role}.py"
    return f"agent_service/services/{stem}/{stem}.py"


def _import_references(module: str) -> list[str]:
    """列出所有静态 import 指向指定模块的项目文件。"""

    references: list[str] = []
    for path in PYTHON_FILES:
        try:
            tree = _parse(path)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        matched = any(
            isinstance(node, ast.ImportFrom) and node.module == module
            or isinstance(node, ast.Import) and any(alias.name == module for alias in node.names)
            for node in ast.walk(tree)
        )
        if matched:
            references.append(path.relative_to(PROJECT_ROOT).as_posix())
    return sorted(references)


def _service_manifest() -> list[dict[str, Any]]:
    """生成 services 根目录全部生产模块的迁移清单。"""

    manifest: list[dict[str, Any]] = []
    for path in sorted(SERVICE_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = _module_name(path)
        manifest.append(
            {
                "source": path.relative_to(PROJECT_ROOT).as_posix(),
                "target": _target_service_path(path),
                "public_symbols": _public_symbols(path),
                "import_references": _import_references(module),
                "status": "pending",
            }
        )
    return manifest


def _grpc_manifest() -> list[dict[str, Any]]:
    """从 protobuf descriptor 导出全部 RPC，并标记当前实现位置。"""

    from agent_service.api.grpc.agent_service_pb2 import DESCRIPTOR

    servicer_path = PROJECT_ROOT / "agent_service" / "api" / "grpc" / "servicer.py"
    method_lines = {
        node.name: node.lineno
        for node in ast.walk(_parse(servicer_path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    manifest: list[dict[str, Any]] = []
    for service in DESCRIPTOR.services_by_name.values():
        for method in service.methods:
            manifest.append(
                {
                    "service": service.full_name,
                    "rpc": method.name,
                    "request": method.input_type.full_name,
                    "response": method.output_type.full_name,
                    "client_streaming": method.client_streaming,
                    "server_streaming": method.server_streaming,
                    "current_line": method_lines.get(method.name),
                    "target_handler": "pending",
                    "target_use_case": "pending",
                    "error_mapper": "pending",
                    "status": "pending",
                }
            )
    return manifest


def _builtin_manifest() -> list[dict[str, Any]]:
    """导出当前注册的全部 builtin 工具定义。"""

    from agent_service.tools.definitions import BUILTIN_TOOL_DEFINITIONS

    return [
        {
            "name": definition.name,
            "description": definition.description,
            "callable": f"{definition.function.__module__}.{definition.function.__name__}",
            "parameters": definition.args_schema,
            "target_file": "pending",
            "status": "pending",
        }
        for definition in BUILTIN_TOOL_DEFINITIONS
    ]


def _write_json(name: str, payload: Any) -> None:
    """以稳定 UTF-8 JSON 写入一份清单。"""

    path = OUTPUT_ROOT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(PROJECT_ROOT)}")


def main() -> int:
    """生成并写入五份迁移清单。"""

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    _write_json("root_service_modules.json", _service_manifest())
    _write_json(
        "knowledge_library_methods.json",
        _public_symbols(SERVICE_ROOT / "knowledge_library" / "service.py"),
    )
    _write_json(
        "knowledge_graph_methods.json",
        _public_symbols(SERVICE_ROOT / "knowledge_graph" / "service.py"),
    )
    _write_json("grpc_rpc_manifest.json", _grpc_manifest())
    _write_json("builtin_tools_manifest.json", _builtin_manifest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
gRPC generated module import tests.

功能说明:
验证包内生成的 gRPC 文件能通过 main.py 使用的包路径导入,避免生成代码回退为
顶层 `import agent_service_pb2` 后导致服务启动失败。

使用说明:
在项目根目录执行 `python -m pytest tests/test_grpc_imports.py`。
"""

from __future__ import annotations


def test_generated_grpc_module_uses_package_import_path() -> None:
    """gRPC servicer 包导入链应能在项目根目录直接加载。"""

    from agent_service.api.grpc.agent_service_pb2_grpc import (  # noqa: PLC0415
        AgentServiceServicer as GeneratedBaseServicer,
        add_AgentServiceServicer_to_server,
    )

    assert GeneratedBaseServicer is not None
    assert callable(add_AgentServiceServicer_to_server)


def test_main_grpc_import_chain_loads_without_top_level_pb2_alias() -> None:
    """main.py 依赖的 gRPC 包导入链不能要求顶层 agent_service_pb2 模块。"""

    from agent_service.api.grpc.servicer import AgentServiceServicer  # noqa: PLC0415

    assert AgentServiceServicer is not None

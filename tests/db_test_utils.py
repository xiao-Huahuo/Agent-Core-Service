"""测试专用数据库 schema 初始化工具。

生产 Service 不再建表；仅测试在创建临时 SQLite engine 后显式调用本函数，确保
测试 fixture 拥有完整当前 schema。
"""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine as _create_engine

import agent_service.models  # noqa: F401


def initialize_test_database(engine: Engine) -> None:
    """仅在测试临时 engine 上创建完整 SQLModel schema。"""

    SQLModel.metadata.create_all(engine)


def create_test_engine(*args, **kwargs) -> Engine:
    """创建 SQLModel 测试 engine 并立即初始化完整测试 schema。"""

    engine = _create_engine(*args, **kwargs)
    initialize_test_database(engine)
    return engine

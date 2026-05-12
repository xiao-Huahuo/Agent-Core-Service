"""
PostgreSQL 数据库初始化脚本。

功能说明:
本文件集中处理 AgentService 的数据库初始化逻辑。它负责在目标数据库不存在时
先连接 PostgreSQL 管理库创建数据库,再连接目标数据库创建 SQLModel 表结构。
当向量库使用 PostgreSQL 时,本模块还会自动创建 `vector` 扩展,确保 pgvector
相关表结构可以正式启用。业务服务和 `main.py` 不应该直接编写建库逻辑,只调用
本模块提供的函数。

使用说明:
代码调用:

config = AgentConfig.load_config()
initialize_database(config=config)

命令行调用:
python -m agent_service.scripts.db_init
"""

from __future__ import annotations

import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlmodel import SQLModel

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig


def initialize_database(*, config: AgentConfig) -> None:
    """
    初始化 AgentService 关系数据库。

    config: 全局配置对象,使用其中的 `storage.relational_dsn` 和 `storage.vector_dsn`
    确保关系库与向量库所在数据库均存在。
    """

    ensure_database_exists(target_dsn=config.storage.relational_dsn)
    ensure_database_exists(target_dsn=config.storage.vector_dsn)
    engine = create_engine(config.storage.relational_dsn, pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)
    ensure_vector_extension(target_dsn=config.storage.vector_dsn)


def ensure_database_exists(*, target_dsn: str) -> None:
    """
    确保 PostgreSQL 目标数据库存在。

    target_dsn: 指向业务数据库的 SQLAlchemy DSN。
    """

    target_url = make_url(target_dsn)
    if not target_url.drivername.startswith("postgresql"):
        return
    database_name = target_url.database
    if not database_name:
        raise ValueError("PostgreSQL DSN 必须包含目标数据库名称。")
    _validate_database_name(database_name)
    admin_engine = create_engine(build_admin_dsn(target_dsn=target_dsn), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
            {"database_name": database_name},
        ).scalar()
        if exists:
            return
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))


def build_admin_dsn(*, target_dsn: str, admin_database: str = "postgres") -> str:
    """
    从业务数据库 DSN 派生 PostgreSQL 管理库 DSN。

    target_dsn: 指向业务数据库的 SQLAlchemy DSN。
    admin_database: 用于执行建库语句的管理库名称。
    """

    target_url = make_url(target_dsn)
    admin_url: URL = target_url.set(database=admin_database)
    return admin_url.render_as_string(hide_password=False)


def ensure_vector_extension(*, target_dsn: str) -> None:
    """
    确保 PostgreSQL 数据库已启用 pgvector 扩展。

    target_dsn: 指向需要启用 vector 扩展的数据库 DSN。
    """

    target_url = make_url(target_dsn)
    if not target_url.drivername.startswith("postgresql"):
        return
    engine = create_engine(target_dsn, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _validate_database_name(database_name: str) -> None:
    """
    校验数据库名,避免在 CREATE DATABASE 语句中拼接不安全标识符。

    database_name: 需要创建或检查的数据库名。
    """

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_name):
        raise ValueError(f"数据库名称不合法: {database_name}")


if __name__ == "__main__":
    initialize_database(config=AgentConfig.load_config(ensure_models=False))

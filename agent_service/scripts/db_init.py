"""
SQLite 数据库初始化脚本。

功能说明:
本文件集中处理 AgentService 的数据库初始化逻辑。SQLite 会自动创建数据库文件,
因此建库逻辑为 no-op。本模块只负责创建 SQLModel 表结构,ChromaDB 集合初始化由
LongTermMemoryService 在首次写入时自动完成。

使用说明:
代码调用:

config = AgentConfig.load_config()
initialize_database(config=config)

命令行调用:
python -m agent_service.scripts.db_init
"""

from __future__ import annotations

from sqlmodel import SQLModel, create_engine

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig


def initialize_database(*, config: AgentConfig) -> None:
    """
    初始化 AgentService 关系数据库和 ChromaDB 向量集合。

    config: 全局配置对象,使用其中的 storage.sqlite_path 创建 SQLite 引擎,
    并使用 storage.chroma_persist_dir 初始化 ChromaDB 集合。
    """

    engine = create_engine(f"sqlite:///{config.storage.sqlite_path}", pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)

    from agent_service.services.memory.longterm_memory_service import LongTermMemoryService

    memory_service = LongTermMemoryService(config=config, create_tables=False)
    memory_service._ensure_chroma_collection(vector_dimension=512)


if __name__ == "__main__":
    initialize_database(config=AgentConfig.load_config(ensure_models=False))

"""AgentService 关系数据库基础设施。

本包提供唯一 engine/session factory 和 Alembic 迁移入口。业务 Service 只接收已经
创建的 engine 或 session factory，不在自身构造函数中修改 schema。
"""

from agent_service.core.db.engine import create_database_engine, create_session_factory, get_database_engine
from agent_service.core.db.migration import upgrade_database

__all__ = ["create_database_engine", "create_session_factory", "get_database_engine", "upgrade_database"]

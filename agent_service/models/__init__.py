"""
数据库模型导出模块。

功能说明:
本文件集中导出数据库模型,方便业务层和初始化脚本统一导入。初始化数据库前
导入本模块可以确保 SQLModel metadata 已注册全部表模型。
pgvector 的向量列由 `LongTermMemoryService.ensure_pgvector_storage()` 通过 SQL
动态创建,不直接声明在 SQLModel 中。
"""

from agent_service.models.longterm_memory_spec import LongTermMemorySpec, LongTermMemorySpecBase
from agent_service.models.message import MessageBase, MessageRecord
from agent_service.models.session import SessionBase, SessionRecord

__all__ = [
    "LongTermMemorySpec",
    "LongTermMemorySpecBase",
    "MessageBase",
    "MessageRecord",
    "SessionBase",
    "SessionRecord",
]

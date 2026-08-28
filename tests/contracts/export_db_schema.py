"""从 SQLModel metadata 导出数据库结构契约快照。

用法：在项目根目录执行 ``python -m tests.contracts.export_db_schema``。
该脚本不会连接或修改用户数据库，只读取模型注册后的 metadata。
"""

from __future__ import annotations

from typing import Any

from sqlmodel import SQLModel

import agent_service.models  # noqa: F401
from tests.contracts.common import write_snapshot


def _column_payload(column: Any) -> dict[str, Any]:
    """将 SQLAlchemy Column 转换成可比较的基础字段结构。"""

    default = None
    if column.default is not None:
        default = str(column.default.arg)
    server_default = None
    if column.server_default is not None:
        server_default = str(column.server_default.arg)
    return {
        "name": column.name,
        "type": str(column.type),
        "nullable": column.nullable,
        "primary_key": column.primary_key,
        "unique": column.unique,
        "index": column.index,
        "default": default,
        "server_default": server_default,
        "foreign_keys": sorted(str(key.target_fullname) for key in column.foreign_keys),
    }


def _table_payload(table: Any) -> dict[str, Any]:
    """将 SQLAlchemy Table 转换成稳定的列、索引和约束结构。"""

    return {
        "name": table.name,
        "columns": [_column_payload(column) for column in table.columns],
        "indexes": [
            {
                "name": index.name,
                "unique": index.unique,
                "columns": [column.name for column in index.columns],
            }
            for index in sorted(table.indexes, key=lambda value: value.name or "")
        ],
        "constraints": sorted(str(constraint) for constraint in table.constraints),
    }


def main() -> int:
    """导出全部已注册 SQLModel 表结构。"""

    payload = [_table_payload(SQLModel.metadata.tables[name]) for name in sorted(SQLModel.metadata.tables)]
    write_snapshot("db_schema.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

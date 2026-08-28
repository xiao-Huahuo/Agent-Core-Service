"""导出规范化 FastAPI OpenAPI 契约快照。

用法：在项目根目录执行 ``python -m tests.contracts.export_openapi``。
脚本只构造应用定义并调用 ``app.openapi()``，不会进入 lifespan 或启动端口。
"""

from __future__ import annotations

from tests.contracts.common import write_snapshot


def main() -> int:
    """导出当前 FastAPI OpenAPI 文档。"""

    from main import app

    write_snapshot("openapi.json", app.openapi())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

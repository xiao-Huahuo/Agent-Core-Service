"""DSH Windows Runtime 受管资源服务公开入口。

业务层和 REST 路由只从本模块导入 ``DshRuntimePackageManager``，下载、校验和
版本目录细节由 ``service`` 模块独占。
"""

from agent_service.services.dsh_runtime.service import DshRuntimePackageManager

__all__ = ["DshRuntimePackageManager"]

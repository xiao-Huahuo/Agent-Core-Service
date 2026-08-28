"""AgentService 启动装配组件。

本包将配置、业务服务、模型和 gRPC 的创建逻辑从根入口拆开，供 lifespan 按固定
顺序调用。外部通常只使用 ``create_application_services`` 和 ``GrpcRuntime``。
"""

from agent_service.core.bootstrap.grpc_bootstrap import GrpcRuntime
from agent_service.core.bootstrap.services_bootstrap import ApplicationServices, create_application_services

__all__ = ["ApplicationServices", "GrpcRuntime", "create_application_services"]

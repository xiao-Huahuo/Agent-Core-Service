"""
AgentService gRPC 接口层。

本包提供 AgentCore 和 SessionService 的 gRPC 对外接口:
- agent_service.proto: 服务定义。
- agent_service_pb2.py / agent_service_pb2_grpc.py: 自动生成的消息和基类。
- servicer.py: Servicer 实现。
"""

from agent_service.api.grpc.servicer import AgentServiceServicer

__all__ = ["AgentServiceServicer"]

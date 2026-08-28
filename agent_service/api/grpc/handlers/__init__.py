"""按业务领域拆分的 gRPC RPC handlers。

每个 handler 以 mixin 形式复用同一个 AgentServiceServicer 依赖和转换助手，handler
之间不互相调用。
"""

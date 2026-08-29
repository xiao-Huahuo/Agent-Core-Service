"""四库联合搜索领域服务导出。

使用说明：应用装配层从本模块导入 ``UnifiedSearchService``，REST 与 gRPC
只负责参数转换和错误映射。
"""

from agent_service.services.unified_search.service import UnifiedSearchService

__all__ = ["UnifiedSearchService"]

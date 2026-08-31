"""知识图谱领域服务包。

当前阶段从 ``service`` 重导出原公开符号，调用方可以统一从本领域包导入；repository、
抽取、重建、去重和查询职责将在同包模块中继续拆分。
"""

from agent_service.services.knowledge_graph.service import *  # noqa: F403
from agent_service.services.knowledge_graph.queue import KnowledgeGraphQueueService
from agent_service.services.knowledge_graph.service import (
    _batch_graph_sections,
    _build_llm_config,
    _extract_graph_section_payloads,
    _graph_progress_doc_entry,
    _run_graph_extraction,
    _set_dedup_progress,
    _update_graph_progress,
)

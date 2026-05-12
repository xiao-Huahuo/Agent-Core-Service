"""
知识库结构化文档灌库脚本。
功能说明:
本脚本不再直接读取原始 Markdown/TXT,而是先调用 `frontmatter_bootstrap` 将原始知识源结构化到
`AgentConfig.storage.frontmatter_dir`,再从这些 JSON 执行切块、Embedding 和长期记忆入库。
使用说明:
python -m agent_service.scripts.knowledge_bootstrap

前置条件:
1. PostgreSQL 业务库可连接。
2. PostgreSQL 已安装 pgvector 扩展或当前用户具备 `CREATE EXTENSION vector` 权限。
3. 已安装 `sentence-transformers`,且本地 Embedding 模型目录存在。
"""

from __future__ import annotations

from agent_service.core.agent_config import AgentConfig
from agent_service.scripts.db_init import initialize_database
from agent_service.scripts.frontmatter_bootstrap import bootstrap_frontmatter
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService


def bootstrap_knowledge(*, config: AgentConfig) -> dict[str, int]:
    """
    执行知识库结构化预处理与灌库并返回统计结果。
    config: 全局配置对象。
    """

    initialize_database(config=config)
    frontmatter_result = bootstrap_frontmatter(config=config)
    ingestion_result = KnowledgeIngestionService(config=config).ingest_frontmatter_dir()
    return {
        "frontmatter_files_seen": frontmatter_result["files_seen"],
        "frontmatter_files_written": frontmatter_result["files_written"],
        "frontmatter_files_skipped": frontmatter_result["files_skipped"],
        "files_seen": ingestion_result.files_seen,
        "files_ingested": ingestion_result.files_ingested,
        "files_skipped": ingestion_result.files_skipped,
        "chunks_created": ingestion_result.chunks_created,
    }


if __name__ == "__main__":
    stats = bootstrap_knowledge(config=AgentConfig.load_config())
    print(stats)

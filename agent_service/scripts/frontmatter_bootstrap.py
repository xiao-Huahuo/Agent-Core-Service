"""
知识源结构化预处理脚本。
功能说明:
本脚本负责先扫描 `AgentConfig.storage.knowledge_dir` 中的原始知识文件,将 Markdown/TXT
等内容解析为统一的结构化知识 JSON,输出到 `AgentConfig.storage.frontmatter_dir`。它是
`knowledge_bootstrap` 的前置步骤,不负责切块、Embedding 或入库。
使用说明:
python -m agent_service.scripts.frontmatter_bootstrap
"""

from __future__ import annotations

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService


def bootstrap_frontmatter(*, config: AgentConfig) -> dict[str, int]:
    """
    执行知识源结构化预处理并返回统计结果。
    config: 全局配置对象。
    """

    result = FrontmatterBootstrapService(config=config).build_frontmatter_dir()
    return {
        "files_seen": result.files_seen,
        "files_written": result.files_written,
        "files_skipped": result.files_skipped,
    }


if __name__ == "__main__":
    stats = bootstrap_frontmatter(config=AgentConfig.load_config(ensure_models=False))
    print(stats)

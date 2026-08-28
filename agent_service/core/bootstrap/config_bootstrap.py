"""加载 AgentService 启动配置并准备基础日志。

使用 ``load_startup_config()`` 获取与原 ``main.py`` 启动流程一致的 AgentConfig；
函数保留首次创建 UTF-8 ``.env`` 模板的既有行为。
"""

from __future__ import annotations

import logging

from agent_service.core.agent_config import AgentConfig
from agent_service.services.logging.service import setup_logging

logger = logging.getLogger(__name__)


def load_startup_config() -> AgentConfig:
    """加载启动配置、初始化日志并确保首次启动的环境模板存在。"""

    config = AgentConfig.load_config(ensure_models=False)
    setup_logging(config)
    env_path = config.storage.project_root / ".env"
    if not env_path.exists():
        env_path.write_text(
            "# AgentService 环境配置\n"
            "# AGENT_MODEL_API_KEY=sk-xxxxxxxx\n"
            "# AGENT_SMALL_MODEL_API_KEY=sk-yyyyyyyy\n",
            encoding="utf-8",
        )
        logger.info(".env 模板已创建 | path=%s", env_path)
    logger.info("AgentService 启动中...")
    logger.info("配置加载完成 | app=%s model=%s", config.constants.app_name, config.model.model_name)
    return config

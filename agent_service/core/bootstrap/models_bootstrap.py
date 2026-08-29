"""创建模型服务，并提供启动完成后可调用的模型加载辅助入口。

应用装配阶段只创建轻量服务对象，不验证、下载或加载任何模型。
"""

from __future__ import annotations

import logging
from typing import Any

from agent_service.core.agent_config import AgentConfig
from agent_service.services.local_qwen.service import get_local_qwen_service
from agent_service.services.model_management.service import ModelManagementService
from agent_service.services.settings.service import SettingsService

logger = logging.getLogger(__name__)


def create_model_services(
    *,
    config: AgentConfig,
    settings_service: SettingsService,
) -> tuple[ModelManagementService, Any]:
    """创建模型管理和本地 Qwen 服务，不在启动装配阶段触碰模型文件。"""

    model_management_service = ModelManagementService(config=config, settings_service=settings_service)
    local_qwen_service = get_local_qwen_service(config)
    return model_management_service, local_qwen_service


def autoload_available_embedding_models(config: AgentConfig) -> None:
    """检测已下载的 Embedding/ReRank 模型并触发原有后台加载入口。"""

    try:
        from agent_service.api.rest.settings import _trigger_embedding_load, _trigger_rerank_load
        from agent_service.core.model_status import ModelState, set_model_state
        from agent_service.scripts.download_model import is_model_available, model_target_dir

        model_loaders = [
            ("embedding", config.model.embedding_model_name, config.storage.embedding_model_dir, _trigger_embedding_load),
            ("rerank", config.model.rerank_model_name, config.storage.rerank_model_dir, _trigger_rerank_load),
        ]
        for model_key, model_name, model_dir, trigger_fn in model_loaders:
            if not model_name or not str(model_dir):
                continue
            target = model_target_dir(model_name, model_dir)
            if is_model_available(target):
                set_model_state(model_key, ModelState.DOWNLOADED)
                logger.info("已检测到 %s 模型文件，触发后台加载", model_key)
                trigger_fn(config)
    except Exception:
        logger.exception("模型自动加载失败，服务继续运行")

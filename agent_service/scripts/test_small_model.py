"""
小模型配置联通性测试脚本。

功能说明:
本文件用于验证 `.env` 或环境变量中的 `AGENT_SMALL_MODEL_*` 配置是否可用。
脚本会读取 `AgentConfig` 中的小模型配置,构建一个最小 `ChatOpenAI` 客户端,
并发送一轮极短的测试请求。如果调用成功,会打印模型名与响应文本,便于快速确认
后续将 `MemoryResolver`、语义分类等任务切到小模型时基础链路已经打通。

使用说明:
在项目根目录执行:
python -m agent_service.scripts.test_small_model
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent_service.core.agent_config import AgentConfig


def main() -> None:
    """
    读取小模型配置并执行一次最小联通性测试。
    """

    config = AgentConfig.load_config(ensure_models=False)
    model_config = config.model
    if not model_config.small_model_name:
        raise ValueError("缺少 AGENT_SMALL_MODEL_NAME,无法测试小模型配置。")
    if not model_config.small_model_api_key:
        raise ValueError("缺少 AGENT_SMALL_MODEL_API_KEY,无法测试小模型配置。")
    if not model_config.small_model_base_url:
        raise ValueError("缺少 AGENT_SMALL_MODEL_BASE_URL,无法测试小模型配置。")

    client = ChatOpenAI(
        model=model_config.small_model_name,
        api_key=model_config.small_model_api_key,
        base_url=model_config.small_model_base_url,
        temperature=model_config.resolve_small_temperature(),
        timeout=model_config.small_model_timeout_seconds,
    )
    response = client.invoke(
        [
            SystemMessage(
                content=(
                    "你是一个用于配置联通性测试的小模型。"
                    "请仅返回一行极短文本,格式固定为: SMALL_MODEL_OK:<模型职责判断>。"
                )
            ),
            HumanMessage(content="请确认你已收到这条测试消息,并判断自己适合做轻量分类任务。"),
        ]
    )
    print(f"small_model_name={model_config.small_model_name}")
    print(f"small_model_base_url={model_config.small_model_base_url}")
    print(f"response={str(response.content).strip()}")


if __name__ == "__main__":
    main()

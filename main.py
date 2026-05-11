"""
AgentService 本地真实 LLM 调用入口。

功能说明:
本文件提供 FastAPI 应用入口和本地脚本入口,用于调用真正的 `AgentCore` 图。
它不会注入测试假图,而是使用 `AgentConfig.load_config()` 从环境变量读取模型配置,
然后创建 `AgentCore(config=config)` 走真实的 `ModelDecisionNode -> ChatOpenAI`
决策路径。

使用说明:
运行前需要在环境变量中配置主模型:
AGENT_MODEL_NAME: 主模型名称。
AGENT_MODEL_API_KEY: 主模型 API Key。
AGENT_MODEL_BASE_URL: OpenAI Compatible API 地址。

命令行测试:
python main.py

接口测试:
启动 FastAPI 后访问 `/agent/test?prompt=你好`。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Query

from agent_service.agent_core import AgentCore
from agent_service.core.agent_config import AgentConfig


app = FastAPI(title="Agent-Core-Service")


def build_real_agent() -> AgentCore:
    """
    创建真实 AgentCore 实例。

    本函数不传入测试图对象,因此会通过 `AgentGraphBuilder` 构建真实图,
    并在 `agent` 节点中调用真正的 LLM 决策节点。
    """

    config = AgentConfig.load_config(ensure_models=False)
    return AgentCore(config=config)


def run_real_agent_once(prompt: str) -> dict[str, Any]:
    """运行一次真实 AgentCore 调用;业务整理逻辑由 AgentCore.run_once() 负责。"""

    return build_real_agent().run_once(prompt=prompt, user_id="demo-user", session_id="demo-session")


@app.get("/")
async def root() -> dict[str, str]:
    """服务健康检查接口。"""

    return {"message": "Agent-Core-Service is running"}


@app.get("/agent/test")
async def agent_test(prompt: str = Query(default="你好,请用一句话回复。")) -> dict[str, Any]:
    """
    运行一次真实 LLM AgentCore 测试调用。

    prompt: 用户输入,会真实发送给配置好的 LLM。
    """

    return run_real_agent_once(prompt)


if __name__ == "__main__":
    result = run_real_agent_once("写一个完全支持linux的操作系统,没写完不准停")
    print("AgentCore raw JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("AgentCore observable process:")
    for process_line in AgentCore.build_human_readable_process(result["events"]):
        print(process_line)
    print("AgentCore final output:")
    print(result["final_output"])

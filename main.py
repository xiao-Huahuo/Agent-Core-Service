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
from agent_service.schemas.session import SessionCreate
from agent_service.scripts.db_init import initialize_database
from agent_service.services.session_service import SessionService


app = FastAPI(title="Agent-Core-Service")


def build_real_agent() -> AgentCore:
    """
    创建真实 AgentCore 实例。

    本函数不传入测试图对象,因此会通过 `AgentGraphBuilder` 构建真实图,
    并在 `agent` 节点中调用真正的 LLM 决策节点。
    """

    config = AgentConfig.load_config(ensure_models=False)
    return AgentCore(config=config)


def build_real_config() -> AgentConfig:
    """创建真实运行配置,供本地演示同时传给 AgentCore 和业务服务。"""

    return AgentConfig.load_config(ensure_models=False)


def run_real_agent_once(prompt: str) -> dict[str, Any]:
    """运行一次真实 AgentCore 调用;业务整理逻辑由 AgentCore.run_once() 负责。"""

    return build_real_agent().run_once(prompt=prompt, user_id="demo-user", session_id="demo-session")


def run_session_dialog_demo() -> dict[str, Any]:
    """
    运行两个 session 的连续对话演示。

    第一个 session 连续发送 2 个前后关联 prompt。
    第二个 session 连续发送 5 个前后关联 prompt。
    """

    config = build_real_config()
    initialize_database(config=config)
    agent = AgentCore(config=config)
    session_service = SessionService(config=config)
    user_id = "demo-user"
    first_session = session_service.create_session(
        SessionCreate(user_id=user_id, session_name="两轮上下文演示")
    )
    second_session = session_service.create_session(
        SessionCreate(user_id=user_id, session_name="五轮上下文演示")
    )
    dialogs = [
        {
            "session": first_session,
            "prompts": [
                "请记住: 我正在测试第一个 session,关键词是 blue-river。只用一句话确认。",
                "我刚刚让你记住的关键词是什么?只回答关键词。",
            ],
        },
        {
            "session": second_session,
            "prompts": [
                "这是第二个 session。请记住项目代号是 stone-cat。只用一句话确认。",
                "请记住负责模块是 ContextBuilder。只用一句话确认。",
                "请记住当前目标是验证滑动窗口上下文。只用一句话确认。",
                "请把项目代号和负责模块一起说出来。",
                "请总结这个 session 到目前为止的目标。",
            ],
        },
    ]
    results: list[dict[str, Any]] = []
    for dialog in dialogs:
        session_results = []
        for prompt in dialog["prompts"]:
            session_results.append(
                {
                    "prompt": prompt,
                    "result": agent.run_session_prompt(
                        prompt=prompt,
                        user_id=user_id,
                        session_id=dialog["session"].session_id,
                    ),
                }
            )
        results.append(
            {
                "session": dialog["session"].model_dump(),
                "turns": session_results,
            }
        )
    return {"user_id": user_id, "dialogs": results}


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
    demo_result = run_session_dialog_demo()
    print("AgentCore session demo raw JSON:")
    print(json.dumps(demo_result, ensure_ascii=False, indent=2, default=str))
    print("AgentCore session demo readable output:")
    for dialog in demo_result["dialogs"]:
        print(f"Session: {dialog['session']['session_id']} - {dialog['session']['session_name']}")
        for index, turn in enumerate(dialog["turns"], start=1):
            print(f"Turn {index} prompt: {turn['prompt']}")
            for process_line in AgentCore.build_human_readable_process(turn["result"]["events"]):
                print(process_line)
            print(f"Turn {index} final output: {turn['result']['final_output']}")

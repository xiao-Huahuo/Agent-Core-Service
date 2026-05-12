"""
AgentService 本地真实 LLM 调用入口。
功能说明:
本文件提供 FastAPI 应用入口和本地脚本入口,用于调用真正的 `AgentCore` 图。默认演示为
“同一用户跨四个 session 的高强度记忆时效性测试”: 连续三次更新同一个长期事实,最后在第四个
session 中同时查询“当前值、旧值是否失效、外部知识库问题”,用于验证多轮覆盖、跨 session 召回、
知识库召回与上下文优先级是否稳定。
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
from uuid import uuid4

from fastapi import FastAPI, Query
from langchain_core.messages import SystemMessage

from agent_service.agent_core import AgentCore
from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.session import SessionCreate
from agent_service.scripts.db_init import initialize_database
from agent_service.scripts.knowledge_bootstrap import bootstrap_knowledge
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.memory.summary_service import SessionSummaryService
from agent_service.services.message_service import MessageService
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
    """运行一次真实 AgentCore 调用;业务整理逻辑由 `AgentCore.run_once()` 负责。"""

    return build_real_agent().run_once(prompt=prompt, user_id="demo-user", session_id="demo-session")


def run_session_dialog_demo() -> dict[str, Any]:
    """
    运行跨四个 session 的高强度长期记忆时效性演示。
    前三轮分别写入三个连续更新后的代号,第四轮在全新 session 中同时查询当前值、旧值有效性
    与知识库问题,用于验证 MemoryResolver 的覆盖链和 RAG 混合召回链路。
    """

    config = build_real_config()
    initialize_database(config=config)
    knowledge_stats = bootstrap_knowledge(config=config)
    agent = AgentCore(config=config)
    session_service = SessionService(config=config)
    message_service = MessageService(config=config)
    context_builder = ContextBuilder(config=config, message_service=message_service)
    summary_service = SessionSummaryService(config=config, message_service=message_service)
    user_id = f"demo-user-{uuid4().hex[:8]}"

    session_one = session_service.create_session(
        SessionCreate(user_id=user_id, session_name="高强度时效性演示-初始代号")
    )
    session_two = session_service.create_session(
        SessionCreate(user_id=user_id, session_name="高强度时效性演示-第二次代号")
    )
    session_three = session_service.create_session(
        SessionCreate(user_id=user_id, session_name="高强度时效性演示-第三次代号")
    )
    session_four = session_service.create_session(
        SessionCreate(user_id=user_id, session_name="高强度时效性演示-最终综合查询")
    )

    dialogs: list[dict[str, Any]] = []

    first_prompt = "请记住这个长期事实: 当前项目代号是1111111。只用一句话确认。"
    first_result = _run_demo_turn(
        agent=agent,
        prompt=first_prompt,
        user_id=user_id,
        session_id=session_one.session_id,
    )
    first_summary = summary_service.summarize_session(user_id=user_id, session_id=session_one.session_id)
    dialogs.append(
        {
            "session": session_one.model_dump(),
            "turns": [
                {
                    "prompt": first_prompt,
                    "retrieved_context_preview": "",
                    "forced_summary": first_summary,
                    "result": first_result,
                }
            ],
        }
    )

    second_prompt = "请记住这个长期事实已经更新: 当前项目代号已经从1111111改成2222222。只用一句话确认。"
    second_result = _run_demo_turn(
        agent=agent,
        prompt=second_prompt,
        user_id=user_id,
        session_id=session_two.session_id,
    )
    second_summary = summary_service.summarize_session(user_id=user_id, session_id=session_two.session_id)
    dialogs.append(
        {
            "session": session_two.model_dump(),
            "turns": [
                {
                    "prompt": second_prompt,
                    "retrieved_context_preview": "",
                    "forced_summary": second_summary,
                    "result": second_result,
                }
            ],
        }
    )

    third_prompt = "请记住这个长期事实再次更新: 当前项目代号已经从2222222改成3333333。只用一句话确认。"
    third_result = _run_demo_turn(
        agent=agent,
        prompt=third_prompt,
        user_id=user_id,
        session_id=session_three.session_id,
    )
    third_summary = summary_service.summarize_session(user_id=user_id, session_id=session_three.session_id)
    dialogs.append(
        {
            "session": session_three.model_dump(),
            "turns": [
                {
                    "prompt": third_prompt,
                    "retrieved_context_preview": "",
                    "forced_summary": third_summary,
                    "result": third_result,
                }
            ],
        }
    )

    fourth_prompt = (
        "不要调用工具。请根据你召回到的长期记忆和知识库内容回答: "
        "当前项目代号是什么? 1111111 和 2222222 现在还算当前值吗? "
        "另外城市有什么内容?"
    )
    preview_messages = context_builder.build_messages(
        user_id=user_id,
        session_id=session_four.session_id,
        current_prompt=fourth_prompt,
    )
    retrieved_context_preview = ""
    if preview_messages and isinstance(preview_messages[0], SystemMessage):
        retrieved_context_preview = preview_messages[0].content
    fourth_result = _run_demo_turn(
        agent=agent,
        prompt=fourth_prompt,
        user_id=user_id,
        session_id=session_four.session_id,
    )
    dialogs.append(
        {
            "session": session_four.model_dump(),
            "turns": [
                {
                    "prompt": fourth_prompt,
                    "retrieved_context_preview": retrieved_context_preview,
                    "forced_summary": None,
                    "result": fourth_result,
                }
            ],
        }
    )

    return {
        "user_id": user_id,
        "knowledge_bootstrap": knowledge_stats,
        "dialogs": dialogs,
    }


def _run_demo_turn(*, agent: AgentCore, prompt: str, user_id: str, session_id: str) -> dict[str, Any]:
    """
    执行一轮 main 演示调用并在异常时返回稳定结果。
    agent: 真实 AgentCore 实例。
    prompt: 当前用户输入。
    user_id: 用户 ID。
    session_id: 会话 ID。
    """

    try:
        return agent.run_session_prompt(
            prompt=prompt,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "graph_diagram_path": str(agent.graph_diagram_path),
            "graph_diagram": agent.graph_diagram_path.read_text(encoding="utf-8"),
            "final_output": "",
            "events": [
                {
                    "node": "agent",
                    "content": "",
                    "tool_calls": [],
                    "trace": [
                        {
                            "node": "agent",
                            "event": "model_error",
                            "error_type": exc.__class__.__name__,
                            "message": str(exc),
                        }
                    ],
                }
            ],
            "chunks": [],
        }


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
    from agent_service.task_schedule import reset_llm_task_schedulers

    try:
        demo_result = run_session_dialog_demo()
        print("AgentCore session demo raw JSON:")
        print(json.dumps(demo_result, ensure_ascii=False, indent=2, default=str))
        print("AgentCore graph Mermaid:")
        first_dialog = demo_result["dialogs"][0]
        first_turn = first_dialog["turns"][0]
        print(first_turn["result"]["graph_diagram"])
        print("AgentCore session demo readable output:")
        print("Knowledge bootstrap:")
        print(json.dumps(demo_result["knowledge_bootstrap"], ensure_ascii=False, indent=2, default=str))
        for dialog in demo_result["dialogs"]:
            print(f"Session: {dialog['session']['session_id']} - {dialog['session']['session_name']}")
            for index, turn in enumerate(dialog["turns"], start=1):
                print(f"Turn {index} prompt: {turn['prompt']}")
                if turn["retrieved_context_preview"]:
                    print("Retrieved context preview:")
                    print(turn["retrieved_context_preview"])
                if turn["forced_summary"]:
                    print(f"Forced summary: {turn['forced_summary']}")
                for process_line in AgentCore.build_human_readable_process(turn["result"]["events"]):
                    print(process_line)
                print(f"Turn {index} final output: {turn['result']['final_output']}")
    finally:
        reset_llm_task_schedulers()

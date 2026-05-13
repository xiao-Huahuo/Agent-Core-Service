"""
AgentService 本地演示脚本。

提供两种演示模式:
    python scripts/run_demo.py           # 跨 session 记忆时效性演示
    python scripts/run_demo.py --stream  # 流式推送演示

运行前需配置环境变量:
    AGENT_MODEL_NAME / AGENT_MODEL_API_KEY / AGENT_MODEL_BASE_URL
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

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
from agent_service.task_schedule import reset_llm_task_schedulers


def _build_config() -> AgentConfig:
    return AgentConfig.load_config(ensure_models=False)


def run_session_dialog_demo() -> dict[str, Any]:
    """
    跨四个 session 的高强度长期记忆时效性演示。
    前三轮分别写入三个连续更新后的项目代号,第四轮在全新 session 中同时查询
    当前值、旧值有效性与知识库问题。
    """

    config = _build_config()
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
    first_result = _run_demo_turn(agent=agent, prompt=first_prompt, user_id=user_id, session_id=session_one.session_id)
    first_summary = summary_service.summarize_session(user_id=user_id, session_id=session_one.session_id)
    dialogs.append({
        "session": session_one.model_dump(),
        "turns": [{"prompt": first_prompt, "retrieved_context_preview": "", "forced_summary": first_summary, "result": first_result}],
    })

    second_prompt = "请记住这个长期事实已经更新: 当前项目代号已经从1111111改成2222222。只用一句话确认。"
    second_result = _run_demo_turn(agent=agent, prompt=second_prompt, user_id=user_id, session_id=session_two.session_id)
    second_summary = summary_service.summarize_session(user_id=user_id, session_id=session_two.session_id)
    dialogs.append({
        "session": session_two.model_dump(),
        "turns": [{"prompt": second_prompt, "retrieved_context_preview": "", "forced_summary": second_summary, "result": second_result}],
    })

    third_prompt = "请记住这个长期事实再次更新: 当前项目代号已经从2222222改成3333333。只用一句话确认。"
    third_result = _run_demo_turn(agent=agent, prompt=third_prompt, user_id=user_id, session_id=session_three.session_id)
    third_summary = summary_service.summarize_session(user_id=user_id, session_id=session_three.session_id)
    dialogs.append({
        "session": session_three.model_dump(),
        "turns": [{"prompt": third_prompt, "retrieved_context_preview": "", "forced_summary": third_summary, "result": third_result}],
    })

    fourth_prompt = (
        "不要调用工具。请根据你召回到的长期记忆和知识库内容回答: "
        "当前项目代号是什么? 1111111 和 2222222 现在还算当前值吗? "
        "另外城市有什么内容?"
    )
    preview_messages = context_builder.build_messages(
        user_id=user_id, session_id=session_four.session_id, current_prompt=fourth_prompt,
    )
    retrieved_context_preview = ""
    if preview_messages and isinstance(preview_messages[0], SystemMessage):
        retrieved_context_preview = preview_messages[0].content
    fourth_result = _run_demo_turn(agent=agent, prompt=fourth_prompt, user_id=user_id, session_id=session_four.session_id)
    dialogs.append({
        "session": session_four.model_dump(),
        "turns": [{"prompt": fourth_prompt, "retrieved_context_preview": retrieved_context_preview, "forced_summary": None, "result": fourth_result}],
    })

    return {"user_id": user_id, "knowledge_bootstrap": knowledge_stats, "dialogs": dialogs}


def _run_demo_turn(*, agent: AgentCore, prompt: str, user_id: str, session_id: str) -> dict[str, Any]:
    try:
        return agent.run_session_prompt(prompt=prompt, user_id=user_id, session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        return {
            "graph_diagram_path": str(agent.graph_diagram_path),
            "graph_diagram": agent.graph_diagram_path.read_text(encoding="utf-8"),
            "final_output": "",
            "events": [{
                "node": "agent", "content": "", "tool_calls": [],
                "trace": [{"node": "agent", "event": "model_error", "error_type": exc.__class__.__name__, "message": str(exc)}],
            }],
            "chunks": [],
        }


def run_stream_session_demo() -> None:
    """流式 session prompt 演示: 每个节点完成后立即打印,展示实时推送效果。"""

    config = _build_config()
    initialize_database(config=config)
    bootstrap_knowledge(config=config)
    agent = AgentCore(config=config)
    session_service = SessionService(config=config)
    session = session_service.create_session(SessionCreate(user_id="stream-demo-user", session_name="流式推送演示"))

    prompt = "你好,请用三句话简单介绍一下你自己,然后调用 echo_text 工具输出'流式测试完成'。"

    print("=" * 60)
    print(f"Session: {session.session_id}")
    print(f"Prompt: {prompt}")
    print("=" * 60)
    print()

    chunk_index = 0
    for chunk in agent.stream_session_prompt(prompt=prompt, user_id="stream-demo-user", session_id=session.session_id):
        chunk_index += 1
        now = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        data = chunk.removeprefix("data: ").strip()
        if data == "[DONE]":
            print(f"[{now}] [{chunk_index:02d}] [DONE]")
            continue
        try:
            payload = json.loads(data)
            node = payload.get("node", "?")
            content = payload.get("content", "")
            tool_calls = payload.get("tool_calls", [])
            trace = payload.get("trace", [])

            print(f"[{now}] [{chunk_index:02d}] node={node}", flush=True)
            if tool_calls:
                tool_names = ", ".join(tc.get("name", "?") for tc in tool_calls)
                print(f"         tool_calls -> {tool_names}", flush=True)
            if content:
                preview = content[:120].replace("\n", "\\n")
                print(f"         content   -> {preview}{'...' if len(content) > 120 else ''}", flush=True)
            if trace:
                for t in trace:
                    print(f"         trace     -> {json.dumps(t, ensure_ascii=False)}", flush=True)
        except json.JSONDecodeError:
            print(f"[{now}] [{chunk_index:02d}] raw: {chunk[:100]}", flush=True)

    agent.close()
    print()
    print("=" * 60)
    print("流式推送演示完成。")


def _print_dialog_result(demo_result: dict[str, Any]) -> None:
    """打印跨 session 演示的可读输出。"""

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


if __name__ == "__main__":
    try:
        if "--stream" in sys.argv:
            run_stream_session_demo()
        else:
            demo_result = run_session_dialog_demo()
            print("AgentCore session demo raw JSON:")
            print(json.dumps(demo_result, ensure_ascii=False, indent=2, default=str))
            first_turn = demo_result["dialogs"][0]["turns"][0]
            print("AgentCore graph Mermaid:")
            print(first_turn["result"]["graph_diagram"])
            print("AgentCore session demo readable output:")
            _print_dialog_result(demo_result)
    finally:
        reset_llm_task_schedulers()

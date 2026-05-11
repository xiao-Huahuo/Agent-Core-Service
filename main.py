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
    """
    运行一次真实 AgentCore 调用。

    prompt: 发送给 Agent 的用户输入。
    """

    agent = build_real_agent()
    chunks = list(agent.stream_run(prompt=prompt, user_id="demo-user", session_id="demo-session"))
    events = parse_stream_chunks(chunks)
    mermaid_text = agent.graph_diagram_path.read_text(encoding="utf-8")
    return {
        "graph_diagram_path": str(agent.graph_diagram_path),
        "graph_diagram": mermaid_text,
        "final_output": extract_final_output(events),
        "events": events,
        "chunks": chunks,
    }


def parse_stream_chunks(chunks: list[str]) -> list[dict[str, Any]]:
    """
    将 AgentCore 的 SSE 风格字符串解析为事件字典列表。

    chunks: `AgentCore.stream_run()` 输出的原始字符串列表。
    """

    events: list[dict[str, Any]] = []
    for chunk in chunks:
        data = chunk.removeprefix("data: ").strip()
        if not data or data == "[DONE]":
            continue
        events.append(json.loads(data))
    return events


def extract_final_output(events: list[dict[str, Any]]) -> str:
    """
    从事件列表中提取最终智能体回复。

    events: 由 `parse_stream_chunks()` 解析出的事件列表。
    """

    final_output = ""
    for event in events:
        is_agent_message = event.get("node") == "agent"
        has_tool_calls = bool(event.get("tool_calls"))
        content = event.get("content", "")
        if is_agent_message and content and not has_tool_calls:
            final_output = content
    return final_output


def build_human_readable_process(events: list[dict[str, Any]]) -> list[str]:
    """
    构建给人阅读的可观测执行过程。

    events: 由 `parse_stream_chunks()` 解析出的事件列表。
    """

    process_lines: list[str] = []
    for index, event in enumerate(events, start=1):
        node_name = event.get("node", "")
        content = event.get("content", "")
        tool_calls = event.get("tool_calls", [])
        if node_name == "agent" and tool_calls:
            tool_names = ", ".join(tool_call.get("name", "") for tool_call in tool_calls)
            process_lines.append(f"{index}. 模型决定调用工具: {tool_names}")
        elif node_name == "action":
            process_lines.append(f"{index}. 工具执行完成,返回内容: {content}")
        elif node_name == "agent" and content:
            process_lines.append(f"{index}. 模型生成最终回复。")
        elif node_name == "summary":
            process_lines.append(f"{index}. 摘要节点执行: {event.get('trace', [])}")
    return process_lines


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
    result = run_real_agent_once("你好,你来分步回答3次现在的UTC时间,注意一定要分步;然后最后说一下你自己的名字.")
    print("AgentCore raw JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("AgentCore observable process:")
    for process_line in build_human_readable_process(result["events"]):
        print(process_line)
    print("AgentCore final output:")
    print(result["final_output"])

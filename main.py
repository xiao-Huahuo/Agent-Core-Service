"""
AgentService 本地演示入口。

功能说明:
本文件提供两个用途:
1. 作为 FastAPI 应用入口,暴露 `/` 和 `/agent/test` 接口。
2. 作为本地脚本入口,执行 `python main.py` 时直接运行一次 AgentCore 测试调用,
   并在终端打印 Mermaid 图路径、Mermaid 内容和流式输出结果。

使用说明:
本文件里的测试调用使用假图对象,不会请求真实大模型,适合确认 AgentCore 的初始化、
Mermaid 图生成和 SSE 风格输出包装是否正常。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from langchain_core.messages import AIMessage

from agent_service.agent_core import AgentCore
from agent_service.core.agent_config import AgentConfig


app = FastAPI(title="Agent-Core-Service")


class DemoCompiledGraph:
    """
    本地演示用假编译图。

    该图只模拟 LangGraph 编译图需要的 `stream()` 和 `get_graph()` 两个接口,
    用于演示 AgentCore 工作链路,避免本地演示时请求真实模型接口。
    """

    def __init__(self) -> None:
        """创建固定的测试节点流和固定的图结构。"""

        self.graph_data = SimpleNamespace(
            nodes={
                "__start__": object(),
                "agent": object(),
                "summary": object(),
                "__end__": object(),
            },
            edges=[
                SimpleNamespace(source="__start__", target="agent", conditional=False),
                SimpleNamespace(source="agent", target="summary", conditional=True),
                SimpleNamespace(source="summary", target="__end__", conditional=False),
            ],
        )

    def stream(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        """返回一次模拟的 Agent 节点输出。"""

        return [
            {
                "agent": {
                    "messages": [AIMessage(content="这是 AgentCore 测试回复。")],
                    "trace": [{"node": "agent", "event": "model_response"}],
                }
            },
            {
                "summary": {
                    "trace": [{"node": "summary", "event": "summary_skipped"}],
                }
            },
        ]

    def get_graph(self) -> Any:
        """返回模拟图结构,供 Mermaid 绘图脚本读取。"""

        return self.graph_data


def build_demo_agent() -> AgentCore:
    """创建本地演示用 AgentCore 实例。"""

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "demo-model",
                "api_key": "demo-key",
                "base_url": "https://example.com/v1",
            }
        },
        load_env=False,
        ensure_directories=True,
        ensure_models=False,
    )
    return AgentCore(config=config, graph=DemoCompiledGraph())


def run_agent_core_demo() -> dict[str, Any]:
    """运行一次 AgentCore 本地演示并返回结构化结果。"""

    agent = build_demo_agent()
    chunks = list(agent.stream_run(prompt="你好", user_id="demo-user", session_id="demo-session"))
    mermaid_text = agent.graph_diagram_path.read_text(encoding="utf-8")
    return {
        "graph_diagram_path": str(agent.graph_diagram_path),
        "graph_diagram": mermaid_text,
        "chunks": chunks,
    }


@app.get("/")
async def root() -> dict[str, str]:
    """服务健康检查接口。"""

    return {"message": "Agent-Core-Service is running"}


@app.get("/agent/test")
async def agent_test() -> dict[str, Any]:
    """运行一次不请求真实模型的 AgentCore 测试调用。"""

    return run_agent_core_demo()


if __name__ == "__main__":
    result = run_agent_core_demo()
    print("AgentCore demo graph:")
    print(result["graph_diagram_path"])
    print(result["graph_diagram"])
    print("AgentCore demo stream chunks:")
    for chunk in result["chunks"]:
        print(chunk, end="")

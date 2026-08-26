"""
本地 Qwen 消息解析与工具调用适配测试。

使用说明:
这些测试只验证纯文本协议，不加载真实模型权重。
"""

from pathlib import Path

from agent_service.services.local_qwen_service import (
    LocalQwenChatModel,
    LocalQwenService,
    parse_qwen_response,
    start_local_qwen_download,
)
from agent_service.services.scheduler import get_llm_task_scheduler, reset_llm_task_schedulers
from langchain_core.messages import HumanMessage
from agent_service.core.agent_config import AgentConfig
from agent_service.tools.tool_registry import ToolRegistry


def test_parse_qwen_response_extracts_tool_calls_without_leaking_markup() -> None:
    """Qwen 工具标签必须转换成 LangChain tool_calls。"""

    message = parse_qwen_response(
        '<tool_call>{"name":"understand_image","arguments":{"attachment":"a.png"}}</tool_call>'
    )

    assert message.content == ""
    assert message.tool_calls[0]["name"] == "understand_image"
    assert message.tool_calls[0]["args"] == {"attachment": "a.png"}


def test_parse_qwen_response_preserves_normal_text() -> None:
    """没有工具标签时保持普通生成文本。"""

    message = parse_qwen_response("这是本地模型的回答。")

    assert message.content == "这是本地模型的回答。"
    assert message.tool_calls == []


def test_local_qwen_serializes_text_as_multimodal_content_blocks() -> None:
    """Qwen3.5 Processor 要求纯文本消息也使用多模态内容块列表。"""

    serialized = LocalQwenService._serialize_messages([HumanMessage(content="你好")])

    assert serialized == [{
        "role": "user",
        "content": [{"type": "text", "text": "你好"}],
    }]


def test_local_qwen_runtime_dependencies_stay_cpu_compatible() -> None:
    """本地多模态模型必须声明匹配版本的 CPU Torch、Torchvision 与 Transformers。"""

    project_root = Path(__file__).resolve().parents[1]
    requirements = (project_root / "agent_service" / "requirements.txt").read_text(encoding="utf-8")
    spec = (project_root / "AgentService.spec").read_text(encoding="utf-8")

    assert "torch==2.11.0+cpu" in requirements
    assert "torchvision==0.26.0+cpu" in requirements
    assert "transformers==5.2.0" in requirements
    assert "sentence-transformers==6.0.0" in requirements
    assert "['xlrd', 'torchvision']" in spec
    assert "'torchvision'," not in spec.split("excludes=[", maxsplit=1)[1]


def test_image_understanding_tool_is_registered() -> None:
    """主 Agent 必须能够显式选择识图工具。"""

    config = AgentConfig.load_config(
        {},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    definition = ToolRegistry.with_builtin_tools(config=config).get("understand_image")

    assert definition is not None
    assert definition.display_name == "识图"


def test_scheduler_builds_local_qwen_adapter_without_remote_credentials() -> None:
    """完全未配置远程模型时，调度器必须构造本地适配器而非 ChatOpenAI。"""

    config = AgentConfig.load_config(
        {},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    scheduler = get_llm_task_scheduler(config)
    try:
        model = scheduler._get_chat_model(
            tool_names=[],
            temperature=0.0,
            timeout_seconds=3,
            model_tier="large",
        )
    finally:
        reset_llm_task_schedulers()

    assert isinstance(model, LocalQwenChatModel)


def test_local_qwen_stream_buffers_tool_markup_into_tool_call_chunk() -> None:
    """工具绑定时不得把内部标签流给用户，完成后应形成结构化 tool call。"""

    class _FakeService:
        """返回拆分后的 Qwen 工具标签。"""

        def stream_chat(self, **kwargs: object):  # noqa: ANN201, ARG002
            yield '<tool_call>{"name":"understand_image",'
            yield '"arguments":{"attachment":"a.png"}}</tool_call>'

    model = LocalQwenChatModel(
        service=_FakeService(),  # type: ignore[arg-type]
        temperature=0.0,
        tools=[object()],
    )

    chunks = list(model.stream([HumanMessage(content="看图")]))

    assert len(chunks) == 1
    assert chunks[0].content == ""
    assert chunks[0].tool_calls[0]["name"] == "understand_image"


def test_local_qwen_download_start_is_idempotent(tmp_path, monkeypatch: object) -> None:
    """重复点击或启动恢复不得创建两个并发下载线程。"""

    from threading import Event

    import agent_service.services.local_qwen_service as local_module

    config = AgentConfig.load_config(
        {"storage": {"local_model_dir": str(tmp_path / "models")}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    started = Event()
    release = Event()

    def fake_ensure_model(*args: object, **kwargs: object):  # noqa: ANN202, ARG001
        started.set()
        release.wait(timeout=2)
        return tmp_path / "models" / "Qwen__Qwen3.5-2B"

    monkeypatch.setattr(local_module, "ensure_model", fake_ensure_model)
    monkeypatch.setattr(local_module, "is_model_available", lambda path: True)

    first = start_local_qwen_download(config, load_after=False)
    assert started.wait(timeout=1)
    second = start_local_qwen_download(config, load_after=False)
    release.set()

    assert first is True
    assert second is False


def test_backend_startup_resumes_detected_local_qwen_partial(tmp_path, monkeypatch: object) -> None:
    """启动恢复入口应识别断点并委托唯一下载线程续传。"""

    import agent_service.services.local_qwen_service as local_module

    config = AgentConfig.load_config(
        {"storage": {"local_model_dir": str(tmp_path / "models")}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    calls: list[bool] = []
    monkeypatch.setattr(local_module, "is_model_available", lambda path: False)
    monkeypatch.setattr(local_module, "has_partial_model_download", lambda path: True)
    monkeypatch.setattr(local_module, "restore_partial_download_progress", lambda model_type, path: {})
    monkeypatch.setattr(
        local_module,
        "start_local_qwen_download",
        lambda config, load_after: calls.append(load_after) or True,
    )

    resumed = local_module.resume_interrupted_local_qwen_download(config)

    assert resumed is True
    assert calls == [True]

"""
CPU 本地 Qwen 多模态推理服务与 LangChain 适配器。

使用说明:
调度器在用户没有可用远程大模型时通过 `get_local_qwen_service()` 复用同一份
Qwen3.5-2B 权重；附件解析器和 `understand_image` 工具也复用该实例完成识图。
模型只在首次真实调用或管理页显式加载时下载并加载，不引入 CUDA PyTorch。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from agent_service.core.model_status import ModelState, set_model_state
from agent_service.scripts.download_model import (
    ensure_model,
    has_partial_model_download,
    is_model_available,
    model_downloaded_bytes,
    model_target_dir,
    restore_partial_download_progress,
    update_download_progress,
)

logger = logging.getLogger(__name__)

_TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)


def parse_qwen_response(text: str) -> AIMessage:
    """把 Qwen chat template 的工具标签转换为 LangChain `AIMessage`。"""

    tool_calls: list[dict[str, Any]] = []
    for raw_payload in _TOOL_CALL_PATTERN.findall(text):
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not str(payload.get("name") or "").strip():
            continue
        arguments = payload.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        tool_calls.append({
            "name": str(payload["name"]),
            "args": arguments if isinstance(arguments, dict) else {},
            "id": f"local_tool_{uuid4().hex}",
            "type": "tool_call",
        })
    content = _TOOL_CALL_PATTERN.sub("", text).strip() if tool_calls else text.strip()
    return AIMessage(content=content, tool_calls=tool_calls)


class LocalQwenService:
    """懒加载并串行执行 CPU Qwen3.5-2B 文本、工具调用与图片理解。"""

    def __init__(self, *, config: Any) -> None:
        """保存服务配置；真实权重保持未加载直到首次调用。"""

        self.config = config
        self._processor: Any | None = None
        self._model: Any | None = None
        self._load_lock = threading.Lock()
        self._generation_lock = threading.Lock()

    @property
    def model_path(self) -> Path:
        """返回内置本地模型的稳定下载目录。"""

        return model_target_dir(self.config.model.local_model_name, self.config.storage.local_model_dir)

    @property
    def loaded(self) -> bool:
        """返回模型和 processor 是否已进入当前进程。"""

        return self._model is not None and self._processor is not None

    def ensure_loaded(self) -> None:
        """按需下载并使用现有 CPU PyTorch 以 BF16 加载模型。"""

        if self.loaded:
            return
        with self._load_lock:
            if self.loaded:
                return
            try:
                set_model_state("local_qwen", ModelState.DOWNLOADING)
                target = ensure_model(
                    self.config.model.local_model_name,
                    self.config.storage.local_model_dir,
                    model_type="local_qwen",
                )
                if target is None:
                    raise RuntimeError("本地 Qwen 模型名称为空。")
                set_model_state("local_qwen", ModelState.LOADING)
                import torch
                from transformers import AutoModelForImageTextToText, AutoProcessor

                self._processor = AutoProcessor.from_pretrained(str(target))
                self._model = AutoModelForImageTextToText.from_pretrained(
                    str(target),
                    dtype=torch.bfloat16,
                    attn_implementation="sdpa",
                ).eval().to("cpu")
                set_model_state("local_qwen", ModelState.READY)
            except Exception:
                self._processor = None
                self._model = None
                set_model_state("local_qwen", ModelState.ERROR)
                logger.exception("本地 Qwen 加载失败 | model=%s", self.config.model.local_model_name)
                raise

    def chat(
        self,
        *,
        messages: Sequence[BaseMessage],
        tools: Sequence[Any] = (),
        temperature: float = 0.0,
        max_new_tokens: int | None = None,
    ) -> AIMessage:
        """同步生成一条 LangChain 消息，并解析可能的工具调用。"""

        text = self._generate_text(
            messages=self._serialize_messages(messages),
            tools=self._serialize_tools(tools),
            temperature=temperature,
            max_new_tokens=max_new_tokens or self.config.model.local_model_max_new_tokens,
        )
        return parse_qwen_response(text)

    def stream_chat(
        self,
        *,
        messages: Sequence[BaseMessage],
        tools: Sequence[Any] = (),
        temperature: float = 0.0,
        max_new_tokens: int | None = None,
    ) -> Iterator[str]:
        """使用 Transformers streamer 按生成片段返回文本。"""

        yield from self._stream_text(
            messages=self._serialize_messages(messages),
            tools=self._serialize_tools(tools),
            temperature=temperature,
            max_new_tokens=max_new_tokens or self.config.model.local_model_max_new_tokens,
        )

    def understand_image(self, *, image_path: Path, ocr_text: str, prompt: str = "") -> str:
        """结合原图与先行 OCR 文本生成视觉语义描述。"""

        from PIL import Image

        normalized_prompt = prompt.strip() or (
            "请描述图片中的对象、布局、空间关系、图表趋势和 OCR 无法表达的视觉含义。"
            "不要重复抄写 OCR 文本，不确定的内容明确说明。"
        )
        ocr_context = ocr_text.strip()[:6000] or "（OCR 未识别到可靠文字）"
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": f"{normalized_prompt}\n\n先行 OCR 文本：\n{ocr_context}"},
                ],
            }]
            return self._generate_text(
                messages=messages,
                tools=[],
                temperature=0.0,
                max_new_tokens=self.config.model.local_model_vision_max_new_tokens,
            ).strip()

    def _generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_new_tokens: int,
    ) -> str:
        """执行一次非流式生成并只解码新增 token。"""

        self.ensure_loaded()
        assert self._processor is not None and self._model is not None
        with self._generation_lock:
            inputs = self._prepare_inputs(messages=messages, tools=tools)
            input_length = int(inputs["input_ids"].shape[-1])
            generation_kwargs = self._generation_kwargs(
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )
            import torch

            with torch.inference_mode():
                output_ids = self._model.generate(**inputs, **generation_kwargs)
            generated = output_ids[0][input_length:]
            return str(self._processor.decode(generated, skip_special_tokens=True))

    def _stream_text(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_new_tokens: int,
    ) -> Iterator[str]:
        """在独立生成线程中消费 `TextIteratorStreamer`。"""

        self.ensure_loaded()
        assert self._processor is not None and self._model is not None
        from transformers import TextIteratorStreamer

        with self._generation_lock:
            inputs = self._prepare_inputs(messages=messages, tools=tools)
            streamer = TextIteratorStreamer(
                self._processor.tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
            )
            kwargs = {
                **inputs,
                **self._generation_kwargs(temperature=temperature, max_new_tokens=max_new_tokens),
                "streamer": streamer,
            }
            failure: list[BaseException] = []

            def _generate() -> None:
                """运行模型生成并把异常传回消费线程。"""

                try:
                    import torch

                    with torch.inference_mode():
                        self._model.generate(**kwargs)
                except BaseException as exc:  # noqa: BLE001
                    failure.append(exc)
                    streamer.end()

            worker = threading.Thread(target=_generate, daemon=True, name="local-qwen-generate")
            worker.start()
            for text in streamer:
                if text:
                    yield str(text)
            worker.join()
            if failure:
                raise RuntimeError("本地 Qwen 流式生成失败。") from failure[0]

    def _prepare_inputs(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """应用模型 chat template 并把张量固定放到 CPU。"""

        assert self._processor is not None
        template_kwargs: dict[str, Any] = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_dict": True,
            "return_tensors": "pt",
            "enable_thinking": False,
        }
        if tools:
            template_kwargs["tools"] = tools
        inputs = self._processor.apply_chat_template(messages, **template_kwargs)
        return {key: value.to("cpu") if hasattr(value, "to") else value for key, value in inputs.items()}

    @staticmethod
    def _generation_kwargs(*, temperature: float, max_new_tokens: int) -> dict[str, Any]:
        """生成稳定的非思考模式参数，避免 2B 模型陷入长思考循环。"""

        kwargs: dict[str, Any] = {
            "max_new_tokens": max(1, int(max_new_tokens)),
            "do_sample": temperature > 0,
            "repetition_penalty": 1.05,
        }
        if temperature > 0:
            kwargs.update({"temperature": float(temperature), "top_p": 0.9})
        return kwargs

    @staticmethod
    def _serialize_tools(tools: Sequence[Any]) -> list[dict[str, Any]]:
        """把已注册 LangChain 工具转换成模型 chat template 接受的 schema。"""

        return [convert_to_openai_tool(tool) for tool in tools]

    @staticmethod
    def _serialize_messages(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
        """保留系统、用户、助手和工具消息的对话语义。"""

        serialized: list[dict[str, Any]] = []
        for message in messages:
            role = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}.get(
                message.type,
                message.type,
            )
            item: dict[str, Any] = {
                "role": role,
                "content": [{"type": "text", "text": str(message.content or "")}],
            }
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                item["tool_calls"] = [{
                    "type": "function",
                    "function": {
                        "name": str(call.get("name") or ""),
                        "arguments": json.dumps(call.get("args") or {}, ensure_ascii=False),
                    },
                } for call in tool_calls]
            if role == "tool":
                item["tool_call_id"] = str(getattr(message, "tool_call_id", "") or "")
                if getattr(message, "name", None):
                    item["name"] = str(message.name)
            serialized.append(item)
        return serialized


class LocalQwenChatModel:
    """提供调度器所需 `bind_tools`、`invoke` 和 `stream` 接口。"""

    def __init__(
        self,
        *,
        service: LocalQwenService,
        temperature: float,
        tools: Sequence[Any] = (),
    ) -> None:
        """保存共享推理服务和本轮绑定工具。"""

        self.service = service
        self.temperature = temperature
        self.tools = tuple(tools)

    def bind_tools(self, tools: Sequence[Any]) -> LocalQwenChatModel:
        """返回绑定指定工具的新轻量包装器，不复制模型权重。"""

        return LocalQwenChatModel(service=self.service, temperature=self.temperature, tools=tools)

    def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        """同步调用共享本地模型。"""

        return self.service.chat(messages=messages, tools=self.tools, temperature=self.temperature)

    def stream(self, messages: Sequence[BaseMessage]) -> Iterator[AIMessageChunk]:
        """自然语言按 token 流式返回；工具决策缓冲到完整 JSON 后一次返回。"""

        generated = ""
        if self.tools:
            for fragment in self.service.stream_chat(
                messages=messages,
                tools=self.tools,
                temperature=self.temperature,
            ):
                generated += fragment
            parsed = parse_qwen_response(generated)
            yield AIMessageChunk(content=parsed.content, tool_calls=parsed.tool_calls)
            return
        for fragment in self.service.stream_chat(
            messages=messages,
            temperature=self.temperature,
        ):
            generated += fragment
            yield AIMessageChunk(content=fragment)


_SERVICES: dict[str, LocalQwenService] = {}
_SERVICES_LOCK = threading.Lock()
_DOWNLOAD_THREADS: dict[str, threading.Thread] = {}
_DOWNLOAD_THREADS_LOCK = threading.Lock()


def get_local_qwen_service(config: Any) -> LocalQwenService:
    """按模型目录和名称复用进程内唯一的本地 Qwen 实例。"""

    key = f"{Path(config.storage.local_model_dir).resolve()}|{config.model.local_model_name}"
    with _SERVICES_LOCK:
        service = _SERVICES.get(key)
        if service is None:
            service = LocalQwenService(config=config)
            _SERVICES[key] = service
        return service


def start_local_qwen_download(config: Any, *, load_after: bool = True) -> bool:
    """Start exactly one resumable local-Qwen download and optionally load it afterwards."""

    target = model_target_dir(config.model.local_model_name, config.storage.local_model_dir)
    key = str(target)
    with _DOWNLOAD_THREADS_LOCK:
        active = _DOWNLOAD_THREADS.get(key)
        if active is not None and active.is_alive():
            return False
        if has_partial_model_download(target):
            restore_partial_download_progress("local_qwen", target)
        set_model_state("local_qwen", ModelState.DOWNLOADING)

        def _download() -> None:
            """Resume/download the model and publish one terminal state."""

            try:
                ensure_model(
                    config.model.local_model_name,
                    config.storage.local_model_dir,
                    model_type="local_qwen",
                )
                if not is_model_available(target):
                    raise RuntimeError(f"本地 Qwen 下载后仍不完整: {target}")
                set_model_state("local_qwen", ModelState.DOWNLOADED)
                if load_after:
                    get_local_qwen_service(config).ensure_loaded()
            except Exception as exc:
                update_download_progress(
                    "local_qwen",
                    status="error",
                    stage="failed",
                    downloaded_bytes=model_downloaded_bytes(target),
                    total_bytes=None,
                    message=str(exc),
                )
                set_model_state("local_qwen", ModelState.ERROR)
                logger.exception("本地 Qwen 下载或加载失败")
            finally:
                with _DOWNLOAD_THREADS_LOCK:
                    _DOWNLOAD_THREADS.pop(key, None)

        worker = threading.Thread(target=_download, daemon=True, name="local-qwen-download")
        _DOWNLOAD_THREADS[key] = worker
        worker.start()
        return True


def resume_interrupted_local_qwen_download(config: Any) -> bool:
    """Resume a detected Hugging Face partial download during backend startup."""

    target = model_target_dir(config.model.local_model_name, config.storage.local_model_dir)
    if is_model_available(target) or not has_partial_model_download(target):
        return False
    return start_local_qwen_download(config, load_after=True)


def reset_local_qwen_services() -> None:
    """清空共享服务注册表，主要供测试和进程关闭使用。"""

    with _SERVICES_LOCK:
        _SERVICES.clear()

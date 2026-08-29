"""PyTorch 本地模型加载的进程级安全辅助。

使用说明:
Embedding 与 ReRank 加载器通过 ``load_with_safe_module_apply`` 临时修补
``torch.nn.Module._apply``，物化残留的 meta tensor。该属性属于进程级全局状态，
因此两个模型线程必须共用本模块的锁，避免补丁嵌套、错误恢复或无限递归。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar

ResultT = TypeVar("ResultT")

_TORCH_MODULE_APPLY_LOCK = threading.Lock()


def load_with_safe_module_apply(torch_module: Any, loader: Callable[[], ResultT]) -> ResultT:
    """串行执行需要全局 ``Module._apply`` 补丁的模型构造并可靠恢复原函数。"""

    with _TORCH_MODULE_APPLY_LOCK:
        original_apply = torch_module.nn.Module._apply

        def materialize_recursive(module: Any) -> None:
            """递归把当前模块树中的 meta parameter 和 buffer 物化到 CPU。"""

            for name, parameter in list(module._parameters.items()):
                if parameter is not None and parameter.is_meta:
                    module._parameters[name] = torch_module.nn.Parameter(
                        torch_module.empty(parameter.shape, device="cpu", dtype=parameter.dtype)
                    )
            for name, buffer in list(module._buffers.items()):
                if buffer is not None and buffer.is_meta:
                    module._buffers[name] = torch_module.empty(
                        buffer.shape,
                        device="cpu",
                        dtype=buffer.dtype,
                    )
            for child in module.children():
                materialize_recursive(child)

        def patched_apply(module: Any, fn: object) -> object:
            """先物化模块树，再委托调用补丁前的 PyTorch `_apply`。"""

            materialize_recursive(module)
            return original_apply(module, fn)

        torch_module.nn.Module._apply = patched_apply
        try:
            return loader()
        finally:
            torch_module.nn.Module._apply = original_apply

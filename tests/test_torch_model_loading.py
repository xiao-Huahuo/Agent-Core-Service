"""PyTorch 模型并发加载保护测试。

使用说明:
只使用轻量假对象验证全局 ``Module._apply`` 补丁不会被两个模型线程并发覆盖，
不导入、下载或加载任何真实模型。
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

from agent_service.services.memory.rag.torch_loading import load_with_safe_module_apply


def test_global_module_apply_patch_is_serialized_and_restored() -> None:
    """Embedding 与 ReRank 同时预热时必须串行进入全局 PyTorch 补丁区。"""

    class FakeModule:
        """提供可替换的 `_apply` 类属性。"""

        def _apply(self, fn: object) -> object:  # noqa: ARG002
            """模拟 PyTorch 原始 `_apply`。"""

            return self

    original_apply = FakeModule._apply
    fake_torch = SimpleNamespace(nn=SimpleNamespace(Module=FakeModule, Parameter=lambda value: value))
    entered_first = threading.Event()
    release_first = threading.Event()
    entered_second = threading.Event()
    order: list[str] = []

    def first_loader() -> str:
        """占用补丁区直到测试允许释放。"""

        order.append("first-enter")
        entered_first.set()
        release_first.wait(timeout=2)
        order.append("first-exit")
        return "first"

    def second_loader() -> str:
        """记录第二个加载器真正进入补丁区的时机。"""

        order.append("second-enter")
        entered_second.set()
        return "second"

    first = threading.Thread(target=lambda: load_with_safe_module_apply(fake_torch, first_loader))
    second = threading.Thread(target=lambda: load_with_safe_module_apply(fake_torch, second_loader))
    first.start()
    assert entered_first.wait(timeout=1)
    second.start()
    assert entered_second.wait(timeout=0.05) is False
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert order == ["first-enter", "first-exit", "second-enter"]
    assert FakeModule._apply is original_apply

"""
LaTeX REST 接口参数和错误映射测试。

使用说明:
挂载正式 settings/knowledge 路由并注入假 LaTeX 服务，验证前端所需接口全部
调用共享服务且缺少编译器时返回稳定的 409。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_service.api.rest import knowledge as knowledge_rest
from agent_service.api.rest import settings as settings_rest


class _LatexStub:
    """记录 REST 调用并返回固定状态。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_status(self) -> dict[str, Any]:
        """返回可用的系统工具链。"""

        self.calls.append(("status", {}))
        return {"status": "ready", "source": "system"}

    def start_install(self) -> dict[str, Any]:
        """返回已启动状态。"""

        self.calls.append(("install", {}))
        return {"status": "downloading"}

    def cancel_install(self) -> dict[str, Any]:
        """返回取消状态。"""

        self.calls.append(("cancel", {}))
        return {"status": "cancelling"}

    def uninstall_managed(self) -> dict[str, Any]:
        """返回卸载后的缺失状态。"""

        self.calls.append(("uninstall", {}))
        return {"status": "missing"}

    def compile_file(self, **kwargs: Any) -> dict[str, Any]:
        """记录编译参数；指定路径用于模拟缺少运行时。"""

        self.calls.append(("compile", kwargs))
        if kwargs["path"] == "missing.tex":
            raise RuntimeError("未检测到 LaTeX 编译环境")
        return {"success": True, "preview": {"kind": "pdf"}}


def _client(monkeypatch: Any) -> tuple[TestClient, _LatexStub]:
    """创建只包含本次目标路由的测试应用。"""

    service = _LatexStub()
    monkeypatch.setattr(settings_rest, "_require_latex_service", lambda: service)
    monkeypatch.setattr(knowledge_rest, "_require_latex_service", lambda: service)
    app = FastAPI()
    app.include_router(settings_rest.router)
    app.include_router(knowledge_rest.router)
    return TestClient(app), service


def test_latex_runtime_lifecycle_endpoints_require_user_and_call_service(monkeypatch: Any) -> None:
    """状态、安装、取消和卸载必须校验用户并调用共享服务。"""

    client, service = _client(monkeypatch)

    assert client.get("/settings/latex/status", params={"user_id": "u1"}).json()["status"] == "ready"
    assert client.post("/settings/latex/install", json={"user_id": "u1"}).status_code == 200
    assert client.post("/settings/latex/install/cancel", json={"user_id": "u1"}).status_code == 200
    assert client.post("/settings/latex/uninstall", json={"user_id": "u1"}).status_code == 200
    assert client.post("/settings/latex/install", json={}).status_code == 422
    assert [name for name, _ in service.calls] == ["status", "install", "cancel", "uninstall"]


def test_compile_endpoint_maps_success_and_missing_runtime(monkeypatch: Any) -> None:
    """编译成功返回 PDF payload，缺少运行时返回 409 而不是 500。"""

    client, service = _client(monkeypatch)

    success = client.post("/knowledge/latex/compile", json={"user_id": "u1", "path": "paper.tex"})
    missing = client.post("/knowledge/latex/compile", json={"user_id": "u1", "path": "missing.tex"})

    assert success.status_code == 200
    assert success.json()["preview"]["kind"] == "pdf"
    assert missing.status_code == 409
    assert service.calls[-1] == ("compile", {"user_id": "u1", "path": "missing.tex"})


def test_compiled_pdf_download_uses_attachment_response(tmp_path: Any, monkeypatch: Any) -> None:
    """下载按钮使用的 raw 路由必须返回编译 PDF 字节和 attachment 文件名。"""

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-download")
    library = type("LibraryStub", (), {
        "resolve_file_for_raw_response": lambda self, **kwargs: (pdf_path, "application/pdf"),
    })()
    monkeypatch.setattr(knowledge_rest, "_require_knowledge_library_service", lambda: library)
    app = FastAPI()
    app.include_router(knowledge_rest.router)
    client = TestClient(app)

    response = client.get(
        "/knowledge/files/raw",
        params={"user_id": "u1", "path": ".mw/latex/key/paper.pdf", "download": "true"},
    )

    assert response.status_code == 200
    assert response.content == b"%PDF-download"
    assert response.headers["content-disposition"].startswith('attachment; filename="paper.pdf"')

"""
编辑器上下文状态服务。

功能说明:
本模块保存 editor 前端上报的“当前用户正在观看的文档”基本信息。该状态是
瞬时 UI 上下文,不写入数据库;Agent 工具可通过 user_id 读取它,再决定是否调用
文件读取工具获取正文。

使用说明:
REST 层调用 `set_current_document()` 更新当前文档;内置工具调用
`get_current_document()` 获取只包含路径、文件名、大小、修改时间和 dirty 状态等
基本信息的快照。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass(slots=True)
class CurrentDocumentInfo:
    """
    当前正在观看的文档基本信息。

    user_id: 用户 ID。
    path: 文件相对于知识库根目录的路径。
    name: 文件名。
    knowledge_dir: 当前知识库根目录。
    library_id: 当前知识库配置 ID。
    library_name: 当前知识库显示名。
    size: 文件大小,未知时为 None。
    mtime: 文件修改时间展示值,由前端或后端文件树提供。
    dirty: 前端编辑器内容是否未保存。
    open_tab_count: 当前前端打开的 tab 数量。
    selected_paths: 文件资源管理器当前多选的知识库相对路径。
    updated_at: 后端接收该状态的 UTC 时间。
    """

    user_id: str
    path: str
    name: str
    knowledge_dir: str = ""
    library_id: str = ""
    library_name: str = ""
    size: int | None = None
    mtime: str = ""
    dirty: bool = False
    open_tab_count: int = 0
    selected_paths: tuple[str, ...] = ()
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """返回可 JSON 序列化的文档基本信息。"""

        return asdict(self)


class EditorContextService:
    """
    线程安全的编辑器上下文内存仓库。

    该服务故意只保存瞬时状态,重启后丢失是符合预期的。用户设置、知识库配置和文件
    内容仍由已有 settings/knowledge 服务负责。
    """

    def __init__(self) -> None:
        """初始化内存状态与锁。"""

        self._lock = RLock()
        self._current_documents: dict[str, CurrentDocumentInfo] = {}

    def set_current_document(self, payload: dict[str, Any]) -> CurrentDocumentInfo:
        """
        写入指定用户当前正在观看的文档基本信息。

        payload: REST 请求体,必须包含 user_id;path 为空表示当前没有活动文件。
        """

        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            raise ValueError("user_id is required")
        path = str(payload.get("path") or "").strip()
        name = str(payload.get("name") or "").strip()
        if path and not name:
            name = path.replace("\\", "/").split("/")[-1]
        info = CurrentDocumentInfo(
            user_id=user_id,
            path=path,
            name=name,
            knowledge_dir=str(payload.get("knowledge_dir") or "").strip(),
            library_id=str(payload.get("library_id") or "").strip(),
            library_name=str(payload.get("library_name") or "").strip(),
            size=_coerce_optional_int(payload.get("size")),
            mtime=str(payload.get("mtime") or "").strip(),
            dirty=bool(payload.get("dirty") or False),
            open_tab_count=max(0, int(payload.get("open_tab_count") or 0)),
            selected_paths=tuple(
                dict.fromkeys(
                    str(path or "").replace("\\", "/").strip("/")
                    for path in (payload.get("selected_paths") or [])
                    if str(path or "").strip()
                )
            ),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._current_documents[user_id] = info
        return info

    def get_current_document(self, user_id: str) -> CurrentDocumentInfo | None:
        """
        读取指定用户当前正在观看的文档基本信息。

        user_id: 用户 ID。
        """

        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            return None
        with self._lock:
            return self._current_documents.get(normalized_user_id)


def _coerce_optional_int(value: Any) -> int | None:
    """将前端传入的 size 转为 int;空值或非法值返回 None。"""

    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


editor_context_service = EditorContextService()

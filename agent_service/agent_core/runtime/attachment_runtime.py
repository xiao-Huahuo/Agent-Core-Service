"""Agent 附件服务与上下文构建器的绑定适配。

该对象只协调已有 SessionAttachmentService 和 ContextBuilder，不复制附件解析、OCR
或视觉模型业务逻辑。
"""

from __future__ import annotations

from typing import Any

from agent_service.services.session_attachment.service import SessionAttachmentService


class AttachmentRuntime:
    """保存附件服务，并把它同步绑定到当前 ContextBuilder。"""

    def __init__(self, service: SessionAttachmentService | None = None) -> None:
        """保存可选的初始附件服务。"""

        self.service = service

    def bind(self, *, service: SessionAttachmentService, context_builder: Any = None) -> None:
        """更新附件服务，并同步给已经存在的上下文构建器。"""

        self.service = service
        if context_builder is not None:
            context_builder.attachment_service = service

    def apply_to(self, context_builder: Any) -> None:
        """把当前附件服务应用到一个新建的上下文构建器。"""

        if self.service is not None:
            context_builder.attachment_service = self.service

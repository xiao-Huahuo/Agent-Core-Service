"""组件库上传 DTO 的源码长度边界测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_service.schemas.component_library import ComponentLibraryItemCreate


def test_component_source_accepts_large_stylesheets() -> None:
    """完整样式表不应被旧的 250,000 字符限制误拒绝。"""

    payload = ComponentLibraryItemCreate(user_id="u1", source="a" * 300_000, tag="cards")

    assert len(payload.source) == 300_000


def test_component_source_rejects_over_two_megabytes() -> None:
    """上传边界仍阻止异常大的单个组件源码请求。"""

    with pytest.raises(ValidationError):
        ComponentLibraryItemCreate(user_id="u1", source="a" * 2_000_001, tag="cards")

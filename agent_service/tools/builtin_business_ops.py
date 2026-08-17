"""Skill、反馈、图书馆、组件库和收藏 Agent 工具。

使用说明:
所有函数只做参数归一化、权限校验和结果序列化，实际读写复用应用启动时注入的
正式业务 service，避免 Agent 工具形成第二套存储实现。
"""

from __future__ import annotations

import json
from typing import Any

from agent_service.schemas.favorite import FavoriteCreate
from agent_service.schemas.feedback import FeedbackCreate, FeedbackUpdate
from agent_service.tools.runtime_context import AGENT_ACCESS_READONLY, get_tool_runtime


def _service(name: str) -> Any:
    """延迟读取 REST 依赖容器中的业务 service，避免 AgentCore 导入环。"""

    from agent_service.api.rest import deps

    return getattr(deps, f"_require_{name}_service")()


def _json(payload: Any) -> str:
    """返回保留中文的格式化 JSON。"""

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _write_runtime(action: str) -> Any:
    """校验写权限并返回当前工具运行时。"""

    runtime = get_tool_runtime()
    if runtime.agent_access_mode == AGENT_ACCESS_READONLY:
        raise PermissionError(f"当前 Agent 为只读模式，不能{action}")
    return runtime


def get_custom_skill(skill_id: str) -> str:
    """读取一个用户定制 Skill 的完整 SKILL.md。"""

    runtime = get_tool_runtime()
    skill = _service("skill").read_skill_body(user_id=runtime.user_id, skill_ref=skill_id)
    if skill is None or str(skill.get("source") or "") != "user":
        raise ValueError("custom skill not found")
    return _json(skill)


def create_custom_skill(name: str, description: str, body: str) -> str:
    """创建与 Skill 页面一致的用户定制 Skill。"""

    runtime = _write_runtime("创建 Skill")
    return _json(
        _service("skill").create_user_skill(
            user_id=runtime.user_id,
            name=name,
            description=description,
            body=body,
        )
    )


def update_custom_skill(
    skill_id: str,
    name: str | None = None,
    description: str | None = None,
    body: str | None = None,
) -> str:
    """增量修改用户定制 Skill 的名称、说明或正文。"""

    runtime = _write_runtime("更新 Skill")
    return _json(
        _service("skill").update_user_skill(
            user_id=runtime.user_id,
            skill_id=skill_id,
            name=name,
            description=description,
            body=body,
        )
    )


def delete_custom_skill(skill_id: str, confirm: bool = False) -> str:
    """删除用户定制 Skill；必须取得用户明确确认。"""

    runtime = _write_runtime("删除 Skill")
    if not confirm:
        raise PermissionError("删除 Skill 需要用户明确确认并传 confirm=true")
    return _json(_service("skill").delete_user_skill(user_id=runtime.user_id, skill_id=skill_id))


def validate_custom_skill(skill_id: str) -> str:
    """验证用户 Skill 的 frontmatter、正文和索引可读性。"""

    runtime = get_tool_runtime()
    return _json(_service("skill").validate_user_skill(user_id=runtime.user_id, skill_id=skill_id))


def test_custom_skill(skill_id: str, prompt: str) -> str:
    """使用真实关键词路由器测试 Skill 对指定提示的匹配情况。"""

    runtime = get_tool_runtime()
    return _json(
        _service("skill").test_user_skill(
            user_id=runtime.user_id,
            skill_id=skill_id,
            prompt=prompt,
        )
    )


def set_skill_enabled(skill_id: str, enabled: bool) -> str:
    """启用或停用一个内置/用户 Skill。"""

    runtime = _write_runtime("修改 Skill 启用状态")
    return _json(
        _service("skill").set_skill_enabled(
            user_id=runtime.user_id,
            skill_id=skill_id,
            enabled=enabled,
        )
    )


def list_user_feedback() -> str:
    """列出当前用户提交的全部反馈。"""

    feedback = _service("feedback").list_feedback(user_id=get_tool_runtime().user_id)
    return _json([item.model_dump(mode="json") for item in feedback])


def get_user_feedback(feedback_id: str) -> str:
    """读取当前用户的一条反馈。"""

    feedback = _service("feedback").get_feedback(
        feedback_id=feedback_id,
        user_id=get_tool_runtime().user_id,
    )
    if feedback is None:
        raise ValueError("feedback not found")
    return _json(feedback)


def create_user_feedback(content: str, source: str = "agent", page: str = "") -> str:
    """以当前用户身份新增反馈。"""

    runtime = _write_runtime("新增用户反馈")
    feedback = _service("feedback").add_feedback(
        FeedbackCreate(user_id=runtime.user_id, content=content, source=source, page=page)
    )
    return _json(feedback)


def update_user_feedback(feedback_id: str, content: str) -> str:
    """修改当前用户拥有的反馈内容。"""

    runtime = _write_runtime("修改用户反馈")
    service = _service("feedback")
    if service.get_feedback(feedback_id=feedback_id, user_id=runtime.user_id) is None:
        raise ValueError("feedback not found")
    feedback = service.update_feedback(feedback_id=feedback_id, payload=FeedbackUpdate(content=content))
    return _json(feedback)


def delete_user_feedback(feedback_id: str) -> str:
    """删除当前用户拥有的一条反馈。"""

    runtime = _write_runtime("删除用户反馈")
    service = _service("feedback")
    if service.get_feedback(feedback_id=feedback_id, user_id=runtime.user_id) is None:
        raise ValueError("feedback not found")
    return _json({"feedback_id": feedback_id, "deleted": service.delete_feedback(feedback_id=feedback_id)})


def get_library_item(item_id: str) -> str:
    """读取图书馆单个图书或集锦的完整元数据。"""

    return _json(_service("library").get_item(user_id=get_tool_runtime().user_id, item_id=item_id))


def list_components(component_type: str = "any") -> str:
    """按组件类型筛选并列出用户组件。"""

    return _json(
        _service("component_library").list_components(
            user_id=get_tool_runtime().user_id,
            tag=component_type,
        )
    )


def get_component(component_id: str) -> str:
    """读取一个组件的源码和元数据。"""

    return _json(
        _service("component_library").get_component(
            user_id=get_tool_runtime().user_id,
            component_id=component_id,
        )
    )


def create_component(source: str, component_type: str, filename: str = "") -> str:
    """创建 Vue SFC 或独立 HTML 组件。"""

    runtime = _write_runtime("创建组件")
    return _json(
        _service("component_library").create_component(
            user_id=runtime.user_id,
            source=source,
            tag=component_type,
            filename=filename,
        )
    )


def update_component(
    component_id: str,
    source: str | None = None,
    component_type: str | None = None,
    title: str | None = None,
) -> str:
    """增量修改组件源码、类型或标题。"""

    runtime = _write_runtime("更新组件")
    return _json(
        _service("component_library").update_component(
            user_id=runtime.user_id,
            component_id=component_id,
            source=source,
            tag=component_type,
            title=title,
        )
    )


def delete_component(component_id: str, confirm: bool = False) -> str:
    """删除一个用户组件；必须由用户明确确认。"""

    runtime = _write_runtime("删除组件")
    if not confirm:
        raise PermissionError("删除组件需要用户明确确认并传 confirm=true")
    return _json(
        _service("component_library").delete_component(
            user_id=runtime.user_id,
            component_id=component_id,
        )
    )


def validate_component(component_id: str) -> str:
    """验证持久化组件的源码格式和基本结构。"""

    return _json(
        _service("component_library").validate_component(
            user_id=get_tool_runtime().user_id,
            component_id=component_id,
        )
    )


def list_favorites(target_type: str | None = None, library_id: str | None = None) -> str:
    """按目标类型和知识库作用域列出收藏。"""

    favorites = _service("favorite").list_favorites(
        user_id=get_tool_runtime().user_id,
        target_type=target_type,
        library_id=library_id,
    )
    return _json([item.model_dump(mode="json") for item in favorites])


def add_favorite(target_type: str, target_id: str, library_id: str = "") -> str:
    """收藏知识库路径、图书馆条目、组件或会话。"""

    runtime = _write_runtime("新增收藏")
    favorite = _service("favorite").add_favorite(
        FavoriteCreate(
            user_id=runtime.user_id,
            target_type=target_type,
            target_id=target_id,
            library_id=library_id,
        )
    )
    return _json(favorite)


def remove_favorite(target_type: str, target_id: str, library_id: str = "") -> str:
    """取消指定知识库路径、图书馆条目、组件或会话的收藏。"""

    runtime = _write_runtime("取消收藏")
    deleted = _service("favorite").delete_favorite(
        user_id=runtime.user_id,
        target_type=target_type,
        target_id=target_id,
        library_id=library_id,
    )
    return _json({"target_type": target_type, "target_id": target_id, "deleted": deleted})

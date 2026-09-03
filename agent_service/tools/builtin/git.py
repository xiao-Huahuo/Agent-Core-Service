"""git 类内置工具实现。

函数体由原 builtin.py 机械迁移，工具行为不变。
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from agent_service.tools.runtime_context import (
    AGENT_ACCESS_READONLY,
    get_markdown_html_visualization_callback,
    get_task_list_callback,
    get_tool_runtime,
    get_tool_service,
    register_network_citation,
    register_tool_citation,
)
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.services.todo.service import TodoService
from agent_service.services.automation.service import AutomationService
from agent_service.tools.builtin.builtin import (
    BuiltinToolDefinition, _deny_readonly_write, _is_readonly_access,
    _safe_visualization_filename, _strip_markdown_html_fence,
)

def _get_git_service():
    """返回应用启动阶段注入的统一 GitService。"""

    return get_tool_service("git")
def _require_git_write_access() -> Any:
    """校验当前 Agent 不是只读模式并返回运行时上下文。"""

    from agent_service.tools.runtime_context import AGENT_ACCESS_READONLY

    runtime = get_tool_runtime()
    if runtime.agent_access_mode == AGENT_ACCESS_READONLY:
        raise PermissionError("当前 Agent 处于只读模式,不能执行 Git 写操作。")
    return runtime
def git_status() -> str:
    """读取当前知识库的结构化 Git 状态。"""

    import json

    runtime = get_tool_runtime()
    payload = _get_git_service().get_status(user_id=runtime.user_id)
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_diff(path: str = "", staged: bool = False) -> str:
    """
    读取当前知识库的 Git diff。

    path: 可选知识库相对路径,为空时返回全部差异。
    staged: 是否读取暂存区差异。
    """

    runtime = get_tool_runtime()
    payload = _get_git_service().get_diff(
        user_id=runtime.user_id,
        path=path,
        staged=staged,
    )
    return str(payload.get("diff") or "没有差异。")
def git_history(limit: int | None = None) -> str:
    """读取提交历史、未推送提交和文件。"""

    import json

    runtime = get_tool_runtime()
    payload = _get_git_service().get_history(
        user_id=runtime.user_id,
        limit=limit or runtime.config.limits.api_default_list_limit,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_init_repository(initial_branch: str = "main") -> str:
    """在当前知识库根目录初始化 Git 仓库。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().initialize_repository(
        user_id=runtime.user_id,
        initial_branch=initial_branch,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_restore_files(paths: list[str]) -> str:
    """
    回滚已跟踪文件并将未跟踪文件移入 MetaWeave 最近删除。

    paths: 需要回滚的知识库相对路径列表。
    """

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().restore_paths(user_id=runtime.user_id, paths=paths)
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_commit_files(paths: list[str], message: str) -> str:
    """暂存选中文件并创建本地提交。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().commit(
        user_id=runtime.user_id,
        paths=paths,
        message=message,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_push_branch(
    local_branch: str,
    remote: str,
    remote_branch: str,
    confirm: bool = False,
    force_with_lease: bool = False,
    confirm_force: bool = False,
    all_branches: bool = False,
) -> str:
    """
    推送分支到远程。

    confirm: 用户是否明确确认普通推送。
    force_with_lease: 是否使用带租约的安全强推。
    confirm_force: 用户是否明确确认高风险覆盖远端历史。
    all_branches: 是否忽略单分支映射并推送全部本地分支。
    """

    import json

    runtime = _require_git_write_access()
    if not confirm:
        raise PermissionError("推送会修改远程仓库,必须先获得用户明确确认并传入 confirm=true。")
    if force_with_lease and not confirm_force:
        raise PermissionError("force-with-lease 需要单独确认并传入 confirm_force=true。")
    payload = _get_git_service().push(
        user_id=runtime.user_id,
        local_branch=local_branch,
        remote=remote,
        remote_branch=remote_branch,
        force_with_lease=force_with_lease,
        all_branches=all_branches,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_create_branch(name: str, checkout: bool = True) -> str:
    """创建本地分支,可选择立即切换。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().create_branch(
        user_id=runtime.user_id,
        name=name,
        checkout=checkout,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_add_remote(name: str, url: str) -> str:
    """
    为当前知识库 Git 仓库新增命名远程。

    name: 远程名称,例如 origin。
    url: HTTPS、SSH 或本地 Git 仓库地址。
    """

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().add_remote(
        user_id=runtime.user_id,
        name=name,
        url=url,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_switch_branch(name: str) -> str:
    """切换本地分支并清理受影响知识文件的旧索引。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().switch_branch(user_id=runtime.user_id, name=name)
    return json.dumps(payload, ensure_ascii=False, indent=2)
def git_pull_branch(remote: str, branch: str) -> str:
    """获取并快进合并远程分支,拒绝隐式合并提交。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().pull_fast_forward(
        user_id=runtime.user_id,
        remote=remote,
        branch=branch,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)

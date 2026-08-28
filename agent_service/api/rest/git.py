"""
知识库 Git REST API。

使用说明:
前端 Git 边栏通过本路由访问结构化 Git 能力。所有写操作委托 GitService,
从而保证路径边界、UTF-8、索引失效和 `--force-with-lease` 安全策略一致。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from agent_service.api.rest.deps import _require_git_service
from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.schemas.git import (
    GitBranchRequest,
    GitCommitRequest,
    GitInitRequest,
    GitPathsRequest,
    GitPullRequest,
    GitPushRequest,
    GitRemoteRequest,
)
from agent_service.services.git.service import GitServiceError

router = APIRouter(prefix="/git", tags=["git"])


def _http_error(exc: GitServiceError) -> HTTPException:
    """把领域错误转换为稳定的 422 API 响应。"""

    return HTTPException(status_code=422, detail=str(exc))


@router.get("/status")
async def get_git_status(user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)) -> dict[str, Any]:
    """读取当前知识库仓库状态。"""

    try:
        return await run_in_threadpool(_require_git_service().get_status, user_id=user_id)
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/init")
async def initialize_git_repository(body: GitInitRequest) -> dict[str, Any]:
    """在当前知识库根目录初始化 Git 仓库。"""

    try:
        return await run_in_threadpool(
            _require_git_service().initialize_repository,
            user_id=body.user_id,
            initial_branch=body.initial_branch,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.get("/diff")
async def get_git_diff(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length),
    path: str = Query(""),
    staged: bool = Query(False),
) -> dict[str, Any]:
    """读取工作区或单文件 diff。"""

    try:
        return await run_in_threadpool(
            _require_git_service().get_diff,
            user_id=user_id,
            path=path,
            staged=staged,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.get("/history")
async def get_git_history(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length),
    limit: int = Query(
        DEFAULT_BUSINESS_LIMITS.api_default_list_limit,
        ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        le=DEFAULT_BUSINESS_LIMITS.api_max_list_limit,
    ),
) -> dict[str, Any]:
    """读取提交历史与未推送内容。"""

    try:
        return await run_in_threadpool(
            _require_git_service().get_history,
            user_id=user_id,
            limit=limit,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/restore")
async def restore_git_paths(body: GitPathsRequest) -> dict[str, Any]:
    """回滚已跟踪文件并把未跟踪文件移入最近删除。"""

    try:
        return await run_in_threadpool(
            _require_git_service().restore_paths,
            user_id=body.user_id,
            paths=body.paths,
        )
    except (GitServiceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/commit")
async def commit_git_paths(body: GitCommitRequest) -> dict[str, Any]:
    """暂存选中文件并提交。"""

    try:
        return await run_in_threadpool(
            _require_git_service().commit,
            user_id=body.user_id,
            paths=body.paths,
            message=body.message,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/push")
async def push_git_branch(body: GitPushRequest) -> dict[str, Any]:
    """推送分支,可选择显式启用 force-with-lease。"""

    try:
        return await run_in_threadpool(
            _require_git_service().push,
            user_id=body.user_id,
            local_branch=body.local_branch,
            remote=body.remote,
            remote_branch=body.remote_branch,
            force_with_lease=body.force_with_lease,
            set_upstream=body.set_upstream,
            all_branches=body.all_branches,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/branches")
async def create_git_branch(body: GitBranchRequest) -> dict[str, Any]:
    """创建本地分支。"""

    try:
        return await run_in_threadpool(
            _require_git_service().create_branch,
            user_id=body.user_id,
            name=body.name,
            checkout=body.checkout,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/remotes")
async def add_git_remote(body: GitRemoteRequest) -> dict[str, Any]:
    """为当前知识库仓库新增命名远程。"""

    try:
        return await run_in_threadpool(
            _require_git_service().add_remote,
            user_id=body.user_id,
            name=body.name,
            url=body.url,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/switch")
async def switch_git_branch(body: GitBranchRequest) -> dict[str, Any]:
    """切换本地分支并清理所有受影响文件索引。"""

    try:
        return await run_in_threadpool(
            _require_git_service().switch_branch,
            user_id=body.user_id,
            name=body.name,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/pull")
async def pull_git_branch(body: GitPullRequest) -> dict[str, Any]:
    """获取并快进合并远程分支。"""

    try:
        return await run_in_threadpool(
            _require_git_service().pull_fast_forward,
            user_id=body.user_id,
            remote=body.remote,
            branch=body.branch,
        )
    except GitServiceError as exc:
        raise _http_error(exc) from exc

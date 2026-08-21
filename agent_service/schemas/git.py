"""
Git REST/gRPC 数据传输模型。

使用说明:
API 层使用这些 Pydantic DTO 校验用户输入,领域服务继续返回普通字典,便于 REST、
gRPC、Agent 工具和前端共享同一套业务逻辑。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class GitUserRequest(BaseModel):
    """只包含当前用户标识的 Git 请求。"""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)


class GitInitRequest(GitUserRequest):
    """初始化知识库仓库请求。"""

    initial_branch: str = "main"


class GitPathsRequest(GitUserRequest):
    """选中文件集合请求。"""

    paths: list[str] = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)


class GitCommitRequest(GitPathsRequest):
    """提交选中文件请求。"""

    message: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.git_commit_message_max_length)


class GitPushRequest(GitUserRequest):
    """推送本地分支到指定远程分支请求。"""

    local_branch: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    remote: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    remote_branch: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    force_with_lease: bool = False
    set_upstream: bool = True
    all_branches: bool = False


class GitBranchRequest(GitUserRequest):
    """创建或切换本地分支请求。"""

    name: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    checkout: bool = True


class GitRemoteRequest(GitUserRequest):
    """新增命名远程仓库请求。"""

    name: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    url: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.large_text_max_length)


class GitPullRequest(GitUserRequest):
    """快进拉取远程分支请求。"""

    remote: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    branch: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)

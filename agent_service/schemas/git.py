"""
Git REST/gRPC 数据传输模型。

使用说明:
API 层使用这些 Pydantic DTO 校验用户输入,领域服务继续返回普通字典,便于 REST、
gRPC、Agent 工具和前端共享同一套业务逻辑。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GitUserRequest(BaseModel):
    """只包含当前用户标识的 Git 请求。"""

    user_id: str = Field(min_length=1)


class GitInitRequest(GitUserRequest):
    """初始化知识库仓库请求。"""

    initial_branch: str = "main"


class GitPathsRequest(GitUserRequest):
    """选中文件集合请求。"""

    paths: list[str] = Field(min_length=1)


class GitCommitRequest(GitPathsRequest):
    """提交选中文件请求。"""

    message: str = Field(min_length=1, max_length=500)


class GitPushRequest(GitUserRequest):
    """推送本地分支到指定远程分支请求。"""

    local_branch: str = Field(min_length=1)
    remote: str = Field(min_length=1)
    remote_branch: str = Field(min_length=1)
    force_with_lease: bool = False
    set_upstream: bool = True
    all_branches: bool = False


class GitBranchRequest(GitUserRequest):
    """创建或切换本地分支请求。"""

    name: str = Field(min_length=1)
    checkout: bool = True


class GitRemoteRequest(GitUserRequest):
    """新增命名远程仓库请求。"""

    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=4096)


class GitPullRequest(GitUserRequest):
    """快进拉取远程分支请求。"""

    remote: str = Field(min_length=1)
    branch: str = Field(min_length=1)

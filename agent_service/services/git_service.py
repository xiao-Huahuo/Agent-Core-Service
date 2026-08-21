"""
知识库 Git 领域服务。

功能说明:
本服务只允许在当前用户的 active 知识库根目录执行结构化 Git 操作,统一处理状态、
差异、提交、回滚、分支和推送。所有会改变知识库文件内容的操作都会调用
KnowledgeLibraryService.invalidate_paths,确保旧切片与语义图谱不会继续被召回。

使用说明:
REST、gRPC、前端边栏和 Agent 工具都必须调用本服务,禁止自行拼接 shell 命令。
服务通过 subprocess 参数数组调用 Git,从不启用 shell。
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS

if TYPE_CHECKING:
    from agent_service.services.knowledge_library_service import KnowledgeLibraryService


class GitServiceError(RuntimeError):
    """表示可安全展示给用户的 Git 命令或仓库状态错误。"""


class GitService:
    """
    管理当前 active 知识库仓库。

    knowledge_library_service: 提供用户知识库根目录、最近删除和索引失效能力。
    """

    _STATUS_CONFLICT_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    _BRANCH_NAME_PATTERN = re.compile(r"^[^\s~^:?*\[\\]+$")

    def __init__(
        self,
        *,
        knowledge_library_service: KnowledgeLibraryService,
        config: AgentConfig | None = None,
    ) -> None:
        """保存知识库服务并创建进程内仓库写锁。"""

        self.knowledge_library_service = knowledge_library_service
        self.config = config or getattr(knowledge_library_service, "config", None) or AgentConfig()
        self._mutation_lock = threading.RLock()

    def get_status(self, *, user_id: str) -> dict[str, Any]:
        """返回仓库、分支、远程以及工作区文件的结构化状态。"""

        root = self._root(user_id=user_id)
        repository_root = self._repository_root(root=root)
        if repository_root is None:
            return self._empty_status(root=root)
        self._ensure_repository_matches_knowledge_root(root=root, repository_root=repository_root)
        output = self._run(
            root=root,
            args=["status", "--porcelain=v1", "-z", "--branch", "--ignored"],
        ).stdout
        changes, untracked, ignored = self._parse_porcelain_status(output)
        current_branch = self._current_branch(root=root)
        upstream = self._upstream(root=root)
        ahead, behind = self._ahead_behind(root=root, upstream=upstream)
        branches = self._branches(root=root)
        remote_branches = self._remote_branches(root=root)
        remotes = self._remotes(root=root)
        return {
            "initialized": True,
            "repository_root": str(root),
            "current_branch": current_branch,
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
            "detached": not bool(current_branch),
            "branches": branches,
            "remote_branches": remote_branches,
            "remotes": remotes,
            "changes": changes,
            "untracked": untracked,
            "ignored": ignored,
            "has_changes": bool(changes or untracked),
        }

    def initialize_repository(self, *, user_id: str, initial_branch: str = "main") -> dict[str, Any]:
        """在知识库根目录初始化仓库,不会修改任何知识文件或索引。"""

        root = self._root(user_id=user_id)
        if self._repository_root(root=root) is not None:
            raise GitServiceError("当前知识库已经位于 Git 仓库中。")
        branch = self._validate_branch_name(initial_branch or "main")
        with self._mutation_lock:
            result = self._run(root=root, args=["init", "-b", branch], check=False)
            if result.returncode != 0:
                self._run(root=root, args=["init"])
                self._run(root=root, args=["symbolic-ref", "HEAD", f"refs/heads/{branch}"])
        return self.get_status(user_id=user_id)

    def get_diff(self, *, user_id: str, path: str = "", staged: bool = False) -> dict[str, Any]:
        """读取单文件或整个工作区的统一 diff,不改变仓库。"""

        root = self._require_root_repository(user_id=user_id)
        args = ["diff", "--no-ext-diff", "--no-color"]
        if staged:
            args.append("--cached")
        normalized_path = ""
        if path:
            normalized_path = self._validate_relative_path(root=root, path=path)
            args.extend(["--", normalized_path])
        result = self._run(root=root, args=args)
        return {"path": normalized_path, "staged": staged, "diff": result.stdout}

    def get_history(self, *, user_id: str, limit: int | None = None) -> dict[str, Any]:
        """返回提交历史、未推送提交及其涉及的文件。"""

        root = self._require_root_repository(user_id=user_id)
        limits = self.config.limits
        safe_limit = max(
            limits.nonempty_min_length,
            min(int(limit or limits.api_default_list_limit), limits.api_max_list_limit),
        )
        history = self._log(root=root, revision="", limit=safe_limit)
        upstream = self._upstream(root=root)
        if upstream:
            unpushed = self._log(root=root, revision=f"{upstream}..HEAD", limit=safe_limit)
            unpushed_files = self._diff_name_status(root=root, revision=f"{upstream}..HEAD")
        elif self._has_head(root=root):
            unpushed = history
            unpushed_files = self._tracked_files(root=root)
        else:
            unpushed = []
            unpushed_files = []
        return {
            "history": history,
            "unpushed_commits": unpushed,
            "unpushed_files": unpushed_files,
            "upstream": upstream,
        }

    def restore_paths(self, *, user_id: str, paths: list[str]) -> dict[str, Any]:
        """
        回滚选中文件。

        已跟踪文件恢复到 HEAD 并提前清理旧索引。未跟踪文件没有 Git 历史,因此通过
        MetaWeave 最近删除机制移动到可恢复垃圾区,不会调用 `git clean`。
        """

        root = self._require_root_repository(user_id=user_id)
        normalized_paths = self._validate_paths(root=root, paths=paths)
        if not normalized_paths:
            raise GitServiceError("至少选择一个需要回滚的文件。")
        status = self.get_status(user_id=user_id)
        untracked_set = {str(item["path"]) for item in status["untracked"]}
        added_set = {
            str(item["path"])
            for item in status["changes"]
            if item.get("state") == "added"
        }
        tracked_paths = [
            path
            for path in normalized_paths
            if path not in untracked_set and path not in added_set
        ]
        untracked_paths = [
            path
            for path in normalized_paths
            if path in untracked_set or path in added_set
        ]
        with self._mutation_lock:
            if tracked_paths:
                self.knowledge_library_service.invalidate_paths(
                    user_id=user_id,
                    relative_paths=tracked_paths,
                )
                self._run(
                    root=root,
                    args=["restore", "--staged", "--worktree", "--", *tracked_paths],
                    check=False,
                )
                worktree_result = self._run(
                    root=root,
                    args=["restore", "--worktree", "--", *tracked_paths],
                    check=False,
                )
                if worktree_result.returncode != 0:
                    raise GitServiceError(self._error_message(worktree_result))
            staged_additions = [path for path in untracked_paths if path in added_set]
            if staged_additions:
                self._run(
                    root=root,
                    args=["restore", "--staged", "--", *staged_additions],
                    check=False,
                )
            for path in untracked_paths:
                self.knowledge_library_service.delete_path(user_id=user_id, path=path)
        return {
            "ok": True,
            "restored": tracked_paths,
            "trashed": untracked_paths,
            "status": self.get_status(user_id=user_id),
        }

    def commit(self, *, user_id: str, paths: list[str], message: str) -> dict[str, Any]:
        """暂存选中文件并创建提交,不自动推送。"""

        root = self._require_root_repository(user_id=user_id)
        normalized_paths = self._validate_paths(root=root, paths=paths)
        summary = str(message or "").strip()
        if not normalized_paths:
            raise GitServiceError("提交前至少选择一个文件。")
        if not summary:
            raise GitServiceError("提交概要不能为空。")
        with self._mutation_lock:
            self._run(root=root, args=["add", "--", *normalized_paths])
            staged = self._run(
                root=root,
                args=["diff", "--cached", "--quiet", "--", *normalized_paths],
                check=False,
            )
            if staged.returncode == 0:
                raise GitServiceError("选中文件没有可提交的内容。")
            if staged.returncode not in {0, 1}:
                raise GitServiceError(self._error_message(staged))
            # `--only` 使提交范围由复选框路径决定，保留用户此前暂存但未选择的内容。
            self._run(root=root, args=["commit", "--only", "-m", summary, "--", *normalized_paths])
            commit_hash = self._run(root=root, args=["rev-parse", "HEAD"]).stdout.strip()
        return {
            "ok": True,
            "commit": commit_hash,
            "short_commit": commit_hash[:self.config.limits.checksum_short_chars],
            "summary": summary,
            "status": self.get_status(user_id=user_id),
        }

    def push(
        self,
        *,
        user_id: str,
        local_branch: str,
        remote: str,
        remote_branch: str,
        force_with_lease: bool = False,
        set_upstream: bool = True,
        all_branches: bool = False,
    ) -> dict[str, Any]:
        """推送当前映射或全部本地分支；高风险覆盖只允许 `--force-with-lease`。"""

        root = self._require_root_repository(user_id=user_id)
        local = self._validate_branch_name(local_branch)
        destination = self._validate_branch_name(remote_branch)
        remote_name = self._validate_remote_name(remote)
        if remote_name not in self._remotes(root=root):
            raise GitServiceError(f"远程仓库不存在: {remote_name}")
        args = ["push"]
        if force_with_lease:
            args.append("--force-with-lease")
        if all_branches:
            args.extend(["--all", remote_name])
        else:
            if set_upstream:
                args.append("--set-upstream")
            args.extend([remote_name, f"{local}:{destination}"])
        with self._mutation_lock:
            result = self._run(root=root, args=args, timeout=self.config.limits.git_network_timeout_seconds)
            if all_branches:
                # `git push --all` 不会自动建立 tracking 关系。为每个同名远程
                # 分支补齐 upstream，确保“未推送提交”预览在成功后立即归零。
                for branch in self._branches(root=root):
                    branch_name = str(branch["name"])
                    self._run(
                        root=root,
                        args=[
                            "branch",
                            f"--set-upstream-to={remote_name}/{branch_name}",
                            branch_name,
                        ],
                        check=False,
                    )
        return {
            "ok": True,
            "local_branch": local,
            "remote": remote_name,
            "remote_branch": destination,
            "force_with_lease": force_with_lease,
            "all_branches": all_branches,
            "output": (result.stdout or result.stderr).strip(),
            "status": self.get_status(user_id=user_id),
        }

    def create_branch(self, *, user_id: str, name: str, checkout: bool = True) -> dict[str, Any]:
        """创建本地分支,可选择立即切换。"""

        root = self._require_root_repository(user_id=user_id)
        branch = self._validate_branch_name(name)
        args = ["switch", "-c", branch] if checkout else ["branch", branch]
        with self._mutation_lock:
            self._run(root=root, args=args)
        return self.get_status(user_id=user_id)

    def add_remote(self, *, user_id: str, name: str, url: str) -> dict[str, Any]:
        """为当前知识库仓库新增命名远程并返回最新结构化状态。"""

        root = self._require_root_repository(user_id=user_id)
        remote_name = self._validate_remote_name(name)
        remote_url = self._validate_remote_url(url)
        if remote_name in self._remotes(root=root):
            raise GitServiceError(f"远程仓库已存在: {remote_name}")
        with self._mutation_lock:
            self._run(root=root, args=["remote", "add", remote_name, remote_url])
        return self.get_status(user_id=user_id)

    def switch_branch(self, *, user_id: str, name: str) -> dict[str, Any]:
        """切换分支并使所有实际可能改变的知识文件索引失效。"""

        root = self._require_root_repository(user_id=user_id)
        branch = self._validate_branch_name(name)
        affected = self._diff_paths_between(root=root, left="HEAD", right=branch)
        affected.extend(
            str(item["path"])
            for item in self.get_status(user_id=user_id)["changes"]
        )
        normalized_affected = sorted(set(affected))
        with self._mutation_lock:
            if normalized_affected:
                self.knowledge_library_service.invalidate_paths(
                    user_id=user_id,
                    relative_paths=normalized_affected,
                )
            self._run(root=root, args=["switch", branch])
        return self.get_status(user_id=user_id)

    def pull_fast_forward(
        self,
        *,
        user_id: str,
        remote: str,
        branch: str,
    ) -> dict[str, Any]:
        """获取并快进合并远程分支,拒绝自动制造合并提交。"""

        root = self._require_root_repository(user_id=user_id)
        remote_name = self._validate_remote_name(remote)
        branch_name = self._validate_branch_name(branch)
        with self._mutation_lock:
            self._run(
                root=root,
                args=["fetch", remote_name, branch_name],
                timeout=self.config.limits.git_network_timeout_seconds,
            )
            affected = self._diff_paths_between(root=root, left="HEAD", right="FETCH_HEAD")
            if affected:
                self.knowledge_library_service.invalidate_paths(
                    user_id=user_id,
                    relative_paths=affected,
                )
            self._run(root=root, args=["merge", "--ff-only", "FETCH_HEAD"])
        return self.get_status(user_id=user_id)

    def _root(self, *, user_id: str) -> Path:
        """解析并返回当前 active 知识库根目录。"""

        return self.knowledge_library_service.get_active_root_path(user_id=user_id).resolve()

    def _require_root_repository(self, *, user_id: str) -> Path:
        """返回已初始化且根目录与知识库完全一致的仓库。"""

        root = self._root(user_id=user_id)
        repository_root = self._repository_root(root=root)
        if repository_root is None:
            raise GitServiceError("当前知识库尚未初始化 Git 仓库。")
        self._ensure_repository_matches_knowledge_root(root=root, repository_root=repository_root)
        return root

    def _repository_root(self, *, root: Path) -> Path | None:
        """
        检测知识库根目录自身是否为 Git 工作树根。

        `git rev-parse` 会向父目录寻找仓库；父仓库不属于当前知识库的版本管理状态，
        因此按“未初始化”返回 None，允许用户在知识库根目录创建独立嵌套仓库。
        """

        result = self._run(
            root=root,
            args=["rev-parse", "--show-toplevel"],
            check=False,
        )
        if result.returncode != 0:
            return None
        raw_root = result.stdout.strip()
        repository_root = Path(raw_root).resolve() if raw_root else None
        if repository_root is None:
            return None
        if os.path.normcase(str(root)) != os.path.normcase(str(repository_root)):
            return None
        return repository_root

    @staticmethod
    def _ensure_repository_matches_knowledge_root(*, root: Path, repository_root: Path) -> None:
        """拒绝把知识库父目录仓库误当成当前知识库仓库。"""

        if os.path.normcase(str(root)) != os.path.normcase(str(repository_root)):
            raise GitServiceError("Git 仓库根目录必须与当前知识库根目录一致。")

    @staticmethod
    def _empty_status(*, root: Path) -> dict[str, Any]:
        """构造未初始化仓库的稳定响应。"""

        return {
            "initialized": False,
            "repository_root": str(root),
            "current_branch": "",
            "upstream": "",
            "ahead": 0,
            "behind": 0,
            "detached": False,
            "branches": [],
            "remote_branches": [],
            "remotes": [],
            "changes": [],
            "untracked": [],
            "ignored": [],
            "has_changes": False,
        }

    def _run(
        self,
        *,
        root: Path,
        args: list[str],
        check: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """以 UTF-8、无 shell、非交互模式运行 Git。"""

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["LC_ALL"] = "C.UTF-8"
        timeout = timeout or self.config.limits.git_command_timeout_seconds
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise GitServiceError("系统未安装 Git 或 Git 不在 PATH 中。") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitServiceError("Git 操作超时,请检查仓库或远程连接。") from exc
        if check and result.returncode != 0:
            raise GitServiceError(self._error_message(result))
        return result

    @staticmethod
    def _error_message(result: subprocess.CompletedProcess[str]) -> str:
        """从 Git 标准错误与标准输出提取稳定错误信息。"""

        message = (result.stderr or result.stdout or "Git 操作失败").strip()
        return message[-4000:]

    def _parse_porcelain_status(self, output: str) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
    ]:
        """解析 `git status --porcelain=v1 -z --branch --ignored` 输出。"""

        fields = output.split("\0")
        changes: list[dict[str, Any]] = []
        untracked: list[dict[str, Any]] = []
        ignored: list[dict[str, Any]] = []
        index = 0
        while index < len(fields):
            field = fields[index]
            index += 1
            if not field or field.startswith("## "):
                continue
            if len(field) < 4:
                continue
            code = field[:2]
            path = field[3:].replace("\\", "/")
            old_path = ""
            if code[0] in {"R", "C"} and index < len(fields):
                old_path = fields[index].replace("\\", "/")
                index += 1
            item = self._status_item(code=code, path=path, old_path=old_path)
            if code == "??":
                untracked.append(item)
            elif code == "!!":
                ignored.append(item)
            else:
                changes.append(item)
        changes.sort(key=lambda item: str(item["path"]).lower())
        untracked.sort(key=lambda item: str(item["path"]).lower())
        ignored.sort(key=lambda item: str(item["path"]).lower())
        return changes, untracked, ignored

    def _status_item(self, *, code: str, path: str, old_path: str = "") -> dict[str, Any]:
        """把 Git XY 状态码转换为前端可消费的语义状态。"""

        if code == "!!":
            parent = str(Path(path).parent).replace("\\", "/")
            return {
                "path": path,
                "name": Path(path).name,
                "directory": "" if parent == "." else parent,
                "old_path": old_path,
                "code": code,
                "state": "ignored",
                "staged": False,
                "working_tree": False,
            }
        if code == "??":
            state = "untracked"
        elif code in self._STATUS_CONFLICT_CODES:
            state = "conflicted"
        elif "D" in code:
            state = "deleted"
        elif "R" in code:
            state = "renamed"
        elif "A" in code:
            state = "added"
        else:
            state = "modified"
        parent = str(Path(path).parent).replace("\\", "/")
        return {
            "path": path,
            "name": Path(path).name,
            "directory": "" if parent == "." else parent,
            "old_path": old_path,
            "code": code,
            "state": state,
            "staged": code[0] not in {" ", "?"},
            "working_tree": code[1] not in {" ", "?"},
        }

    def _current_branch(self, *, root: Path) -> str:
        """读取当前本地分支,detached HEAD 返回空字符串。"""

        result = self._run(
            root=root,
            args=["symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _upstream(self, *, root: Path) -> str:
        """读取当前分支 upstream,未配置时返回空字符串。"""

        result = self._run(
            root=root,
            args=["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _ahead_behind(self, *, root: Path, upstream: str) -> tuple[int, int]:
        """计算 HEAD 相对 upstream 的领先与落后提交数。"""

        if not upstream:
            return 0, 0
        result = self._run(
            root=root,
            args=["rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
            check=False,
        )
        if result.returncode != 0:
            return 0, 0
        parts = result.stdout.strip().split()
        return (int(parts[0]), int(parts[1])) if len(parts) == 2 else (0, 0)

    def _branches(self, *, root: Path) -> list[dict[str, Any]]:
        """返回本地分支和各自 upstream。"""

        result = self._run(
            root=root,
            args=[
                "for-each-ref",
                "--format=%(refname:short)%00%(upstream:short)",
                "refs/heads",
            ],
            check=False,
        )
        current = self._current_branch(root=root)
        branches: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            name, _, upstream = line.partition("\0")
            if name:
                branches.append(
                    {
                        "name": name,
                        "upstream": upstream,
                        "current": name == current,
                    }
                )
        return branches

    def _remotes(self, *, root: Path) -> list[str]:
        """返回远程名称列表。"""

        result = self._run(root=root, args=["remote"], check=False)
        return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())

    def _remote_branches(self, *, root: Path) -> list[str]:
        """返回 `remote/branch` 形式的远程跟踪分支。"""

        result = self._run(
            root=root,
            args=["for-each-ref", "--format=%(refname:short)", "refs/remotes"],
            check=False,
        )
        return sorted(
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and not line.strip().endswith("/HEAD")
        )

    def _log(self, *, root: Path, revision: str, limit: int) -> list[dict[str, str]]:
        """读取机器可解析的提交历史。"""

        args = [
            "log",
            f"--max-count={limit}",
            "--date=iso-strict",
            "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1e",
        ]
        if revision:
            args.append(revision)
        result = self._run(root=root, args=args, check=False)
        if result.returncode != 0:
            return []
        commits: list[dict[str, str]] = []
        for record in result.stdout.split("\x1e"):
            fields = record.strip().split("\x1f")
            if len(fields) != 5:
                continue
            commits.append(
                {
                    "hash": fields[0],
                    "short_hash": fields[1],
                    "author": fields[2],
                    "date": fields[3],
                    "summary": fields[4],
                }
            )
        return commits

    def _diff_name_status(self, *, root: Path, revision: str) -> list[dict[str, str]]:
        """返回两个提交范围内涉及的文件。"""

        result = self._run(
            root=root,
            args=["diff", "--name-status", "-z", revision],
            check=False,
        )
        if result.returncode != 0:
            return []
        fields = result.stdout.split("\0")
        files: list[dict[str, str]] = []
        index = 0
        while index < len(fields):
            code = fields[index]
            index += 1
            if not code or index >= len(fields):
                continue
            path = fields[index].replace("\\", "/")
            index += 1
            if code.startswith(("R", "C")) and index < len(fields):
                path = fields[index].replace("\\", "/")
                index += 1
            files.append({"path": path, "status": code})
        return files

    def _tracked_files(self, *, root: Path) -> list[dict[str, str]]:
        """列出 HEAD 中的全部文件,用于尚未设置 upstream 的首次推送预览。"""

        result = self._run(
            root=root,
            args=["ls-tree", "-r", "--name-only", "-z", "HEAD"],
            check=False,
        )
        if result.returncode != 0:
            return []
        return [
            {"path": path.replace("\\", "/"), "status": "A"}
            for path in result.stdout.split("\0")
            if path
        ]

    def _has_head(self, *, root: Path) -> bool:
        """判断仓库是否已有首次提交。"""

        return self._run(
            root=root,
            args=["rev-parse", "--verify", "HEAD"],
            check=False,
        ).returncode == 0

    def _diff_paths_between(self, *, root: Path, left: str, right: str) -> list[str]:
        """返回两个树对象间会变化的相对路径。"""

        result = self._run(
            root=root,
            args=["diff", "--name-only", "-z", left, right],
            check=False,
        )
        if result.returncode != 0:
            raise GitServiceError(self._error_message(result))
        return sorted(path.replace("\\", "/") for path in result.stdout.split("\0") if path)

    def _validate_paths(self, *, root: Path, paths: list[str]) -> list[str]:
        """验证、去重并规范化用户选择的知识库相对路径。"""

        normalized = [self._validate_relative_path(root=root, path=path) for path in paths]
        return list(dict.fromkeys(path for path in normalized if path))

    @staticmethod
    def _validate_relative_path(*, root: Path, path: str) -> str:
        """拒绝绝对路径、父目录跳转和 VCS 元数据路径。"""

        normalized = str(path or "").replace("\\", "/").strip("/")
        if not normalized:
            raise GitServiceError("文件路径不能为空。")
        candidate = (root / normalized).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise GitServiceError("文件路径超出知识库根目录。") from exc
        if normalized == ".git" or normalized.startswith(".git/"):
            raise GitServiceError("禁止直接操作 Git 内部元数据。")
        return normalized

    def _validate_branch_name(self, value: str) -> str:
        """校验分支名并拒绝可被 Git 解释为选项的输入。"""

        name = str(value or "").strip()
        if not name or name.startswith("-") or not self._BRANCH_NAME_PATTERN.fullmatch(name):
            raise GitServiceError("分支名称无效。")
        return name

    @staticmethod
    def _validate_remote_name(value: str) -> str:
        """校验远程名称。"""

        name = str(value or "").strip()
        if not name or name.startswith("-") or not re.fullmatch(r"[A-Za-z0-9._/-]+", name):
            raise GitServiceError("远程名称无效。")
        return name

    @staticmethod
    def _validate_remote_url(value: str) -> str:
        """校验远程 URL 或本地仓库路径,拒绝选项注入与控制字符。"""

        url = str(value or "").strip()
        if (
            not url
            or len(url) > DEFAULT_BUSINESS_LIMITS.large_text_max_length
            or url.startswith("-")
            or any(character in url for character in {"\0", "\r", "\n"})
        ):
            raise GitServiceError("远程仓库地址无效。")
        return url

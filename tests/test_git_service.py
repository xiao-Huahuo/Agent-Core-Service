"""
Git 领域服务回归测试。

使用说明:
测试使用临时知识库仓库和本地 bare remote,不访问网络。重点验证状态解析、提交、
回滚、推送以及所有会改变文件内容的操作都会经过知识库索引失效入口。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from agent_service.services.git_service import GitService


class _KnowledgeServiceStub:
    """提供 GitService 所需的知识库根目录和索引失效记录。"""

    def __init__(self, root: Path) -> None:
        """保存临时仓库根目录。"""

        self.root = root
        self.invalidated: list[list[str]] = []
        self.trashed: list[str] = []

    def get_active_root_path(self, *, user_id: str) -> Path:
        """返回当前测试知识库目录。"""

        return self.root

    def invalidate_paths(self, *, user_id: str, relative_paths: list[str]) -> dict[str, int]:
        """记录应失效的来源路径。"""

        self.invalidated.append(list(relative_paths))
        return {"files_invalidated": len(relative_paths), "chunks_deleted": len(relative_paths)}

    def delete_path(self, *, user_id: str, path: str) -> dict[str, object]:
        """模拟 MetaWeave 最近删除,并真实移除临时文件。"""

        self.trashed.append(path)
        (self.root / path).unlink()
        return {"ok": True}


def _git(root: Path, *args: str) -> str:
    """在临时仓库执行确定性的测试 Git 命令。"""

    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _service(tmp_path: Path) -> tuple[GitService, _KnowledgeServiceStub, Path]:
    """创建带首次提交的临时知识库仓库。"""

    root = tmp_path / "knowledge"
    root.mkdir()
    knowledge_service = _KnowledgeServiceStub(root)
    service = GitService(knowledge_library_service=knowledge_service)
    service.initialize_repository(user_id="user-1", initial_branch="main")
    _git(root, "config", "user.name", "MetaWeave Test")
    _git(root, "config", "user.email", "test@metaweave.local")
    tracked = root / "tracked.md"
    tracked.write_text("version one", encoding="utf-8")
    _git(root, "add", "tracked.md")
    _git(root, "commit", "-m", "initial")
    return service, knowledge_service, root


def test_status_groups_tracked_and_untracked_files(tmp_path: Path) -> None:
    """状态接口应分别返回更改与未跟踪文件。"""

    service, _knowledge_service, root = _service(tmp_path)
    (root / "tracked.md").write_text("version two", encoding="utf-8")
    (root / "new.md").write_text("new", encoding="utf-8")

    status = service.get_status(user_id="user-1")

    assert status["initialized"] is True
    assert [item["path"] for item in status["changes"]] == ["tracked.md"]
    assert [item["path"] for item in status["untracked"]] == ["new.md"]
    assert status["current_branch"] == "main"


def test_restore_invalidates_tracked_source_and_trashes_untracked_file(tmp_path: Path) -> None:
    """回滚必须清理旧索引,未跟踪文件则走可恢复的最近删除。"""

    service, knowledge_service, root = _service(tmp_path)
    (root / "tracked.md").write_text("changed", encoding="utf-8")
    (root / "new.md").write_text("new", encoding="utf-8")

    result = service.restore_paths(
        user_id="user-1",
        paths=["tracked.md", "new.md"],
    )

    assert (root / "tracked.md").read_text(encoding="utf-8") == "version one"
    assert not (root / "new.md").exists()
    assert knowledge_service.invalidated == [["tracked.md"]]
    assert knowledge_service.trashed == ["new.md"]
    assert result["restored"] == ["tracked.md"]
    assert result["trashed"] == ["new.md"]


def test_commit_and_push_to_local_remote(tmp_path: Path) -> None:
    """选中文件可提交并推送到指定远程分支。"""

    service, _knowledge_service, root = _service(tmp_path)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    _git(root, "remote", "add", "origin", str(remote))
    (root / "tracked.md").write_text("committed content", encoding="utf-8")

    commit_result = service.commit(
        user_id="user-1",
        paths=["tracked.md"],
        message="update tracked note",
    )
    push_result = service.push(
        user_id="user-1",
        local_branch="main",
        remote="origin",
        remote_branch="main",
    )

    assert commit_result["summary"] == "update tracked note"
    assert push_result["ok"] is True
    assert _git(root, "rev-parse", "HEAD") == _git(remote, "rev-parse", "refs/heads/main")


def test_push_all_publishes_every_local_branch(tmp_path: Path) -> None:
    """选择“所有”推送范围时应把全部本地分支发布到远程。"""

    service, _knowledge_service, root = _service(tmp_path)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    _git(root, "remote", "add", "origin", str(remote))
    service.create_branch(user_id="user-1", name="notes", checkout=False)

    push_result = service.push(
        user_id="user-1",
        local_branch="main",
        remote="origin",
        remote_branch="main",
        all_branches=True,
    )

    assert push_result["all_branches"] is True
    assert push_result["status"]["upstream"] == "origin/main"
    assert _git(remote, "rev-parse", "refs/heads/main")
    assert _git(remote, "rev-parse", "refs/heads/notes")


def test_commit_does_not_include_unselected_staged_file(tmp_path: Path) -> None:
    """复选框提交范围不能夹带之前已暂存但未选择的文件。"""

    service, _knowledge_service, root = _service(tmp_path)
    selected = root / "selected.md"
    selected.write_text("initial", encoding="utf-8")
    _git(root, "add", "selected.md")
    _git(root, "commit", "-m", "add selected")
    (root / "tracked.md").write_text("staged but unselected", encoding="utf-8")
    _git(root, "add", "tracked.md")
    selected.write_text("selected change", encoding="utf-8")

    service.commit(
        user_id="user-1",
        paths=["selected.md"],
        message="only selected",
    )

    assert _git(root, "show", "--pretty=", "--name-only", "HEAD") == "selected.md"
    assert _git(root, "diff", "--cached", "--name-only") == "tracked.md"


def test_commit_accepts_selected_untracked_file(tmp_path: Path) -> None:
    """未进行版本管理的文件被勾选后应可直接加入提交。"""

    service, _knowledge_service, root = _service(tmp_path)
    (root / "new-note.md").write_text("new note", encoding="utf-8")

    service.commit(
        user_id="user-1",
        paths=["new-note.md"],
        message="add note",
    )

    assert _git(root, "show", "--pretty=", "--name-only", "HEAD") == "new-note.md"


def test_parent_repository_does_not_count_as_knowledge_repository(tmp_path: Path) -> None:
    """父目录仓库不能阻止知识库显示未初始化状态并创建独立仓库。"""

    parent = tmp_path / "parent"
    parent.mkdir()
    subprocess.run(["git", "init", str(parent)], check=True, capture_output=True)
    knowledge_root = parent / "knowledge"
    knowledge_root.mkdir()
    knowledge_service = _KnowledgeServiceStub(knowledge_root)
    service = GitService(knowledge_library_service=knowledge_service)

    status_before_init = service.get_status(user_id="user-1")
    status_after_init = service.initialize_repository(user_id="user-1", initial_branch="main")

    assert status_before_init["initialized"] is False
    assert status_after_init["initialized"] is True
    assert Path(status_after_init["repository_root"]) == knowledge_root.resolve()


def test_add_remote_registers_new_remote_repository(tmp_path: Path) -> None:
    """新增远程仓库应写入 Git 配置并立即出现在结构化状态中。"""

    service, _knowledge_service, root = _service(tmp_path)
    remote = tmp_path / "new-origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    status = service.add_remote(
        user_id="user-1",
        name="new-origin",
        url=str(remote),
    )

    assert status["remotes"] == ["new-origin"]
    assert _git(root, "remote", "get-url", "new-origin") == str(remote)

"""
Agent 终端沙盒测试。

功能说明:
验证结构化终端指令段只能在工作区内执行,路径参数会被解析并阻止越界。
"""

from pathlib import Path

import pytest
from sqlmodel import SQLModel, create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.settings_service import SettingsService
from agent_service.services.terminal.command_sandbox import TerminalSandbox, TerminalSandboxSettings


def _build_settings(workspace_root: Path) -> TerminalSandboxSettings:
    """创建测试用终端沙盒配置。"""

    config = AgentConfig.load_config(
        {
            "terminal_sandbox": {
                "enabled": True,
                "default_workspace_root": str(workspace_root),
                "allowed_programs": {"cmd": ["python"], "powershell": ["python"], "bash": ["python"]},
                "default_timeout_seconds": 10,
                "max_timeout_seconds": 10,
                "max_output_chars": 4000,
                "max_segments_per_call": 2,
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )
    return TerminalSandboxSettings.from_config_payload(config=config)


def test_terminal_sandbox_runs_allowed_structured_segment(tmp_path: Path) -> None:
    """允许的结构化外部程序段应能在工作区内执行。"""

    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    result = sandbox.run(
        shell="cmd",
        cwd=".",
        segments=[{"program": "python", "args": ["--version"]}],
    )

    assert result["ok"] is True
    assert result["results"][0]["exit_code"] == 0
    assert "Python" in result["results"][0]["stdout"]


def test_terminal_sandbox_blocks_cwd_escape(tmp_path: Path) -> None:
    """cwd 不能通过相对路径跳出工作区。"""

    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    with pytest.raises(ValueError, match="不在终端沙盒工作区内"):
        sandbox.run(
            shell="cmd",
            cwd="..",
            segments=[{"program": "python", "args": ["--version"]}],
        )


def test_terminal_sandbox_blocks_path_argument_escape(tmp_path: Path) -> None:
    """参数中出现的路径必须留在工作区内。"""

    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))
    outside_file = tmp_path.parent / "outside.txt"

    with pytest.raises(ValueError, match="不在终端沙盒工作区内"):
        sandbox.run(
            shell="cmd",
            cwd=".",
            segments=[{"program": "python", "args": ["-m", "pytest", str(outside_file)]}],
        )


def test_terminal_sandbox_runs_internal_list_command(tmp_path: Path) -> None:
    """内部 ls/dir 指令应能列出工作区内目录且不依赖系统 shell。"""

    (tmp_path / "alpha.txt").write_text("hello", encoding="utf-8")
    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    result = sandbox.run(
        shell="cmd",
        cwd=".",
        segments=[{"type": "internal_command", "command": "ls", "args": ["."]}],
    )

    assert result["ok"] is True
    assert "alpha.txt" in result["results"][0]["stdout"]


def test_terminal_sandbox_internal_list_command_parses_flags(tmp_path: Path) -> None:
    """内部 ls/dir 指令应解析常见选项,不能把 -la 当成路径。"""

    (tmp_path / ".secret").write_text("hidden", encoding="utf-8")
    (tmp_path / "alpha.txt").write_text("hello", encoding="utf-8")
    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    result = sandbox.run(
        shell="cmd",
        cwd=".",
        segments=[{"type": "internal_command", "command": "ls", "args": ["-la", "."]}],
    )

    assert result["ok"] is True
    assert ".secret" in result["results"][0]["stdout"]
    assert "alpha.txt" in result["results"][0]["stdout"]


def test_terminal_sandbox_runs_internal_cat_command_with_path(tmp_path: Path) -> None:
    """内部 cat/type 指令应把普通参数解析为文件路径。"""

    (tmp_path / "foo.txt").write_text("read me", encoding="utf-8")
    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    result = sandbox.run(
        shell="cmd",
        cwd=".",
        segments=[{"type": "internal_command", "command": "cat", "args": ["foo.txt"]}],
    )

    assert result["ok"] is True
    assert result["results"][0]["stdout"] == "read me"


def test_terminal_sandbox_runs_internal_head_command(tmp_path: Path) -> None:
    """内部 head 指令应按行读取工作区内文本文件。"""

    (tmp_path / "notes.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    result = sandbox.run(
        shell="cmd",
        cwd=".",
        segments=[{"type": "internal_command", "command": "head", "args": ["-n", "2", "notes.txt"]}],
    )

    assert result["ok"] is True
    assert result["results"][0]["stdout"] == "one\ntwo"


def test_terminal_sandbox_blocks_internal_command_path_escape(tmp_path: Path) -> None:
    """内部系统指令的路径参数仍必须留在工作区内。"""

    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    with pytest.raises(ValueError, match="不在终端沙盒工作区内"):
        sandbox.run(
            shell="cmd",
            cwd=".",
            segments=[{"type": "internal_command", "command": "cat", "args": ["../outside.txt"]}],
        )


def test_terminal_sandbox_blocks_nested_shell_program(tmp_path: Path) -> None:
    """即使写入 allowlist,嵌套 shell 程序仍会被全局 denylist 拦截。"""

    config = AgentConfig.load_config(
        {
            "terminal_sandbox": {
                "enabled": True,
                "default_workspace_root": str(tmp_path),
                "allowed_programs": {"cmd": ["cmd"], "powershell": [], "bash": []},
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )
    sandbox = TerminalSandbox(settings=TerminalSandboxSettings.from_config_payload(config=config))

    with pytest.raises(ValueError, match="被沙盒禁止"):
        sandbox.run(shell="cmd", cwd=".", segments=[{"program": "cmd", "args": ["/c", "dir"]}])


def test_terminal_sandbox_blocks_python_inline_code(tmp_path: Path) -> None:
    """解释器内联代码参数不能绕过结构化命令和路径沙盒。"""

    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    with pytest.raises(ValueError, match="内联代码"):
        sandbox.run(shell="cmd", cwd=".", segments=[{"program": "python", "args": ["-c", "print('bad')"]}])


def test_terminal_sandbox_allows_expanded_readonly_tooling(tmp_path: Path) -> None:
    """新增的诊断工具子命令应覆盖 Codex 常用读取和检查场景。"""

    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    sandbox._validate_git_args(args=["grep", "TODO"])
    sandbox._validate_pip_args(args=["list"])
    sandbox._validate_package_manager_args(args=["run", "type-check"], manager="npm")


def test_terminal_sandbox_blocks_dependency_mutation_commands(tmp_path: Path) -> None:
    """扩展命令后仍应禁止安装、卸载和未登记脚本。"""

    sandbox = TerminalSandbox(settings=_build_settings(tmp_path))

    with pytest.raises(ValueError, match="pip 只允许"):
        sandbox._validate_pip_args(args=["install", "requests"])
    with pytest.raises(ValueError, match="npm 只允许"):
        sandbox._validate_package_manager_args(args=["run", "deploy"], manager="npm")


def test_terminal_sandbox_upgrades_unmodified_legacy_allowlist(tmp_path: Path) -> None:
    """历史保存的旧默认 allowlist 应自动扩展到当前默认命令集。"""

    config = AgentConfig.load_config(
        {"terminal_sandbox": {"enabled": True, "default_workspace_root": str(tmp_path)}},
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )

    settings = TerminalSandboxSettings.from_config_payload(
        config=config,
        payload={
            "allowed_programs": {
                "cmd": ["python", "pytest", "git", "npm", "node", "where"],
                "powershell": ["python", "pytest", "git", "npm", "node"],
                "bash": ["python", "pytest", "git", "npm", "node", "which"],
            }
        },
    )

    assert "rg" in settings.allowed_programs["cmd"]
    assert "vue-tsc" in settings.allowed_programs["powershell"]
    assert "cargo" in settings.allowed_programs["bash"]


def test_terminal_sandbox_defaults_to_active_knowledge_dir(tmp_path: Path) -> None:
    """用户终端沙盒的旧项目根工作区应迁移到当前 active 知识库目录。"""

    project_root = tmp_path / "MetaWeave"
    knowledge_dir = tmp_path / "knowledge"
    project_root.mkdir()
    knowledge_dir.mkdir()
    config = AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(project_root),
                "knowledge_dir": str(project_root / "resources" / "knowledge"),
            },
            "terminal_sandbox": {
                "enabled": True,
                "default_workspace_root": str(project_root),
            },
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    settings_service = SettingsService(config=config, memory_service=memory_service)

    settings_service.update_knowledge_dir(user_id="user_terminal", knowledge_dir=str(knowledge_dir))
    settings_service.save_terminal_sandbox_config(
        user_id="user_terminal",
        config_payload={"enabled": True, "workspace_root": str(project_root)},
    )
    payload = settings_service.get_terminal_sandbox_config(user_id="user_terminal")

    assert Path(payload["config"]["workspace_root"]) == knowledge_dir.resolve()

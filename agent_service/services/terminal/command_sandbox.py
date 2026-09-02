"""
Agent 终端命令沙盒。

功能说明:
本文件实现非交互式终端指令段的安全校验与执行。Agent 只能提交结构化
`shell + cwd + segments` 参数,不能提交整条 shell 字符串。执行阶段使用
`subprocess.run(..., shell=False)`,避免 shell 注入。

使用说明:
通过 `TerminalSandboxSettings.from_config_payload()` 合并进程默认值和用户设置,
再创建 `TerminalSandbox(settings=...)` 调用 `run()`。segment 支持
`external_program` 外部程序段和 `internal_command` 内部读写指令段;所有新增
指令都必须在本文件显式扩展 catalog、参数解析和路径权限校验。
"""

from __future__ import annotations

import glob as globmod
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_service.core.agent_config import AgentConfig
from agent_service.tools.runtime_context import AGENT_ACCESS_FULL, AGENT_ACCESS_READONLY, AGENT_ACCESS_SANDBOX

SUPPORTED_SHELLS = ("cmd", "powershell", "bash")
TERMINAL_ACCESS_MODES = {AGENT_ACCESS_READONLY, AGENT_ACCESS_SANDBOX, AGENT_ACCESS_FULL}
PATH_VALUE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]|[\\/]|^\.\.?($|[\\/])|^~[\\/]|[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}$")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
URL_SCHEMES = {"http", "https", "git", "ssh"}
SAFE_GIT_SUBCOMMANDS = {
    "blame",
    "branch",
    "describe",
    "diff",
    "grep",
    "log",
    "ls-files",
    "remote",
    "rev-parse",
    "show",
    "status",
    "tag",
}
SAFE_PACKAGE_SCRIPTS = {
    "build",
    "build-only",
    "check",
    "format",
    "format:check",
    "lint",
    "lint:eslint",
    "lint:oxlint",
    "test",
    "test:e2e",
    "test:unit",
    "type-check",
    "typecheck",
    "vitest",
}
SAFE_PYTHON_MODULES = {"compileall", "mypy", "pip", "py_compile", "pytest", "ruff"}
SAFE_PIP_SUBCOMMANDS = {"check", "freeze", "list", "show"}
SAFE_JS_EXEC_TOOLS = {"eslint", "playwright", "prettier", "tsc", "vite", "vitest", "vue-tsc"}
SAFE_GO_SUBCOMMANDS = {"build", "env", "fmt", "list", "test", "version", "vet"}
SAFE_CARGO_SUBCOMMANDS = {"build", "check", "clippy", "fmt", "metadata", "test", "version"}
SAFE_DOTNET_SUBCOMMANDS = {"build", "format", "test", "--info", "--list-sdks", "--version"}
SAFE_JAVA_BUILD_SUBCOMMANDS = {"compile", "package", "test", "verify"}
SCRIPT_SUFFIXES = {".cjs", ".js", ".jsx", ".mjs", ".py", ".ts", ".tsx"}
LEGACY_DEFAULT_ALLOWED_PROGRAMS = {
    "cmd": ["python", "pytest", "git", "npm", "node", "where", "find", "wc"],
    "powershell": ["python", "pytest", "git", "npm", "node", "find", "wc"],
    "bash": ["python", "pytest", "git", "npm", "node", "which", "find", "wc"],
}

COMMON_TERMINAL_PROGRAMS = [
    {"type": "external_program", "program": "python", "usage": "python -m pytest tests/test_x.py"},
    {"type": "external_program", "program": "py", "usage": "py -m pytest tests"},
    {"type": "external_program", "program": "pytest", "usage": "pytest tests"},
    {"type": "external_program", "program": "pip", "usage": "pip list / pip show package"},
    {"type": "external_program", "program": "pip3", "usage": "pip3 list / pip3 show package"},
    {"type": "external_program", "program": "uv", "usage": "uv --version / uv run pytest"},
    {"type": "external_program", "program": "ruff", "usage": "ruff check . / ruff format --check ."},
    {"type": "external_program", "program": "mypy", "usage": "mypy package_or_tests"},
    {"type": "external_program", "program": "pyright", "usage": "pyright"},
    {"type": "external_program", "program": "git", "usage": "git status / git diff / git grep"},
    {"type": "external_program", "program": "rg", "usage": "rg pattern path"},
    {"type": "external_program", "program": "grep", "usage": "grep -R pattern path"},
    {"type": "external_program", "program": "findstr", "usage": "findstr /S pattern *.py"},
    {"type": "external_program", "program": "npm", "usage": "npm test / npm run build"},
    {"type": "external_program", "program": "npx", "usage": "npx eslint . / npx vue-tsc --noEmit"},
    {"type": "external_program", "program": "pnpm", "usage": "pnpm test / pnpm run build"},
    {"type": "external_program", "program": "yarn", "usage": "yarn test / yarn run build"},
    {"type": "external_program", "program": "node", "usage": "node scripts/check.js"},
    {"type": "external_program", "program": "eslint", "usage": "eslint src"},
    {"type": "external_program", "program": "prettier", "usage": "prettier --check ."},
    {"type": "external_program", "program": "tsc", "usage": "tsc --noEmit"},
    {"type": "external_program", "program": "vue-tsc", "usage": "vue-tsc --noEmit"},
    {"type": "external_program", "program": "vite", "usage": "vite build"},
    {"type": "external_program", "program": "vitest", "usage": "vitest run"},
    {"type": "external_program", "program": "playwright", "usage": "playwright test"},
    {"type": "external_program", "program": "go", "usage": "go test ./..."},
    {"type": "external_program", "program": "cargo", "usage": "cargo test / cargo check"},
    {"type": "external_program", "program": "rustc", "usage": "rustc --version"},
    {"type": "external_program", "program": "dotnet", "usage": "dotnet test / dotnet build"},
    {"type": "external_program", "program": "java", "usage": "java --version"},
    {"type": "external_program", "program": "javac", "usage": "javac --version"},
    {"type": "external_program", "program": "mvn", "usage": "mvn test / mvn verify"},
    {"type": "external_program", "program": "gradle", "usage": "gradle test / gradle build"},
    {"type": "external_program", "program": "find", "usage": "find . -name '*.docx' -type f"},
    {"type": "external_program", "program": "wc", "usage": "wc -l file.txt / wc -c file.txt"},
]
COMMON_INTERNAL_COMMANDS = [
    {"type": "internal_command", "command": "pwd", "usage": "pwd"},
    {"type": "internal_command", "command": "ls", "usage": "ls -la . / ls src"},
    {"type": "internal_command", "command": "dir", "usage": "dir /a . / dir src"},
    {"type": "internal_command", "command": "cat", "usage": "cat README.md"},
    {"type": "internal_command", "command": "type", "usage": "type README.md"},
    {"type": "internal_command", "command": "head", "usage": "head -n 40 README.md"},
    {"type": "internal_command", "command": "tail", "usage": "tail -n 40 logs/app.log"},
    {"type": "internal_command", "command": "stat", "usage": "stat README.md"},
    {"type": "internal_command", "command": "wc", "usage": "wc README.md"},
    {"type": "internal_command", "command": "write", "usage": "write notes/todo.md content"},
    {"type": "internal_command", "command": "append", "usage": "append notes/todo.md content"},
    {"type": "internal_command", "command": "touch", "usage": "touch notes/todo.md"},
    {"type": "internal_command", "command": "mkdir", "usage": "mkdir notes"},
    {"type": "internal_command", "command": "rm", "usage": "rm notes/todo.md"},
    {"type": "internal_command", "command": "mv", "usage": "mv old.md new.md"},
    {"type": "internal_command", "command": "kill", "usage": "kill PID / taskkill /F /PID PID（仅完全访问）"},
]

DEFAULT_TERMINAL_SEGMENT_CATALOG: dict[str, list[dict[str, str]]] = {
    "cmd": [
        *COMMON_INTERNAL_COMMANDS,
        *COMMON_TERMINAL_PROGRAMS,
        {"type": "external_program", "program": "where", "usage": "where python"},
    ],
    "powershell": [
        *COMMON_INTERNAL_COMMANDS,
        *COMMON_TERMINAL_PROGRAMS,
        {"type": "external_program", "program": "where", "usage": "where python"},
    ],
    "bash": [
        *COMMON_INTERNAL_COMMANDS,
        *COMMON_TERMINAL_PROGRAMS,
        {"type": "external_program", "program": "which", "usage": "which python"},
    ],
}


@dataclass(slots=True)
class TerminalSandboxSettings:
    """Agent 终端沙盒运行设置。"""

    enabled: bool
    workspace_root: Path
    enabled_shells: list[str]
    allowed_programs: dict[str, list[str]]
    blocked_programs: list[str]
    default_timeout_seconds: int
    max_timeout_seconds: int
    max_output_chars: int
    max_segments_per_call: int
    read_default_lines: int
    read_max_lines: int

    @classmethod
    def from_config_payload(
        cls,
        *,
        config: AgentConfig,
        payload: dict[str, Any] | None = None,
    ) -> "TerminalSandboxSettings":
        """合并 AgentConfig 默认值与用户持久化沙盒配置。"""

        payload = payload or {}
        default_root = config.terminal_sandbox.default_workspace_root or str(config.storage.project_root)
        workspace_root = Path(str(payload.get("workspace_root") or default_root)).expanduser()
        enabled_shells = _normalize_shells(payload.get("enabled_shells") or config.terminal_sandbox.enabled_shells)
        raw_allowed_programs = payload.get("allowed_programs")
        if isinstance(raw_allowed_programs, dict):
            raw_allowed_programs = _upgrade_legacy_allowed_programs(
                raw_allowed_programs,
                config.terminal_sandbox.allowed_programs,
            )
        else:
            raw_allowed_programs = config.terminal_sandbox.allowed_programs
        allowed_programs = _normalize_allowed_programs(raw_allowed_programs)
        blocked_programs = _normalize_program_list(
            payload.get("blocked_programs") or config.terminal_sandbox.blocked_programs
        )
        return cls(
            enabled=bool(payload.get("enabled", config.terminal_sandbox.enabled)),
            workspace_root=workspace_root.resolve(),
            enabled_shells=enabled_shells,
            allowed_programs=allowed_programs,
            blocked_programs=blocked_programs,
            default_timeout_seconds=_clamp_int(
                payload.get("default_timeout_seconds"),
                default=config.terminal_sandbox.default_timeout_seconds,
                minimum=config.limits.terminal_timeout_min_seconds,
                maximum=config.terminal_sandbox.max_timeout_seconds,
            ),
            max_timeout_seconds=_clamp_int(
                payload.get("max_timeout_seconds"),
                default=config.terminal_sandbox.max_timeout_seconds,
                minimum=config.limits.terminal_timeout_min_seconds,
                maximum=config.limits.terminal_timeout_max_seconds,
            ),
            max_output_chars=_clamp_int(
                payload.get("max_output_chars"),
                default=config.terminal_sandbox.max_output_chars,
                minimum=config.limits.terminal_output_min_chars,
                maximum=config.limits.terminal_output_max_chars,
            ),
            max_segments_per_call=_clamp_int(
                payload.get("max_segments_per_call"),
                default=config.terminal_sandbox.max_segments_per_call,
                minimum=config.limits.terminal_segments_min_count,
                maximum=config.limits.terminal_segments_max_count,
            ),
            read_default_lines=config.limits.terminal_read_default_lines,
            read_max_lines=config.limits.terminal_read_max_lines,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化配置字典。"""

        return {
            "enabled": self.enabled,
            "workspace_root": str(self.workspace_root),
            "enabled_shells": self.enabled_shells,
            "allowed_programs": self.allowed_programs,
            "blocked_programs": self.blocked_programs,
            "default_timeout_seconds": self.default_timeout_seconds,
            "max_timeout_seconds": self.max_timeout_seconds,
            "max_output_chars": self.max_output_chars,
            "max_segments_per_call": self.max_segments_per_call,
        }


class TerminalSandbox:
    """执行结构化终端指令段的沙盒。"""

    def __init__(self, *, settings: TerminalSandboxSettings, access_mode: str = AGENT_ACCESS_SANDBOX) -> None:
        """保存已规范化的沙盒设置。"""

        self.settings = settings
        self.access_mode = access_mode if access_mode in TERMINAL_ACCESS_MODES else AGENT_ACCESS_SANDBOX

    def run(
        self,
        *,
        shell: str,
        cwd: str = ".",
        segments: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """执行一个或多个结构化指令段并返回汇总结果。"""

        if not self.settings.enabled:
            raise ValueError("Agent 终端沙盒未启用。")
        normalized_shell = shell.strip().lower()
        if normalized_shell not in self.settings.enabled_shells:
            raise ValueError(f"终端类型 {shell} 未启用。")
        safe_cwd = self._resolve_safe_path(cwd or ".")
        normalized_segments = self._normalize_segments(segments)
        timeout = self._resolve_timeout(timeout_seconds)

        results: list[dict[str, Any]] = []
        combined_output = ""
        for index, segment in enumerate(normalized_segments, 1):
            segment_type = str(segment["type"])
            program = str(segment.get("program") or segment.get("command") or "")
            args = [str(arg) for arg in segment.get("args", [])]
            if segment_type == "internal_command":
                self._validate_control_chars(args=args)
                result = self._run_internal_one(index=index, command=program, args=args, cwd=safe_cwd)
            else:
                if self.access_mode == AGENT_ACCESS_READONLY:
                    raise ValueError("只读权限下终端只允许执行 pwd、ls、dir、cat、type、head、tail、stat、wc 等内部读取指令。")
                if self.access_mode == AGENT_ACCESS_SANDBOX:
                    self._assert_path_in_workspace(safe_cwd)
                self._validate_program(shell=normalized_shell, program=program)
                self._validate_program_args(program=program, args=args, cwd=safe_cwd)
                self._validate_external_args(args=args, cwd=safe_cwd)
                result = self._run_one(index=index, program=program, args=args, cwd=safe_cwd, timeout=timeout)
            results.append(result)
            combined_output += result["stdout"] + result["stderr"]
            if result["exit_code"] != 0 or result["timed_out"]:
                break

        truncated = len(combined_output) > self.settings.max_output_chars
        return {
            "ok": bool(results and results[-1]["exit_code"] == 0 and not results[-1]["timed_out"]),
            "shell": normalized_shell,
            "cwd": str(safe_cwd),
            "results": results,
            "truncated": truncated or any(item["truncated"] for item in results),
        }

    def _normalize_segments(self, segments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """校验并规范化指令段列表。"""

        if not isinstance(segments, list) or not segments:
            raise ValueError("segments 必须是非空数组。")
        normalized: list[dict[str, Any]] = []
        for segment in segments:
            if not isinstance(segment, dict):
                raise ValueError("每个 segment 必须是对象。")
            segment_type = str(segment.get("type") or "external_program")
            if segment_type not in {"external_program", "internal_command"}:
                raise ValueError(f"暂不支持指令段类型 {segment_type}。")
            program = str(segment.get("program") or segment.get("command") or "").strip()
            if not program:
                raise ValueError("segment.program 或 segment.command 不能为空。")
            raw_args = segment.get("args") or []
            if not isinstance(raw_args, list):
                raise ValueError("segment.args 必须是数组。")
            normalized_segment = {"type": segment_type, "args": [str(arg) for arg in raw_args]}
            if segment_type == "internal_command":
                normalized_segment["command"] = _normalize_program_name(program)
            else:
                normalized_segment["program"] = program
            normalized.append(normalized_segment)
        return normalized

    def _resolve_timeout(self, timeout_seconds: int | None) -> int:
        """返回受最大值约束的执行超时时间。"""

        requested = timeout_seconds or self.settings.default_timeout_seconds
        try:
            value = int(requested)
        except (TypeError, ValueError):
            value = self.settings.default_timeout_seconds
        return max(1, min(value, self.settings.max_timeout_seconds))

    def _validate_program(self, *, shell: str, program: str) -> None:
        """校验程序段名称。

        完全访问模式: 仅检查嵌套 shell 黑名单,跳过程序白名单,允许任意外部程序。
        沙盒/只读模式: 同时检查嵌套 shell 黑名单和程序白名单。
        """

        normalized = _normalize_program_name(program)
        if normalized in set(self.settings.blocked_programs):
            raise ValueError(f"程序 {program} 被沙盒禁止。")
        if self.access_mode == AGENT_ACCESS_FULL:
            return
        allowed = set(self.settings.allowed_programs.get(shell, []))
        if normalized not in allowed:
            raise ValueError(f"{shell} 终端不支持程序段 {program}。")
        if _looks_like_path(program):
            self._resolve_safe_path(program)

    def _validate_external_args(self, *, args: list[str], cwd: Path) -> None:
        """校验外部程序参数,沙盒模式下路径仍不能越过工作区。"""

        self._validate_control_chars(args=args)
        for arg in args:
            for value in _extract_path_candidates(arg):
                path = Path(value).expanduser()
                if not path.is_absolute():
                    path = cwd / path
                if self.access_mode == AGENT_ACCESS_FULL:
                    path.resolve(strict=False)
                else:
                    self._assert_path_in_workspace(path)

    @staticmethod
    def _validate_control_chars(*, args: list[str]) -> None:
        """校验参数中没有不可见控制字符。"""

        for arg in args:
            if CONTROL_CHAR_PATTERN.search(arg):
                raise ValueError("参数中包含不可见控制字符。")

    def _validate_program_args(self, *, program: str, args: list[str], cwd: Path) -> None:
        """按程序类型限制高风险子命令和内联代码执行入口。

        完全访问模式跳过所有参数级限制,信任用户完全控制能力。
        """

        if self.access_mode == AGENT_ACCESS_FULL:
            return
        normalized_program = _normalize_program_name(program)
        if normalized_program in {"python", "python.exe", "py", "py.exe"}:
            self._validate_python_args(args=args, cwd=cwd)
            return
        if normalized_program in {"node", "node.exe"}:
            self._validate_node_args(args=args, cwd=cwd)
            return
        if normalized_program in {"git", "git.exe"}:
            self._validate_git_args(args=args)
            return
        if normalized_program in {"npm", "npm.cmd", "npm.exe"}:
            self._validate_package_manager_args(args=args, manager="npm")
            return
        if normalized_program in {"pnpm", "pnpm.cmd", "pnpm.exe", "yarn", "yarn.cmd", "yarn.exe"}:
            self._validate_package_manager_args(args=args, manager=normalized_program.split(".")[0])
            return
        if normalized_program in {"npx", "npx.cmd", "npx.exe"}:
            self._validate_npx_args(args=args)
            return
        if normalized_program in {"pip", "pip.exe", "pip3", "pip3.exe"}:
            self._validate_pip_args(args=args)
            return
        if normalized_program in {"uv", "uv.exe"}:
            self._validate_uv_args(args=args)
            return
        if normalized_program in {"ruff", "ruff.exe"}:
            self._validate_ruff_args(args=args)
            return
        if normalized_program in {"go", "go.exe"}:
            self._validate_go_args(args=args)
            return
        if normalized_program in {"cargo", "cargo.exe"}:
            self._validate_cargo_args(args=args)
            return
        if normalized_program in {"rustc", "rustc.exe"}:
            self._validate_version_only_args(args=args, program="rustc")
            return
        if normalized_program in {"dotnet", "dotnet.exe"}:
            self._validate_dotnet_args(args=args)
            return
        if normalized_program in {"java", "java.exe", "javac", "javac.exe"}:
            self._validate_java_args(args=args, program=normalized_program)
            return
        if normalized_program in {"mvn", "mvn.cmd", "mvn.exe", "gradle", "gradle.bat", "gradle.exe"}:
            self._validate_java_build_args(args=args, program=normalized_program.split(".")[0])

    def _validate_python_args(self, *, args: list[str], cwd: Path) -> None:
        """限制 Python 只能运行安全模块或工作区内脚本,禁止 `-c` 内联代码。"""

        if not args or args[0] in {"-V", "--version"}:
            return
        if args[0] in {"-c", "--command"}:
            raise ValueError("python 内联代码参数被沙盒禁止。")
        if args[0] == "-m":
            module_name = args[1] if len(args) > 1 else ""
            if module_name not in SAFE_PYTHON_MODULES:
                raise ValueError(f"python -m {module_name} 不在安全模块列表中。")
            if module_name == "pip":
                self._validate_pip_args(args=args[2:])
            if module_name == "ruff":
                self._validate_ruff_args(args=args[2:])
            return
        script_arg = _first_non_option_arg(args)
        if not script_arg:
            raise ValueError("python 只能执行工作区脚本、--version 或安全 -m 模块。")
        script_path = Path(script_arg).expanduser()
        if not script_path.is_absolute():
            script_path = cwd / script_path
        safe_path = self._assert_path_in_workspace(script_path)
        if safe_path.suffix.lower() != ".py":
            raise ValueError("python 脚本入口必须是工作区内 .py 文件。")

    def _validate_node_args(self, *, args: list[str], cwd: Path) -> None:
        """限制 Node.js 只能运行工作区脚本,禁止 `-e` 内联代码。"""

        if not args or args[0] in {"-v", "--version"}:
            return
        if args[0] in {"-e", "--eval", "-p", "--print"}:
            raise ValueError("node 内联代码参数被沙盒禁止。")
        script_arg = _first_non_option_arg(args)
        if not script_arg:
            raise ValueError("node 只能执行工作区内脚本或 --version。")
        script_path = Path(script_arg).expanduser()
        if not script_path.is_absolute():
            script_path = cwd / script_path
        safe_path = self._assert_path_in_workspace(script_path)
        if safe_path.suffix.lower() not in SCRIPT_SUFFIXES:
            raise ValueError("node 脚本入口必须是工作区内 JS/CJS/MJS 文件。")

    @staticmethod
    def _validate_git_args(*, args: list[str]) -> None:
        """限制 git 为只读/诊断子命令。"""

        subcommand = _first_non_option_arg(args)
        if not subcommand or subcommand not in SAFE_GIT_SUBCOMMANDS:
            raise ValueError("git 只允许 status、diff、log、show、branch、rev-parse、ls-files 等只读子命令。")

    @staticmethod
    @staticmethod
    def _validate_package_manager_args(*, args: list[str], manager: str) -> None:
        """限制 npm/pnpm/yarn 为常见测试、构建和检查脚本入口。"""

        if not args:
            raise ValueError(f"{manager} 必须指定 test 或 run <script>。")
        if args[0] in {"--version", "-v", "test"}:
            return
        if args[0] in {"exec", "dlx"} and len(args) > 1 and args[1] in SAFE_JS_EXEC_TOOLS:
            return
        if args[0] == "run" and len(args) > 1 and args[1] in SAFE_PACKAGE_SCRIPTS:
            return
        if manager == "yarn" and args[0] in SAFE_PACKAGE_SCRIPTS:
            return
        raise ValueError(f"{manager} 只允许 test、run 安全脚本或 exec 安全前端工具。")

    @staticmethod
    def _validate_npx_args(*, args: list[str]) -> None:
        """限制 npx 只能执行已列入安全清单的前端诊断工具。"""

        if not args or args[0] in {"--version", "-v"}:
            return
        tool_name = _normalize_program_name(_first_non_option_arg(args))
        if tool_name not in SAFE_JS_EXEC_TOOLS:
            raise ValueError("npx 只允许 eslint、prettier、tsc、vue-tsc、vite、vitest、playwright。")

    @staticmethod
    def _validate_pip_args(*, args: list[str]) -> None:
        """限制 pip 为只读包信息和环境检查,禁止安装或卸载依赖。"""

        if not args or args[0] in {"--version", "-V"}:
            return
        subcommand = _first_non_option_arg(args)
        if subcommand not in SAFE_PIP_SUBCOMMANDS:
            raise ValueError("pip 只允许 list、show、freeze、check 和 --version。")

    @staticmethod
    def _validate_uv_args(*, args: list[str]) -> None:
        """限制 uv 为版本查询、只读 pip 子命令或运行安全工具。"""

        if not args or args[0] in {"--version", "-V"}:
            return
        if args[0] == "pip":
            TerminalSandbox._validate_pip_args(args=args[1:])
            return
        if args[0] in {"run", "tool"} and len(args) > 1:
            nested_program = _normalize_program_name(_first_non_option_arg(args[1:]))
            if nested_program in SAFE_JS_EXEC_TOOLS or nested_program in SAFE_PYTHON_MODULES:
                return
        raise ValueError("uv 只允许 --version、pip 只读子命令、run/tool 安全工具。")

    @staticmethod
    def _validate_ruff_args(*, args: list[str]) -> None:
        """限制 ruff 为检查和格式化入口。"""

        if not args or args[0] in {"--version", "-V", "check", "format"}:
            return
        raise ValueError("ruff 只允许 check、format 和 --version。")

    @staticmethod
    def _validate_go_args(*, args: list[str]) -> None:
        """限制 go 为常见构建、测试、格式化和环境诊断子命令。"""

        subcommand = _first_non_option_arg(args)
        if not subcommand or subcommand not in SAFE_GO_SUBCOMMANDS:
            raise ValueError("go 只允许 build、test、vet、fmt、list、env、version。")

    @staticmethod
    def _validate_cargo_args(*, args: list[str]) -> None:
        """限制 cargo 为常见构建、测试、检查和格式化子命令。"""

        subcommand = _first_non_option_arg(args)
        if not subcommand or subcommand not in SAFE_CARGO_SUBCOMMANDS:
            raise ValueError("cargo 只允许 build、test、check、clippy、fmt、metadata、version。")

    @staticmethod
    def _validate_dotnet_args(*, args: list[str]) -> None:
        """限制 dotnet 为构建、测试、格式化和 SDK 信息查询。"""

        subcommand = _first_non_option_arg(args)
        if not subcommand or subcommand not in SAFE_DOTNET_SUBCOMMANDS:
            raise ValueError("dotnet 只允许 build、test、format、--info、--list-sdks、--version。")

    @staticmethod
    def _validate_java_args(*, args: list[str], program: str) -> None:
        """限制 java/javac 为版本查询或编译工作区内源码。"""

        if not args or args[0] in {"--version", "-version"}:
            return
        if program.startswith("javac"):
            return
        raise ValueError("java 只允许 --version 或 -version;运行类入口暂不开放。")

    @staticmethod
    def _validate_java_build_args(*, args: list[str], program: str) -> None:
        """限制 Maven/Gradle 为常见构建验证任务。"""

        subcommand = _first_non_option_arg(args)
        if not subcommand or subcommand not in SAFE_JAVA_BUILD_SUBCOMMANDS | {"build"}:
            raise ValueError(f"{program} 只允许 compile、test、verify、package、build。")

    @staticmethod
    def _validate_version_only_args(*, args: list[str], program: str) -> None:
        """限制单文件编译器为版本查询,避免沙盒外隐式产物。"""

        if not args or args[0] in {"--version", "-V", "-v"}:
            return
        raise ValueError(f"{program} 暂只允许版本查询。")

    def _resolve_safe_path(self, raw_path: str) -> Path:
        """按当前权限模式解析 cwd 或路径参数。"""

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = self.settings.workspace_root / path
        return self._assert_read_path_allowed(path)

    def _assert_read_path_allowed(self, raw_path: Path) -> Path:
        """按权限模式校验读取路径,三档权限均允许读取穿透。"""

        if self.access_mode in {AGENT_ACCESS_READONLY, AGENT_ACCESS_SANDBOX, AGENT_ACCESS_FULL}:
            return raw_path.resolve(strict=False)
        return self._assert_path_in_workspace(raw_path)

    def _assert_path_in_workspace(self, raw_path: Path) -> Path:
        """解析路径并确认它没有通过相对路径或链接跳出 workspace_root。"""

        workspace_root = self.settings.workspace_root.resolve()
        resolved = raw_path.resolve(strict=False)
        try:
            resolved.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(f"路径 {raw_path} 不在终端沙盒工作区内。") from exc
        existing = raw_path
        while not existing.exists() and existing != existing.parent:
            existing = existing.parent
        if existing.exists():
            existing_resolved = existing.resolve(strict=True)
            try:
                existing_resolved.relative_to(workspace_root)
            except ValueError as exc:
                raise ValueError(f"路径 {raw_path} 的真实位置不在终端沙盒工作区内。") from exc
        return resolved

    def _run_internal_one(self, *, index: int, command: str, args: list[str], cwd: Path) -> dict[str, Any]:
        """执行不依赖系统 shell 的内置基础系统指令。"""

        try:
            stdout = self._dispatch_internal_command(command=command, args=args, cwd=cwd)
            stderr = ""
            exit_code = 0
        except ValueError as exc:
            if "不在终端沙盒工作区内" in str(exc):
                raise
            stdout = ""
            stderr = str(exc)
            exit_code = -1
        stdout, stdout_truncated = _truncate(stdout, self.settings.max_output_chars)
        stderr, stderr_truncated = _truncate(stderr, self.settings.max_output_chars)
        return {
            "index": index,
            "program": command,
            "args": args,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "truncated": stdout_truncated or stderr_truncated,
        }

    def _dispatch_internal_command(self, *, command: str, args: list[str], cwd: Path) -> str:
        """按命令名分发内部系统指令。"""

        if command == "pwd":
            if args:
                raise ValueError("pwd 不接受参数。")
            return str(cwd)
        if command in {"ls", "dir"}:
            return self._internal_list_dir(args=args, cwd=cwd)
        if command in {"cat", "type"}:
            return self._internal_read_file(args=args, cwd=cwd)
        if command in {"head", "tail"}:
            return self._internal_read_file_lines(command=command, args=args, cwd=cwd)
        if command == "stat":
            return self._internal_stat(args=args, cwd=cwd)
        if command == "wc":
            return self._internal_wc(args=args, cwd=cwd)
        if command == "write":
            return self._internal_write_file(args=args, cwd=cwd, append=False)
        if command == "append":
            return self._internal_write_file(args=args, cwd=cwd, append=True)
        if command == "touch":
            return self._internal_touch(args=args, cwd=cwd)
        if command == "mkdir":
            return self._internal_mkdir(args=args, cwd=cwd)
        if command in {"rm", "del"}:
            return self._internal_remove(args=args, cwd=cwd)
        if command in {"mv", "move"}:
            return self._internal_move(args=args, cwd=cwd)
        if command in {"kill", "taskkill"}:
            return self._internal_kill(args=args)
        raise ValueError(f"不支持内部系统指令 {command}。")

    def _expand_glob_matches(self, raw_path: str, *, cwd: Path) -> list[Path] | None:
        """展开 glob 通配符匹配;不含通配符或无匹配时返回 None。"""
        if not any(ch in raw_path for ch in "*?["):
            return None
        search_path = raw_path if Path(raw_path).is_absolute() else str(cwd / raw_path)
        matches = [Path(p) for p in sorted(globmod.iglob(search_path, recursive=False))]
        if not matches:
            return None
        return [self._resolve_arg_path(str(m), cwd=cwd) for m in matches]

    def _internal_list_dir(self, *, args: list[str], cwd: Path) -> str:
        """列出工作区内目录内容,等价于基础 `ls/dir`。"""

        list_options = _parse_list_dir_args(args)
        targets: list[Path] = []
        for raw_path in list_options["paths"]:
            matched = self._expand_glob_matches(raw_path, cwd=cwd)
            if matched is None:
                target = self._resolve_arg_path(raw_path, cwd=cwd)
                if not target.exists():
                    raise ValueError(f"路径不存在: {target}")
                targets.append(target)
            else:
                targets.extend(matched)

        lines: list[str] = []
        for target in targets:
            if len(targets) > 1:
                lines.append(f"{target}:")
            self._list_dir_contents(target=target, options=list_options, lines=lines)
            if lines:
                lines.append("")
        return "\n".join(lines).rstrip("\n")

    def _list_dir_contents(self, *, target: Path, options: dict[str, Any], lines: list[str]) -> None:
        """递归列出目录内容。"""

        if not target.is_dir():
            lines.append(str(target))
            return

        children = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        for child in children:
            if not options["show_all"] and _is_hidden_path(child):
                continue
            if options["bare"]:
                lines.append(child.name)
                continue
            if options["long"]:
                stat = child.stat()
                kind = "dir " if child.is_dir() else "file"
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"{kind}\t{stat.st_size}\t{modified}\t{child.name}")
            else:
                lines.append(child.name + ("/" if child.is_dir() else ""))
            if options.get("recursive") and child.is_dir():
                self._list_dir_contents(target=child, options=options, lines=lines)

    def _internal_read_file(self, *, args: list[str], cwd: Path) -> str:
        """读取工作区内文本文件内容,等价于基础 `cat/type`。"""

        if not args:
            raise ValueError("cat/type 至少指定一个文件路径。")
        outputs = []
        for arg in args:
            target = self._resolve_arg_path(arg, cwd=cwd)
            self._assert_regular_file(target)
            outputs.append(target.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(outputs)

    def _internal_read_file_lines(self, *, command: str, args: list[str], cwd: Path) -> str:
        """读取工作区内文本文件的前 N 行或后 N 行。"""

        parsed = _parse_line_window_args(
            args,
            default_lines=self.settings.read_default_lines,
            max_lines=self.settings.read_max_lines,
        )
        results: list[str] = []
        for path_arg in parsed["paths"]:
            target = self._resolve_arg_path(path_arg, cwd=cwd)
            self._assert_regular_file(target)
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = lines[:parsed["lines"]] if command == "head" else lines[-parsed["lines"]:]
            if len(parsed["paths"]) > 1:
                results.append(f"==> {target} <==")
            results.append("\n".join(selected))
        return "\n".join(results)

    def _internal_stat(self, *, args: list[str], cwd: Path) -> str:
        """返回工作区内文件或目录的基础状态信息。"""

        if not args:
            raise ValueError("stat 至少指定一个路径。")
        results = []
        for arg in args:
            target = self._resolve_arg_path(arg, cwd=cwd)
            if not target.exists():
                raise ValueError(f"路径不存在: {target}")
            stat = target.stat()
            kind = "directory" if target.is_dir() else "file"
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            results.append(f"path: {target}\ntype: {kind}\nsize: {stat.st_size}\nmodified: {modified}")
        return "\n---\n".join(results)

    def _internal_wc(self, *, args: list[str], cwd: Path) -> str:
        """统计工作区内文本文件的行数、词数和字符数。

        支持 -l(行数)、-w(词数)、-c(字符数)标志筛选,默认显示全部。
        """

        if not args:
            raise ValueError("wc 至少指定一个文件路径。")
        count_lines = True
        count_words = True
        count_chars = True
        file_args: list[str] = []
        for arg in args:
            if arg.startswith("/"):
                flags = arg[1:]
                if "l" in flags:
                    count_words = count_chars = False
                if "w" in flags:
                    count_lines = count_chars = False
                if "c" in flags:
                    count_lines = count_words = False
            elif arg.startswith("-"):
                flags = arg.lstrip("-")
                if "l" in flags:
                    count_words = count_chars = False
                if "w" in flags:
                    count_lines = count_chars = False
                if "c" in flags:
                    count_lines = count_words = False
                if flags in {"lines"}:
                    count_words = count_chars = False
                if flags in {"words"}:
                    count_lines = count_chars = False
                if flags in {"chars", "bytes"}:
                    count_lines = count_words = False
            else:
                file_args.append(arg)
        if not file_args:
            raise ValueError("wc 至少指定一个文件路径。")
        total_lines = total_words = total_chars = 0
        results: list[str] = []
        for arg in file_args:
            target = self._resolve_arg_path(arg, cwd=cwd)
            self._assert_regular_file(target)
            content = target.read_text(encoding="utf-8", errors="replace")
            line_count = len(content.splitlines())
            word_count = len(re.findall(r"\S+", content))
            char_count = len(content)
            cols = []
            if count_lines:
                cols.append(str(line_count))
            if count_words:
                cols.append(str(word_count))
            if count_chars:
                cols.append(str(char_count))
            cols.append(str(target))
            results.append("\t".join(cols))
            total_lines += line_count
            total_words += word_count
            total_chars += char_count
        if len(file_args) > 1:
            cols = []
            if count_lines:
                cols.append(str(total_lines))
            if count_words:
                cols.append(str(total_words))
            if count_chars:
                cols.append(str(total_chars))
            cols.append("总和")
            results.append("\t".join(cols))
        return "\n".join(results)

    def _internal_write_file(self, *, args: list[str], cwd: Path, append: bool) -> str:
        """在允许写入的路径内创建、覆盖或追加文本文件。"""

        if len(args) < 2:
            command = "append" if append else "write"
            raise ValueError(f"{command} 必须指定文件路径和文本内容。")
        target = self._resolve_write_path(args[0], cwd=cwd)
        content = args[1] if len(args) == 2 else " ".join(args[1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8", newline="") as file:
            file.write(content)
        action = "追加" if append else "写入"
        return f"已{action}: {target}"

    def _internal_touch(self, *, args: list[str], cwd: Path) -> str:
        """在允许写入的路径内创建空文件或更新时间戳。"""

        if not args:
            raise ValueError("touch 至少指定一个文件路径。")
        results = []
        for arg in args:
            target = self._resolve_write_path(arg, cwd=cwd)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=True)
            results.append(str(target))
        return f"已 touch: {', '.join(results)}"

    def _internal_mkdir(self, *, args: list[str], cwd: Path) -> str:
        """在允许写入的路径内创建目录,始终支持多级目录（等价于 mkdir -p）。"""

        if not args:
            raise ValueError("mkdir 至少指定一个目录路径。")
        results = []
        for arg in args:
            if arg in {"-p", "--parents"}:
                continue
            target = self._resolve_write_path(arg, cwd=cwd)
            target.mkdir(parents=True, exist_ok=True)
            results.append(str(target))
        return f"已创建目录: {', '.join(results)}"

    def _internal_remove(self, *, args: list[str], cwd: Path) -> str:
        """删除允许写入范围内的文件或目录,目录递归删除。"""

        if not args:
            raise ValueError("rm/del 至少指定一个路径。")

        results = []
        for arg in args:
            if arg.startswith("-") or arg.upper() in {"/S", "/Q", "/F"}:
                continue
            target = self._resolve_write_path(arg, cwd=cwd)
            if not target.exists():
                raise ValueError(f"路径不存在: {target}")
            if target.is_dir():
                shutil.rmtree(target)
                results.append(str(target))
            else:
                target.unlink()
                results.append(str(target))
        return f"已删除: {', '.join(results)}"

    def _internal_move(self, *, args: list[str], cwd: Path) -> str:
        """移动或重命名允许写入范围内的文件和目录。"""

        if len(args) < 2:
            raise ValueError("mv/move 必须指定源路径和目标路径。")

        if len(args) == 2:
            source = self._resolve_write_path(args[0], cwd=cwd)
            target = self._resolve_write_path(args[1], cwd=cwd)
            if not source.exists():
                raise ValueError(f"源路径不存在: {source}")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            return f"已移动: {source} -> {target}"

        # Bulk move: last arg is target directory
        target_dir = self._resolve_write_path(args[-1], cwd=cwd)
        if not target_dir.exists():
            raise ValueError(f"目标目录不存在: {target_dir}")
        if not target_dir.is_dir():
            raise ValueError(f"目标必须是目录: {target_dir}")
        results = []
        for arg in args[:-1]:
            source = self._resolve_write_path(arg, cwd=cwd)
            if not source.exists():
                raise ValueError(f"源路径不存在: {source}")
            dest = target_dir / source.name
            source.replace(dest)
            results.append(f"{source.name} -> {dest}")
        return f"已移动: {', '.join(results)}"

    def _internal_kill(self, *, args: list[str]) -> str:
        """在完全访问权限下通过系统 kill/taskkill 终止进程。"""

        if self.access_mode != AGENT_ACCESS_FULL:
            raise ValueError("kill/taskkill 只能在完全访问权限下执行。")
        if not args:
            raise ValueError("kill 必须指定进程 PID 或名称。")
        if sys.platform == "win32":
            cmd = ["taskkill", *args]
        else:
            cmd = ["kill", *args]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            raise ValueError(f"杀进程失败: {stderr or stdout}")
        return stdout or f"已执行: {' '.join(cmd)}"

    def _resolve_arg_path(self, raw_path: str, *, cwd: Path) -> Path:
        """按当前 cwd 解析内部读取路径。"""

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = cwd / path
        return self._assert_read_path_allowed(path)

    def _resolve_write_path(self, raw_path: str, *, cwd: Path) -> Path:
        """按当前 cwd 解析内部写入路径并套用权限边界。"""

        if self.access_mode == AGENT_ACCESS_READONLY:
            raise ValueError("只读权限下禁止终端写入。")
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = cwd / path
        if self.access_mode == AGENT_ACCESS_FULL:
            return path.resolve(strict=False)
        return self._assert_path_in_workspace(path)

    @staticmethod
    def _assert_regular_file(target: Path) -> None:
        """确认内部读取命令的目标是已存在普通文件。"""

        if not target.exists():
            raise ValueError(f"文件不存在: {target}")
        if not target.is_file():
            raise ValueError(f"目标不是文件: {target}")

    def _run_one(self, *, index: int, program: str, args: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
        """执行单个外部程序段并截断输出。"""

        command = [program, *args]
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=_build_safe_env(),
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            timed_out = False
            exit_code = int(completed.returncode)
        except subprocess.TimeoutExpired as exc:
            stdout = _decode_timeout_stream(exc.stdout)
            stderr = _decode_timeout_stream(exc.stderr) + f"\n命令超时: {timeout} 秒。"
            timed_out = True
            exit_code = -1
        except FileNotFoundError as exc:
            stdout = ""
            stderr = f"程序不存在或不可执行: {program}"
            timed_out = False
            exit_code = -1
        except OSError as exc:
            stdout = ""
            stderr = f"命令启动失败: {exc}"
            timed_out = False
            exit_code = -1

        stdout, stdout_truncated = _truncate(stdout, self.settings.max_output_chars)
        stderr, stderr_truncated = _truncate(stderr, self.settings.max_output_chars)
        return {
            "index": index,
            "program": program,
            "args": args,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "truncated": stdout_truncated or stderr_truncated,
        }


def build_default_terminal_sandbox_payload(config: AgentConfig) -> dict[str, Any]:
    """返回设置页使用的默认终端沙盒配置 payload。"""

    return TerminalSandboxSettings.from_config_payload(config=config).to_dict()


def build_terminal_segment_catalog(settings: TerminalSandboxSettings) -> dict[str, list[dict[str, str]]]:
    """按当前 allowlist 输出三类终端支持的指令段目录。"""

    catalog: dict[str, list[dict[str, str]]] = {}
    for shell in SUPPORTED_SHELLS:
        allowed = set(settings.allowed_programs.get(shell, []))
        catalog[shell] = [
            item for item in DEFAULT_TERMINAL_SEGMENT_CATALOG.get(shell, [])
            if item.get("type") == "internal_command" or _normalize_program_name(item["program"]) in allowed
        ]
    return catalog


def _normalize_shells(value: Any) -> list[str]:
    """规范化启用终端列表。"""

    if not isinstance(value, list):
        return list(SUPPORTED_SHELLS)
    shells = [str(item).strip().lower() for item in value]
    return [shell for shell in SUPPORTED_SHELLS if shell in shells]


def _normalize_allowed_programs(value: Any) -> dict[str, list[str]]:
    """规范化每类终端的程序 allowlist。"""

    if not isinstance(value, dict):
        value = {}
    result: dict[str, list[str]] = {}
    for shell in SUPPORTED_SHELLS:
        result[shell] = _normalize_program_list(value.get(shell) or [])
    return result


def _upgrade_legacy_allowed_programs(value: dict[str, Any], defaults: dict[str, list[str]]) -> dict[str, list[str]]:
    """把未改动过的旧默认 allowlist 升级到当前默认命令集。"""

    upgraded: dict[str, list[str]] = {}
    for shell in SUPPORTED_SHELLS:
        current = _normalize_program_list(value.get(shell) or [])
        legacy = _normalize_program_list(LEGACY_DEFAULT_ALLOWED_PROGRAMS.get(shell) or [])
        upgraded[shell] = list(defaults.get(shell, [])) if current == legacy else current
    return upgraded


def _normalize_program_list(value: Any) -> list[str]:
    """规范化程序名列表,去重并转为小写 basename。"""

    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        raw_items = [str(item).strip() for item in value]
    else:
        raw_items = []
    seen: set[str] = set()
    result: list[str] = []
    for item in raw_items:
        normalized = _normalize_program_name(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _normalize_program_name(program: str) -> str:
    """提取程序 basename 并统一大小写。"""

    return Path(str(program).strip()).name.lower()


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    """把配置值转换为指定范围内的 int。"""

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _looks_like_path(value: str) -> bool:
    """判断参数片段是否像文件系统路径。"""

    normalized = value.strip().strip('"').strip("'")
    if not normalized:
        return False
    parsed = urlparse(normalized)
    if parsed.scheme in URL_SCHEMES:
        return False
    return bool(PATH_VALUE_PATTERN.search(normalized))


def _extract_path_candidates(arg: str) -> list[str]:
    """从单个参数中提取可能的路径值。"""

    values = [arg]
    if "=" in arg:
        values.append(arg.split("=", 1)[1])
    candidates: list[str] = []
    for value in values:
        normalized = value.strip().strip('"').strip("'")
        if _looks_like_path(normalized):
            candidates.append(normalized)
    return candidates


def _first_non_option_arg(args: list[str]) -> str:
    """返回第一个不像选项的参数。"""

    for arg in args:
        if arg and not arg.startswith("-"):
            return arg
    return ""


def _parse_line_window_args(
    args: list[str],
    *,
    default_lines: int,
    max_lines: int,
) -> dict[str, Any]:
    """解析 head/tail 的 `-n 数量 文件...` 或 `文件...` 参数。

    返回值: {"lines": int, "paths": list[str]}
    """

    if not args:
        raise ValueError("head/tail 必须指定文件路径。")
    line_count = default_lines
    remaining = list(args)
    if remaining[0] == "-n":
        if len(remaining) < 3:
            raise ValueError("head/tail 的 -n 参数必须包含数量和文件路径。")
        try:
            line_count = int(remaining[1])
        except ValueError as exc:
            raise ValueError("head/tail 的 -n 数量必须是整数。") from exc
        remaining = remaining[2:]
    if line_count < 1 or line_count > max_lines:
        raise ValueError(f"head/tail 的行数必须在 1 到 {max_lines} 之间。")
    if not remaining:
        raise ValueError("head/tail 必须指定文件路径。")
    return {"lines": line_count, "paths": remaining}


def _parse_list_dir_args(args: list[str]) -> dict[str, Any]:
    """解析 ls/dir 的显示选项和目录路径列表。

    支持 -a/l/1/R 短标志、--all/--long/--recursive/--bare 长标志、
    /a/l/s/b 等 Windows 风格标志。未知标志静默忽略，允许多个路径。
    """

    show_all = False
    long = False
    recursive = False
    bare = False
    paths: list[str] = []
    for arg in args:
        lower_arg = arg.lower()
        if arg in {"-a", "--all"}:
            show_all = True
            continue
        if arg in {"-l", "--long"}:
            long = True
            continue
        if arg in {"-1", "--one-column"}:
            continue
        if arg in {"-R", "--recursive"}:
            recursive = True
            continue
        if arg in {"--bare"}:
            bare = True
            continue
        if arg.startswith("/"):
            if lower_arg in {"/a", "/all"}:
                show_all = True
                continue
            if lower_arg in {"/l", "/long"}:
                long = True
                continue
            if lower_arg in {"/s", "/s/q"}:
                recursive = True
                continue
            if lower_arg in {"/b", "/bare"}:
                bare = True
                continue
            # Windows /D, /Q, /W 等未知标志静默忽略
            continue
        if arg.startswith("-") and len(arg) > 1:
            short_flags = set(arg[1:])
            if short_flags and short_flags.issubset({"a", "l", "1", "R"}):
                show_all = show_all or "a" in short_flags
                long = long or "l" in short_flags
                recursive = recursive or "R" in short_flags
                continue
            # 未知标志静默忽略而非报错,避免不必要的中断
            continue
        paths.append(arg)
    if not paths:
        paths.append(".")
    return {"show_all": show_all, "long": long, "recursive": recursive, "bare": bare, "paths": paths}


def _is_hidden_path(path: Path) -> bool:
    """判断目录项是否应在默认 ls/dir 输出中隐藏。"""

    if path.name.startswith("."):
        return True
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & getattr(os, "FILE_ATTRIBUTE_HIDDEN", 0))


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    """资源安全上限触发时保留 stdout/stderr 头尾和明确省略信息。"""

    if len(text) <= limit:
        return text, False
    marker = f"\n[resource safety limit omitted {len(text) - limit} characters; head and tail preserved]\n"
    payload_limit = max(limit - len(marker), 0)
    head_limit = round(payload_limit * 0.6)
    tail_limit = payload_limit - head_limit
    return text[:head_limit] + marker + (text[-tail_limit:] if tail_limit else ""), True


def _decode_timeout_stream(value: bytes | str | None) -> str:
    """兼容 TimeoutExpired 中可能为 bytes 的输出。"""

    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _build_safe_env() -> dict[str, str]:
    """构造最小环境变量白名单,保留可执行文件查找和 UTF-8 输出。"""

    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "LANG",
        "LC_ALL",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def dumps_terminal_result(payload: dict[str, Any]) -> str:
    """将终端执行结果转为 Agent 可读 JSON 文本。"""

    return json.dumps(payload, ensure_ascii=False, indent=2)

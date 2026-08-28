"""以独立子进程串行运行前端 Vitest spec 文件。

用法：在项目根目录执行 ``python -m tests.contracts.run_serial_vitest``。
每个 spec 在单 worker Vitest 进程中运行，避免前端测试 worker 和未关闭句柄跨文件
累积。结果写入 JSON，并以失败文件数量决定退出码。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VitestFileResult:
    """记录单个前端 spec 的路径、退出码和完整输出。"""

    path: str
    returncode: int
    output: str


def _parse_args() -> argparse.Namespace:
    """解析可选 spec 路径和结果文件。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("specs", nargs="*", help="可选的 editor 相对 spec 路径。")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/acceptance/backend_maintenance/BASELINE_VITEST.json"),
        help="相对项目根目录的结果 JSON。",
    )
    return parser.parse_args()


def _discover_specs(editor_root: Path, requested: list[str]) -> list[Path]:
    """返回稳定排序的显式 spec 或全部前端测试文件。"""

    if requested:
        paths = [editor_root / value for value in requested]
    else:
        patterns = ("*.spec.ts", "*.test.ts", "*.spec.js", "*.test.js")
        paths = [path for pattern in patterns for path in (editor_root / "src").rglob(pattern)]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(", ".join(str(path) for path in missing))
    return sorted(set(paths))


def _npm_command() -> str:
    """返回当前平台可执行的 npm 命令路径。"""

    command = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if command is None:
        raise FileNotFoundError("npm executable not found")
    return command


def _run_spec(editor_root: Path, spec_path: Path) -> VitestFileResult:
    """以单 worker、禁止文件并行的方式运行一个 Vitest spec。"""

    relative_path = spec_path.relative_to(editor_root)
    completed = subprocess.run(
        [
            _npm_command(),
            "exec",
            "--",
            "vitest",
            "run",
            relative_path.as_posix(),
            "--maxWorkers=1",
            "--no-file-parallelism",
        ],
        cwd=editor_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return VitestFileResult(
        path=f"editor/{relative_path.as_posix()}",
        returncode=completed.returncode,
        output=completed.stdout,
    )


def main() -> int:
    """逐 spec 执行、保存结果并报告失败文件数。"""

    args = _parse_args()
    project_root = Path(__file__).resolve().parents[2]
    editor_root = project_root / "editor"
    results: list[VitestFileResult] = []
    for spec_path in _discover_specs(editor_root, args.specs):
        result = _run_spec(editor_root, spec_path)
        results.append(result)
        status = "PASS" if result.returncode == 0 else f"FAIL({result.returncode})"
        print(f"{status} {result.path}", flush=True)

    output_path = args.output if args.output.is_absolute() else project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    failures = sum(result.returncode != 0 for result in results)
    print(f"Completed {len(results)} specs; failures={failures}; output={output_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""以独立子进程串行运行后端测试文件。

用法：在项目根目录执行 ``python -m tests.contracts.run_serial_pytest``。
每个 ``tests/test_*.py`` 都在独立 Python 进程中运行，避免模型、线程池和全局
状态在完整 pytest 进程内持续累积。结果写入指定 JSON 文件，并以失败数量作为
进程退出码依据。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TestFileResult:
    """记录单个测试文件的执行结果。

    fields:
        path: 相对项目根目录的测试文件路径。
        returncode: pytest 子进程退出码。
        output: pytest 合并后的标准输出与错误输出。
    """

    path: str
    returncode: int
    output: str


def _parse_args() -> argparse.Namespace:
    """解析输出文件和可选测试文件参数。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tests",
        nargs="*",
        help="可选的测试文件；省略时运行 tests/test_*.py。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/acceptance/backend_maintenance/BASELINE_TESTS.json"),
        help="JSON 结果文件。",
    )
    return parser.parse_args()


def _discover_tests(project_root: Path, requested: list[str]) -> list[Path]:
    """返回稳定排序且确实存在的测试文件列表。"""

    paths = [project_root / value for value in requested] if requested else list((project_root / "tests").glob("test_*.py"))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(", ".join(str(path) for path in missing))
    return sorted(paths)


def _run_test_file(project_root: Path, test_path: Path) -> TestFileResult:
    """在低并行环境变量下运行一个 pytest 文件并返回完整结果。"""

    environment = os.environ.copy()
    environment.setdefault("HF_ENABLE_PARALLEL_LOADING", "false")
    environment.setdefault("TOKENIZERS_PARALLELISM", "false")
    relative_path = test_path.relative_to(project_root)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(relative_path)],
        cwd=project_root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return TestFileResult(
        path=relative_path.as_posix(),
        returncode=completed.returncode,
        output=completed.stdout,
    )


def main() -> int:
    """逐文件运行测试、写入结果，并在存在失败时返回 1。"""

    args = _parse_args()
    project_root = Path(__file__).resolve().parents[2]
    results: list[TestFileResult] = []
    for test_path in _discover_tests(project_root, args.tests):
        result = _run_test_file(project_root, test_path)
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
    print(f"Completed {len(results)} files; failures={failures}; output={output_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

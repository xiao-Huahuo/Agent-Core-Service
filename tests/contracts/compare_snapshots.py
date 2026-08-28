"""比较两组契约快照目录。

用法：``python -m tests.contracts.compare_snapshots BASELINE ACTUAL``。
两个目录中的 JSON 文件名和规范化内容必须完全一致，否则返回非零退出码。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    """解析基线目录和实际目录。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("actual", type=Path)
    return parser.parse_args()


def _load(directory: Path) -> dict[str, object]:
    """读取目录下全部 JSON 文件并以文件名索引。"""

    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    }


def main() -> int:
    """比较文件集合与 JSON 内容并输出差异文件名。"""

    args = _parse_args()
    baseline = _load(args.baseline)
    actual = _load(args.actual)
    names = sorted(set(baseline) | set(actual))
    changed = [name for name in names if baseline.get(name) != actual.get(name)]
    if changed:
        print("snapshot differences:")
        for name in changed:
            print(f"- {name}")
        return 1
    print(f"snapshots match: {len(names)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""契约快照脚本共享的稳定 JSON 写入工具。

本模块只处理目录创建、UTF-8 JSON 序列化和 SHA-256 计算，不包含业务规则。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT_ROOT = PROJECT_ROOT / "docs" / "acceptance" / "backend_maintenance" / "snapshots"


def write_snapshot(name: str, payload: Any, output_root: Path | None = None) -> Path:
    """将 payload 以排序后的 UTF-8 JSON 写入快照目录并打印摘要。"""

    root = output_root or DEFAULT_SNAPSHOT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    print(f"wrote {path.relative_to(PROJECT_ROOT)} sha256={digest}")
    return path

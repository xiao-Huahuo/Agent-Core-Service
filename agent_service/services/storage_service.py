"""
存储管理服务。

用途:
- 提供运行目录路径的定义、查询、覆盖和清空功能。
- 启动时执行路径迁移：读取用户保存的覆盖，将旧路径内容移动到新路径。
- 供 REST API 和前端"存储管理"设置页使用。
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 路径定义：key → (label, parent_key, can_clear, requires_restart)
STORAGE_PATH_DEFINITIONS: dict[str, dict[str, Any]] = {
    "knowledge_dir": {"label": "知识库路径", "parent": None, "can_clear": False, "requires_restart": False},
    "library_storage_dir": {"label": "图书馆存储路径", "parent": "knowledge_dir", "can_clear": False, "requires_restart": False},
    "base_data_dir": {"label": "运行时文件根路径(R)", "parent": None, "can_clear": False, "requires_restart": True},
    "assets_dir": {"label": "资源文件路径", "parent": "base_data_dir", "can_clear": True, "requires_restart": True},
    "db_dir": {"label": "数据库根路径(D)", "parent": "base_data_dir", "can_clear": False, "requires_restart": True},
    "relation_db_dir": {"label": "关系库路径", "parent": "db_dir", "can_clear": False, "requires_restart": True},
    "sqlite_path": {"label": "关联库路径", "parent": "relation_db_dir", "can_clear": True, "requires_restart": True},
    "vector_db_dir": {"label": "向量数据库根路径", "parent": "db_dir", "can_clear": False, "requires_restart": True},
    "chroma_persist_dir": {"label": "向量库路径", "parent": "vector_db_dir", "can_clear": True, "requires_restart": True},
    "frontmatter_dir": {"label": "预处理中间文件", "parent": "base_data_dir", "can_clear": True, "requires_restart": True},
    "log_dir": {"label": "日志文件", "parent": "base_data_dir", "can_clear": True, "requires_restart": True},
    "models_dir": {"label": "模型路径", "parent": "base_data_dir", "can_clear": False, "requires_restart": True},
    "embedding_model_dir": {"label": "Embedding模型路径", "parent": "models_dir", "can_clear": True, "requires_restart": True},
    "paddleocr_model_dir": {"label": "OCR模型路径", "parent": "models_dir", "can_clear": True, "requires_restart": True},
    "rerank_model_dir": {"label": "CrossEncoder模型路径", "parent": "models_dir", "can_clear": True, "requires_restart": True},
    "trash_dir": {"label": "最近删除", "parent": "base_data_dir", "can_clear": True, "requires_restart": True},
}

# 明确不可清空的路径 key 列表
UNCLEARABLE_KEYS = {"knowledge_dir", "library_storage_dir", "base_data_dir", "relation_db_dir", "vector_db_dir", "models_dir", "db_dir"}

# 虚拟节点 key（不对应实际 config.storage 属性）
VIRTUAL_KEYS = {"models_dir", "db_dir"}

# 明确可清空的路径 key 列表
CLEARABLE_KEYS = {k for k, v in STORAGE_PATH_DEFINITIONS.items() if v["can_clear"]}


def _dir_size(path: Path) -> int:
    """递归计算目录下所有文件的总字节数（不存在则返回 0）。"""

    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    pass
    except PermissionError:
        pass
    return total


class StorageService:
    """存储管理服务：路径查询、覆盖持久化、清空、迁移。"""

    def __init__(self, config, settings_service):
        self.config = config
        self.settings_service = settings_service

    def get_storage_config(self, *, user_id: str) -> dict:
        """返回当前所有路径的值、大小和配置元数据。"""

        from agent_service.core.agent_config import AgentConfig  # noqa: F811

        storage = self.config.storage
        overrides = self.settings_service.get_storage_path_overrides(user_id=user_id)

        paths = []
        active_library = self.settings_service.get_active_knowledge_library(user_id=user_id)
        active_knowledge_dir = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        for key, definition in STORAGE_PATH_DEFINITIONS.items():
            if key == "knowledge_dir":
                size_bytes = _dir_size(active_knowledge_dir)
                paths.append({
                    "key": key,
                    "label": definition["label"],
                    "value": str(active_knowledge_dir),
                    "size_bytes": size_bytes,
                    "requires_restart": definition["requires_restart"],
                    "can_clear": definition["can_clear"],
                    "parent": definition["parent"],
                })
                continue
            if key == "library_storage_dir":
                relative_dir = str(active_library.get("library_storage_dir") or "library").strip() or "library"
                current_path = (active_knowledge_dir / relative_dir).resolve()
                size_bytes = _dir_size(current_path)
                paths.append({
                    "key": key,
                    "label": definition["label"],
                    "value": str(current_path),
                    "size_bytes": size_bytes,
                    "requires_restart": definition["requires_restart"],
                    "can_clear": definition["can_clear"],
                    "parent": definition["parent"],
                })
                continue
            if key in VIRTUAL_KEYS:
                # 虚拟节点：路径基于 base_data_dir 拼接，大小为子项之和
                base = Path(getattr(storage, "base_data_dir")).expanduser().resolve()
                sub = "models" if key == "models_dir" else "db"
                virtual_path = base / sub
                size_bytes = _dir_size(virtual_path)
                paths.append({
                    "key": key,
                    "label": definition["label"],
                    "value": str(virtual_path),
                    "size_bytes": size_bytes,
                    "requires_restart": definition["requires_restart"],
                    "can_clear": definition["can_clear"],
                    "parent": definition["parent"],
                })
                continue
            override_value = overrides.get(key)
            if override_value and not key == "knowledge_dir":
                current_path = Path(override_value).expanduser().resolve()
            else:
                current_path = Path(getattr(storage, key)).expanduser().resolve()
            size_bytes = _dir_size(current_path)
            paths.append({
                "key": key,
                "label": definition["label"],
                "value": str(current_path),
                "size_bytes": size_bytes,
                "requires_restart": definition["requires_restart"],
                "can_clear": definition["can_clear"],
                "parent": definition["parent"],
            })

        # 计算顶层汇总
        knowledge_dir_total = _dir_size(active_knowledge_dir)
        runtime_total = _dir_size(Path(getattr(storage, "base_data_dir")))

        return {
            "paths": paths,
            "knowledge_dir_total_bytes": knowledge_dir_total,
            "runtime_total_bytes": runtime_total,
        }

    def save_storage_config(self, *, user_id: str, paths: dict[str, str]) -> dict:
        """保存用户存储路径覆盖（knowledge_dir 除外，用现有 API 单独处理）。"""

        saved_keys: list[str] = []
        if str(paths.get("library_storage_dir") or "").strip():
            self.settings_service.update_library_storage_dir(
                user_id=user_id,
                library_storage_dir=str(paths["library_storage_dir"]),
            )
            saved_keys.append("library_storage_dir")

        # 移除 knowledge_dir 与 library_storage_dir（用即时 API 处理）和虚拟节点
        cleaned = {
            k: str(v).strip()
            for k, v in paths.items()
            if k not in ("knowledge_dir", "library_storage_dir", *VIRTUAL_KEYS) and str(v).strip()
        }
        # 只保留 STORAGE_PATH_DEFINITIONS 中定义的 key
        cleaned = {
            k: v
            for k, v in cleaned.items()
            if k in STORAGE_PATH_DEFINITIONS and k not in ("knowledge_dir", "library_storage_dir", *VIRTUAL_KEYS)
        }
        if cleaned:
            self.settings_service.save_storage_path_overrides(user_id=user_id, overrides=cleaned)
            saved_keys.extend(cleaned.keys())
        return {"requires_restart": len(cleaned) > 0, "saved": saved_keys}

    def clear_path(self, *, path_key: str) -> dict:
        """删除指定路径的内容（保留目录本身）。"""

        if path_key not in CLEARABLE_KEYS:
            raise ValueError(f"不允许清空路径: {path_key}")

        storage = self.config.storage
        target = Path(getattr(storage, path_key)).expanduser().resolve()
        freed = _dir_size(target)

        if not target.exists():
            return {"path_key": path_key, "freed_bytes": 0}

        if target.is_file():
            # sqlite_path 是文件，需要特殊处理：同时移除 WAL/SHM 日志文件
            if path_key == "sqlite_path":
                for suffix in ("", "-wal", "-shm"):
                    journal = target.with_suffix(target.suffix + suffix if suffix else target.suffix)
                    if journal.exists():
                        journal.unlink(missing_ok=True)
            else:
                target.unlink(missing_ok=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            # 重建空文件避免下游报错
            target.touch()
            return {"path_key": path_key, "freed_bytes": freed}

        # 目录路径：删除所有内容后重建空目录
        target.mkdir(parents=True, exist_ok=True)
        for child in target.iterdir():
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
            except OSError:
                pass
        return {"path_key": path_key, "freed_bytes": freed}


def migrate_storage_paths(config, settings_service) -> Any:
    """启动时迁移：读取用户保存的覆盖，将旧路径内容移动到新路径。

    在 main.py lifespan 中 AgentCore 初始化之前调用。
    返回可能被覆盖路径更新过的 config。
    """

    try:
        from sqlalchemy import select
        from sqlmodel import Session

        from agent_service.models.user_settings import UserSettingsRecord

        engine = settings_service.engine
        with Session(engine) as db:
            records = db.exec(select(UserSettingsRecord)).all()
            for record in records:
                overrides_str = getattr(record, "storage_path_overrides", "") or ""
                if not overrides_str:
                    continue
                try:
                    overrides = json.loads(overrides_str)
                except json.JSONDecodeError:
                    continue
                if not overrides:
                    continue

                storage = config.storage
                for key, new_path_str in overrides.items():
                    if key not in STORAGE_PATH_DEFINITIONS or key in ("knowledge_dir", *VIRTUAL_KEYS):
                        continue
                    new_path = Path(new_path_str).expanduser().resolve()
                    old_path = Path(getattr(storage, key)).expanduser().resolve()
                    if str(new_path) == str(old_path):
                        continue
                    if not old_path.exists() or (_dir_size(old_path) == 0):
                        continue

                    # 确保新路径父目录存在
                    new_path.parent.mkdir(parents=True, exist_ok=True)

                    # sqlite_path 是文件（需同时迁移 WAL/SHM）
                    if key == "sqlite_path":
                        for suffix in ("", "-wal", "-shm"):
                            journal_path = old_path.with_suffix(
                                old_path.suffix + suffix if suffix else old_path.suffix
                            )
                            if journal_path.exists():
                                dest = new_path.with_suffix(
                                    new_path.suffix + suffix if suffix else new_path.suffix
                                )
                                shutil.move(str(journal_path), str(dest))
                    else:
                        new_path.mkdir(parents=True, exist_ok=True)
                        if old_path.is_dir():
                            for child in old_path.iterdir():
                                dest = new_path / child.name
                                shutil.move(str(child), str(dest))
                    logger.info(
                        "存储路径迁移完成 | key=%s old=%s new=%s user=%s",
                        key, old_path, new_path, record.user_id,
                    )
    except Exception:
        logger.exception("存储路径迁移失败，继续启动")
    return config

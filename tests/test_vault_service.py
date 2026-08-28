"""
密码库服务测试。

功能说明:
验证密码库主密码二次解锁、独立 JWT、敏感字段加密存储、回收站、导入导出
和 token 用户隔离。

使用说明:
在项目根目录执行 `python -m pytest tests/test_vault_service.py`。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, select

from tests.db_test_utils import create_test_engine as create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.models.vault import VaultItem
from agent_service.services.vault.service import VaultService


def make_service(tmp_path: Path) -> VaultService:
    """创建使用内存数据库和临时运行目录的密码库服务。"""

    config = AgentConfig.load_config(
        {
            "storage": {
                "base_data_dir": str(tmp_path / "runtime"),
                "assets_dir": str(tmp_path / "runtime" / "assets"),
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=True,
        ensure_models=False,
    )
    return VaultService(config=config, engine=create_engine("sqlite:///:memory:"))


def unlock_session(service: VaultService, user_id: str = "u1"):
    """设置主密码并返回服务端解锁会话。"""

    token = service.setup(user_id=user_id, master_password="correct horse")["token"]
    return service.verify_token(token)


def test_vault_encrypts_sensitive_payload_and_lists_after_unlock(tmp_path: Path) -> None:
    """敏感字段加密落库,解锁后可正常列表和搜索。"""

    service = make_service(tmp_path)
    session = unlock_session(service)
    created = service.create_item(
        session=session,
        item_type="login",
        fields={"name": "GitHub", "username": "octo", "password": "secret", "uri": "https://github.com"},
        tags=["dev"],
        asset_ids=[],
    )["item"]

    with Session(service.engine) as db:
        raw = db.exec(select(VaultItem)).first()
        assert raw is not None
        assert "secret" not in raw.encrypted_payload
        assert "GitHub" not in raw.encrypted_payload

    listed = service.list_items(session=session, query="secret", tag="dev")["items"]
    assert listed[0]["item_id"] == created["item_id"]
    assert "password" not in listed[0]["fields"]
    assert "password" not in listed[0]["safe_fields"]
    assert listed[0]["field_keys"] == ["name", "username", "password", "uri"]
    assert service.get_item(session=session, item_id=created["item_id"])["item"]["fields"]["password"] == "secret"


def test_vault_token_scope_and_user_isolation(tmp_path: Path) -> None:
    """密码库 token 必须是 vault scope,且不能跨 user_id 读取。"""

    service = make_service(tmp_path)
    session_u1 = unlock_session(service, "u1")
    token_u2 = service.setup(user_id="u2", master_password="correct horse")["token"]
    session_u2 = service.verify_token(token_u2)
    item = service.create_item(
        session=session_u1,
        item_type="secure_note",
        fields={"name": "note", "note": "hidden"},
        tags=[],
        asset_ids=[],
    )["item"]

    with pytest.raises(ValueError):
        service.get_item(session=session_u2, item_id=item["item_id"])


def test_vault_trash_restore_purge_and_export(tmp_path: Path) -> None:
    """回收站恢复、永久删除和明文导出语义完整。"""

    service = make_service(tmp_path)
    session = unlock_session(service)
    item = service.create_item(
        session=session,
        item_type="card",
        fields={"name": "Visa", "number": "4111111111111111", "security_code": "123"},
        tags=["pay"],
        asset_ids=[],
    )["item"]

    service.move_to_trash(session=session, item_ids=[item["item_id"]])
    assert service.list_items(session=session, trash=False)["items"] == []
    assert service.list_items(session=session, trash=True)["items"][0]["name"] == "Visa"

    service.restore_items(session=session, item_ids=[item["item_id"]])
    exported = service.export_items(session=session, item_ids=[item["item_id"]])
    assert exported["items"][0]["fields"]["security_code"] == "123"

    service.purge_items(session=session, item_ids=[item["item_id"]])
    assert service.list_items(session=session)["items"] == []


def test_vault_import_converts_mismatched_item_to_secure_note(tmp_path: Path) -> None:
    """字段不匹配的可识别导入项会转成安全笔记。"""

    service = make_service(tmp_path)
    session = unlock_session(service)
    result = service.import_items(session=session, raw_items=[{"item_type": "login", "title": "Broken"}])
    items = service.list_items(session=session)["items"]

    assert result["imported"] == 1
    assert result["converted_to_secure_note"] == 1
    assert items[0]["item_type"] == "secure_note"


def test_vault_debug_master_password_is_saved_on_setup_and_unlock(tmp_path: Path) -> None:
    """调试接口可以读取最近一次设置或成功解锁写入的主密码。"""

    service = make_service(tmp_path)
    service.setup(user_id="u1", master_password="first-password")
    assert service.debug_master_password(user_id="u1")["master_password"] == "first-password"

    service.unlock(user_id="u1", master_password="first-password")
    result = service.debug_master_password(user_id="u1")

    assert result["configured"] is True
    assert result["available"] is True
    assert result["master_password"] == "first-password"

"""
密码库数据库模型。

功能说明:
本文件定义仅供密码库使用的主密码档案、加密条目、标签关系和图片资产表。
敏感业务字段不以明文列保存,统一放入 VaultItem.encrypted_payload。

使用说明:
VaultService 在启动时调用 SQLModel.metadata.create_all 创建这些表,REST 和
gRPC 层只通过服务层读写,不得直接操作模型。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text

from agent_service.models.session import utc_now


class VaultProfile(SQLModel, table=True):
    """用户密码库主密码档案。"""

    __tablename__ = "vault_profiles"

    user_id: str = Field(primary_key=True, max_length=128)
    password_hash: str = Field(max_length=256)
    password_salt: str = Field(max_length=128)
    debug_master_password: str = Field(default="", max_length=512)
    kdf_iterations: int = Field(default=260_000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class VaultItem(SQLModel, table=True):
    """密码库加密条目。"""

    __tablename__ = "vault_items"

    item_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    item_type: str = Field(index=True, max_length=32)
    encrypted_payload: str = Field(sa_column=Column(Text))
    deleted_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class VaultTag(SQLModel, table=True):
    """密码库标签。"""

    __tablename__ = "vault_tags"

    tag_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    name: str = Field(index=True, max_length=128)
    created_at: datetime = Field(default_factory=utc_now)


class VaultItemTag(SQLModel, table=True):
    """密码库条目与标签的多对多关系。"""

    __tablename__ = "vault_item_tags"

    item_id: str = Field(primary_key=True, max_length=64)
    tag_id: str = Field(primary_key=True, max_length=64)


class VaultAsset(SQLModel, table=True):
    """密码库受鉴权保护的图片资产。"""

    __tablename__ = "vault_assets"

    asset_id: str = Field(primary_key=True, max_length=64)
    item_id: str = Field(default="", index=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    mime_type: str = Field(default="", max_length=128)
    file_name: str = Field(default="", max_length=512)
    storage_path: str = Field(max_length=2048)
    size: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)

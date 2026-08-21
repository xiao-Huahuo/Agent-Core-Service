"""
图书馆虚拟编目数据库模型。

功能说明:
本文件只保存图书馆页面的虚拟结构与展示元数据。真实知识库文件仍由
KnowledgeLibraryService 管理,图书馆条目仅通过 source_path 引用真实文件。

使用说明:
LibraryItem 表示图书或集锦,LibraryTag 表示用户标签,LibraryItemTag 维护
多对多关系,LibraryAsset 保存上传封面的运行时资产路径。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

from agent_service.models.session import utc_now


class LibraryItem(SQLModel, table=True):
    """图书馆虚拟条目,可表示一本图书或一个虚拟集锦。"""

    __tablename__ = "library_items"

    item_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    parent_id: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    item_type: str = Field(default="book", index=True, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    content_type: str = Field(default="knowledge_file", index=True, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    title: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.title_max_length)
    description: str = Field(default="", sa_column=Column(Text))
    storage_path: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    source_path: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    source_url: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    source_name: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.summary_max_length)
    source_mime: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.title_max_length)
    source_size: int = Field(default=0)
    source_mtime: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    cover_mode: str = Field(default="icon", max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    cover_asset_id: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    sort_order: int = Field(default=0, index=True)
    index_status: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    graph_status: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LibraryTag(SQLModel, table=True):
    """图书馆标签。"""

    __tablename__ = "library_tags"

    tag_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    name: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    created_at: datetime = Field(default_factory=utc_now)


class LibraryItemTag(SQLModel, table=True):
    """图书馆条目与标签的多对多关系。"""

    __tablename__ = "library_item_tags"

    item_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    tag_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)


class LibraryAsset(SQLModel, table=True):
    """图书馆封面等运行时资产。"""

    __tablename__ = "library_assets"

    asset_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    asset_type: str = Field(default="cover", max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    mime_type: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    file_name: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.summary_max_length)
    storage_path: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    width: int = Field(default=0)
    height: int = Field(default=0)
    size: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)

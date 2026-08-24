"""
Smart form database models.

功能说明:
本文件定义智能表格的关系型数据库表。表格、列、行、单元格分别存储,避免使用
知识库 JSON 文件作为业务主存储,并确保标签、智能标签、星级、文件列等所有列类型
都能完整保存和加载。

使用说明:
SmartFormService 负责把前端 SmartLiteratureForm 结构拆分写入这些表,再按列/行顺序
组装回前端需要的表格结构。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

from agent_service.models.session import utc_now

DEFAULT_SMART_FORM_ROW_HEIGHT = DEFAULT_BUSINESS_LIMITS.smart_form_default_row_height


class SmartFormRecord(SQLModel, table=True):
    """智能表格主表。"""

    __tablename__ = "smart_forms"

    form_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    title: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.title_max_length)
    asset_dir: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.secret_max_length)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SmartFormColumnRecord(SQLModel, table=True):
    """智能表格列定义。"""

    __tablename__ = "smart_form_columns"
    __table_args__ = (
        UniqueConstraint("form_id", "column_id", name="uq_smart_form_columns_form_column"),
    )

    column_record_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.form_label_max_length)
    form_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    column_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    order_index: int = Field(index=True)
    title: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.title_max_length)
    description: str = Field(default="", sa_column=Column(Text))
    column_type: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    removable: bool = Field(default=True)
    editable: bool = Field(default=True)
    width: int = Field(default=160)
    options_json: str = Field(default="", sa_column=Column(Text))
    tone: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)


class SmartFormRowRecord(SQLModel, table=True):
    """智能表格行定义。"""

    __tablename__ = "smart_form_rows"
    __table_args__ = (
        UniqueConstraint("form_id", "row_id", name="uq_smart_form_rows_form_row"),
    )

    row_record_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.form_label_max_length)
    form_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    row_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    order_index: int = Field(index=True)
    height: int = Field(default=DEFAULT_BUSINESS_LIMITS.smart_form_default_row_height)


class SmartFormCellRecord(SQLModel, table=True):
    """智能表格单元格值。"""

    __tablename__ = "smart_form_cells"
    __table_args__ = (
        UniqueConstraint("form_id", "row_id", "column_id", name="uq_smart_form_cells_position"),
    )

    cell_record_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.title_max_length)
    form_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    row_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    column_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    value: str = Field(default="", sa_column=Column(Text))
    status: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    asset_path: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    file_name: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.summary_max_length)

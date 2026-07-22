"""
用户设置数据库模型。

功能说明:
- UserSystemPromptEntry: 用户自定义系统提示词条目，每条独立存储，启动时全部加载拼接。
- UserSettingsRecord: 用户级 editor/console 共享设置档案。
- UserKnowledgeLibrary: 用户知识库配置,一个用户可拥有多个互相隔离的知识库。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text

from agent_service.models.session import utc_now


class UserSystemPromptEntry(SQLModel, table=True):
    """用户自定义系统提示词条目。"""

    __tablename__ = "user_system_prompts"

    prompt_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now)


class UserSettingsRecord(SQLModel, table=True):
    """用户设置档案记录。"""

    __tablename__ = "user_settings"

    user_id: str = Field(primary_key=True, max_length=128)
    knowledge_dir: str = Field(max_length=1024)
    proxy_url: str = Field(default="", max_length=1024)
    web_search_enabled: bool = Field(default=False)
    auto_ingest_on_upload: bool = Field(default=False)
    ocr_enabled: bool = Field(default=False)
    knowledge_ignore_patterns: str = Field(default="", sa_column=Column(Text))
    disabled_tools: str = Field(default="", sa_column=Column(Text))
    terminal_sandbox_config: str = Field(default="", sa_column=Column(Text))
    ui_font_families: str = Field(default="", sa_column=Column(Text))
    text_font_families: str = Field(default="", sa_column=Column(Text))
    theme_primary_color: str = Field(default="", max_length=16)
    theme_soft_color: str = Field(default="", max_length=16)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserKnowledgeLibrary(SQLModel, table=True):
    """用户知识库配置记录。"""

    __tablename__ = "user_knowledge_libraries"

    library_id: str = Field(primary_key=True, max_length=96)
    user_id: str = Field(index=True, max_length=128)
    name: str = Field(max_length=256)
    knowledge_dir: str = Field(index=True, max_length=1024)
    is_active: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserLLMConfig(SQLModel, table=True):
    """用户自定义 LLM 配置，支持一大一小两个模型。

    每个用户一条记录，存储大模型和小模型的 API Key、Base URL、模型名称。
    """

    __tablename__ = "user_llm_config"

    user_id: str = Field(primary_key=True, max_length=128)

    # 大模型
    api_key: str = Field(default="", max_length=1024)
    base_url: str = Field(default="", max_length=1024)
    model_name: str = Field(default="", max_length=256)

    # 小模型
    small_api_key: str = Field(default="", max_length=1024)
    small_base_url: str = Field(default="", max_length=1024)
    small_model_name: str = Field(default="", max_length=256)

    updated_at: datetime = Field(default_factory=utc_now)

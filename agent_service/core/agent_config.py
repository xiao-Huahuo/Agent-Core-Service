"""
Agent 服务统一配置模块。

功能说明:
本文件集中管理 Agent-Core-Service 的所有通用常量、环境变量和运行参数。
后端代码需要配置时应显式接收 `AgentConfig` 实例,避免在业务模块中直接书写
全局常量或直接读取环境变量。

使用说明:
推荐通过 `AgentConfig.load_config()` 创建配置对象。该方法会先加载 dataclass
默认值,再读取项目根目录 `.env` 文件和 `AGENT_` 前缀环境变量,最后应用
`overrides` 显式覆盖项。进程环境变量优先于 `.env`, `overrides` 的优先级
高于环境变量。

示例:
config = AgentConfig.load_config()
config = AgentConfig.load_config({"model": {"model_name": "moonshot-v1-8k"}})

模型检查:
默认调用 `load_config()` 时会检查本地 Embedding 与 ReRank 模型是否存在。
如果模型缺失,会调用 `agent_service.scripts.download_model.ensure_models()` 自动下载。
测试或只读取配置时可以传入 `ensure_models=False` 关闭该行为。`AgentCore`
初始化时也会再次调用 `ensure_local_models()`,确保真正启动 Agent 时一定完成检查。
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote_plus


@dataclass(slots=True)
class AgentConfig:
    @dataclass(slots=True)
    class Constants:
        """
        管理应用级常量与跨模块共享的固定标识。

        app_name: 服务名称,用于日志、监控和对外展示。
        default_session_name: 新建会话时使用的默认名称。
        memory_tag: 跨会话长期记忆的默认标签。
        knowledge_tag: 知识库或大文本记忆的默认标签。
        default_display_mode: 默认输出展示模式,用于控制响应字段展示策略。
        """

        app_name: str = "Agent-Core-Service"
        default_session_name: str = "新对话"
        memory_tag: str = "Memory"
        knowledge_tag: str = "Knowledge"
        default_display_mode: str = "default"

    @dataclass(slots=True)
    class StorageConfig:
        """
        管理运行目录、知识库文件以及关系库/向量库连接地址。

        project_root: 项目根目录,用于解析 resources 等项目级目录。
        base_data_dir: 服务运行时数据根目录。
        relational_dsn: PostgreSQL 关系数据库连接地址;为空时按独立密码字段自动组装。
        vector_dsn: pgvector 向量数据库连接地址;为空时按独立密码字段自动组装。
        relational_db_password: PostgreSQL 关系库默认 DSN 使用的密码。
        vector_db_password: pgvector 默认 DSN 使用的密码。
        relation_db_dir: 关系数据库运行数据目录。
        vector_db_dir: 向量数据库运行数据目录。
        embedding_model_dir: Embedding 模型本地缓存目录。
        rerank_model_dir: ReRank 模型本地缓存目录。
        knowledge_dir: 本地知识库原始资源目录,用于 frontmatter 结构化预处理扫描。
        frontmatter_dir: 结构化知识文档 JSON 目录,用于 frontmatter_bootstrap 输出与 knowledge_bootstrap 输入。
        log_dir: 日志文件输出目录。
        """

        project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
        base_data_dir: Path = field(default_factory=lambda: Path("./runtime"))
        relational_dsn: str = ""
        vector_dsn: str = ""
        relational_db_password: str = "postgres"
        vector_db_password: str = "postgres"
        relation_db_dir: Path = field(default_factory=lambda: Path("db/relation"))
        vector_db_dir: Path = field(default_factory=lambda: Path("db/vector"))
        embedding_model_dir: Path = field(default_factory=lambda: Path("models/embedding"))
        rerank_model_dir: Path = field(default_factory=lambda: Path("models/rerank"))
        knowledge_dir: Path = field(default_factory=lambda: Path("resources/knowledge"))
        frontmatter_dir: Path = field(default_factory=lambda: Path("frontmatter"))
        log_dir: Path = field(default_factory=lambda: Path("logs"))

        def __post_init__(self) -> None:
            """初始化后统一展开并规范化所有路径配置。"""

            self.project_root = Path(self.project_root).expanduser().resolve()
            self.base_data_dir = self._resolve_project_path(self.base_data_dir)
            self.relation_db_dir = self._resolve_runtime_path(self.relation_db_dir)
            self.vector_db_dir = self._resolve_runtime_path(self.vector_db_dir)
            self.embedding_model_dir = self._resolve_runtime_path(self.embedding_model_dir)
            self.rerank_model_dir = self._resolve_runtime_path(self.rerank_model_dir)
            self.knowledge_dir = self._resolve_project_path(self.knowledge_dir)
            self.frontmatter_dir = self._resolve_runtime_path(self.frontmatter_dir)
            self.log_dir = self._resolve_runtime_path(self.log_dir)
            if not self.relational_dsn:
                self.relational_dsn = self._build_postgres_dsn(self.relational_db_password)
            if not self.vector_dsn:
                self.vector_dsn = self._build_postgres_dsn(self.vector_db_password)

        def _resolve_project_path(self, path_value: Path | str) -> Path:
            """将相对路径转换为基于 project_root 的绝对路径。"""

            path = Path(path_value).expanduser()
            if path.is_absolute():
                return path.resolve()
            return (self.project_root / path).resolve()

        def _resolve_runtime_path(self, path_value: Path | str) -> Path:
            """将相对路径转换为基于 base_data_dir 的绝对路径。"""

            path = Path(path_value).expanduser()
            if path.is_absolute():
                return path.resolve()
            return (self.base_data_dir / path).resolve()

        def ensure_directories(self) -> None:
            """创建运行目录、模型目录、日志目录以及知识库资源目录。"""

            self.base_data_dir.mkdir(parents=True, exist_ok=True)
            self.relation_db_dir.mkdir(parents=True, exist_ok=True)
            self.vector_db_dir.mkdir(parents=True, exist_ok=True)
            self.embedding_model_dir.mkdir(parents=True, exist_ok=True)
            self.rerank_model_dir.mkdir(parents=True, exist_ok=True)
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)
            self.frontmatter_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir.mkdir(parents=True, exist_ok=True)

        @staticmethod
        def _build_postgres_dsn(password: str) -> str:
            """根据独立密码字段组装默认 PostgreSQL DSN。"""

            escaped_password = quote_plus(password)
            return f"postgresql+psycopg://postgres:{escaped_password}@localhost:5432/agent_service"

    @dataclass(slots=True)
    class ModelConfig:
        """
        管理模型提供商、推理参数、系统提示词与重排模型配置。

        provider: 模型服务提供方类型,默认兼容 OpenAI API。
        model_name: 主推理模型名称。
        api_key: 主推理模型 API Key。
        base_url: 主推理模型 API 基础地址。
        small_model_provider: 小模型服务提供方类型,默认兼容 OpenAI API。
        small_model_name: 小模型名称,用于轻量分类、摘要或事实抽取任务。
        small_model_api_key: 小模型 API Key。
        small_model_base_url: 小模型 API 基础地址。
        small_model_temperature: 小模型采样温度。
        small_model_timeout_seconds: 小模型请求超时时间,单位为秒。
        temperature: 模型采样温度。
        timeout_seconds: 模型请求超时时间,单位为秒。
        system_prompt: Agent 默认系统提示词。
        retrieval_context_system_prompt: 检索增强上下文注入时使用的系统提示词模板。
        embedding_model_name: Embedding 模型名称。
        rerank_model_name: RAG 召回结果重排模型名称。
        """

        provider: str = "openai-compatible"
        model_name: str = ""
        api_key: str = ""
        base_url: str = ""
        small_model_provider: str = "openai-compatible"
        small_model_name: str = ""
        small_model_api_key: str = ""
        small_model_base_url: str = ""
        small_model_temperature: float = 0.0
        small_model_timeout_seconds: int = 120
        temperature: float = 0.0
        timeout_seconds: int = 240
        system_prompt: str = "你是一个具备自主能力的 AI Agent。"
        retrieval_context_system_prompt: str = (
            "以下是与当前问题相关的历史记忆和知识片段,回答时优先参考,但不要编造未出现的信息。\n"
            "上下文优先级:\n"
            "- 第一优先级: 当前 session 的短期历史消息。\n"
            "- 第二优先级: 当前 session 的长期摘要记忆。\n"
            "- 第三优先级: 外部知识库检索结果。"
        )
        embedding_model_name: str = ""
        rerank_model_name: str = ""

        def resolve_primary_temperature(self, requested_temperature: float | None = None) -> float:
            """
            为主模型返回兼容当前 provider 约束的温度值。

            requested_temperature: 调用方显式指定的温度;为空时回退到主模型默认温度。
            """

            return self._normalize_temperature_for_model(
                model_name=self.model_name,
                requested_temperature=self.temperature if requested_temperature is None else requested_temperature,
            )

        def resolve_small_temperature(self, requested_temperature: float | None = None) -> float:
            """
            为小模型返回兼容当前 provider 约束的温度值。

            requested_temperature: 调用方显式指定的温度;为空时回退到小模型默认温度。
            """

            return self._normalize_temperature_for_model(
                model_name=self.small_model_name,
                requested_temperature=(
                    self.small_model_temperature if requested_temperature is None else requested_temperature
                ),
            )

        @staticmethod
        def _normalize_temperature_for_model(*, model_name: str, requested_temperature: float) -> float:
            """
            根据模型兼容性要求规范温度值。

            目前 Kimi `kimi-k2` 系列要求 temperature 固定为 1,否则接口会返回
            `invalid temperature: only 1 is allowed for this model`。

            model_name: 实际调用的模型名称。
            requested_temperature: 调用方想使用的温度值。
            """

            normalized_model_name = model_name.strip().lower()
            if normalized_model_name.startswith("kimi-k2"):
                return 1.0
            return float(requested_temperature)

    @dataclass(slots=True)
    class MemoryConfig:
        """
        管理上下文窗口、RAG 召回、重排与记忆时效相关参数。

        context_window_tokens: 会话上下文最大 token 窗口。
        max_context_messages: 第一版滑动窗口保留的最近历史消息数量。
        summary_trigger_tokens: 触发上下文摘要压缩的 token 阈值。
        chunk_size: 知识切片目标大小。
        chunk_overlap: 相邻知识切片的重叠大小。
        vector_top_k: 向量检索召回数量。
        keyword_top_k: 关键词检索召回数量。
        rerank_top_k: 重排后保留的最终召回数量。
        score_threshold: 检索结果最低相关性阈值。
        freshness_weight: 时效性在综合排序中的权重。
        relevance_weight: 相关性在综合排序中的权重。
        authority_weight: 权威性在综合排序中的权重。
        knowledge_hash_lock_enabled: 是否启用知识库文件哈希锁。
        """

        context_window_tokens: int = 8192
        max_context_messages: int = 20
        summary_trigger_tokens: int = 6144
        chunk_size: int = 512
        chunk_overlap: int = 128
        vector_top_k: int = 5
        keyword_top_k: int = 5
        rerank_top_k: int = 3
        score_threshold: float = 0.7
        freshness_weight: float = 0.3
        relevance_weight: float = 0.5
        authority_weight: float = 0.2
        knowledge_hash_lock_enabled: bool = True

    @dataclass(slots=True)
    class TaskScheduleConfig:
        """
        管理 LLM 多级任务队列调度参数。

        enabled: 是否启用统一 LLM 调度器。
        redis_url: 可选 Redis 地址,用于共享熔断状态。
        redis_prefix: Redis 键前缀。
        global_max_concurrency: 全局允许同时执行的 LLM 任务上限。
        foreground_agent_worker_count: Agent 主循环 worker 数量。
        background_summary_worker_count: Summary 后台 worker 数量。
        background_fact_worker_count: Fact Extraction 后台 worker 数量。
        foreground_queue_max_size: 主循环队列最大长度。
        background_queue_max_size: 后台队列最大长度。
        default_timeout_seconds: 默认任务超时时间。
        foreground_timeout_seconds: 主循环任务超时时间。
        summary_timeout_seconds: Summary 任务超时时间。
        fact_resolution_timeout_seconds: Fact Extraction 任务超时时间。
        max_retries: 可重试错误的最大重试次数。
        initial_backoff_seconds: 首次退避秒数。
        max_backoff_seconds: 最大退避秒数。
        circuit_breaker_failure_threshold: 熔断器连续失败阈值。
        circuit_breaker_recovery_seconds: 熔断恢复探测时间窗口。
        summary_deduplicate_by_session: 是否按 session 合并 summary 任务。
        drop_low_priority_when_overloaded: 队列满载时是否直接拒绝低优先级任务。
        redis_consumer_group: Redis Stream consumer group 名称。
        redis_stream_maxlen: Redis Stream 近似裁剪上限。
        redis_result_ttl_seconds: 任务结果保留秒数。
        redis_dedup_ttl_seconds: 去重键保留秒数。
        redis_visibility_timeout_seconds: pending message 认领阈值秒数。
        redis_block_timeout_ms: 阻塞拉取超时毫秒数。
        redis_result_poll_interval_seconds: 等待结果时的 Redis 轮询间隔秒数。
        """

        enabled: bool = True
        redis_url: str = ""
        redis_prefix: str = "agent_service:llm_scheduler"
        global_max_concurrency: int = 6
        foreground_agent_worker_count: int = 4
        background_summary_worker_count: int = 1
        background_fact_worker_count: int = 1
        foreground_queue_max_size: int = 256
        background_queue_max_size: int = 256
        default_timeout_seconds: int = 120
        foreground_timeout_seconds: int = 120
        summary_timeout_seconds: int = 180
        fact_resolution_timeout_seconds: int = 120
        max_retries: int = 2
        initial_backoff_seconds: float = 1.0
        max_backoff_seconds: float = 8.0
        circuit_breaker_failure_threshold: int = 5
        circuit_breaker_recovery_seconds: int = 30
        summary_deduplicate_by_session: bool = True
        drop_low_priority_when_overloaded: bool = False
        redis_consumer_group: str = "agent_service_llm_workers"
        redis_stream_maxlen: int = 10000
        redis_result_ttl_seconds: int = 600
        redis_dedup_ttl_seconds: int = 600
        redis_visibility_timeout_seconds: int = 120
        redis_block_timeout_ms: int = 1000
        redis_result_poll_interval_seconds: float = 0.2

    constants: Constants = field(default_factory=Constants)
    storage: StorageConfig = field(default_factory=StorageConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    task_schedule: TaskScheduleConfig = field(default_factory=TaskScheduleConfig)

    @classmethod
    def load_config(
        cls,
        overrides: Mapping[str, Any] | None = None,
        *,
        load_env: bool = True,
        load_dotenv: bool = True,
        ensure_directories: bool = True,
        ensure_models: bool = True,
    ) -> "AgentConfig":
        """
        加载完整 Agent 配置。

        overrides: 外部传入的显式配置覆盖项,按子配置分组传入,高于环境变量配置。
        load_env: 是否读取环境变量覆盖默认配置。
        load_dotenv: 是否在读取环境变量前加载项目根目录 `.env` 文件。
        ensure_directories: 是否自动创建运行所需目录。
        ensure_models: 是否检查并自动下载本地 Embedding 与 ReRank 模型。
        """

        data = cls._default_mapping()
        if load_dotenv:
            cls._load_dotenv_file(data["storage"]["project_root"])
        if load_env:
            cls._apply_env_overrides(data)
        if overrides:
            cls._deep_update(data, overrides)

        config = cls(
            constants=cls.Constants(**data["constants"]),
            storage=cls.StorageConfig(**data["storage"]),
            model=cls.ModelConfig(**data["model"]),
            memory=cls.MemoryConfig(**data["memory"]),
            task_schedule=cls.TaskScheduleConfig(**data["task_schedule"]),
        )

        if ensure_directories:
            config.storage.ensure_directories()
        if ensure_models:
            config.ensure_local_models()

        return config

    def ensure_local_models(self) -> None:
        """
        检查本地 Embedding 与 ReRank 模型,缺失时调用下载脚本补齐。

        该方法是 `scripts/download_model.py` 在配置层的唯一入口。`load_config()`
        和 `AgentCore.__init__()` 都会调用它,保证配置加载和 Agent 启动路径均能
        触发模型存在性检查。
        """

        from agent_service.scripts.download_model import ensure_models

        ensure_models(
            embedding_model_name=self.model.embedding_model_name,
            embedding_model_dir=self.storage.embedding_model_dir,
            rerank_model_name=self.model.rerank_model_name,
            rerank_model_dir=self.storage.rerank_model_dir,
        )

    @classmethod
    def _default_mapping(cls) -> dict[str, dict[str, Any]]:
        """返回所有子配置的默认值映射。"""

        data = asdict(cls())
        data["storage"]["relational_dsn"] = ""
        data["storage"]["vector_dsn"] = ""
        return data

    @staticmethod
    def _apply_env_overrides(data: dict[str, dict[str, Any]]) -> None:
        """读取 AGENT_ 前缀环境变量并覆盖对应配置项。"""

        env_mapping: dict[str, tuple[str, str, Any]] = {
            "AGENT_APP_NAME": ("constants", "app_name", str),
            "AGENT_DEFAULT_SESSION_NAME": ("constants", "default_session_name", str),
            "AGENT_MEMORY_TAG": ("constants", "memory_tag", str),
            "AGENT_KNOWLEDGE_TAG": ("constants", "knowledge_tag", str),
            "AGENT_DISPLAY_MODE": ("constants", "default_display_mode", str),
            "AGENT_PROJECT_ROOT": ("storage", "project_root", str),
            "AGENT_BASE_DATA_DIR": ("storage", "base_data_dir", str),
            "AGENT_RELATIONAL_DSN": ("storage", "relational_dsn", str),
            "AGENT_VECTOR_DSN": ("storage", "vector_dsn", str),
            "AGENT_RELATIONAL_DB_PASSWORD": ("storage", "relational_db_password", str),
            "AGENT_VECTOR_DB_PASSWORD": ("storage", "vector_db_password", str),
            "AGENT_RELATION_DB_DIR": ("storage", "relation_db_dir", str),
            "AGENT_VECTOR_DB_DIR": ("storage", "vector_db_dir", str),
            "AGENT_EMBEDDING_MODEL_DIR": ("storage", "embedding_model_dir", str),
            "AGENT_RERANK_MODEL_DIR": ("storage", "rerank_model_dir", str),
            "AGENT_KNOWLEDGE_DIR": ("storage", "knowledge_dir", str),
            "AGENT_FRONTMATTER_DIR": ("storage", "frontmatter_dir", str),
            "AGENT_LOG_DIR": ("storage", "log_dir", str),
            "AGENT_MODEL_PROVIDER": ("model", "provider", str),
            "AGENT_MODEL_NAME": ("model", "model_name", str),
            "AGENT_MODEL_API_KEY": ("model", "api_key", str),
            "AGENT_MODEL_BASE_URL": ("model", "base_url", str),
            "AGENT_SMALL_MODEL_PROVIDER": ("model", "small_model_provider", str),
            "AGENT_SMALL_MODEL_NAME": ("model", "small_model_name", str),
            "AGENT_SMALL_MODEL_API_KEY": ("model", "small_model_api_key", str),
            "AGENT_SMALL_MODE_API_KEY": ("model", "small_model_api_key", str),
            "AGENT_SMALL_MODEL_BASE_URL": ("model", "small_model_base_url", str),
            "AGENT_SMALL_MODEL_TEMPERATURE": ("model", "small_model_temperature", float),
            "AGENT_SMALL_MODEL_TIMEOUT_SECONDS": ("model", "small_model_timeout_seconds", int),
            "AGENT_MODEL_TEMPERATURE": ("model", "temperature", float),
            "AGENT_MODEL_TIMEOUT_SECONDS": ("model", "timeout_seconds", int),
            "AGENT_SYSTEM_PROMPT": ("model", "system_prompt", str),
            "AGENT_RETRIEVAL_CONTEXT_SYSTEM_PROMPT": ("model", "retrieval_context_system_prompt", str),
            "AGENT_EMBEDDING_MODEL_NAME": ("model", "embedding_model_name", str),
            "AGENT_RERANK_MODEL_NAME": ("model", "rerank_model_name", str),
            "AGENT_CONTEXT_WINDOW_TOKENS": ("memory", "context_window_tokens", int),
            "AGENT_MAX_CONTEXT_MESSAGES": ("memory", "max_context_messages", int),
            "AGENT_SUMMARY_TRIGGER_TOKENS": ("memory", "summary_trigger_tokens", int),
            "AGENT_MEMORY_CHUNK_SIZE": ("memory", "chunk_size", int),
            "AGENT_MEMORY_CHUNK_OVERLAP": ("memory", "chunk_overlap", int),
            "AGENT_MEMORY_VECTOR_TOP_K": ("memory", "vector_top_k", int),
            "AGENT_MEMORY_KEYWORD_TOP_K": ("memory", "keyword_top_k", int),
            "AGENT_MEMORY_RERANK_TOP_K": ("memory", "rerank_top_k", int),
            "AGENT_MEMORY_SCORE_THRESHOLD": ("memory", "score_threshold", float),
            "AGENT_MEMORY_FRESHNESS_WEIGHT": ("memory", "freshness_weight", float),
            "AGENT_MEMORY_RELEVANCE_WEIGHT": ("memory", "relevance_weight", float),
            "AGENT_MEMORY_AUTHORITY_WEIGHT": ("memory", "authority_weight", float),
            "AGENT_MEMORY_HASH_LOCK_ENABLED": (
                "memory",
                "knowledge_hash_lock_enabled",
                AgentConfig._parse_bool,
            ),
            "AGENT_TASK_SCHEDULE_ENABLED": ("task_schedule", "enabled", AgentConfig._parse_bool),
            "AGENT_TASK_SCHEDULE_REDIS_URL": ("task_schedule", "redis_url", str),
            "AGENT_TASK_SCHEDULE_REDIS_PREFIX": ("task_schedule", "redis_prefix", str),
            "AGENT_TASK_SCHEDULE_GLOBAL_MAX_CONCURRENCY": (
                "task_schedule",
                "global_max_concurrency",
                int,
            ),
            "AGENT_TASK_SCHEDULE_FOREGROUND_WORKERS": (
                "task_schedule",
                "foreground_agent_worker_count",
                int,
            ),
            "AGENT_TASK_SCHEDULE_SUMMARY_WORKERS": (
                "task_schedule",
                "background_summary_worker_count",
                int,
            ),
            "AGENT_TASK_SCHEDULE_FACT_WORKERS": (
                "task_schedule",
                "background_fact_worker_count",
                int,
            ),
            "AGENT_TASK_SCHEDULE_FOREGROUND_QUEUE_MAX_SIZE": (
                "task_schedule",
                "foreground_queue_max_size",
                int,
            ),
            "AGENT_TASK_SCHEDULE_BACKGROUND_QUEUE_MAX_SIZE": (
                "task_schedule",
                "background_queue_max_size",
                int,
            ),
            "AGENT_TASK_SCHEDULE_DEFAULT_TIMEOUT_SECONDS": (
                "task_schedule",
                "default_timeout_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_FOREGROUND_TIMEOUT_SECONDS": (
                "task_schedule",
                "foreground_timeout_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_SUMMARY_TIMEOUT_SECONDS": (
                "task_schedule",
                "summary_timeout_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_FACT_TIMEOUT_SECONDS": (
                "task_schedule",
                "fact_resolution_timeout_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_MAX_RETRIES": ("task_schedule", "max_retries", int),
            "AGENT_TASK_SCHEDULE_INITIAL_BACKOFF_SECONDS": (
                "task_schedule",
                "initial_backoff_seconds",
                float,
            ),
            "AGENT_TASK_SCHEDULE_MAX_BACKOFF_SECONDS": (
                "task_schedule",
                "max_backoff_seconds",
                float,
            ),
            "AGENT_TASK_SCHEDULE_CIRCUIT_BREAKER_FAILURE_THRESHOLD": (
                "task_schedule",
                "circuit_breaker_failure_threshold",
                int,
            ),
            "AGENT_TASK_SCHEDULE_CIRCUIT_BREAKER_RECOVERY_SECONDS": (
                "task_schedule",
                "circuit_breaker_recovery_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_SUMMARY_DEDUPLICATE_BY_SESSION": (
                "task_schedule",
                "summary_deduplicate_by_session",
                AgentConfig._parse_bool,
            ),
            "AGENT_TASK_SCHEDULE_DROP_LOW_PRIORITY_WHEN_OVERLOADED": (
                "task_schedule",
                "drop_low_priority_when_overloaded",
                AgentConfig._parse_bool,
            ),
            "AGENT_TASK_SCHEDULE_REDIS_CONSUMER_GROUP": (
                "task_schedule",
                "redis_consumer_group",
                str,
            ),
            "AGENT_TASK_SCHEDULE_REDIS_STREAM_MAXLEN": (
                "task_schedule",
                "redis_stream_maxlen",
                int,
            ),
            "AGENT_TASK_SCHEDULE_REDIS_RESULT_TTL_SECONDS": (
                "task_schedule",
                "redis_result_ttl_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_REDIS_DEDUP_TTL_SECONDS": (
                "task_schedule",
                "redis_dedup_ttl_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_REDIS_VISIBILITY_TIMEOUT_SECONDS": (
                "task_schedule",
                "redis_visibility_timeout_seconds",
                int,
            ),
            "AGENT_TASK_SCHEDULE_REDIS_BLOCK_TIMEOUT_MS": (
                "task_schedule",
                "redis_block_timeout_ms",
                int,
            ),
            "AGENT_TASK_SCHEDULE_REDIS_RESULT_POLL_INTERVAL_SECONDS": (
                "task_schedule",
                "redis_result_poll_interval_seconds",
                float,
            ),
        }
        for env_name, (section, key, caster) in env_mapping.items():
            raw_value = os.getenv(env_name)
            if raw_value is None or raw_value == "":
                continue
            data[section][key] = caster(raw_value)

    @staticmethod
    def _load_dotenv_file(project_root: Path | str) -> None:
        """
        从项目根目录 `.env` 文件加载环境变量。

        project_root: 项目根目录路径。
        """

        dotenv_path = Path(project_root).expanduser().resolve() / ".env"
        if not dotenv_path.exists():
            return

        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    @staticmethod
    def _deep_update(target: dict[str, Any], source: Mapping[str, Any]) -> None:
        """递归合并显式传入的配置覆盖项。"""

        for key, value in source.items():
            if isinstance(value, Mapping) and isinstance(target.get(key), dict):
                AgentConfig._deep_update(target[key], value)
                continue
            target[key] = value

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """将环境变量中的布尔字符串转换为 bool。"""

        normalized = value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}

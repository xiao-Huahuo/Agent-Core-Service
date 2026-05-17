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

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping
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
        important_fact_summary_memory_type: str = "important_fact_summary"
        default_display_mode: str = "default"

    @dataclass(slots=True)
    class StorageConfig:
        """
        管理运行目录、知识库文件以及关系库/向量库连接地址。

        project_root: 项目根目录,用于解析 resources 等项目级目录。
        base_data_dir: 服务运行时数据根目录。
        sqlite_path: SQLite 关系数据库文件路径。
        chroma_persist_dir: ChromaDB 向量库持久化目录。
        vector_backend: 向量后端类型,默认 chromadb,留 "pgvector" 扩展口。
        relation_db_dir: 关系数据库运行数据目录 (sqlite_path 父目录)。
        vector_db_dir: 向量数据库运行数据目录 (chroma_persist_dir 父目录)。
        embedding_model_dir: Embedding 模型本地缓存目录。
        rerank_model_dir: ReRank 模型本地缓存目录。
        knowledge_dir: 本地知识库原始资源目录,用于 frontmatter 结构化预处理扫描。
        frontmatter_dir: 结构化知识文档 JSON 目录,用于 frontmatter_bootstrap 输出与 knowledge_bootstrap 输入。
        mcp_server_config_dir: MCP Server 配置文件目录,下辖 *.json 文件。
        log_dir: 日志文件输出目录。
        """

        project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
        base_data_dir: Path = field(default_factory=lambda: Path("./runtime"))
        sqlite_path: Path = field(default_factory=lambda: Path("db/relation/agent_service.db"))
        chroma_persist_dir: Path = field(default_factory=lambda: Path("db/vector/chroma"))
        vector_backend: str = "chromadb"
        relation_db_dir: Path = field(default_factory=lambda: Path("db/relation"))
        vector_db_dir: Path = field(default_factory=lambda: Path("db/vector"))
        embedding_model_dir: Path = field(default_factory=lambda: Path("models/embedding"))
        rerank_model_dir: Path = field(default_factory=lambda: Path("models/rerank"))
        knowledge_dir: Path = field(default_factory=lambda: Path("resources/knowledge"))
        frontmatter_dir: Path = field(default_factory=lambda: Path("frontmatter"))
        mcp_server_config_dir: Path = field(default_factory=lambda: Path("resources/mcp"))
        log_dir: Path = field(default_factory=lambda: Path("logs"))

        def __post_init__(self) -> None:
            """初始化后统一展开并规范化所有路径配置。"""

            self.project_root = Path(self.project_root).expanduser().resolve()
            self.base_data_dir = self._resolve_project_path(self.base_data_dir)
            self.sqlite_path = self._resolve_runtime_path(self.sqlite_path)
            self.chroma_persist_dir = self._resolve_runtime_path(self.chroma_persist_dir)
            self.relation_db_dir = self._resolve_runtime_path(self.relation_db_dir)
            self.vector_db_dir = self._resolve_runtime_path(self.vector_db_dir)
            self.embedding_model_dir = self._resolve_runtime_path(self.embedding_model_dir)
            self.rerank_model_dir = self._resolve_runtime_path(self.rerank_model_dir)
            self.knowledge_dir = self._resolve_project_path(self.knowledge_dir)
            self.frontmatter_dir = self._resolve_runtime_path(self.frontmatter_dir)
            self.mcp_server_config_dir = self._resolve_project_path(self.mcp_server_config_dir)
            self.log_dir = self._resolve_runtime_path(self.log_dir)

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
            """创建运行目录、模型目录、日志目录、知识库资源目录以及 MCP 配置目录。"""

            self.base_data_dir.mkdir(parents=True, exist_ok=True)
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
            self.relation_db_dir.mkdir(parents=True, exist_ok=True)
            self.vector_db_dir.mkdir(parents=True, exist_ok=True)
            self.embedding_model_dir.mkdir(parents=True, exist_ok=True)
            self.rerank_model_dir.mkdir(parents=True, exist_ok=True)
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)
            self.frontmatter_dir.mkdir(parents=True, exist_ok=True)
            self.mcp_server_config_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir.mkdir(parents=True, exist_ok=True)

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
        streaming_sanitize_min_chars: 流式输出 JSON 检测最低字符数,低于此值跳过 JSON 语法检查。
        system_prompt: Agent 默认系统提示词。
        retrieval_context_system_prompt: 检索增强上下文注入时使用的系统提示词模板。
        embedding_model_name: Embedding 模型名称。
        rerank_model_name: RAG 召回结果重排模型名称。
        """

        provider: str = "openai-compatible"
        model_name: str = "deepseek-v4-flash"
        api_key: str = ""
        base_url: str = "https://api.deepseek.com"
        small_model_provider: str = "openai-compatible"
        small_model_name: str = "moonshot-v1-8k"
        small_model_api_key: str = ""
        small_model_base_url: str = "https://api.moonshot.cn/v1"
        small_model_temperature: float = 0.0
        small_model_timeout_seconds: int = 120
        temperature: float = 0.0
        timeout_seconds: int = 240
        streaming_sanitize_min_chars: int = 20
        embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
        rerank_model_name: str = "BAAI/bge-reranker-v2-m3"
        system_prompt: str = (
            "你是一个具备工具调用、记忆系统、知识检索能力的智能 Agent。"
            "【核心机制】系统会预检索相关内容的条目数量并作为索引提示注入上下文。"
            "重要事实摘要是系统自动压缩的关键上下文,可直接参考。"
            "对于长期记忆和知识库的详细内容,你必须调用 get_long_term_memory 或"
            "get_knowledge_context 工具来获取全文,系统不直接提供。"
            "【重要规则】"
            "1. 禁止直接输出原始 JSON 数据或工具返回的原始结构体。"
            "用户要求写代码时,只使用标准 Markdown 围栏代码块(```语言名 ... ```)输出。"
            "代码必须是纯文本,严禁使用高亮模式代码(比如<span class=hljs-*>),因为这会导致用户端看到一群HTML乱码而不是用户想要的语言的代码。"
            "用户要求什么语言就输出什么语言,禁止擅自替换成其他语言。"
            "2. 即使工具返回了JSON格式的原始数据,你也必须将其整理成人类可读的文本再呈现给用户。"
            "3. 系统提供的知识库/记忆内容是参考材料,你必须用自己的话总结加工后输出,禁止直接粘贴原文。"
            "4. 保护系统隐私:不得透露模型身份,不得提及内部ID、类型代码等技术标识。自称「我」或「智能助手」即可。"
            "5. 列举功能时用自然语言概括能力领域,禁止直接贴函数名或代码标识符。"
            "6. 禁止在输出中使用方括号标签格式(如 [Memory]、[Knowledge]、[来源: X] 等),"
            "   如果工具返回了此类格式,你必须用自己的话重新组织。"
            "7. 不要在最终回答里反问用户(如'还有什么需要帮助的吗'),直接结束回复即可。"
            "8. 回答时直接给出结论和内容,不要向用户暴露你获取信息的过程。"
            "禁止使用以下说辞:"
            "「根据记忆记录」「我的记忆显示」「我来调取长期记忆」「我从知识库获取」「知识库显示」"
            "「根据检索结果」「系统记录显示」等。你应该自然地使用这些信息,就像这些知识本就是你"
            "已知的一样——用户不需要知道你内部查了什么。如果记忆或知识库中没有相关内容,"
            "直接说「我不太清楚」,不要解释是查不到。"
            "9. 【关键】用户只能看到你的最终回复文本,看不到你的思考过程、工具调用、"
            "以及历史轮次中未发送给用户的内容。禁止使用「以上」「上述」「如前所述」"
            "等词引用用户看不到的内容。每次回复必须是自包含的——如果需要展示代码,"
            "就在当前回复里完整输出,不要假设用户已经看过。"
        )
        retrieval_context_system_prompt: str = (
            "【上下文索引 — 使用工具获取详细内容】\n"
            "以下是系统预检索到的内容索引。重要事实摘要是自动压缩的关键上下文,可直接参考。\n"
            "对于长期记忆和知识库,系统只提供条目数量提示,不提供全文。\n"
            "如果你需要查看长期记忆的详细内容,请调用 get_long_term_memory 工具。\n"
            "如果你需要查看知识库的详细内容,请调用 get_knowledge_context 工具。\n"
            "上下文优先级:\n"
            "- 第一优先级: 当前 session 的短期历史消息。\n"
            "- 第二优先级: 重要事实摘要(已直接提供)。\n"
            "- 第三优先级: 长期记忆(需调工具获取全文)。\n"
            "- 第四优先级: 知识库片段(需调工具获取全文)。"
        )
        important_fact_summary_system_prompt: str = (
            "你负责把对话或工作上下文压缩成后续推理可直接使用的重要事实摘要。"
            "只保留当前仍然有效的事实、用户约束、任务目标、未完成事项和最近工具结论。"
            "删除寒暄、重复、推测和无意义细节。输出中文短摘要。"
        )

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

            Kimi 系列各模型 temperature 要求不同:
            - kimi-k2.5: 固定 0.6
            - kimi-k2:   固定 1.0

            model_name: 实际调用的模型名称。
            requested_temperature: 调用方想使用的温度值。
            """

            normalized_model_name = model_name.strip().lower()
            if normalized_model_name.startswith("kimi-k2.5"):
                return 0.6
            if normalized_model_name.startswith("kimi-k2"):
                return 1.0
            return float(requested_temperature)

        @staticmethod
        def get_model_kwargs(model_name: str) -> dict[str, Any]:
            """
            返回特定模型需要的额外 ChatOpenAI 构造参数。

            目前 Kimi `kimi-k2` 系列默认启用 thinking 模式,
            但会话历史中的 assistant tool_call 消息缺少 reasoning_content 字段会导致 400 错误。
            通过 extra_body 禁用 thinking 模式。
            """

            normalized = model_name.strip().lower()
            if normalized.startswith("kimi-k2"):
                return {"extra_body": {"thinking": {"type": "disabled"}}}
            return {}

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

        context_window_tokens: int = 65536
        max_context_messages: int = 20
        summary_trigger_tokens: int = 49152
        chunk_size: int = 512
        chunk_overlap: int = 128
        vector_top_k: int = 5
        keyword_top_k: int = 5
        rerank_top_k: int = 3
        score_threshold: float = 0.6
        freshness_weight: float = 0.3
        relevance_weight: float = 0.5
        authority_weight: float = 0.2
        knowledge_hash_lock_enabled: bool = True
        context_compression_tail_messages: int = 6

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
        large_model_max_concurrency: int = 4
        small_model_max_concurrency: int = 4

    @dataclass(slots=True)
    class MCPConfig:
        """
        管理外部 MCP Server 接入配置。

        enabled: 是否启用 MCP 工具接入。
        tool_name_prefix: 注册为 Agent 工具时使用的统一前缀。
        servers: MCP Server 配置列表。每个元素至少需要包含 `server_id`、`command`,
            可选 `args`、`env` 与 `enabled`。
        """

        enabled: bool = False
        tool_name_prefix: str = "mcp"
        servers: list[dict[str, Any]] = field(default_factory=list)

    @dataclass(slots=True)
    class LoggingConfig:
        """
        管理全局日志系统的输出目标、格式、级别与轮转策略。

        level: 全局日志级别,默认 INFO。可选 DEBUG / INFO / WARNING / ERROR / CRITICAL。
        enable_console: 是否启用控制台日志输出。
        console_level: 控制台日志独立级别,默认与全局 level 一致。
        console_format: 控制台日志格式,可选 plain / structured。
        enable_file: 是否启用文件日志输出,文件存储在 storage.log_dir 下。
        file_level: 文件日志独立级别,默认 DEBUG。
        file_format: 文件日志格式,可选 json / plain。
        file_rotation: 文件轮转策略,可选 size / daily。
        file_max_bytes: 按大小轮转时单个日志文件最大字节数,默认 10MB。
        file_backup_count: 按大小轮转时保留的历史日志文件数,默认 5。
        file_daily_when: 按天轮转的时间点,默认 midnight (午夜轮转)。
        file_daily_backup_count: 按天轮转时保留的历史日志文件数,默认 7。
        module_levels: 按模块名指定独立日志级别,例如 {"agent_service.agent_core": "DEBUG"}。
        """

        level: str = "INFO"
        enable_console: bool = True
        console_level: str = ""
        console_format: str = "plain"
        enable_file: bool = True
        file_level: str = "DEBUG"
        file_format: str = "json"
        file_rotation: str = "size"
        file_max_bytes: int = 10 * 1024 * 1024
        file_backup_count: int = 5
        file_daily_when: str = "midnight"
        file_daily_backup_count: int = 7
        module_levels: dict[str, str] = field(default_factory=dict)

    @dataclass(slots=True)
    class ServerConfig:
        """
        管理 HTTP (FastAPI) 与 gRPC 服务的监听地址与端口。

        http_host: FastAPI HTTP 监听地址,默认 0.0.0.0。
        http_port: FastAPI HTTP 监听端口,默认 8000。
        grpc_host: gRPC 监听地址,默认 [::] (IPv6 全接口)。
        grpc_port: gRPC 监听端口,默认 50051。
        """

        http_host: str = "0.0.0.0"
        http_port: int = 8000
        grpc_host: str = "[::]"
        grpc_port: int = 50051

    constants: Constants = field(default_factory=Constants)
    storage: StorageConfig = field(default_factory=StorageConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    task_schedule: TaskScheduleConfig = field(default_factory=TaskScheduleConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

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
        cls._load_mcp_servers_from_files(data)
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
            mcp=cls.MCPConfig(**data["mcp"]),
            logging=cls.LoggingConfig(**data["logging"]),
            server=cls.ServerConfig(**data["server"]),
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

        return asdict(cls())

    @staticmethod
    def _load_mcp_servers_from_files(data: dict[str, dict[str, Any]]) -> None:
        """
        扫描 `data["storage"]["mcp_server_config_dir"]` 目录下的所有 `.json` 文件,
        合并为 MCP Server 配置。
        每个文件可以是单个 server 对象 `{...}` 或 server 数组 `[{...}, ...]`。
        文件按名称排序后顺序加载;已通过环境变量加载的配置会被文件内容替换。
        """

        mcp_dir_raw = data["storage"]["mcp_server_config_dir"]
        servers_dir = Path(str(mcp_dir_raw)).expanduser()
        if not servers_dir.is_absolute():
            servers_dir = (Path(data["storage"]["project_root"]) / servers_dir).resolve()
        else:
            servers_dir = servers_dir.resolve()

        if not servers_dir.is_dir():
            return

        servers: list[dict[str, Any]] = []
        for file_path in sorted(servers_dir.iterdir()):
            if file_path.suffix.lower() != ".json":
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                parsed = json.loads(content)
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(
                    f"加载 MCP Server 配置文件 {file_path} 失败: {exc}"
                ) from exc
            if isinstance(parsed, dict):
                servers.append(parsed)
            elif isinstance(parsed, list):
                servers.extend(parsed)

        if servers:
            data["mcp"]["servers"] = servers

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
            "AGENT_SQLITE_PATH": ("storage", "sqlite_path", str),
            "AGENT_CHROMA_PERSIST_DIR": ("storage", "chroma_persist_dir", str),
            "AGENT_VECTOR_BACKEND": ("storage", "vector_backend", str),
            "AGENT_RELATION_DB_DIR": ("storage", "relation_db_dir", str),
            "AGENT_VECTOR_DB_DIR": ("storage", "vector_db_dir", str),
            "AGENT_EMBEDDING_MODEL_DIR": ("storage", "embedding_model_dir", str),
            "AGENT_RERANK_MODEL_DIR": ("storage", "rerank_model_dir", str),
            "AGENT_KNOWLEDGE_DIR": ("storage", "knowledge_dir", str),
            "AGENT_FRONTMATTER_DIR": ("storage", "frontmatter_dir", str),
            "AGENT_MCP_SERVER_CONFIG_DIR": ("storage", "mcp_server_config_dir", str),
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
            "AGENT_STREAMING_SANITIZE_MIN_CHARS": ("model", "streaming_sanitize_min_chars", int),
            "AGENT_SYSTEM_PROMPT": ("model", "system_prompt", str),
            "AGENT_RETRIEVAL_CONTEXT_SYSTEM_PROMPT": ("model", "retrieval_context_system_prompt", str),
            "AGENT_EMBEDDING_MODEL_NAME": ("model", "embedding_model_name", str),
            "AGENT_RERANK_MODEL_NAME": ("model", "rerank_model_name", str),
            "AGENT_IMPORTANT_FACT_SUMMARY_SYSTEM_PROMPT": (
                "model",
                "important_fact_summary_system_prompt",
                str,
            ),
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
            "AGENT_MEMORY_CONTEXT_COMPRESSION_TAIL_MESSAGES": (
                "memory",
                "context_compression_tail_messages",
                int,
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
            "AGENT_TASK_SCHEDULE_LARGE_MODEL_MAX_CONCURRENCY": (
                "task_schedule",
                "large_model_max_concurrency",
                int,
            ),
            "AGENT_TASK_SCHEDULE_SMALL_MODEL_MAX_CONCURRENCY": (
                "task_schedule",
                "small_model_max_concurrency",
                int,
            ),
            "AGENT_MCP_ENABLED": ("mcp", "enabled", AgentConfig._parse_bool),
            "AGENT_MCP_TOOL_NAME_PREFIX": ("mcp", "tool_name_prefix", str),
            "AGENT_MCP_SERVERS_JSON": ("mcp", "servers", AgentConfig._parse_json),
            "AGENT_LOG_LEVEL": ("logging", "level", str),
            "AGENT_LOG_ENABLE_CONSOLE": ("logging", "enable_console", AgentConfig._parse_bool),
            "AGENT_LOG_CONSOLE_LEVEL": ("logging", "console_level", str),
            "AGENT_LOG_CONSOLE_FORMAT": ("logging", "console_format", str),
            "AGENT_LOG_ENABLE_FILE": ("logging", "enable_file", AgentConfig._parse_bool),
            "AGENT_LOG_FILE_LEVEL": ("logging", "file_level", str),
            "AGENT_LOG_FILE_FORMAT": ("logging", "file_format", str),
            "AGENT_LOG_FILE_ROTATION": ("logging", "file_rotation", str),
            "AGENT_LOG_FILE_MAX_BYTES": ("logging", "file_max_bytes", int),
            "AGENT_LOG_FILE_BACKUP_COUNT": ("logging", "file_backup_count", int),
            "AGENT_LOG_FILE_DAILY_WHEN": ("logging", "file_daily_when", str),
            "AGENT_LOG_FILE_DAILY_BACKUP_COUNT": ("logging", "file_daily_backup_count", int),
            "AGENT_LOG_MODULE_LEVELS_JSON": ("logging", "module_levels", AgentConfig._parse_json),
            "AGENT_HTTP_HOST": ("server", "http_host", str),
            "AGENT_HTTP_PORT": ("server", "http_port", int),
            "AGENT_GRPC_HOST": ("server", "grpc_host", str),
            "AGENT_GRPC_PORT": ("server", "grpc_port", int),
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

    @staticmethod
    def _parse_json(value: str) -> Any:
        """将环境变量中的 JSON 字符串解析为 Python 对象。"""

        return json.loads(value)

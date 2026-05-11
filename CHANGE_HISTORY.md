# CHANGE HISTORY

## 2026-05-11
- 新增 `agent_service/core/agent_config.py` 中的分层配置体系，包含 `Constants`、`StorageConfig`、`ModelConfig`、`MemoryConfig` 与 `AgentConfig.load_config()`。
- 配置支持默认值、环境变量覆盖、显式 `overrides` 覆盖以及运行目录自动创建，作为后端统一常量与环境变量入口。
- 按结构要求将子配置类收敛为 `AgentConfig` 的内部类，并为每个子配置类补充职责注释，避免配置定义分散在模块顶层。
- 为每个配置字段补充集中式说明,并为配置加载、路径解析、目录创建和环境变量解析函数补充注释。
- 修正 `StorageConfig.base_data_dir` 字段缺失和默认值不一致问题,确保直接实例化与 `load_config()` 的运行目录语义一致。
- 将知识库配置从单文件 `knowledge_file_path` 调整为项目根目录下的 `resources/knowledge` 目录,并根据现有 `runtime` 结构新增关系库、向量库、Embedding 模型和 ReRank 模型运行目录配置。
- 为 `ModelConfig` 增加 `embedding_model_name` 字段和对应环境变量覆盖项,并统一 `system_prompt` 的字段默认值与加载默认值。
- 将默认配置映射改为从 dataclass 默认实例生成,减少字段默认值与加载默认值重复维护导致的配置漂移。
- 新增 `scripts/download_model.py` 模型检查与下载脚本,并在 `AgentConfig.load_config()` 中默认检查 Embedding 与 ReRank 模型,缺失时自动调用下载逻辑。
- 调整 `scripts/download_model.py` 命令行入口为四参数形式,支持手动指定 Embedding/ReRank 的模型名称和本地绝对下载目录。
- 按最新开发规范为 `scripts/download_model.py` 增加文件头部功能说明和命令行使用说明。
- 按最新开发规范为 `core/agent_config.py` 增加文件头部功能说明、配置加载说明和模型检查说明。
- 新增最基础的 LangGraph Agent 循环骨架,包含 `agent -> action -> agent -> summary -> END` 图结构,并按每个节点文件只实现一个节点的要求拆分模型决策、工具调用和摘要节点。
- 新增 `scripts/draw_agent_graph.py` 静态 SVG 绘图脚本,并让 `AgentCore` 每次初始化时在项目根目录生成 `agent_graph.svg` 节点流程图。
- 修正绘图脚本硬编码图结构的问题,改为读取 `CompiledStateGraph.get_graph()` 的真实节点和边来生成 SVG。
- 将绘图脚本调整为从实际图结构生成 Mermaid 文本,并在存在 Mermaid CLI 时自动渲染 SVG,避免维护手写 SVG 坐标逻辑。
- 为 `AgentCore` 增加测试用编译图注入入口,并在 `tests/test_agent_core_service.py` 中补充初始化绘图、流式输出和 Mermaid 生成测试。
- 在 `main.py` 中新增 AgentCore 本地演示调用和 `/agent/test` 接口,用于直接查看 Mermaid 图生成结果和流式输出包装结果。
- 将 `main.py` 从测试假图演示调整为真实 LLM 调用入口,默认通过 `AgentCore(config=config)` 构建真实图并执行 `ModelDecisionNode` 的 ChatOpenAI 决策。
- 为 `AgentConfig.load_config()` 增加项目根目录 `.env` 加载能力,进程环境变量优先于 `.env`,避免本地运行时模型配置无法读取。
- 新增 PostgreSQL 版 Session 会话管理基础实现,包含 `models/session.py` 数据库模型、`schemas/session.py` DTO 和 `services/session_service.py` 业务服务。
- 将默认 PostgreSQL DSN 调整为 SQLAlchemy psycopg3 方言 `postgresql+psycopg://`,与 `psycopg[binary]` 依赖保持一致。

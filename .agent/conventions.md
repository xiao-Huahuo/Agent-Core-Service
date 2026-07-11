# MetaWeave 编码规范

本文件是 MetaWeave 项目的强制性编码规范。所有参与者（人类开发者及 AI 编码助手）在修改项目代码前必须阅读并遵守本文件。违反本规范的代码不得合入主分支。

---

## 通用规范

### 文件编码

所有源文件必须使用 UTF-8 编码保存，推荐 UTF-8 no BOM。这一要求覆盖 Python、JavaScript、Vue、JSON、Markdown、protobuf 以及 `resources/` 目录下的一切文本文件。

Windows 平台的默认代码页（CP936/GBK/ANSI）会在处理中文、日文、emoji、特殊标点时产生乱码。因此严禁依赖 PowerShell 的 `Get-Content`、`Set-Content`、`Out-File` 等 cmdlet 的默认编码行为。如果必须在脚本中使用 PowerShell，需显式指定 `-Encoding UTF8`。更可靠的做法是统一使用 Python 或 Node.js 的 UTF-8 读写能力，避免经过 PowerShell 管道。

提交前确认 VS Code 右下角状态栏的编码标记为 "UTF-8"，Git 配置 `core.quotepath=false`，终端代码页设为 65001。已经被写乱码的文件需要从 Git 历史中恢复原始内容后重新修改，严禁将乱码直接再次写回。

### 修改日志

每次对代码的任何修改（包括 bug fix、feature、重构、配置变更）都必须在项目根目录的 `CHANGE_HISTORY.md` 中追加一条修改日志。日志格式为日期标题 `## YYYY-MM-DD` 下列出修改条目，每条以短横线开头，说明修改内容和原因。

### 文档注释

每一个 Python 文件的开头必须包含文件功能与使用说明的 docstring。每一个公开类必须包含描述其职责和使用方式的 docstring。每一个公开函数和方法必须包含说明其功能、参数含义和返回值含义的 docstring。

这些注释的目标受众是刚接触该模块的开发者。注释应该回答"这个文件做什么"、"这个类承担什么角色"、"这个函数接受什么输入并产出什么输出"。私有实现细节的内部逻辑不要求逐行注释，但非显而易见的业务规则、约束条件和边界情况应该用单行注释标注。

---

## 后端 Python 规范

### 配置管理

一切全局常量和环境变量的读取必须通过 `agent_service.core.agent_config` 模块的 `AgentConfig` 类完成。业务模块应当显式接收一个 `AgentConfig` 实例作为构造参数，严禁在模块体或函数内部直接调用 `os.environ.get()` 或书写魔法字符串。

`AgentConfig` 内部采用嵌套 dataclass 结构组织配置域：`Constants`（应用级常量）、`StorageConfig`（路径与存储）、`ModelConfig`（模型提供商与推理参数）、`MemoryConfig`（RAG 参数与上下文窗口）、`TaskScheduleConfig`（调度与并发）、`MCPConfig`（外部工具服务器）、`LoggingConfig`（日志系统）、`ServerConfig`（HTTP/gRPC 绑定地址）。

加载配置的入口是 `AgentConfig.load_config()`。推荐用法是每个服务对象通过构造参数注入 `config`，在模块作用域不要持有对 `load_config()` 返回值的全局引用。

### 模型层规范

数据模型分为 `models/` 和 `schemas/` 两个模块：

`models/` 存放 SQLModel 数据库映射类，命名约定为 `XXXBase`（基础字段集合）和 `XXXRecord`（完整表映射，继承 `XXXBase` 并带有 `__tablename__` 和主键字段）。`schemas/` 存放 Pydantic DTO：`XXXCreate`（创建请求体，继承 `XXXBase`）、`XXXUpdate`（更新请求体，通常继承 `SQLModel`）、`XXXOut`（响应体，继承 `XXXBase` 并附加 `created_at`、`updated_at` 等只读字段）。

所有时间字段统一使用 UTC 无时区感知未必可靠：数据库写入时通过 `utc_now()` 工厂函数生成带 `timezone.utc` 的 datetime，读取时再统一归一化。

### API 规范

MetaWeave 同时对外提供 REST 和 gRPC 两套接口，二者必须保持功能等价。如果修改或新增 REST 端点，必须同步修改 `protos/agent_service.proto` 和 `agent_service/api/grpc/servicer.py` 中的对应 RPC 实现。

REST 端点分布在 `agent_service/api/rest/` 下按资源拆分的路由模块中（`agent.py`、`sessions.py`、`settings.py`），全局前缀和中间件逻辑在 `main.py` 中注册。gRPC servicer 集中在 `agent_service/api/grpc/servicer.py` 这一个文件中实现。

流式接口使用 SSE（Server-Sent Events）协议。每个 SSE 事件的 JSON payload 必须包含 `node`、`content`、`tool_calls`、`trace`、`model_name` 字段。服务端需在客户端断开连接时通过 `GeneratorExit` 异常传播取消信号。

### 工具开发规范

新增内置工具时在 `agent_service/tools/builtin.py` 中编写纯 Python 函数，并在对应的分组列表（`UTILITY_TOOL_DEFINITIONS`、`MEMORY_TOOL_DEFINITIONS`、`KNOWLEDGE_TOOL_DEFINITIONS`、`STATE_TOOL_DEFINITIONS`）中登记 `BuiltinToolDefinition`。工具函数接受简单类型参数并返回字符串，不直接访问数据库或配置——运行时上下文通过 `agent_service.tools.runtime_context.get_tool_runtime()` 获取。

工具函数的 docstring 就是 LLM 看到的功能描述，因此必须准确、简洁、中文优先。

MCP 外部工具通过 `agent_service/tools/mcp/` 子模块接入。每个 MCP 服务器在 `resources/mcp/` 下用 JSON 文件配置，启动时自动发现、连接并注册为带前缀的工具名（格式 `{prefix}__{server_id}__{tool_name}`）。

### 代码风格

类型注解必须使用 Python 3.12 语法：`list[X]` 替代 `List[X]`，`dict[str, Any]` 替代 `Dict[str, Any]`，使用 `X | None` 替代 `Optional[X]`。所有文件顶部写 `from __future__ import annotations`。

slots dataclass 是推荐的数据载体：`@dataclass(slots=True)`。它比 NamedTuple 支持可变形为，比普通类减少字典开销。

日志通过 `logging.getLogger(__name__)` 获取模块级 Logger，使用 `logger.info("描述 | key=%s", value)` 的管道符分隔格式（结构化日志约定）。

条件导入和大体积依赖（ChromaDB、MCP SDK、transformers）使用 try/except 延迟导入，避免在模块导入阶段就触发重依赖加载。代表案例是 `LongTermMemoryService` 对 ChromaDB 的导入检查和 `MCPClient._import_mcp_sdk()` 的延迟导入。

### 测试规范

测试文件放在 `tests/` 目录下，文件名以 `test_` 开头。测试应覆盖业务逻辑层（services）、工具层（tools）和 API 层（rest）。测试不允许连接真实的外部模型 API，必须使用 mock 或 stub 替代。

---

## 前端规范

### 组件组织

页面级组件放在 `src/views/`，以大驼峰命名（如 `UserProfile.vue`）。可复用的子组件放在 `src/components/`，按页面功能组织子目录（蛇形命名法），如 `src/components/user_profile/UserInfo.vue`。全局通用组件放在 `src/components/common/` 下。

每个文件的组件 `name` 属性必须与文件名保持一致。单文件不超过 1000 行，超过时必须拆分为更小的子组件。组件设计遵循"能复用不重写、能抽象不重复、能组件化不冗余"原则。

### 路由管理

API 路由统一登记在 `src/router/api_routes.js`。页面路由、路由守卫和 vue-router 相关逻辑统一登记在 `src/router/index.js`。各业务模块通过集中导出的路由函数调用 API，不自行拼装 fetch/axios 实例。

### 配色与主题

全局配色由 `src/stores/settings.js` 集中管理。`theme_mode` 控制明暗主题，通过设置 `document.documentElement` 的 `data-theme` 属性切换 `light`/`dark`/系统跟随。`color_scheme` 控制全局色板，通过 `data-color-scheme` 属性驱动 `src/assets/main.css` 与 `src/assets/ui-system.css` 中的 CSS 变量。

禁止在任何页面或组件中编写未在 `settings.js` 中登记的自定义配色方案。一切的配色偏好变更都必须走 settings store。

### 字体管理

全局字体栈由 `src/assets/ui-system.css` 和 `src/assets/main.css` 俩文件控制。`body` 的中英文默认字体、标题字体、等宽代码字体均在这两个文件中通过 CSS 变量定义。禁止在任何页面或组件中单独声明 `font-family` 覆盖全局字体。

### 界面风格

MetaWeave 前端定位为开发者工具面板，遵循"工业感"设计原则。

所有元素采用直角配细线边框（`border-radius: 0`，1px `border` 区分层次）。低饱和冷色调配色，深色背景使用 `#0d1117` 或 `#1a1a2e`，文字使用 `#e6e6e6`，强调色仅使用一个核心色。一个页面不超过四种颜色。

图标仅在功能需要时使用（刷新、发送、展开、折叠等操作入口），使用 Feather Icons 或 Lucide 的极简线条图标集。禁止装饰性图标和 emoji。

字体采用系统原生字体栈。中文优先使用 system-ui / PingFang SC / Noto Sans SC 无衬线体，等宽使用 JetBrains Mono 或 Cascadia Code。禁止使用微软雅黑、楷体等传统字体。

间距遵循网格化固定值（4px / 8px / 12px / 16px / 24px / 32px），不随机留白。过渡动画限制在 150ms 以内且仅用于功能性状态变化（hover 变色、loading 脉冲），不添加淡入淡出类装饰性动画。

禁止使用圆角矩形包裹短文本（胶囊标签）、阴影卡片、渐变背景等"AI 生成感"强烈的视觉元素。按钮、输入框、面板一律直角。

### 登录注册

登录和注册功能统一使用 Home 页面已有的登录注册组件，禁止在项目中创建其他的独立登录页面或注册页面。

---

## 部署与运维

`Dockerfile` 和 `docker-compose.yml` 仅在确有需要时修改（如增加环境变量、调整端口映射），且修改必须在 `CHANGE_HISTORY.md` 中记录内容和原因。禁止随意调整基础镜像版本、文件挂载路径或网络配置。

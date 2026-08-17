# 启动,构建与部署

## 启动

### 环境要求

* Python 3.12+
* Node.js 22.18，或 Node.js 24.12 及以上版本
* 已配置 LLM API（OpenAI 兼容接口）

### 1. 配置模型

推荐直接在 Editor 客户端的设置页填写主模型与小模型的名称、API Key 和 OpenAI 兼容 API 地址。根目录 `.env` 只用于提供服务级默认值，例如 `AGENT_MODEL_API_KEY` 和 `AGENT_SMALL_MODEL_API_KEY`。

### 2. 启动后端（FastAPI）

```bash
# 安装后端依赖
pip install -r agent_service/requirements.txt

# 启动服务（HTTP: 8002, gRPC: 50051）
uvicorn main:app --host 0.0.0.0 --port 8002
```
开发模式默认将项目目录下的 `resources/knowledge/` 作为知识库根目录，用户可在前端重新选择知识库。服务启动和切换知识库都不会自动重建全部索引；灌库由前端的全库、目录或单文件操作按需触发，启动阶段不占用 embedding、rerank 与额外磁盘资源。

### 3. 启动前端（Electron + Vite + Vue 3）

##### 编辑器(Editor)--主要关注知识库与图谱的可视化
```bash
cd editor
npm i --verbose
npm run dev:electron # 开发模式 → http://localhost:5173
```

### 4. 验证

编辑器: `npm run dev:electron`时Electron自动打开浏览器内核窗口.或者在浏览器中访问 `http://localhost:5173`,但浏览器模式下可能某些文件服务不兼容.

后端健康检查：`curl http://localhost:8002/health`

### 5. 必要设置

1. **务必在 Editor 客户端的设置中配置模型名称、API Key 和 OpenAI 兼容 API 地址**。主模型与小模型均由用户选择；未配置可用模型时无法使用 Agent 功能。
2. 如果需要启用联网搜索引擎,则需要在设置中配置好代理地址(如:`http://127.0.0.1:11719`),因为DuckDuckGo需要连接外网才能正常使用,否则即使启用了联网引擎也无法使用联网.

## 构建

### Electron 桌面安装包（推荐）

当前正式发布形态是 **Electron 桌面端 + 内置后端 exe + NSIS 安装包**：

- Electron 负责桌面窗口、托盘、悬浮窗和安装器。
- `AgentService.exe` 作为内置后端放入安装包的 `resources/backend/`。
- 默认资源模板放入安装包的 `resources/default-resources/`。
- 运行时由 Electron 拉起后端,窗口加载 `http://127.0.0.1:8002`。
- 安装器允许用户选择安装目录。
- `runtime/` 不进入安装包。数据库、模型缓存、日志和上传文件在用户数据目录首次运行时自动生成；知识库 Markdown 与 frontmatter 则保存在各知识库自己的 `.mw/` 中。

```bash
cd editor
npm install
npm run dist:win
```

构建过程会依次执行：

1. `npm run build-only`: 构建前端静态资源到 `editor/dist/`。
2. `npm run prepare:default-resources`: 生成安装包资源模板到 `editor/.packaging/default-resources/`。
3. `npm run build:backend`: 调用 PyInstaller 读取根目录 `AgentService.spec`,生成 `dist/AgentService.exe`。
4. `electron-builder --win nsis`: 生成 Windows NSIS 安装包,输出到 `editor/release/`。

资源模板规则：

```text
editor/.packaging/default-resources/
├── mcp/
│   └── example.json      # MCP 配置模板
├── safety/               # 从 resources/safety 原样复制
├── skills/               # 从 resources/skills 原样复制
└── knowledge/            # 只创建空目录,不复制本地知识库内容
```

最终产物：

```text
editor/release/
├── MetaWeave Setup <version>.exe   # 安装包,安装时可选择路径
└── win-unpacked/                   # 免安装展开目录,用于调试
```

### 后端 exe（单独构建）

如果只需要后端单文件 exe,可在根目录单独执行：

```bash
# 安装 PyInstaller
pip install pyinstaller
# 安装后端依赖
pip install -r agent_service/requirements.txt
# 打包（读取 AgentService.spec）
pyinstaller AgentService.spec
```

产物为 `dist/AgentService.exe`。`.spec` 配置只打包程序和 `editor/dist/` 前端静态资源。**不要把 `resources/` 或 `runtime/` 放入 PyInstaller datas**；默认资源由 Electron 安装包外置携带。

### 部署结构

安装后的结构大致如下：

```text
MetaWeave/
├── MetaWeave.exe
├── resources/
│   ├── backend/
│   │   └── AgentService.exe
│   └── default-resources/
│       ├── mcp/
│       ├── safety/
│       ├── skills/
│       └── knowledge/
└── ...
```

首次运行后,Electron 会把默认资源模板复制到用户数据目录,并通过环境变量让后端使用该目录：

```text
%APPDATA%/MetaWeave/
├── .env
├── resources/           # 自动生成空目录,放入文件即可覆盖 exe 内置默认
│   ├── knowledge/       # 默认知识库,启动不自动灌库,按需触发
│   ├── mcp/             # 首次复制 example.json 模板,可放 .json MCP 服务器配置
│   └── safety/          # 放 sensitive_words.json,覆盖内置安全词库
└── runtime/             # 自动生成: db/ models/ logs/ uploads/
```

> **读取规则**: 正式安装包运行时以后端收到的 `AGENT_PROJECT_ROOT=%APPDATA%/MetaWeave` 为准。`resources/` 是用户可编辑目录,`runtime/` 是运行期数据目录,二者都不写入安装目录和后端 exe。

### 运行方式

桌面安装包安装完成后,直接启动 `MetaWeave`。Electron 会自动拉起内置后端并打开桌面窗口。

如需调试后端 exe,也可以单独运行：

```bash
AgentService.exe
```

后端单独运行时提供 API 和前端页面：`http://localhost:8002`。`runtime/`、外置 `resources/` 和 `.env` 空文件首次启动自动生成。首次启动后需要在 `.env` 或客户端设置中配置大小模型 API Key、模型名和 API 地址,否则 Agent 功能不可用。单独运行后端 exe 时如果希望模拟安装包行为,可手动设置 `AGENT_PROJECT_ROOT` 和 `AGENT_BASE_DATA_DIR`。

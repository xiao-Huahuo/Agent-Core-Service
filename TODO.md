# 最高优先级规则：对用户提供的 TODO，必须**逐句**建立可验证的实现与验收对应关系,**必须**自己根据TODO反复逐句修改,**绝对禁止**自己随便实现一个长得像TODO但不符合用户的TODO的某一句的事情发生,每一句用户TODO都要在代码中有迹可循,每一句TODO都要遵守开发规范。禁止将任何一项降级为 MVP、替代实现或视觉近似；如无法复用用户指定组件，必须先说明阻塞并征得用户同意。完成前必须逐项进行实际界面冒烟验证，并报告未完成项。

- 题外话: MHS,Anthropic发明的新接口体系,使得AI物联网成为现实,可能成为和MCP同等级的AI统一化接口.

### UI/UX
- [ ] 工作区大卡片响应式布局优化: 主要测试手段是打开联网搜索侧边栏然后拽住左边拖动,此时工作区大卡片就会左右坍缩,根据当前宽度实现响应式布局:

### TODOs
- [ ] 给readme加badge(![显示名称](https://img.shields.io/badge/左边文字-右边文字-颜色),或者可跳转的[![Release](https://img.shields.io/badge/release-v1.8.0-brightgreen)](https://github.com/你的用户名/你的仓库/releases),或者动态badge![Stars](https://img.shields.io/github/stars/OWNER/REPO))
### IDEAs
- [ ] DSH Adapter的实现
  - 文档位于`docs/ADAPTER_DESIGN.md`
- [ ] 维护后端的屎山代码(+readme表示在readme的文件树里面补充),禁止修改任何业务逻辑,仅转移和规范和适配代码.务必遵循`开发规范.md`:
  - `agent_core.py`是上帝类,拆解:
    - `agent_service/agent_core/runtime/`:    
      - 图运行、流式事件转换、会话、附件、子 Agent、取消、模型调用、token 统计和错误恢复,每种分别创建一个文件.
  - `main.py`拆解:  (以下全都+readme)
    - `agent_service/core/bootstrap/`: 
      - `services_bootstrap.py` 服务创建和相互连接    
      - `grpc_bootstrap.py` 启动grpc    
      - `config_bootstrap.py` 加载配置
      - `models_bootstrap.py` 加载和下载模型
    - `agent_service/core/lifespan.py` 生命周期
  - `agent_service/api/rest/deps.py`里面定义了大量 `_xxx_service` 全局变量，再由 `main.py` 逐个赋值.
    - 新建 ApplicationServices 容器，由 bootstrap 创建并保存到 app.state.services；REST 使用 FastAPI Depends 获取依赖。AgentConfig 只管理静态配置，不持有任何 service 实例。
  - `knowledge_library_service.py` 知识库业务太大.
    - 彻底拆解,拆到`agent_service/services/knowledge_library/`里面.原服务文件删除.   
      - 文件树,入库,预览,搜索,回收站,其他操作,分别写一个文件.
  - `knowledge_graph_service.py` 知识图谱业务太大.
    - 彻底拆解,拆到`agent_service/services/knowledge_graph/`里面.原服务文件删除.   
      - 按照图谱的构成过程拆.
  - 多达十几个 service 自行调用 `SQLModel.metadata.create_all()`,而且数据库没有一个真正的统一迁移器.
    - 新建`agent_service/core/db/engine.py`: 统一的数据库factory.    +readme
    - 引入Alembic,建立带版本号的migration,新建`agent_service/core/db/migration.py`,集中处理数据库版本迁移,只在应用启动前统一迁移一次.
    - 将所有service里面越权的`create_all()`去掉,接收 session/repository，不自行建表或建 engine,将现有所有 `ALTER TABLE` 转成幂等迁移版本。
  - `agent_service/core/agent_config.py`暂时不要变
  - `agent_service/tools/`里面的builtin太散乱.
    - 把所有的builtin全都弄到`agent_service/tools/builtin/`里面,按照系统规定的职责划分文件.一类工具一个文件.只移动builtin.
    - `builtin.py`仅保留加载工具的核心逻辑.
  - service层重构: 现有的service层太混杂,单文件和领域文件夹混在一起.
    - 将所有的单文件都归类放在领域文件夹里面,允许一个文件夹只放一个文件.(我就要这么做!)
  - `agent_service/api/grpc/servicer.py`太大,并且业务内容过多.
    - 业务内容全都拆到`agent_service/api/grpc/handlers/`里面去,按照业务领域划分文件     +readme
    - 共享业务逻辑进入`agent_service/services/use_cases/`或者现有的领域service
    - 新增`agent_service/api/grpc/mappers/`处理错误和响应     +readme
    - 本体只承担注册和转换和派发职责.
    - servicer之间相互解耦,REST 和 gRPC 只做 DTO 转换、调用 use case、错误映射。
### BUGs

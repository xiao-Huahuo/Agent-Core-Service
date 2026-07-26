### TODOs

- [ ] 系统性的真正打通多模态解析链,包括图片OCR解析,扫描件pdf的图片渲染,pptx的渲染与预览等.
- [ ] 尝试使用[OpenDataloader-PDF](https://github.com/opendataloader-project/opendataloader-pdf)代替OCR进行解析?

- [ ] 多agent:智能体蜂群,AgentSworm
- [ ] Skill能力是Agent从通用Agent走向专用Agent的关键。其设计如下：
  - 所有的内置Skill默认统一存放在根目录的`resources/skills/`文件夹中，用户级Skill放在用户知识库目录下的`.agents/skills/`文件夹中。
  - 统一兼容[OpenAI开放标准](https://developers.openai.com/api/docs/guides/tools-skills)作为主标准，兼容[Anthropic标准](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)扩展字段。
  - 目录结构：
    ```text
    skill-name/
      SKILL.md (必须有）
      scripts/ （可选）
      references/ （可选）
      assets/ （可选）
    ```
  - 用户级Skill按用户知识库隔离，**用户登录或知识库目录变更时**扫描Skill目录，读取元信息，建立索引，将已启用Skill的基本索引信息注入上下文。
  - 对于非Simple思考模式下的每次用户输入，Agent决策前，在入口节点设置一个`Skill路由器`节点： 调用小模型，返回针对用户当前询问场景适合的3个Skill。 小模型不可用或返回异常时，使用关键词/description 简单匹配。随后将命中的 Skill 正文（`SKILL.md`）注入本轮运行上下文（用户下一轮询问后从上下文中去除），Skill 正文默认只对当前轮生效，下一轮重新路由。。
  - [ ] 调试Skill，协调Skill要求与沙盒/完全访问模式的终端权限。
  - [ ] 左侧图标栏添加一个新的Skill配置页面：
    - 分为Skill概览页面和Skill定制页面。
    - Skill概览页面以卡片形式展示系统自带Skill和用户注入的Skill，用户可开关Skill，可注入自定义的Skill。
    - 点击右上角按钮可查看Skill格式和规范说明。
  - [ ] 配备2个Agent工具： 列出所有Skill；使用Skill（主动召唤`SKILL.md`正文）
- [ ] 可统计的：
  - 工具总计调用次数
  - [ ] 会话内统计右边栏：
    - Dashboard里面理论上需要统计的是“长时统计结果”。因此，dashboard里面的三率饼图放到会话内统计右边栏，三率曲线图改成统计session为单位的，每次message思考耗时图放到会话内统计右边栏。
### BUGs

- [ ] 解决agent输出的代码块没渲染和HTML高亮乱码问题,尤其是修复输出大量含有这种乱码渲染导致页面卡死的问题.(&amp?,span?)
- [ ] 修理安全审核节点不明原因的抽风把正常内容拦截的问题.
- [ ] 解决思考过长导致"HTTP/1.1 400 Bad Request"禁止访问的问题(可能需要彻底的优化上下文构建机制)


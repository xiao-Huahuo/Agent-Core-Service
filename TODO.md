### TODOs

- [ ] 系统性的真正打通多模态解析链,包括图片OCR解析,扫描件pdf的图片渲染,pptx的渲染与预览等.
- [ ] 尝试使用[OpenDataloader-PDF](https://github.com/opendataloader-project/opendataloader-pdf)代替OCR进行解析?
- [ ] 定时自动化任务： 可以给Agent布置定时自动化任务，比如每天晚上9点git commit之类的。
- [ ] 多agent:智能体蜂群,AgentSworm

- [ ] 调试Skill，协调Skill要求与沙盒/完全访问模式的终端权限。
- [ ] 可统计的：
  - 工具总计调用次数
  - [ ] 会话内统计右边栏：
    - Dashboard里面理论上需要统计的是“长时统计结果”。因此，dashboard里面的三率饼图放到会话内统计右边栏，三率曲线图改成统计session为单位的，每次message思考耗时图放到会话内统计右边栏。
### BUGs

- [ ] 解决agent输出的代码块没渲染和HTML高亮乱码问题,尤其是修复输出大量含有这种乱码渲染导致页面卡死的问题.(&amp?,span?)
- [ ] 修理安全审核节点不明原因的抽风把正常内容拦截的问题.
- [ ] 解决思考过长导致"HTTP/1.1 400 Bad Request"禁止访问的问题(可能需要彻底的优化上下文构建机制)


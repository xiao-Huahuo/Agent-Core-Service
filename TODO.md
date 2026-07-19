### TODOs
- [ ] 系统性的真正打通多模态解析链,包括图片解析,扫描件pdf的图片渲染,pptx的渲染与预览,markdown无法真正渲染图片等.
- [ ] 尝试使用[OpenDataloader-PDF](https://github.com/opendataloader-project/opendataloader-pdf)代替OCR进行PDF解析?

### BUGs
- [ ] 修复markdown预览模式显示不了嵌入的图片的问题(显示图片破碎).
- [ ] 解决agent输出的代码块没渲染和HTML高亮乱码问题,尤其是修复输出大量含有这种乱码渲染导致页面卡死的问题.(&amp?,span?)
- [ ] 解决几轮对话之后agent对话越来越卡,流式输出越来越大块的问题
- [ ] 修理安全审核节点不明原因的抽风把正常内容拦截的问题.
- [ ] 解决思考过长导致"HTTP/1.1 400 Bad Request"禁止访问的问题(可能需要彻底的优化上下文构建机制)
- [ ] 修复agent的session有时候没有恰当的重命名的问题.


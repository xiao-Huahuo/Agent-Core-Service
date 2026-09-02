# 子 Agent 完成提示与 DeepSeek reasoning 修复验收

## 用户反馈对应

1. 多子 Agent 完成提示可能多于创建数量
   - 实现：服务端按子 Agent Turn 原子领取 wakeup；SSE 展示与轮询唤醒共用同一 claim。
   - 验收：两个并发观察者仅一个 claim 成功；实际 Agent 页面两个 created 对应两个 completed。
2. thinking 模式工具续轮返回 `reasoning_content` 400
   - 实现：DeepSeek 原始 reasoning 在流式合并、持久化和 assistant tool-call 续轮请求中保留；命名空间模型同样启用适配器。
   - 验收：`unsloth/deepseek-v3.2` 选择 DeepSeek 适配器，序列化请求包含 assistant `reasoning_content`、tool_calls 与后续 ToolMessage。

## 验证结果

- `tests/test_child_agent_manager.py`：12 passed。
- `tests/test_task_scheduler.py`：17 passed。
- `editor/src/stores/__tests__/chat.spec.ts`：26 passed。
- `editor/src/api/__tests__/agentStream.spec.ts`：2 passed。
- `editor/e2e/child-agent-completion-dedup.spec.ts`（Chromium）：1 passed。
- `tests/test_agent_core_service.py`：60 passed，10 个无关既有失败；集中于 ReRank 未加载、上下文预算预期和既有返回值变更。
- 全量 `vue-tsc --build` 仍被无关既有类型错误阻塞；过滤复检确认本次触及的 store、API、路由、API 测试与 E2E 文件没有类型错误。

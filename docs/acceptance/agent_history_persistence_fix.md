# Agent 历史保存与加载修复验收

## 真实数据证据

- 会话：`sess_01766784eac443e898f44e021be2553c`（子Agent结果等待中）。
- 原始数据库事件：926 行。
- 角色分布：469 assistant、437 tool、10 user、10 system。
- 病态重复：418 个空 `wait_for_child_agents` 结果、383 个相同“已收到 3/4”回复。
- 最后一个用户 Turn：339 assistant + 339 tool，持续约 18 分钟。

## 根因与实现

1. 自动唤醒创建新父 run，旧实现只能等待当前父 run 的子 Agent，因而立即返回空结果。
   - 修复：新增 session 级跨父 run 等待；当前父 run 无子任务时自动回退。
2. `agent_max_tool_calls_per_turn` 只限制单个模型响应的并行调用，没有限制整轮累计调用。
   - 修复：最近用户消息后的累计工具调用达到上限时，下一次模型请求解绑全部工具。
3. 聊天历史 API 直接返回内部事件日志，与实时聊天的折叠语义不一致。
   - 修复：新增只供聊天/导出使用的语义投影；上下文和观测仍读取完整日志。

## 验证

- `tests/test_chat_history_projection.py`：2 passed。
- `tests/test_child_agent_manager.py`：13 passed。
- `tests/test_agent_loop_model_tier.py`：22 passed。
- `editor/src/stores/__tests__/chat.spec.ts`：27 passed。
- 真实旧会话只读投影：926 → 69 条。
- Chromium 历史重载：一个“等待子 Agent”行、一个最终回复，1 passed。

# Agent 中途停流后终态全文突现调查

## 结论

根因位于 `LLMTaskScheduler._stream_chat_request` 的 provider chunk 分类。当前代码把 `reasoning_content`、`content` 和 `tool_calls` 当成互斥字段：只有 chunk 同时不含 reasoning 和 tool call 时才读取正文。DeepSeek 的消息契约允许这些字段共存，因此中间正文被静默丢弃；流结束时，LangChain 合并消息仍保存完整正文，Graph 将它作为终态事件发出，前端又以终态全文修正流式前缀，于是出现“先输出一段—停住—最终全文突然出现”。

```text
provider: content + reasoning/tool_calls
                 │
                 ▼
scheduler: reasoning/tool_calls 存在 → 不 yield content_delta
                 │
                 ▼
前端停留在此前已收到的第一段
                 │
                 ▼
provider 完成 → merged AIMessage 含完整 content
                 │
                 ▼
Graph 终态全文 → 前端 authoritative replace → 全文突现
```

## 可重复证据

| 实验 | 实际增量 | 终态内容 | 结论 |
| --- | --- | --- | --- |
| 首块仅正文；后两块同时含正文与 reasoning | 仅收到首块正文；reasoning 正常收到 | 三块正文完整存在 | reasoning 条件静默吞掉后续正文 |
| 单块同时含正文与 tool call | 正文增量为 0 | 正文和 tool call 均完整存在 | tool call 条件静默吞掉正文 |

真实数据库最近 40 条 assistant 记录中有 27 条 Agent 消息：22 条带 reasoning、20 条带工具调用、14 条同时具有正文、reasoning 和工具调用。这不是仅存在于假数据的边界形状，而是当前 `api.deepseek.com / deepseek-v4-flash` 工作流中的常见消息形状。当前 Redis scheduler 未启用，因此 Redis 不是本次主因。

DeepSeek 官方文档的 thinking/tool-call 输出示例也明确展示一个 assistant message 同时具有 `reasoning_content`、`content` 和 `tool_calls`；流式 Chat Completions schema 同时定义 `delta.content` 与 `delta.reasoning_content`，不能由客户端假定互斥：[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)、[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)。

## 排除项

- 不是前端 50ms 草稿缓冲：它最多造成约 50ms 延迟，且结束前会持续冲刷。
- 不是 SSE 事件边界：REST 层通过线程和 Queue 收到一个事件就发送一个事件，并有 3 秒 heartbeat。
- 不是 Vite 压缩缓存：代理主动删除 `Accept-Encoding`，并设置 `no-cache`、`X-Accel-Buffering: no`。
- 不是浏览器事件饥饿：解析器每 16 个 SSE 事件主动让出执行权。
- 不是竞态：受控单线程 chunk 序列可以确定性复现，最终内容与丢失增量严格对应。

## 影响范围

- `simple`：没有工具时，只要 provider chunk 同时带 reasoning 和 content，也会丢正文增量。
- `react` / `plan`：同时受 reasoning 和 tool call 两个过滤条件影响，最容易出现该症状。
- 工具循环：工具执行期间的静默本身可能合理，但工具前说明或下一轮回答被过滤后，会把合理等待放大成终态全文突现。
- Redis：另有旁路缺陷——worker 仅发布 `content_delta`，未发布 `reasoning_delta`；当前未启用，但启用后 Think 流会消失。
- 依赖风险：`langchain-openai` 未锁版本；当前 1.2.1 明示不保证提取第三方 `reasoning_content`，项目却依赖该字段，升级或打包环境变化可能改变症状。

## 推荐修复

1. scheduler 独立处理三个通道：有 reasoning 就发送 reasoning；有字符串 content 就发送 content；tool calls 只负责结构化合并，绝不阻断正文。
2. 本地和 Redis 流使用同一规范化事件结构，Redis 同步发布 reasoning/content/tool-call 状态。
3. 增加无正文内容的观测计数：`raw_content_chars`、`streamed_content_chars`、`final_content_chars`、混合字段 chunk 数；终态差值非零时记录不含正文的 warning。
4. 为 DeepSeek 建立明确的 provider adapter，并锁定 `langchain-openai/openai` 版本；不要依赖 ChatOpenAI 对非标准字段的偶然透传。
5. 保留前端终态修正作为数据完整性兜底，但记录修正字符数；不得用前端逐字补动画掩盖后端丢流。

## 修复验收矩阵

- reasoning-only、content-only、tool-only chunk 各自正确。
- reasoning+content、tool+content、reasoning+tool+content 同块时三个通道均不丢失、不重复。
- 多轮工具调用后，最终正文从第一字到最后一字持续产生 delta，终态差值为 0。
- simple/react/plan 三条入口均覆盖。
- 本地 scheduler 与 Redis scheduler 事件序列一致。
- 通过真实 SSE 代理验证增量到达时间，不只验证最终字符串。
- DeepSeek reasoning 能正确保存并在工具后续请求中回传。

## 观测缺口

当前日志没有记录每次模型调用的原始 chunk 字段形状、各通道字符计数或“终态正文减去已流正文”的差值，因此线上只能看到结果，无法直接定位是哪一批 chunk 被过滤。上述安全计数器应作为修复的一部分，不记录用户正文。

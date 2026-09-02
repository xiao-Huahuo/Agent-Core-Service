# Agent 大块输出与长任务滚动性能验收

## 结论

本轮剩余的“大块输出”不是终态全文突然补齐：抽查真实长回答时，`streamed_content_chars == final_content_chars` 且 `reconciled_content_chars == 0`。可复现根因是前端把正文和 reasoning 固定按 50ms 定时批量提交；长任务滚动卡顿则来自全部历史 Markdown、工具结果和子 Agent 结果持续参与布局与绘制，以及滚动事件逐次同步读取布局。

## 实现与 TODO 对应

- 大块输出：正文和 reasoning 草稿改为在下一个 `requestAnimationFrame` 提交；保留同一帧内合并，避免每个 token 都触发重复渲染，同时取消固定 50ms 的可见批量延迟。
- 链路定位：`stream_diagnostics` 新增 `content_chunk_count` 和 `max_content_chunk_chars`，可区分 provider 原始大 chunk 与客户端显示批量。
- 长任务滚动：消息、工具条和子 Agent 事件启用 `content-visibility: auto` 与记忆式固有尺寸，离屏内容由浏览器跳过布局和绘制。
- 折叠结果：工具结果与子 Agent 详情只在展开时挂载，收起时不再保留大块解析 DOM。
- 滚动处理：滚动事件按动画帧合并，每帧最多执行一次布局读取与状态更新，并在卸载时取消待执行帧。

## 自动化验证

- `python -m pytest tests\\test_task_scheduler.py -q`：17 项通过。
- `npx vitest run src\\stores\\__tests__\\chat.spec.ts src\\components\\editor_workspace\\agent_chat\\__tests__\\CollapsibleRows.spec.ts src\\components\\editor_workspace\\agent_chat\\__tests__\\MessageListAttachmentCitation.spec.ts src\\components\\editor_workspace\\agent_chat\\__tests__\\ChatBubble.spec.ts src\\components\\editor_workspace\\agent_chat\\__tests__\\MarkdownContent.spec.ts --maxWorkers=1`：67 项通过。
- `npm run build-only`：生产构建通过。

## 实际界面冒烟

在 1440×960 的真实 Agent 页面加载 24 轮超长历史消息，并让每第 4 个 Assistant 回答包含约 2000 行的折叠工具结果：

- 6 个折叠工具结果的正文 DOM 挂载数为 0。
- 消息根节点计算样式 `contentVisibility` 为 `auto`。
- 121 帧内从底部滚到顶部再返回底部，最大帧间隔 18.4ms，无超过 50ms 的 Long Task。
- 测试服务以 5ms 间隔发送 60 个单字符正文事件，页面产生 53 次可见长度更新，单次最大增量 2 字符，最终长度 60；未出现先停顿再整块补齐。
- 验收截图：[agent_output_scroll_performance.png](agent_output_scroll_performance.png)。

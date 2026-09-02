# Notes: Agent 大块输出与滚动性能

## Hypotheses
- provider本身以数百或数千字符chunk返回，50ms草稿层只能原样提交。
- SSE网络层仍有缓冲或心跳期间只产生reasoning/tool事件。
- 完成长对话的所有Markdown和工具结果都在同一滚动容器内参与layout/paint。
- 折叠工具结果只把高度压成0,但正文DOM仍挂载。
- 每次scroll同步读取scrollHeight并更新Pinia/父组件。

## Evidence
- 最新真实长回答的`streamed_content_chars == final_content_chars`,且`reconciled_content_chars == 0`,排除终态补齐复发。
- 前端正文和thinking此前固定每50ms提交一次,会把快速token合成明显大块;已改为每动画帧提交。
- ToolCallInline和ChildAgentEventInline折叠时仍完整创建解析后的大结果DOM;已改为展开时才挂载。
- 所有历史Markdown/工具消息原先持续参与布局与绘制;已增加Chromium原生`content-visibility:auto`及记忆式固有尺寸。
- scroll处理原先每个事件同步读取布局;已按requestAnimationFrame合并为每帧一次。
- provider终态诊断新增content chunk数量与最大chunk字符数,用于区分provider整块与客户端批量。
- 真实页面冒烟：60个5ms间隔单字符事件产生53次可见更新,单次最大增量2字符；24轮超长历史往返滚动121帧,最大帧间隔18.4ms且无Long Task；6个收起工具正文均未挂载。

---

# Notes: 子 Agent 终态提示与 DeepSeek 400

## 初步证据
- `ChildAgentManager._emit` 会把每次生命周期事件放入 session 队列，同时回调持久化同一事件。
- `GraphRunnerMixin` 在活动 SSE 中排空 session 事件队列并推给前端。
- 前端 `checkChildAgentsForWakeup` 另行轮询 `/children`，在主流结束后自动发起带 `child_agent_event` 的新 Agent Turn。
- 当前前端去重集合 `seenChildStatus` 只存在于单个 store 内存，无法作为跨窗口/重载的幂等依据。
- 当前 `DeepSeekChatOpenAI` 已尝试在 `_get_request_payload` 中回填 `reasoning_content`，但测试未覆盖 tool-call 续轮。

## 已确认根因
- 多窗口或多个 session store 可同时观察到同一个活动态→终态变化；原实现只有各自内存中的 `seenChildStatus`，没有服务端原子幂等点。
- 主窗口已通过 SSE 显示终态时，镜像窗口的轮询状态不会自动消费该终态，因此仍可能额外触发一次唤醒。
- `DeepSeekChatOpenAI` 仅在模型名以 `deepseek` 开头时启用；`unsloth/deepseek-v3.2` 等命名空间模型落入普通 `ChatOpenAI`，工具续轮丢失必需的 `reasoning_content`。

## 修复策略
- `ChildAgentManager` 按 `run_id + Turn 编号` 原子领取终态唤醒；DSH 追问递增 Turn 后可重新领取。
- 活动 SSE 渲染终态时也领取一次，阻止其他窗口轮询重复唤醒。
- 前端轮询唤醒仅在 claim 成功后发送；终态后的新运行态重新进入监测。
- DeepSeek 适配器按模型路径段识别直连名和命名空间名。

## 最终验证
- 子 Agent 管理器：12 passed；并发 claim 结果固定为一真一假，DSH 新 Turn 可再次领取。
- 调度器：17 passed；真实 tool-call 序列化含 `reasoning_content`。
- 前端 Chat/API：26 + 2 passed。
- Chromium 实际 Agent 页面：2 created、2 completed、2 claim，视觉检查完成。
- 宽回归 `test_agent_core_service.py`：60 passed、10 个无关既有失败。
- 全量 TypeScript 检查仍有无关既有错误；过滤复检确认本次前端文件没有类型错误，定向测试均通过。

---

# Notes: Agent 历史重复

## 用户可见症状
- 会话“子Agent结果等待中”重载后，同一 `wait_for_child_agents` 空结果和“已收到 3/4”回答被连续恢复多次。
- 重复单元同时包含思考、工具等待行与回答，需区分真实多轮保存和前端重复渲染。

## 数据库取证
- session_id=`sess_01766784eac443e898f44e021be2553c`，原始 926 行。
- assistant=469、tool=437、user=10、system=10。
- 空等待 418 次，相同 3/4 回复 383 次；第 10 Turn 有 339 assistant + 339 tool。

## 最终实现与验证
- session 级等待跨越自动唤醒产生的新 parent run。
- 当前用户 Turn 累计 4 次工具调用后解绑工具。
- 历史 API 使用语义投影，原始事件继续供上下文/观测读取。
- 旧会话只读投影 926 → 69；不迁移、不删除用户原始数据。
- Python：2 + 13 + 22 passed；Vitest：27 passed；Chromium 重载：1 passed。

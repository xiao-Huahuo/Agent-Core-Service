# Task Plan: 修复 Agent 大块输出与长任务滚动卡顿

## Goal
确定剩余大块输出发生在provider、SSE还是前端提交层，并让长对话的离屏消息、折叠工具结果不再持续参与布局与绘制。

## TODO—验收对应
- [x] T1：从最新真实消息诊断provider正文chunk大小、数量和终态补齐差值。
- [x] T2：建立能复现大块提交与滚动长任务的前端性能测试。
- [x] T3：修复确认的批量输出根因，不以逐字动画伪装流式。
- [x] T4：离屏完成消息和折叠大结果停止布局/绘制，保持展开与复制能力。
- [x] T5：滚动事件不触发不必要的响应式更新或同步布局。
- [x] T6：真实界面验证长消息连续输出、上下滚动和按钮响应。
- [x] T7：更新当日变更日志与验收报告，完成前重读TODO和开发规范。

## Phases
- [x] Phase 1：读取真实诊断并建立性能基线
- [x] Phase 2：建立失败测试并定位主线程热点
- [x] Phase 3：实施流提交与离屏渲染修复
- [x] Phase 4：串行回归、真实界面冒烟与规范复核

## Decisions Made
- 优先使用浏览器原生 `content-visibility` 和现有草稿缓冲，不引入虚拟列表依赖。
- 只有证据表明provider产生整块chunk时，才在后端增加安全拆分/节奏控制。

## Errors Encountered
- 首轮联合测试中子Agent自动唤醒用例偶发得到2次唤醒；同批修复后重跑全部31项通过，确认不是本次滚动/流提交路径的稳定回归。

## Status
**Complete** - 代码、串行回归、生产构建、真实界面验收、文档和最终规范复核均已完成。

---

# Task Plan: 子 Agent 终态提示去重与 DeepSeek 思考回传修复

## Goal
每个子 Agent Turn 的终态只产生一次用户可见提示，并确保带工具调用的 DeepSeek 思考消息在下一次模型请求中完整回传。

## TODO—验收对应
- [x] T1：创建 N 个子 Agent 时，每个 `run_id`/Turn 的终态提示恰好一次。
- [x] T2：DeepSeek thinking 模式的 assistant tool-call 消息在 tool 结果后的请求中保留 `reasoning_content`，不再返回 400。
- [x] T3：两条缺陷均先由失败测试复现，再修复并串行回归。
- [x] T4：完成实际 Agent 界面冒烟，报告任何无法验证项。

## Phases
- [x] Phase 1：读取规范、技能并梳理双链路
- [x] Phase 2：建立真实失败测试
- [x] Phase 3：实施最小根因修复
- [x] Phase 4：串行回归与实际界面冒烟

## Decisions Made
- 保留当前工作区全部既有未提交改动，不覆盖或回滚。
- 去重必须基于稳定事件身份，不依赖单个前端 store 的瞬时状态。
- reasoning 验证必须覆盖 assistant tool_calls + ToolMessage 的连续请求。

## Errors Encountered
- 初次 `rg` 在 `cmd.exe` 中使用含管道符的正则，被 shell 解释；已改为逐个固定模式查询。
- 前端定向用例最初把 Vitest `-t` 参数放在错误位置，导致全项目用例被收集但目标被跳过；已改为按测试文件串行执行。
- `test_agent_core_service.py` 有 10 个无关既有失败；本次相关定向套件均通过。
- 全量 `vue-tsc --build` 被仓库无关既有类型错误阻塞；本次文件定向 Vitest/E2E 通过。

## Status
**Complete** - 两条用户反馈均完成实现、失败基线、回归与实际界面验收。

---

# Task Plan: 修复 Agent 历史保存与加载重复

## Goal
历史恢复必须与一次真实对话的语义消息一一对应，不重复显示循环中的等待工具、思考或中间回答。

## TODO—验收对应
- [x] T1：确认截图会话的重复记录究竟存在于数据库、历史 API 还是仅由前端恢复放大。
- [x] T2：修复共享持久化/恢复根因，禁止用前端文案去重掩盖坏数据。
- [x] T3：覆盖 Agent 多循环、重复工具等待、历史重载和当前已有坏数据的兼容恢复。
- [x] T4：实际界面重新加载会话，重复等待块不再出现。

## Phases
- [x] Phase 1：读取规范与调试技能
- [x] Phase 2：核对真实数据库与保存/加载链路，建立失败测试
- [x] Phase 3：实施最小根因修复
- [x] Phase 4：串行回归与历史页面冒烟

## Decisions Made
- 数据库、API、前端三层逐层计数；不先假设前端有错。
- 保留现有未提交改动，不回滚其他任务。

## Errors Encountered
- 本地完整 FastAPI lifespan 启动被仓库现有迁移/启动状态阻塞，改用正式 MessageService 直读真实 SQLite，并用 Chromium 验证前端重载。
- 首次历史 E2E 重载时 session 行被活动栏遮挡，改为 DOM 语义点击后通过。

## Status
**Complete** - 真实坏数据、执行循环和历史语义投影均已修复并验收。

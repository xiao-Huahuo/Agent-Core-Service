# Task Plan: 修复 Agent 中途丢流与终态全文突现

## Goal
保证 reasoning、content、tool_calls 在所有 scheduler 路径独立、无损、有序传输，终态正文与已流正文差值为零，并保留可观测兜底。

## TODO—验收对应
- [ ] T1：本地 scheduler 混合字段 chunk 不丢 reasoning/content/tool call。
- [ ] T2：Redis scheduler 与本地事件一致，包含 reasoning delta。
- [ ] T3：记录不含正文的安全计数与终态差值，不记录用户正文。
- [ ] T4：DeepSeek provider reasoning 字段稳定提取，依赖版本锁定。
- [ ] T5：前端保留终态兜底并记录修正字符数，不用动画掩盖后端缺陷。
- [ ] T6：simple/react/plan、工具循环、真实 SSE 代理逐项验证。
- [ ] T7：更新调查报告、当日变更日志；完成前重读 TODO 与开发规范并清理临时文件。

## Phases
- [ ] Phase 1：建立正式失败测试
- [ ] Phase 2：修复 provider chunk 规范化与 Redis parity
- [ ] Phase 3：补齐观测、依赖与前端诊断
- [ ] Phase 4：串行回归、真实 SSE 冒烟与规范复核

## Decisions Made
- 在共享 scheduler 根部修复，不在各调用方重复打补丁。
- 复用现有 `reasoning_delta` / `content_delta` 事件，不引入新依赖或新持久化。

## Errors Encountered
- 暂无。

## Status
**Currently in Phase 1** - 正在把调查中的两个控制实验转成正式测试。

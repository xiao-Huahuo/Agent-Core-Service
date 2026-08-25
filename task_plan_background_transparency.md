# Task Plan: 背景封面指定组件穿透

## Goal
背景封面启用时，让用户指定的界面表面半透明显示背景，同时保持 Skills 卡片不透明。

## Phases
- [x] Phase 1: 定位九项验收对应的真实 class
- [ ] Phase 2: 建立背景启用态样式回归
- [ ] Phase 3: 实现集中式穿透样式
- [ ] Phase 4: 单元测试与逐项 Chromium 视觉冒烟
- [ ] Phase 5: 差异、端口与变更历史审计

## Decisions Made
- 所有覆盖仅挂在 `html[data-app-background-cover='true']` 下，默认外观不变。
- Skills 卡片不进入任何穿透选择器。
- 集中在 `main.css` 使用主题色半透明遮罩与 backdrop blur；不修改重叠业务组件。

## Errors Encountered
- Chromium 将 `color-mix()` 计算为现代 `color(srgb ... / alpha)`，首版测试仅解析 rgba 导致误判；输出 computed color 后修正解析器。
- CSS 契约离屏 fixture 未移除，后续真实 `.topbar` 严格定位命中两个元素；读取结果后立即删除 fixture。
- 知识库悬浮子菜单在 Playwright 等待稳定时因 hover 离开被卸载；对已解析真实按钮使用 `dispatchEvent('click')`。

## Status
**Currently in Phase 2** - 建立实际 class 的背景启用态回归。

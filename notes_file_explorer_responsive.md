# Notes: 文件资源管理器三级响应式布局

## Code Findings

- 主页面链路：`EditorWorkspace.vue` 的 `.main-shell.ide-panel` 内渲染 `FileResourceManager`。
- 联网搜索侧边栏由 `.browser-resizer` 从左侧拖动，`workspaceGridStyle` 改变浏览器列宽并压缩 `.editor-col`。
- `FileResourceManager.css` 当前没有容器查询；仅 `.resource-manager` 有 `min-width: 0`。
- 列表 `.list-view` 固定 `min-width: 900px`，回收站 `.trash-view` 固定 `min-width: 940px`。
- 工具栏是单行 flex，路径、操作和视图切换没有适于三级重排的分组。
- 列表列宽来自 Vue 内联 `gridTemplateColumns`，窄宽度需要用语义单元类切换为 flex 布局，才能保留设置驱动的可选状态列。
- 现有 `top-command-bar.spec.ts` 已有真实拖动 `.browser-resizer` 的测试路径，可直接复用其指针操作方式。

## Verification Evidence

- 修改前：`FileResourceManagerResponsive.spec.ts` 2 项均失败，分别证明无容器查询、无语义重排结构。
- 修改后：响应式结构测试与原有菜单集成测试共 6 项通过。

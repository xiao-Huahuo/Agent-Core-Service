# 密码库实现状态

## 目标

实现独立密码库：普通软件继续直接使用 `user_id`，仅密码库需要主密码二次解锁和仅限密码库的 JWT。

## 已确认

- 密码库需求已更新至 `TODO.md`。
- 已阅读 `开发规范.md`、`.agents/skills/frontend-design/SKILL.md` 和 `.agents/skills/design-md/SKILL.md`。
- `ponytail` 技能不在当前可用的 `.agents` 技能清单中。
- 现有图书馆模式：SQLModel 模型在 `agent_service/models`，服务在 `agent_service/services`，REST 路由在 `agent_service/api/rest`，依赖由 `deps.py` 注入；前端使用 `editor/src/api`、`editor/src/views` 与 `editor/src/components`。
- 普通 `user_id` 为业务侧隔离标识，密码库 JWT 必须带 `user_id` 和 `scope: vault` 并校验。

## 实施计划

1. 新增 vault 模型、schema、服务、REST 路由及启动注入。
2. 新增前端 vault API、页面组件和入口/路由。
3. 增加测试并执行后端和前端验证。

## 已修改

- `TODO.md`：明确密码库二次解锁与 JWT 范围，补充图片、回收站、搜索与导入导出边界。


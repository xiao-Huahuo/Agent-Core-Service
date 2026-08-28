# 后端结构维护基线

> 本文件记录 `d86faa4457d84f03c9474245fd32125a60005a67` 上建立的自动化基线。所有重构阶段必须与这些结果和快照比较。

## 环境

- Branch: `master`
- Commit: `d86faa4457d84f03c9474245fd32125a60005a67`
- Python: 3.12.10
- Node: 22.20.0
- npm: 10.9.3

## 后端测试

- 低内存命令：`python -m tests.contracts.run_serial_pytest`
- 文件总数：64
- 通过：62
- 既有失败：2
- 完整结果：`BASELINE_TESTS.json`
- `test_agent_core_service.py`：Windows native access violation，退出码 3221225477。
- `test_mcp_tool_registry.py`：`echo_text` 注册断言失败。

## 前端测试与构建

- 低内存命令：`python -m tests.contracts.run_serial_vitest`
- spec 总数：130
- 通过：120
- 既有失败：10
- 完整结果：`BASELINE_VITEST.json`
- `npm run type-check`：既有 TypeScript 错误，退出码 2。
- `npm run build-only`：通过。

## 契约快照

- `snapshots/openapi.json`: `ce6fa04f5c2355810b465fbd238b4acbee10a73ab003aa75086b819bd4bb2a7c`
- `snapshots/grpc_descriptor.json`: `b9806b7b25bf920931b6a92d67eed757bd2f017fbca5620e569ffc2d00f7d14f`
- `snapshots/db_schema.json`: `6ccdb5a75d89299d04b7f25fbb33f9783ceecb4d0eae7460d734157e535067d3`

> 初次快照发现统一模型导出遗漏图谱、图书馆、TODO 和密码库表；修正模型注册后重新生成了完整 metadata 快照。业务表定义未改变。
- `snapshots/agent_stream.json`: `56d2a1f4d0bbf604fd0eeab96a21cb79ea8d500ba715654ed4299caa5ae45b77`

## 迁移清单

- 根级 Service 模块：34
- gRPC RPC：123
- builtin 工具：105
- 知识库和知识图谱公开符号：见 `manifests/`。

## 限制

- 本阶段没有启动真实桌面应用，避免在测试基线之后立即加载本地模型造成内存峰值；真实界面冒烟必须在最终阶段逐项完成。

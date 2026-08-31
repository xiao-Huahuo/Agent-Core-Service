# DeepSeek Harness Python SDK

此目录固定自 `deepseek-ai/deepseek-harness` 的 Python SDK 客户端源码，版本与
MetaWeave DSH Runtime 兼容清单共同审核。上游项目采用 MIT License；发行包必须
同时携带上游 `LICENSE` 与 `THIRD_PARTY_NOTICES.md`。

MetaWeave 仅在 `client.py` 维护进程工厂与白名单环境补丁；协议和高层 API 保持
上游结构，升级时必须重新核对 `docs/ADAPTER_DESIGN.md` 的协议验收项。

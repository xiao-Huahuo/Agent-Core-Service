# Notes: Agent 丢流修复

## Root Cause
- `if not tool_calls and not has_reasoning` 把三个可共存通道误当互斥。
- 终态合并消息保留完整 content，Graph/前端因此一次性补齐。

## Required Coverage
- mixed reasoning+content
- mixed tool_calls+content
- Redis reasoning publish
- streamed/final char accounting
- final frontend reconciliation metadata
- simple and graph paths

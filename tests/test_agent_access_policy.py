"""
Agent 权限分层测试。

功能说明:
验证 Agent 每轮权限模式会进入工具运行时,并约束内置文件写操作。
"""

from agent_service.core.agent_config import AgentConfig
from agent_service.tools.builtin import create_knowledge_folder, write_knowledge_file
from agent_service.tools.runtime_context import (
    AGENT_ACCESS_FULL,
    AGENT_ACCESS_READONLY,
    AGENT_ACCESS_SANDBOX,
    clear_tool_runtime,
    normalize_agent_access_mode,
    set_tool_runtime,
)


def test_agent_access_mode_normalization() -> None:
    """权限模式应兼容常见别名,未知值回退为沙盒。"""

    assert normalize_agent_access_mode("readonly") == AGENT_ACCESS_READONLY
    assert normalize_agent_access_mode("read_only") == AGENT_ACCESS_READONLY
    assert normalize_agent_access_mode("full") == AGENT_ACCESS_FULL
    assert normalize_agent_access_mode("unknown") == AGENT_ACCESS_SANDBOX


def test_readonly_access_blocks_builtin_file_writes(tmp_path) -> None:
    """只读权限下内置知识库写工具应在构建文件服务前被拒绝。"""

    config = AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(tmp_path),
                "knowledge_dir": str(tmp_path / "knowledge"),
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )
    set_tool_runtime(
        config=config,
        user_id="access-user",
        session_id="access-session",
        memory_service=None,
        embedding_service=None,
        agent_access_mode=AGENT_ACCESS_READONLY,
    )
    try:
        assert "权限不足" in write_knowledge_file("note.md", "blocked")
        assert "权限不足" in create_knowledge_folder("blocked")
    finally:
        clear_tool_runtime()

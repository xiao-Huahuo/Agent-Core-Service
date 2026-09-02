"""临时打印正式 Agent 工具及其测试文本覆盖；审计完成后删除。"""

from pathlib import Path

from agent_service.tools import ToolRegistry


def main() -> None:
    """按注册顺序输出工具数量和名称。"""

    registry = ToolRegistry.with_builtin_tools()
    test_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("tests").glob("test_*.py")
    )
    missing = [name for name in registry.definitions if name not in test_text]
    print(f"registered={len(registry.definitions)} missing_test_text={len(missing)}")
    print("\n".join(missing))


if __name__ == "__main__":
    main()

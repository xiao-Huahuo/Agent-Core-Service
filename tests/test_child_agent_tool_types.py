"""Public child-agent type mapping tests for the main-agent tool."""

from types import SimpleNamespace

from agent_service.tools.builtin import agent as agent_tools


def test_public_agent_types_map_to_internal_provider_and_category(monkeypatch) -> None:
    """The model-facing type must deterministically own all internal dimensions."""

    calls: list[dict[str, object]] = []
    runtime = SimpleNamespace(child_agent_spawner=lambda **kwargs: calls.append(kwargs) or "ok")
    monkeypatch.setattr(agent_tools, "get_tool_runtime", lambda: runtime)

    assert agent_tools.spawn_child_agent("inspect", agent_type="explore") == "ok"
    assert agent_tools.spawn_child_agent(
        "edit", agent_type="dsh", workspace_root="D:/repo",
    ) == "ok"
    assert agent_tools.spawn_child_agent(
        "fallback", agent_type="coding", workspace_root="D:/repo",
    ) == "ok"

    assert (calls[0]["provider"], calls[0]["category"], calls[0]["access_mode"]) == (
        "native", "explore", "readonly",
    )
    assert (calls[1]["provider"], calls[1]["category"]) == ("dsh", "dsh")
    assert (calls[2]["provider"], calls[2]["category"]) == ("native", "coding")

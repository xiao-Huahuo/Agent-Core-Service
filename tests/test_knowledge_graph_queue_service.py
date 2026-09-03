"""知识图谱动态队列服务回归测试。

功能说明:
验证运行期间可追加新文件、在途路径去重，以及每次入队和出队都会重算聚合进度。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from agent_service.services.knowledge_graph.queue import KnowledgeGraphQueueService


def test_graph_queue_runs_two_tasks_concurrently_and_deduplicates_inflight_path(tmp_path: Path) -> None:
    """同库两个任务应并发且可乱序完成，同时复用仍在途的同一路径。"""

    first_started = threading.Event()
    both_started = threading.Barrier(3)
    releases = {name: threading.Event() for name in ("first.md", "second.md")}
    finished: list[str] = []
    all_finished = threading.Event()
    calls: list[str] = []
    snapshots: list[dict[str, Any]] = []

    def writer(_user_id: str, _library_id: str, **payload: Any) -> None:
        snapshots.append(payload)

    def runner(*, target_source_path: Path, progress_callback: Any, **_kwargs: Any) -> None:
        path = target_source_path.name
        calls.append(path)
        progress_callback(status="running", total=1, current=0, message=path, docs=[{
            "path": path, "name": path, "status": "processing", "progress": 25,
        }])
        if path == "first.md":
            first_started.set()
        both_started.wait(timeout=2)
        assert releases[path].wait(timeout=2)
        finished.append(path)
        if len(finished) == 2:
            all_finished.set()
        progress_callback(status="completed", total=1, current=1, message=path, docs=[{
            "path": path, "name": path, "status": "done", "progress": 100,
        }])

    service = KnowledgeGraphQueueService(runner=runner, progress_writer=writer)
    common = {
        "config": object(), "user_id": "u1", "library_id": "lib1",
        "frontmatter_dir": tmp_path, "user_llm_config": {}, "target_is_dir": False, "force": False,
    }
    first = service.submit(
        **common, target_source_path=tmp_path / "first.md", target_display_path="first.md",
    )
    assert first_started.wait(timeout=2)
    duplicate = service.submit(
        **common, target_source_path=tmp_path / "first.md", target_display_path="first.md",
    )
    appended = service.submit(
        **common, target_source_path=tmp_path / "second.md", target_display_path="second.md",
    )
    both_started.wait(timeout=2)
    releases["second.md"].set()
    while not finished:
        assert not all_finished.wait(timeout=0.01)
    releases["first.md"].set()
    assert all_finished.wait(timeout=2)
    for thread in list(service._states[("u1", "lib1")].threads):
        thread.join(timeout=2)

    assert first["status"] == "queued"
    assert duplicate["status"] == "deduplicated"
    assert appended["status"] == "queued"
    assert set(calls) == {"first.md", "second.md"}
    assert finished == ["second.md", "first.md"]
    assert any(snapshot["total"] == 2 and snapshot["current"] == 0 for snapshot in snapshots)
    assert snapshots[-1]["status"] == "completed"
    assert snapshots[-1]["current"] == snapshots[-1]["total"] == 2

"""知识图谱动态队列服务回归测试。

功能说明:
验证运行期间可追加新文件、在途路径去重，以及每次入队和出队都会重算聚合进度。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from agent_service.services.knowledge_graph.queue import KnowledgeGraphQueueService


def test_graph_queue_appends_during_run_and_deduplicates_inflight_path(tmp_path: Path) -> None:
    """第二次点击应追加新文件，并复用仍在途的同一路径。"""

    first_started = threading.Event()
    release_first = threading.Event()
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
            assert release_first.wait(timeout=2)
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
    release_first.set()
    thread = service._states[("u1", "lib1")].thread
    assert thread is not None
    thread.join(timeout=2)

    assert first["status"] == "queued"
    assert duplicate["status"] == "deduplicated"
    assert appended["status"] == "queued"
    assert calls == ["first.md", "second.md"]
    assert any(snapshot["total"] == 2 and snapshot["current"] == 0 for snapshot in snapshots)
    assert snapshots[-1]["status"] == "completed"
    assert snapshots[-1]["current"] == snapshots[-1]["total"] == 2

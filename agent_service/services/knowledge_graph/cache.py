"""知识图谱章节缓存编排。

本模块按正文和实现版本复用章节结果；缓存存在灰区候选时只重试候选，不重新扫描全文。
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import replace
from typing import Any, Callable

from agent_service.models.knowledge_graph import KnowledgeGraphSectionCache
from agent_service.models.session import utc_now
from agent_service.services.memory.rag.frontmatter_document import StructuredKnowledgeDocument, StructuredKnowledgeSection


def extract_cached_graph_section_payloads(
    *,
    service: Any,
    extractor: Any,
    user_id: str,
    library_id: str,
    document: StructuredKnowledgeDocument,
    max_workers: int,
    cancel_event: threading.Event | None = None,
    on_progress: Callable[[int, int, int, int], None] | None = None,
    force: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[KnowledgeGraphSectionCache], bool]:
    """复用有效章节缓存，只抽取变化章节并单独重试缓存中的灰区候选。"""

    extractor_version = str(getattr(extractor, "extractor_version", "injected-v1"))
    rule_version = str(getattr(extractor, "rule_version", "injected-v1"))
    result_version = str(getattr(extractor, "result_version", "graph-payload-v1"))
    existing = service.list_section_caches(user_id=user_id, library_id=library_id, document_id=document.document_id)
    payloads: dict[str, dict[str, Any]] = {}
    changed_sections: list[StructuredKnowledgeSection] = []
    section_hashes: dict[str, str] = {}
    for section in document.sections:
        section_hash = hashlib.sha256(section.content.encode("utf-8")).hexdigest()
        section_hashes[section.section_id] = section_hash
        cached = existing.get(section.section_id)
        valid = bool(
            not force and cached and cached.section_hash == section_hash
            and cached.extractor_version == extractor_version
            and cached.rule_version == rule_version
            and cached.result_version == result_version
        )
        if not valid:
            changed_sections.append(section)
            continue
        accepted = dict(cached.payload_json or {"entities": [], "relations": []})
        pending = dict(cached.pending_candidates_json or {})
        if pending and hasattr(extractor, "retry_pending"):
            payloads[section.section_id] = extractor.retry_pending(
                document=document,
                section=section,
                accepted_payload=accepted,
                pending_candidates=pending,
            )
        else:
            payloads[section.section_id] = {**accepted, "_pending_candidates": pending}

    if changed_sections:
        changed_document = replace(document, sections=changed_sections)
        if hasattr(extractor, "extract_batch"):
            from agent_service.services.knowledge_graph.service import _extract_graph_section_payloads

            extracted = _extract_graph_section_payloads(
                extractor=extractor,
                document=changed_document,
                max_workers=max_workers,
                cancel_event=cancel_event,
                on_progress=on_progress or (lambda *_args: None),
            )
        else:
            extracted = {
                section.section_id: extractor.extract(document=document, section=section)
                for section in changed_sections
            }
        payloads.update(extracted)

    caches: list[KnowledgeGraphSectionCache] = []
    has_pending = False
    for section in document.sections:
        payload = dict(payloads.get(section.section_id, {"entities": [], "relations": []}))
        pending = dict(payload.pop("_pending_candidates", {}) or {})
        pending_has_candidates = bool(pending.get("entities") or pending.get("relations"))
        has_pending = has_pending or pending_has_candidates
        caches.append(KnowledgeGraphSectionCache(
            cache_id=service._section_cache_id(
                user_id=user_id,
                library_id=library_id,
                document_id=document.document_id,
                section_id=section.section_id,
            ),
            user_id=user_id,
            library_id=library_id,
            document_id=document.document_id,
            section_id=section.section_id,
            section_hash=section_hashes[section.section_id],
            extractor_version=extractor_version,
            rule_version=rule_version,
            result_version=result_version,
            status="pending_remote" if pending_has_candidates else "completed",
            payload_json=payload,
            pending_candidates_json=pending,
            updated_at=utc_now(),
        ))
        payloads[section.section_id] = payload
    return payloads, caches, has_pending

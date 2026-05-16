"""
召回详情响应构建工具。

功能说明:
为 REST 与 gRPC 观测接口统一生成长期记忆 / 知识库召回快照。优先返回
ContextBuilder 已持久化到 system message metadata 中的真实快照; 对于旧消息
或未携带 metadata 的会话,使用最近一条用户问题现场执行同一检索链路生成快照。

使用说明:
payload = build_recall_details_payload(agent=agent, message_service=ms, user_id="u1", session_id="s1")
"""

from __future__ import annotations

from typing import Any

from agent_service.agent_core.agent_core import AgentCore
from agent_service.schemas.message import MessageOut
from agent_service.services.message_service import MessageService
from agent_service.services.memory.retrieval_service import RetrievedMemory, RetrievalDebugSnapshot


def empty_recall_payload(*, session_id: str, user_id: str) -> dict[str, Any]:
    """构造空的召回观测快照响应。"""

    return {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": "",
        "query": "",
        "rag_metrics": {},
        "memory_recall": {"pre_rerank": [], "post_rerank": []},
        "knowledge_recall": {"pre_rerank": [], "post_rerank": []},
    }


def build_recall_details_payload(
    *,
    agent: AgentCore,
    message_service: MessageService,
    user_id: str,
    session_id: str,
    limit: int = 200,
) -> dict[str, Any]:
    """
    构建指定会话最近一次召回详情响应。

    agent: 当前 AgentCore,用于复用 ContextBuilder 中的检索服务。
    message_service: 消息服务,用于读取会话历史。
    user_id: 用户 ID。
    session_id: 会话 ID。
    limit: 最多回看消息条数。
    """

    messages = message_service.list_session_messages(user_id=user_id, session_id=session_id, limit=limit)
    persisted = _payload_from_persisted_metadata(messages=messages, user_id=user_id, session_id=session_id)
    if persisted is not None:
        return persisted
    return _payload_from_live_retrieval(
        agent=agent,
        message_service=message_service,
        messages=messages,
        user_id=user_id,
        session_id=session_id,
    )


def _payload_from_persisted_metadata(
    *,
    messages: list[MessageOut],
    user_id: str,
    session_id: str,
) -> dict[str, Any] | None:
    """从已持久化的 system message metadata 还原召回详情。"""

    for message in reversed(messages):
        if message.role != "system":
            continue
        metadata = message.metadata_json or {}
        recall_details = metadata.get("recall_details")
        if not recall_details:
            continue
        return {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": message.created_at.isoformat(),
            "query": recall_details.get("query", ""),
            "rag_metrics": metadata.get("rag_metrics", {}),
            "memory_recall": recall_details.get("memory_recall", {"pre_rerank": [], "post_rerank": []}),
            "knowledge_recall": recall_details.get("knowledge_recall", {"pre_rerank": [], "post_rerank": []}),
        }
    return None


def _payload_from_live_retrieval(
    *,
    agent: AgentCore,
    message_service: MessageService,
    messages: list[MessageOut],
    user_id: str,
    session_id: str,
) -> dict[str, Any]:
    """为没有持久化快照的会话实时补算召回详情。"""

    latest_user = next((message for message in reversed(messages) if message.role == "user"), None)
    if latest_user is None or not latest_user.content.strip():
        return empty_recall_payload(session_id=session_id, user_id=user_id)

    context_builder = agent._get_context_builder(message_service=message_service)
    retrieval_service = context_builder.retrieval_service
    top_k = agent.config.memory.rerank_top_k
    memory_snapshot = retrieval_service.retrieve_long_term_memory_with_debug(
        query=latest_user.content,
        user_id=user_id,
        session_id=session_id,
        top_k=top_k,
    )
    knowledge_snapshot = retrieval_service.retrieve_knowledge_with_debug(
        query=latest_user.content,
        top_k=top_k,
    )
    rag_metrics = _build_rag_metrics(
        top_k=max(top_k, 1),
        memory_snapshot=memory_snapshot,
        knowledge_snapshot=knowledge_snapshot,
    )
    return {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": latest_user.created_at.isoformat(),
        "query": latest_user.content,
        "rag_metrics": rag_metrics,
        "memory_recall": retrieval_service.serialize_debug_snapshot(memory_snapshot),
        "knowledge_recall": retrieval_service.serialize_debug_snapshot(knowledge_snapshot),
    }


def _build_rag_metrics(
    *,
    top_k: int,
    memory_snapshot: RetrievalDebugSnapshot,
    knowledge_snapshot: RetrievalDebugSnapshot,
) -> dict[str, float | int]:
    """根据实时召回快照计算 Obs 面板使用的 RAG 指标。"""

    memory_results = memory_snapshot.post_rerank_results
    knowledge_results = knowledge_snapshot.post_rerank_results
    memory_count = len(memory_results)
    knowledge_count = len(knowledge_results)
    recall = round((((memory_count / top_k) * 100) + ((knowledge_count / top_k) * 100)) / 2, 1)
    hit_rate = round((((1 if memory_results else 0) + (1 if knowledge_results else 0)) / 2) * 100, 1)
    all_results: list[RetrievedMemory] = [*memory_results, *knowledge_results]
    confidence = (
        round(sum(item.final_score for item in all_results) / len(all_results) * 100, 1)
        if all_results
        else 0.0
    )
    return {
        "recall": min(recall, 100.0),
        "hit_rate": hit_rate,
        "confidence": confidence,
        "memory_count": memory_count,
        "knowledge_count": knowledge_count,
        "important_count": 0,
    }

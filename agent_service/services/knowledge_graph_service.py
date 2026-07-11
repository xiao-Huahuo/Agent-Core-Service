"""
知识库图谱抽取与查询服务。

功能说明:
本文件把结构化 frontmatter 文档转换为 SQLite 中的知识图谱点边数据。它只消费
`StructuredKnowledgeDocument.sections` 中的文字内容,不处理图片、OCR 或视觉描述。

使用说明:
知识库入库完成后调用 `extract_frontmatter_file()` 或 `extract_frontmatter_dir()`。
前端调用 `get_graph()` 获取可视化所需的 nodes/links 数据。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.knowledge_graph import (
    KnowledgeGraphDocumentStatus,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
)
from agent_service.models.session import utc_now
from agent_service.services.memory.rag.frontmatter_document import (
    StructuredKnowledgeDocument,
    StructuredKnowledgeSection,
)
from agent_service.services.scheduler import (
    BACKGROUND_FACT_RESOLUTION_TASK,
    LLMTaskScheduler,
    SMALL_MODEL_TIER,
    get_llm_task_scheduler,
)

logger = logging.getLogger(__name__)

ENTITY_TYPES = {
    "person",
    "organization",
    "project",
    "module",
    "class",
    "function",
    "file",
    "concept",
    "config",
    "data",
    "other",
}
RELATION_TYPES = {
    "defines",
    "contains",
    "depends_on",
    "produces",
    "consumes",
    "calls",
    "configures",
    "mentions",
    "related_to",
}
WEAK_RELATION_TYPES = {"mentions", "related_to"}


class KnowledgeGraphExtractor(Protocol):
    """实体关系候选抽取器协议,测试可注入假实现。"""

    def extract(self, *, document: StructuredKnowledgeDocument, section: StructuredKnowledgeSection) -> dict[str, Any]:
        """从一个 section 中抽取候选实体和关系。"""


@dataclass(slots=True)
class GraphExtractionResult:
    """知识图谱抽取统计结果。"""

    files_seen: int = 0
    files_extracted: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    entities_written: int = 0
    relations_written: int = 0
    document_ids_seen: set[str] = field(default_factory=set)


@dataclass(slots=True)
class EntityCandidate:
    """清洗后的实体候选。"""

    name: str
    entity_type: str
    aliases: list[str]
    description: str
    confidence: float


@dataclass(slots=True)
class RelationCandidate:
    """清洗后的关系候选。"""

    source: str
    target: str
    relation_type: str
    evidence: str
    confidence: float


class LLMKnowledgeGraphExtractor:
    """使用小模型生成实体和关系候选。"""

    def __init__(
        self,
        *,
        config: AgentConfig,
        task_scheduler: LLMTaskScheduler | None = None,
        llm_config: dict[str, Any] | None = None,
    ) -> None:
        """保存模型调度依赖和用户模型覆盖配置。"""

        self.config = config
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.llm_config = llm_config or {}

    def extract(self, *, document: StructuredKnowledgeDocument, section: StructuredKnowledgeSection) -> dict[str, Any]:
        """调用 small tier 模型,要求只返回 JSON 对象。"""

        content = section.content.strip()
        if not content:
            return {"entities": [], "relations": []}
        response = self.task_scheduler.invoke_chat(
            task_type=BACKGROUND_FACT_RESOLUTION_TASK,
            model_tier=SMALL_MODEL_TIER,
            messages=[
                SystemMessage(content=self._system_prompt()),
                HumanMessage(content=self._human_prompt(document=document, section=section, content=content[:6000])),
            ],
            api_key=self._value("api_key"),
            base_url=self._value("base_url"),
            small_api_key=self._value("small_api_key"),
            small_base_url=self._value("small_base_url"),
        )
        return self._parse_json_object(str(response.content or ""))

    @staticmethod
    def _system_prompt() -> str:
        """返回实体关系抽取系统提示词。"""

        return (
            "你是知识图谱抽取器。只从给定文本中抽取明确出现的实体和关系,不要推理文本没有表达的事实。"
            "只输出合法 JSON,不要输出解释。"
            "实体类型只能是: person, organization, project, module, class, function, file, concept, config, data, other。"
            "关系类型只能是: defines, contains, depends_on, produces, consumes, calls, configures, mentions, related_to。"
            "关系两端必须来自 entities.name。每条关系必须有 evidence, evidence 必须是原文中的短句或短语。"
            "不确定就不要抽。输出结构固定为 {\"entities\":[],\"relations\":[]}。"
        )

    @staticmethod
    def _human_prompt(
        *,
        document: StructuredKnowledgeDocument,
        section: StructuredKnowledgeSection,
        content: str,
    ) -> str:
        """构造单 section 抽取输入。"""

        return (
            f"文档标题: {document.title}\n"
            f"标题路径: {' / '.join(section.title_path)}\n"
            f"section_id: {section.section_id}\n"
            "正文:\n"
            f"{content}"
        )

    def _value(self, key: str) -> str | None:
        """读取用户模型覆盖配置。"""

        value = self.llm_config.get(key)
        return str(value).strip() if value else None

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        """解析模型返回的 JSON 对象,兼容包裹在代码块中的输出。"""

        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                return {"entities": [], "relations": []}
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {"entities": [], "relations": []}
        return payload if isinstance(payload, dict) else {"entities": [], "relations": []}


class KnowledgeGraphService:
    """知识库图谱抽取、清理和查询服务。"""

    def __init__(
        self,
        *,
        config: AgentConfig,
        engine: Engine | None = None,
        extractor: KnowledgeGraphExtractor | None = None,
        create_tables: bool = True,
    ) -> None:
        """初始化 SQLite 引擎并按需创建图谱表。"""

        self.config = config
        self.engine = engine or create_engine(f"sqlite:///{config.storage.sqlite_path}", pool_pre_ping=True)
        self.extractor = extractor
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def extract_frontmatter_dir(
        self,
        *,
        user_id: str,
        library_id: str,
        frontmatter_dir: Path,
        keep_document_ids: set[str] | None = None,
        llm_config: dict[str, Any] | None = None,
    ) -> GraphExtractionResult:
        """扫描 frontmatter 目录并抽取知识图谱。"""

        result = GraphExtractionResult()
        paths = sorted(path for path in frontmatter_dir.rglob("*.json") if path.is_file()) if frontmatter_dir.exists() else []
        self.sync_document_nodes_frontmatter_dir(
            user_id=user_id,
            library_id=library_id,
            frontmatter_dir=frontmatter_dir,
            keep_document_ids=keep_document_ids,
        )
        for path in paths:
            result.files_seen += 1
            document = self._load_document(path)
            result.document_ids_seen.add(document.document_id)
            item_result = self.extract_document(
                user_id=user_id,
                library_id=library_id,
                document=document,
                llm_config=llm_config,
            )
            result.files_extracted += item_result.files_extracted
            result.files_skipped += item_result.files_skipped
            result.files_failed += item_result.files_failed
            result.entities_written += item_result.entities_written
            result.relations_written += item_result.relations_written
        self.delete_graph_except_documents(
            user_id=user_id,
            library_id=library_id,
            keep_document_ids=keep_document_ids if keep_document_ids is not None else result.document_ids_seen,
        )
        return result

    def sync_document_nodes_frontmatter_dir(
        self,
        *,
        user_id: str,
        library_id: str,
        frontmatter_dir: Path,
        keep_document_ids: set[str] | None = None,
    ) -> int:
        """Synchronize source document nodes without invoking semantic extraction."""

        paths = sorted(path for path in frontmatter_dir.rglob("*.json") if path.is_file()) if frontmatter_dir.exists() else []
        document_ids: set[str] = set()
        synced = 0
        for path in paths:
            document = self._load_document(path)
            document_ids.add(document.document_id)
            self._write_document_node(user_id=user_id, library_id=library_id, document=document)
            synced += 1
        self.delete_graph_except_documents(
            user_id=user_id,
            library_id=library_id,
            keep_document_ids=keep_document_ids if keep_document_ids is not None else document_ids,
        )
        return synced

    def extract_frontmatter_file(
        self,
        *,
        user_id: str,
        library_id: str,
        frontmatter_path: Path,
        llm_config: dict[str, Any] | None = None,
    ) -> GraphExtractionResult:
        """抽取单个 frontmatter 文件的知识图谱。"""

        document = self._load_document(frontmatter_path)
        return self.extract_document(
            user_id=user_id,
            library_id=library_id,
            document=document,
            llm_config=llm_config,
        )

    def extract_document(
        self,
        *,
        user_id: str,
        library_id: str,
        document: StructuredKnowledgeDocument,
        llm_config: dict[str, Any] | None = None,
    ) -> GraphExtractionResult:
        """抽取单个结构化文档并写入图谱表。"""

        result = GraphExtractionResult(files_seen=1, document_ids_seen={document.document_id})
        if self._is_document_current(
            user_id=user_id,
            library_id=library_id,
            document_id=document.document_id,
            source_hash=document.source_hash,
        ):
            result.files_skipped = 1
            return result
        self.delete_document_graph(user_id=user_id, library_id=library_id, document_id=document.document_id)
        self._write_document_node(user_id=user_id, library_id=library_id, document=document)
        extractor = self.extractor or LLMKnowledgeGraphExtractor(
            config=self.config,
            llm_config=llm_config,
        )
        try:
            entities_by_key: dict[tuple[str, str], EntityCandidate] = {}
            relations: list[tuple[RelationCandidate, StructuredKnowledgeSection]] = []
            for section in document.sections:
                payload = extractor.extract(document=document, section=section)
                section_entities = self._sanitize_entities(payload.get("entities"))
                for entity in section_entities:
                    entities_by_key[(self._normalize_label(entity.name), entity.entity_type)] = entity
                section_entity_names = {entity.name for entity in section_entities}
                relations.extend(
                    (relation, section)
                    for relation in self._sanitize_relations(
                        payload.get("relations"),
                        section_text=section.content,
                        allowed_entity_names=section_entity_names,
                    )
                )
            written_entities, written_relations = self._write_graph(
                user_id=user_id,
                library_id=library_id,
                document=document,
                entities=list(entities_by_key.values()),
                relations=relations,
            )
            self._write_status(
                user_id=user_id,
                library_id=library_id,
                document=document,
                status="completed" if written_entities or written_relations else "skipped",
                message="" if written_entities or written_relations else "no valid graph candidates",
                entity_count=written_entities,
                relation_count=written_relations,
            )
            result.files_extracted = 1 if written_entities or written_relations else 0
            result.files_skipped = 0 if written_entities or written_relations else 1
            result.entities_written = written_entities
            result.relations_written = written_relations
            return result
        except Exception as exc:
            logger.warning("知识图谱抽取失败 | document=%s error=%s", document.document_id, exc)
            self._write_status(
                user_id=user_id,
                library_id=library_id,
                document=document,
                status="failed",
                message=str(exc)[:1000],
                entity_count=0,
                relation_count=0,
            )
            result.files_failed = 1
            return result

    def get_graph(self, *, user_id: str, library_id: str, limit: int = 500) -> dict[str, Any]:
        """返回前端 Canvas 可直接消费的图谱数据。"""

        safe_limit = max(50, min(int(limit or 500), 1200))
        with Session(self.engine) as db:
            nodes = db.exec(
                select(KnowledgeGraphNode)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .limit(safe_limit)
            ).all()
            node_ids = {node.node_id for node in nodes}
            edges = [
                edge
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .limit(safe_limit * 2)
                ).all()
                if edge.source_node_id in node_ids and edge.target_node_id in node_ids
            ]
            statuses = db.exec(
                select(KnowledgeGraphDocumentStatus)
                .where(KnowledgeGraphDocumentStatus.user_id == user_id)
                .where(KnowledgeGraphDocumentStatus.library_id == library_id)
            ).all()
        return {
            "nodes": [self._serialize_node(node) for node in nodes],
            "links": [self._serialize_edge(edge) for edge in edges],
            "stats": {
                "nodes": len(nodes),
                "links": len(edges),
                "documents": sum(1 for node in nodes if node.node_type == "document"),
                "entities": sum(1 for node in nodes if node.node_type == "entity"),
                "completed_documents": sum(1 for status in statuses if status.status == "completed"),
                "failed_documents": sum(1 for status in statuses if status.status == "failed"),
                "skipped_documents": sum(1 for status in statuses if status.status == "skipped"),
            },
        }

    def delete_document_graph(self, *, user_id: str, library_id: str, document_id: str) -> int:
        """删除单文档来源的图谱点边和状态。"""

        document_node_id = self._document_node_id(user_id=user_id, library_id=library_id, document_id=document_id)
        with Session(self.engine) as db:
            edge_ids = [
                edge.edge_id
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.source_document_id == document_id)
                ).all()
            ]
            edge_ids.extend(
                edge.edge_id
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.source_node_id == document_node_id)
                ).all()
            )
            for edge_id in set(edge_ids):
                edge = db.get(KnowledgeGraphEdge, edge_id)
                if edge:
                    db.delete(edge)
            for node in db.exec(
                select(KnowledgeGraphNode)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .where(KnowledgeGraphNode.document_id == document_id)
            ).all():
                db.delete(node)
            self._delete_orphan_entity_nodes(db=db, user_id=user_id, library_id=library_id)
            status = db.get(
                KnowledgeGraphDocumentStatus,
                self._status_id(user_id=user_id, library_id=library_id, document_id=document_id),
            )
            if status:
                db.delete(status)
            db.commit()
            return len(set(edge_ids))

    def delete_graph_except_documents(
        self,
        *,
        user_id: str,
        library_id: str,
        keep_document_ids: set[str],
    ) -> int:
        """全库重建后清理已经不存在的文档来源图谱数据。"""

        with Session(self.engine) as db:
            stale_statuses = db.exec(
                select(KnowledgeGraphDocumentStatus)
                .where(KnowledgeGraphDocumentStatus.user_id == user_id)
                .where(KnowledgeGraphDocumentStatus.library_id == library_id)
            ).all()
        deleted = 0
        for status in stale_statuses:
            if status.document_id not in keep_document_ids:
                deleted += self.delete_document_graph(
                    user_id=user_id,
                    library_id=library_id,
                    document_id=status.document_id,
                )
        return deleted

    @staticmethod
    def _delete_orphan_entity_nodes(*, db: Session, user_id: str, library_id: str) -> None:
        """删除没有任何入边或出边的实体节点。"""

        edges = db.exec(
            select(KnowledgeGraphEdge)
            .where(KnowledgeGraphEdge.user_id == user_id)
            .where(KnowledgeGraphEdge.library_id == library_id)
        ).all()
        linked_node_ids = {edge.source_node_id for edge in edges} | {edge.target_node_id for edge in edges}
        for node in db.exec(
            select(KnowledgeGraphNode)
            .where(KnowledgeGraphNode.user_id == user_id)
            .where(KnowledgeGraphNode.library_id == library_id)
            .where(KnowledgeGraphNode.node_type == "entity")
        ).all():
            if node.node_id not in linked_node_ids:
                db.delete(node)

    def _write_graph(
        self,
        *,
        user_id: str,
        library_id: str,
        document: StructuredKnowledgeDocument,
        entities: list[EntityCandidate],
        relations: list[tuple[RelationCandidate, StructuredKnowledgeSection]],
    ) -> tuple[int, int]:
        """写入文档节点、实体节点和关系边。"""

        now = utc_now()
        document_node_id = self._document_node_id(user_id=user_id, library_id=library_id, document_id=document.document_id)
        entity_node_ids: dict[str, str] = {}
        with Session(self.engine) as db:
            db.merge(self._build_document_node(user_id=user_id, library_id=library_id, document=document, now=now))
            for entity in entities:
                node_id = self._entity_node_id(
                    user_id=user_id,
                    library_id=library_id,
                    entity_type=entity.entity_type,
                    label=entity.name,
                )
                entity_node_ids[entity.name] = node_id
                db.merge(
                    KnowledgeGraphNode(
                        node_id=node_id,
                        user_id=user_id,
                        library_id=library_id,
                        node_type="entity",
                        label=entity.name,
                        normalized_label=self._normalize_label(entity.name),
                        entity_type=entity.entity_type,
                        document_id="",
                        source_uri=document.source_uri,
                        metadata_json={
                            "aliases": entity.aliases,
                            "description": entity.description,
                            "confidence": entity.confidence,
                        },
                        created_at=now,
                        updated_at=now,
                    )
                )
                db.merge(
                    KnowledgeGraphEdge(
                        edge_id=self._edge_id(
                            user_id,
                            library_id,
                            document_node_id,
                            node_id,
                            "mentions",
                            document.document_id,
                            "",
                        ),
                        user_id=user_id,
                        library_id=library_id,
                        source_node_id=document_node_id,
                        target_node_id=node_id,
                        relation_type="mentions",
                        weight=max(0.2, entity.confidence * 0.5),
                        evidence="",
                        source_document_id=document.document_id,
                        source_section_id="",
                        metadata_json={"edge_role": "document_entity"},
                        created_at=now,
                        updated_at=now,
                    )
                )
            written_relations = 0
            for relation, section in relations:
                source_id = entity_node_ids.get(relation.source)
                target_id = entity_node_ids.get(relation.target)
                if not source_id or not target_id:
                    continue
                db.merge(
                    KnowledgeGraphEdge(
                        edge_id=self._edge_id(
                            user_id,
                            library_id,
                            source_id,
                            target_id,
                            relation.relation_type,
                            document.document_id,
                            section.section_id,
                        ),
                        user_id=user_id,
                        library_id=library_id,
                        source_node_id=source_id,
                        target_node_id=target_id,
                        relation_type=relation.relation_type,
                        weight=self._relation_weight(relation),
                        evidence=relation.evidence,
                        source_document_id=document.document_id,
                        source_section_id=section.section_id,
                        metadata_json={"title_path": section.title_path},
                        created_at=now,
                        updated_at=now,
                    )
                )
                written_relations += 1
            db.commit()
        return len(entities), written_relations

    def _write_document_node(self, *, user_id: str, library_id: str, document: StructuredKnowledgeDocument) -> None:
        """Persist a document node before best-effort semantic extraction."""

        with Session(self.engine) as db:
            db.merge(
                self._build_document_node(
                    user_id=user_id,
                    library_id=library_id,
                    document=document,
                    now=utc_now(),
                )
            )
            db.commit()

    def _build_document_node(
        self,
        *,
        user_id: str,
        library_id: str,
        document: StructuredKnowledgeDocument,
        now: Any,
    ) -> KnowledgeGraphNode:
        """Build the stable graph node representing a source document."""

        return KnowledgeGraphNode(
            node_id=self._document_node_id(user_id=user_id, library_id=library_id, document_id=document.document_id),
            user_id=user_id,
            library_id=library_id,
            node_type="document",
            label=document.title,
            normalized_label=self._normalize_label(document.title),
            entity_type="document",
            document_id=document.document_id,
            source_uri=document.source_uri,
            metadata_json={"source_type": document.source_type, "tags": document.tags, **document.metadata},
            created_at=now,
            updated_at=now,
        )

    def _is_document_current(self, *, user_id: str, library_id: str, document_id: str, source_hash: str) -> bool:
        """判断当前文档图谱是否已按相同 hash 完成抽取。"""

        with Session(self.engine) as db:
            status = db.get(
                KnowledgeGraphDocumentStatus,
                self._status_id(user_id=user_id, library_id=library_id, document_id=document_id),
            )
            return bool(status and status.source_hash == source_hash and status.status in {"completed", "skipped"})

    def _write_status(
        self,
        *,
        user_id: str,
        library_id: str,
        document: StructuredKnowledgeDocument,
        status: str,
        message: str,
        entity_count: int,
        relation_count: int,
    ) -> None:
        """写入单文档图谱抽取状态。"""

        with Session(self.engine) as db:
            db.merge(
                KnowledgeGraphDocumentStatus(
                    status_id=self._status_id(user_id=user_id, library_id=library_id, document_id=document.document_id),
                    user_id=user_id,
                    library_id=library_id,
                    document_id=document.document_id,
                    source_hash=document.source_hash,
                    status=status,
                    message=message,
                    entity_count=entity_count,
                    relation_count=relation_count,
                    updated_at=utc_now(),
                )
            )
            db.commit()

    def _sanitize_entities(self, raw_entities: Any) -> list[EntityCandidate]:
        """清洗模型返回实体候选。"""

        if not isinstance(raw_entities, list):
            return []
        entities: list[EntityCandidate] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_entities:
            if not isinstance(item, dict):
                continue
            name = self._clean_label(item.get("name"))
            entity_type = str(item.get("type") or item.get("entity_type") or "other").strip().lower()
            if entity_type not in ENTITY_TYPES:
                entity_type = "other"
            if not self._is_valid_entity_name(name):
                continue
            key = (self._normalize_label(name), entity_type)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                EntityCandidate(
                    name=name,
                    entity_type=entity_type,
                    aliases=[
                        self._clean_label(alias)
                        for alias in item.get("aliases", [])
                        if self._is_valid_entity_name(self._clean_label(alias))
                    ][:5],
                    description=str(item.get("description") or "")[:240],
                    confidence=self._clamp_float(item.get("confidence"), default=0.7),
                )
            )
        return entities[:80]

    def _sanitize_relations(
        self,
        raw_relations: Any,
        *,
        section_text: str,
        allowed_entity_names: set[str],
    ) -> list[RelationCandidate]:
        """清洗模型返回关系候选。"""

        if not isinstance(raw_relations, list):
            return []
        allowed_by_norm = {self._normalize_label(name): name for name in allowed_entity_names}
        relations: list[RelationCandidate] = []
        seen: set[tuple[str, str, str, str]] = set()
        for item in raw_relations:
            if not isinstance(item, dict):
                continue
            source = allowed_by_norm.get(self._normalize_label(str(item.get("source") or "")))
            target = allowed_by_norm.get(self._normalize_label(str(item.get("target") or "")))
            relation_type = str(item.get("type") or item.get("relation_type") or "").strip().lower()
            evidence = str(item.get("evidence") or "").strip()
            confidence = self._clamp_float(item.get("confidence"), default=0.7)
            if not source or not target or source == target:
                continue
            if relation_type not in RELATION_TYPES or confidence < 0.55:
                continue
            if not evidence or evidence not in section_text:
                continue
            key = (source, target, relation_type, evidence)
            if key in seen:
                continue
            seen.add(key)
            relations.append(
                RelationCandidate(
                    source=source,
                    target=target,
                    relation_type=relation_type,
                    evidence=evidence[:500],
                    confidence=confidence,
                )
            )
        return relations[:120]

    @staticmethod
    def _load_document(frontmatter_path: Path) -> StructuredKnowledgeDocument:
        """从 frontmatter JSON 加载结构化文档。"""

        payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
        return StructuredKnowledgeDocument.from_dict(payload)

    @staticmethod
    def _serialize_node(node: KnowledgeGraphNode) -> dict[str, Any]:
        """序列化图谱节点。"""

        return {
            "id": node.node_id,
            "label": node.label,
            "kind": node.node_type,
            "entity_type": node.entity_type,
            "document_id": node.document_id,
            "source_uri": node.source_uri,
            "source_range": node.source_range_json,
            "metadata": node.metadata_json,
        }

    @staticmethod
    def _serialize_edge(edge: KnowledgeGraphEdge) -> dict[str, Any]:
        """序列化图谱关系边。"""

        return {
            "id": edge.edge_id,
            "source": edge.source_node_id,
            "target": edge.target_node_id,
            "kind": edge.relation_type,
            "weight": edge.weight,
            "evidence": edge.evidence,
            "source_document_id": edge.source_document_id,
            "source_section_id": edge.source_section_id,
            "metadata": edge.metadata_json,
        }

    @staticmethod
    def _relation_weight(relation: RelationCandidate) -> float:
        """根据关系类型和置信度计算边权重。"""

        if relation.relation_type in WEAK_RELATION_TYPES:
            return max(0.2, min(0.55, relation.confidence * 0.55))
        return max(0.4, min(1.0, relation.confidence))

    @staticmethod
    def _clean_label(value: Any) -> str:
        """清理实体标签。"""

        return re.sub(r"\s+", " ", str(value or "").strip()).strip("`\"'“”‘’")

    @staticmethod
    def _is_valid_entity_name(value: str) -> bool:
        """过滤明显无效或过泛的实体名。"""

        if not value or len(value) > 80:
            return False
        if re.fullmatch(r"[\W_]+", value, flags=re.UNICODE):
            return False
        return value not in {"系统", "用户", "文件", "文档", "内容", "数据", "信息"}

    @staticmethod
    def _normalize_label(value: str) -> str:
        """实体规范名归一。"""

        return re.sub(r"\s+", " ", value.strip().lower())

    @staticmethod
    def _clamp_float(value: Any, *, default: float) -> float:
        """解析并裁剪 0-1 浮点数。"""

        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
        return max(0.0, min(1.0, parsed))

    @classmethod
    def _document_node_id(cls, *, user_id: str, library_id: str, document_id: str) -> str:
        """生成稳定文档节点 ID。"""

        return cls._hashed_id("kgdoc", user_id, library_id, document_id)

    @classmethod
    def _entity_node_id(cls, *, user_id: str, library_id: str, entity_type: str, label: str) -> str:
        """生成稳定实体节点 ID。"""

        return cls._hashed_id("kgent", user_id, library_id, entity_type, cls._normalize_label(label))

    @classmethod
    def _edge_id(
        cls,
        user_id: str,
        library_id: str,
        source_id: str,
        target_id: str,
        relation_type: str,
        document_id: str,
        section_id: str,
    ) -> str:
        """生成稳定关系边 ID。"""

        return cls._hashed_id("kgedge", user_id, library_id, source_id, target_id, relation_type, document_id, section_id)

    @classmethod
    def _status_id(cls, *, user_id: str, library_id: str, document_id: str) -> str:
        """生成稳定状态记录 ID。"""

        return cls._hashed_id("kgstat", user_id, library_id, document_id)

    @staticmethod
    def _hashed_id(prefix: str, *parts: str) -> str:
        """生成短 hash ID。"""

        digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:40]
        return f"{prefix}_{digest}"

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
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
import numpy as np
from sklearn.cluster import DBSCAN
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
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.scheduler import (
    BACKGROUND_FACT_RESOLUTION_TASK,
    LLMTaskScheduler,
    SMALL_MODEL_TIER,
    get_llm_task_scheduler,
)
from agent_service.services.token_usage_service import TokenUsageService

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
        user_id: str | None = None,
        library_id: str | None = None,
    ) -> None:
        """保存模型调度依赖和用户模型覆盖配置。"""

        self.config = config
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.llm_config = llm_config or {}
        self.user_id = user_id
        self.library_id = library_id
        self.token_usage_service = TokenUsageService(config=config)

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
            model_name=self._value("model_name"),
            api_key=self._value("api_key"),
            base_url=self._value("base_url"),
            small_model_name=self._value("small_model_name"),
            small_api_key=self._value("small_api_key"),
            small_base_url=self._value("small_base_url"),
        )
        self._record_token_usage(response=response, document=document, section=section)
        return self._parse_json_object(str(response.content or ""))

    def _record_token_usage(
        self,
        *,
        response: Any,
        document: StructuredKnowledgeDocument,
        section: StructuredKnowledgeSection,
    ) -> None:
        """Persist graph extraction model usage as a non-session background call."""

        if not self.user_id:
            return
        source_id = f"knowledge_graph_{self.library_id or 'default'}_{document.document_id}_{section.section_id}"
        self.token_usage_service.record_llm_response_token_usage(
            user_id=self.user_id,
            session_id=None,
            response=response,
            node="knowledge_graph",
            event="section_extracted",
            model_tier=SMALL_MODEL_TIER,
            source_id=source_id,
        )

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

    def deduplicate_entities(
        self,
        entities: list[EntityCandidate],
        document: StructuredKnowledgeDocument,
    ) -> dict[str, Any]:
        """对文档级实体做语义去重,返回合并后的实体列表和名称映射表。"""

        if len(entities) <= 1:
            return {"entities": list(entities), "name_mapping": {e.name: e.name for e in entities}}
        response = self.task_scheduler.invoke_chat(
            task_type=BACKGROUND_FACT_RESOLUTION_TASK,
            model_tier=SMALL_MODEL_TIER,
            messages=[
                SystemMessage(content=self._dedup_system_prompt()),
                HumanMessage(content=self._dedup_human_prompt(document=document, entities=entities)),
            ],
            model_name=self._value("model_name"),
            api_key=self._value("api_key"),
            base_url=self._value("base_url"),
            small_model_name=self._value("small_model_name"),
            small_api_key=self._value("small_api_key"),
            small_base_url=self._value("small_base_url"),
        )
        self._record_dedup_token_usage(response=response, document=document)
        payload = self._parse_json_object(str(response.content or ""))
        groups = payload.get("groups", []) if isinstance(payload, dict) else []
        if not groups:
            return {"entities": list(entities), "name_mapping": {e.name: e.name for e in entities}}

        consumed: set[int] = set()
        merged: list[EntityCandidate] = []
        name_mapping: dict[str, str] = {}

        for group in groups:
            if not isinstance(group, dict):
                continue
            canonical_name = str(group.get("canonical_name", "")).strip()
            if not self._is_valid_entity_name(canonical_name):
                continue
            entity_type = str(group.get("canonical_type") or "other").strip().lower()
            if entity_type not in ENTITY_TYPES:
                entity_type = "other"
            indices = [
                i for i in group.get("entity_indices", [])
                if isinstance(i, int) and 0 <= i < len(entities)
            ]
            if not indices:
                continue
            consumed.update(indices)
            for idx in indices:
                orig_name = entities[idx].name
                if orig_name != canonical_name:
                    name_mapping[orig_name] = canonical_name

            merged.append(
                EntityCandidate(
                    name=canonical_name,
                    entity_type=entity_type,
                    aliases=group.get("aliases", [])[:5],
                    description="",
                    confidence=max(entities[i].confidence for i in indices),
                )
            )

        for i, entity in enumerate(entities):
            if i not in consumed:
                merged.append(entity)
                name_mapping[entity.name] = entity.name

        for entity in entities:
            if entity.name not in name_mapping:
                name_mapping[entity.name] = entity.name

        return {"entities": merged, "name_mapping": name_mapping}

    @staticmethod
    def _dedup_system_prompt() -> str:
        """返回实体语义去重系统提示词。"""

        return (
            "你是实体语义去重器。你的任务是对同一文档中抽取出的实体候选进行语义去重。"
            "如果多个候选指代的是同一个事物或概念（例如「AI」和「Artificial Intelligence」、"
            "「用户」和「end user」、「Python」和「Python语言」），将它们合并为一个规范实体。"
            "只输出合法 JSON，不要输出解释。"
        )

    @staticmethod
    def _dedup_human_prompt(
        *,
        document: StructuredKnowledgeDocument,
        entities: list[EntityCandidate],
    ) -> str:
        """构造语义去重输入。"""

        lines = []
        for i, entity in enumerate(entities):
            lines.append(
                f"  [{i}] name={entity.name}  type={entity.entity_type}  "
                f"aliases={entity.aliases}  desc={entity.description[:80]}"
            )
        return (
            f"文档标题: {document.title}\n"
            "候选实体列表(每行格式: [index] name=... type=... aliases=... desc=...):\n"
            + "\n".join(lines)
            + "\n\n请返回 JSON 数组 groups，每个 group 包含:\n"
            '  - canonical_name: 规范名称\n'
            '  - canonical_type: 实体类型\n'
            '  - entity_indices: 属于该组的输入实体索引列表\n'
            '  - aliases: 该实体的别名列表\n'
            '输出: {"groups": [...]}'
        )

    def deduplicate_entities_incremental(
        self,
        entities: list[EntityCandidate],
        candidates: dict[str, list[tuple[str, float]]],
        document: StructuredKnowledgeDocument,
    ) -> dict[str, str]:
        """对入库新实体做库级去重: 小模型判断新实体是否与已有实体同义。

        candidates: {new_entity_name: [(existing_name, similarity), ...]}

        返回 name_mapping: {new_entity_name: canonical_existing_name, ...}
        """

        if not candidates:
            return {}
        response = self.task_scheduler.invoke_chat(
            task_type=BACKGROUND_FACT_RESOLUTION_TASK,
            model_tier=SMALL_MODEL_TIER,
            messages=[
                SystemMessage(content=self._dedup_incremental_system_prompt()),
                HumanMessage(content=self._dedup_incremental_human_prompt(
                    document=document, entities=entities, candidates=candidates,
                )),
            ],
            model_name=self._value("model_name"),
            api_key=self._value("api_key"),
            base_url=self._value("base_url"),
            small_model_name=self._value("small_model_name"),
            small_api_key=self._value("small_api_key"),
            small_base_url=self._value("small_base_url"),
        )
        self._record_dedup_token_usage(response=response, document=document)
        payload = self._parse_json_object(str(response.content or ""))
        merges = payload.get("merges", []) if isinstance(payload, dict) else []
        name_mapping: dict[str, str] = {}
        for merge in merges:
            if not isinstance(merge, dict):
                continue
            from_name = str(merge.get("from", "")).strip()
            to_name = str(merge.get("to", "")).strip()
            if from_name and to_name and from_name != to_name:
                name_mapping[from_name] = to_name
        return name_mapping

    @staticmethod
    def _dedup_incremental_system_prompt() -> str:
        """返回增量去重系统提示词。"""

        return (
            "你是实体同义判断器。你的任务是判断文档新抽取的实体是否与知识库中已有的实体语义相同。"
            "每个新实体后附有库中候选列表(含向量相似度)。如果新实体与某个候选指向同一事物，"
            "输出 from→to 映射。不确定就不映射。只输出 JSON。"
        )

    @staticmethod
    def _dedup_incremental_human_prompt(
        *,
        document: StructuredKnowledgeDocument,
        entities: list[EntityCandidate],
        candidates: dict[str, list[tuple[str, float]]],
    ) -> str:
        """构造增量去重输入。"""

        lines = [f"文档标题: {document.title}", "新实体及候选:"]
        for entity in entities:
            name = entity.name
            entry = f"  [{name}] type={entity.entity_type}"
            cands = candidates.get(name, [])
            if cands:
                cand_str = ", ".join(f"{c}({s:.2f})" for c, s in cands[:5])
                entry += f" → 候选: {cand_str}"
            lines.append(entry)
        return (
            "\n".join(lines)
            + '\n\n请输出: {"merges": [{"from": "新实体名", "to": "库中已有实体名"}, ...]}'
            + "\n只输出确定同义的映射。"
        )

    def _record_dedup_token_usage(
        self,
        *,
        response: Any,
        document: StructuredKnowledgeDocument,
    ) -> None:
        """记录语义去重步骤的模型用量。"""

        if not self.user_id or not self.library_id:
            return
        source_id = f"knowledge_graph_{self.library_id}_dedup_{document.document_id}"
        self.token_usage_service.record_llm_response_token_usage(
            user_id=self.user_id,
            session_id=None,
            response=response,
            node="knowledge_graph",
            event="entity_dedup",
            model_tier=SMALL_MODEL_TIER,
            source_id=source_id,
        )

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

    @staticmethod
    def _is_valid_entity_name(value: str) -> bool:
        """过滤明显无效或过泛的实体名。"""

        if not value or len(value) > 80:
            return False
        if re.fullmatch(r"[\W_]+", value, flags=re.UNICODE):
            return False
        return value not in {"系统", "用户", "文件", "文档", "内容", "数据", "信息"}


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
            user_id=user_id,
            library_id=library_id,
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

            # 语义去重: 合并不同 section 中同名但不同表述的实体
            if isinstance(extractor, LLMKnowledgeGraphExtractor) and entities_by_key:
                entity_list = list(entities_by_key.values())
                dedup_result = extractor.deduplicate_entities(entity_list, document=document)
                merged_entities = dedup_result.get("entities", entity_list)
                name_mapping = dedup_result.get("name_mapping", {})
                if name_mapping:
                    entities_by_key = {
                        (self._normalize_label(e.name), e.entity_type): e
                        for e in merged_entities
                    }
                    remapped: list[tuple[RelationCandidate, StructuredKnowledgeSection]] = []
                    for relation, section in relations:
                        new_source = name_mapping.get(relation.source, relation.source)
                        new_target = name_mapping.get(relation.target, relation.target)
                        if new_source == new_target:
                            continue
                        relation.source = new_source
                        relation.target = new_target
                        remapped.append((relation, section))
                    relations = remapped

            # 库级增量去重: embedding 检索 + 小模型裁决,合并与库中已有同义实体
            if isinstance(extractor, LLMKnowledgeGraphExtractor) and entities_by_key:
                entity_list = list(entities_by_key.values())
                cross_mapping = self._deduplicate_entities_incremental(
                    user_id=user_id, library_id=library_id,
                    new_entities=entity_list, extractor=extractor, document=document,
                )
                if cross_mapping:
                    new_keyed: dict[tuple[str, str], EntityCandidate] = {}
                    for entity in entity_list:
                        new_name = cross_mapping.get(entity.name, entity.name)
                        if self._normalize_label(new_name) != self._normalize_label(entity.name):
                            entity.name = new_name
                        key = (self._normalize_label(entity.name), entity.entity_type)
                        if key not in new_keyed or entity.confidence > new_keyed[key].confidence:
                            new_keyed[key] = entity
                    entities_by_key = new_keyed
                    remapped: list[tuple[RelationCandidate, StructuredKnowledgeSection]] = []
                    for relation, section in relations:
                        new_source = cross_mapping.get(relation.source, relation.source)
                        new_target = cross_mapping.get(relation.target, relation.target)
                        if new_source == new_target:
                            continue
                        relation.source = new_source
                        relation.target = new_target
                        remapped.append((relation, section))
                    relations = remapped

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

        safe_limit = max(50, min(int(limit or 500), 10000))
        with Session(self.engine) as db:
            raw_nodes = list(db.exec(
                select(KnowledgeGraphNode)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .order_by(KnowledgeGraphNode.node_id)
                .limit(safe_limit)
            ).all())
            nodes, node_id_aliases = self._coalesce_entity_nodes(raw_nodes)
            node_ids = {node.node_id for node in nodes} | set(node_id_aliases)
            raw_edges = [
                edge
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .order_by(KnowledgeGraphEdge.edge_id)
                    .limit(safe_limit * 2)
                ).all()
                if edge.source_node_id in node_ids and edge.target_node_id in node_ids
            ]
            edges = self._coalesce_edges(raw_edges, node_id_aliases)
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

    def _deduplicate_entities_incremental(
        self,
        *,
        user_id: str,
        library_id: str,
        new_entities: list[EntityCandidate],
        extractor: LLMKnowledgeGraphExtractor,
        document: StructuredKnowledgeDocument,
    ) -> dict[str, str]:
        """增量去重: embedding 检索相似实体 → 小模型裁决同义 → 返回 name_mapping。"""

        if not isinstance(extractor, LLMKnowledgeGraphExtractor) or not new_entities:
            return {}
        candidates = self._search_similar_entities(
            user_id=user_id, library_id=library_id, new_entities=new_entities,
        )
        if not candidates:
            return {}
        return extractor.deduplicate_entities_incremental(
            entities=new_entities, candidates=candidates, document=document,
        )

    def _search_similar_entities(
        self,
        *,
        user_id: str,
        library_id: str,
        new_entities: list[EntityCandidate],
    ) -> dict[str, list[tuple[str, float]]]:
        """用 Embedding 搜索库中已有相似实体,返回 {新实体名: [(库中实体名, 相似度), ...]}。"""

        with Session(self.engine) as db:
            existing = db.exec(
                select(KnowledgeGraphNode.node_id, KnowledgeGraphNode.label)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .where(KnowledgeGraphNode.node_type == "entity")
            ).all()
        if not existing:
            return {}
        try:
            embedder = EmbeddingService(config=self.config)
            new_texts = [e.name for e in new_entities]
            existing_texts = [row.label for row in existing]
            new_vecs = embedder.embed_texts(new_texts)
            existing_vecs = embedder.embed_texts(existing_texts)
        except Exception:
            logger.warning("Embedding 不可用,跳过增量去重", exc_info=True)
            return {}

        results: dict[str, list[tuple[str, float]]] = {}
        for i, nv in enumerate(new_vecs):
            scores = []
            for j, ev in enumerate(existing_vecs):
                sim = self._cosine_similarity(nv, ev)
                if sim >= 0.55:
                    scores.append((existing_texts[j], sim))
            scores.sort(key=lambda x: x[1], reverse=True)
            if scores:
                results[new_entities[i].name] = scores[:10]
        return results

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算余弦相似度。"""
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def full_dedup_library(
        self,
        *,
        user_id: str,
        library_id: str,
        llm_config: dict[str, Any] | None = None,
        eps: float = 0.5,
        min_samples: int = 2,
        max_cluster_size: int = 500,
    ) -> int:
        """全库实体去重: Embedding 聚类 + 逐簇小模型去重。

        先用 Embedding 将全库实体向量化,再用 DBSCAN 按余弦距离聚出"语义密集团"。
        如果单个簇超过 max_cluster_size 则拆成子批次,避免一次喂给 LLM 太多实体。
        """

        with Session(self.engine) as db:
            entity_rows = db.exec(
                select(KnowledgeGraphNode)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .where(KnowledgeGraphNode.node_type == "entity")
            ).all()

        if len(entity_rows) <= 1:
            _set_dedup_progress(user_id, library_id, "completed", 0, 0, "无需去重", 0)
            return 0

        _set_dedup_progress(user_id, library_id, "running", 0, 0, "正在生成 Embedding…", 0)

        # 生成全部实体的嵌入向量
        embedder = EmbeddingService(config=self.config)
        all_labels = [row.label for row in entity_rows]
        all_vectors = embedder.embed_texts(all_labels)  # list[list[float]]

        # DBSCAN 聚类 (余弦距离)
        matrix = np.array(all_vectors, dtype=np.float64)
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit(matrix)
        cluster_labels = clustering.labels_

        # 按簇分组,跳过噪声点(簇标签 -1); 超大簇拆成子批次
        raw_clusters: dict[int, list[tuple[str, KnowledgeGraphNode]]] = {}
        for label, entity_label, row in zip(cluster_labels, all_labels, entity_rows):
            if label == -1:
                continue
            raw_clusters.setdefault(label, []).append((entity_label, row))

        batches: list[list[tuple[str, KnowledgeGraphNode]]] = []
        for items in raw_clusters.values():
            for start in range(0, len(items), max_cluster_size):
                batches.append(items[start:start + max_cluster_size])

        total_batches = len(batches)
        _set_dedup_progress(user_id, library_id, "running", total_batches, 0,
                            f"聚类完成,共 {total_batches} 批需要处理", 0)

        extractor = LLMKnowledgeGraphExtractor(
            config=self.config,
            llm_config=llm_config,
            user_id=user_id,
            library_id=library_id,
        )
        dummy_doc = StructuredKnowledgeDocument(
            document_id="__full_dedup__", source_type="text", source_path="", source_uri="",
            source_hash="", title="【全库去重】", summary="", tags=[], authority=0.7,
            valid_from=None, valid_until=None, metadata={}, sections=[],
        )

        all_mapping: dict[str, str] = {}
        for idx, cluster_items in enumerate(batches, start=1):
            if len(cluster_items) <= 1:
                continue
            batch = [
                EntityCandidate(
                    name=label,
                    entity_type=row.entity_type,
                    aliases=row.metadata_json.get("aliases", []) if row.metadata_json else [],
                    description="",
                    confidence=row.metadata_json.get("confidence", 0.7) if row.metadata_json else 0.7,
                )
                for label, row in cluster_items
            ]
            _set_dedup_progress(user_id, library_id, "running", total_batches, idx,
                                f"正在处理第 {idx}/{total_batches} 批 ({len(batch)} 个实体)", 0)
            result = extractor.deduplicate_entities(batch, document=dummy_doc)
            name_mapping = result.get("name_mapping", {}) or {}
            for src, dst in name_mapping.items():
                all_mapping[src] = dst

        if not all_mapping:
            _set_dedup_progress(user_id, library_id, "completed", total_batches, total_batches, "未发现同义实体", 0)
            return 0

        _set_dedup_progress(user_id, library_id, "running", total_batches, total_batches, "正在更新数据库…", 0)

        # ----------------------------------------------------------------
        # 以下 DB 更新逻辑与原实现一致 (链式映射 + 重定向边 + 清理自环)
        # ----------------------------------------------------------------
        label_map: dict[str, str] = {}
        seen_labels: set[str] = set()
        for src, dst in all_mapping.items():
            if src == dst:
                continue
            resolved = dst
            visited = {src}
            while resolved in all_mapping and resolved != all_mapping[resolved]:
                if resolved in visited:
                    resolved = dst
                    break
                visited.add(resolved)
                resolved = all_mapping[resolved]
            label_map[src] = resolved
            seen_labels.add(src)
            seen_labels.add(resolved)

        with Session(self.engine) as db:
            for src_label, dst_label in label_map.items():
                src_rows = db.exec(
                    select(KnowledgeGraphNode)
                    .where(KnowledgeGraphNode.user_id == user_id)
                    .where(KnowledgeGraphNode.library_id == library_id)
                    .where(KnowledgeGraphNode.node_type == "entity")
                    .where(KnowledgeGraphNode.label == src_label)
                ).all()
                dst_rows = db.exec(
                    select(KnowledgeGraphNode)
                    .where(KnowledgeGraphNode.user_id == user_id)
                    .where(KnowledgeGraphNode.library_id == library_id)
                    .where(KnowledgeGraphNode.node_type == "entity")
                    .where(KnowledgeGraphNode.label == dst_label)
                ).all()
                if not src_rows or not dst_rows:
                    continue
                src_node = src_rows[0]
                dst_node = dst_rows[0]
                if src_node.node_id == dst_node.node_id:
                    continue
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.source_node_id == src_node.node_id)
                ).all():
                    edge.source_node_id = dst_node.node_id
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.target_node_id == src_node.node_id)
                ).all():
                    edge.target_node_id = dst_node.node_id
                db.delete(src_node)
            for edge in db.exec(
                select(KnowledgeGraphEdge)
                .where(KnowledgeGraphEdge.user_id == user_id)
                .where(KnowledgeGraphEdge.library_id == library_id)
                .where(KnowledgeGraphEdge.source_node_id == KnowledgeGraphEdge.target_node_id)
            ).all():
                db.delete(edge)
            db.commit()
        merged = len(label_map)
        _set_dedup_progress(user_id, library_id, "completed", total_batches, total_batches,
                            f"去重完成,合并了 {merged} 个实体", merged)
        return merged

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
        written_entity_node_ids: set[str] = set()
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
                entity_node_ids[self._normalize_label(entity.name)] = node_id
                written_entity_node_ids.add(node_id)
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
                source_id = entity_node_ids.get(relation.source) or entity_node_ids.get(self._normalize_label(relation.source))
                target_id = entity_node_ids.get(relation.target) or entity_node_ids.get(self._normalize_label(relation.target))
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
        return len(written_entity_node_ids), written_relations

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

    def list_document_statuses(self, *, user_id: str, library_id: str) -> dict[str, KnowledgeGraphDocumentStatus]:
        """Return graph extraction status records keyed by source document id."""

        with Session(self.engine) as db:
            statuses = db.exec(
                select(KnowledgeGraphDocumentStatus)
                .where(KnowledgeGraphDocumentStatus.user_id == user_id)
                .where(KnowledgeGraphDocumentStatus.library_id == library_id)
            ).all()
            return {status.document_id: status for status in statuses}

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

    @classmethod
    def _coalesce_entity_nodes(
        cls,
        nodes: list[KnowledgeGraphNode],
    ) -> tuple[list[KnowledgeGraphNode], dict[str, str]]:
        """按规范化实体名合并历史同名实体节点并返回旧 ID 到规范 ID 的映射。"""

        result: list[KnowledgeGraphNode] = []
        entity_by_label: dict[str, KnowledgeGraphNode] = {}
        aliases: dict[str, str] = {}
        for node in nodes:
            if node.node_type != "entity":
                result.append(node)
                continue
            key = cls._normalize_label(node.label)
            canonical = entity_by_label.get(key)
            if canonical is None:
                entity_by_label[key] = node
                result.append(node)
                continue
            aliases[node.node_id] = canonical.node_id
            if canonical.entity_type in {"", "other"} and node.entity_type not in {"", "other"}:
                canonical.entity_type = node.entity_type
        return result, aliases

    @staticmethod
    def _coalesce_edges(
        edges: list[KnowledgeGraphEdge],
        node_id_aliases: dict[str, str],
    ) -> list[KnowledgeGraphEdge]:
        """把边两端映射到合并后的实体节点,并删除合并后重复或自环的边。"""

        result: list[KnowledgeGraphEdge] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for edge in edges:
            source_id = node_id_aliases.get(edge.source_node_id, edge.source_node_id)
            target_id = node_id_aliases.get(edge.target_node_id, edge.target_node_id)
            if source_id == target_id:
                continue
            key = (
                source_id,
                target_id,
                edge.relation_type,
                edge.source_document_id,
                edge.source_section_id,
            )
            if key in seen:
                continue
            seen.add(key)
            edge.source_node_id = source_id
            edge.target_node_id = target_id
            result.append(edge)
        return result

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

        return cls._hashed_id("kgent", user_id, library_id, cls._normalize_label(label))

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


# ---------------------------------------------------------------------------
# 后台图谱抽取进度追踪
# ---------------------------------------------------------------------------

_graph_extraction_progress: dict[tuple[str, str], dict[str, Any]] = {}
_graph_progress_lock = threading.Lock()


def get_graph_extraction_progress(user_id: str, library_id: str) -> dict[str, Any]:
    """返回给定用户/知识库的图谱抽取进度。"""
    with _graph_progress_lock:
        state = _graph_extraction_progress.get((user_id, library_id))
        if state is None:
            return {"status": "idle", "total": 0, "current": 0, "message": ""}
        return dict(state)


def _update_graph_progress(
    user_id: str,
    library_id: str,
    *,
    status: str,
    total: int = 0,
    current: int = 0,
    message: str = "",
    result_json: str = "",
    docs: list[dict] | None = None,
) -> None:
    """线程安全地更新进度状态。"""
    with _graph_progress_lock:
        entry: dict[str, Any] = {
            "status": status,
            "total": total,
            "current": current,
            "message": message,
            "result": result_json,
        }
        if docs is not None:
            entry["docs"] = docs
        _graph_extraction_progress[(user_id, library_id)] = entry


# ---------------------------------------------------------------------------
# 全库去重进度追踪
# ---------------------------------------------------------------------------

_dedup_progress: dict[tuple[str, str], dict[str, Any]] = {}
_dedup_progress_lock = threading.Lock()


def get_dedup_progress(user_id: str, library_id: str) -> dict[str, Any]:
    """返回给定用户/知识库的全库去重进度。"""
    with _dedup_progress_lock:
        state = _dedup_progress.get((user_id, library_id))
        if state is None:
            return {"status": "idle", "total": 0, "current": 0, "message": ""}
        return dict(state)


def _set_dedup_progress(
    user_id: str,
    library_id: str,
    status: str,
    total: int = 0,
    current: int = 0,
    message: str = "",
    merged_count: int = 0,
) -> None:
    """更新全库去重进度。"""
    with _dedup_progress_lock:
        _dedup_progress[(user_id, library_id)] = {
            "status": status,
            "total": total,
            "current": current,
            "message": message,
            "merged_count": merged_count,
        }


def _build_llm_config(
    config: AgentConfig,
    user_llm_config: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    """从 config 构造抽取器可用的 llm_config 字典。

    优先级: user_llm_config（用户设置页）> AgentConfig（env/默认值）。
    当小模型未配置时，整体降级使用主模型配置（model_name + key + base_url 一起切换），
    避免将主模型的 key 发送到小模型默认端点，或缺少 small_model_name 导致调度器无法构造模型。
    """
    has_user_config = bool(user_llm_config)
    source = user_llm_config or {}
    base = {
        "model_name": None,
        "api_key": None,
        "base_url": None,
        "small_model_name": None,
        "small_api_key": None,
        "small_base_url": None,
    }
    if has_user_config:
        for key in base:
            val = source.get(key)
            if val and isinstance(val, str) and val.strip():
                base[key] = val.strip()
    else:
        base = {
            "model_name": config.model.model_name.strip() or None,
            "api_key": config.model.api_key.strip() or None,
            "base_url": config.model.base_url.strip() or None,
            "small_model_name": config.model.small_model_name.strip() or None,
            "small_api_key": config.model.small_model_api_key.strip() or None,
            "small_base_url": config.model.small_model_base_url.strip() or None,
        }

    small_model_name = base.get("small_model_name")
    if not small_model_name:
        small_model_name = base.get("model_name")
        small_key = base.get("api_key")
        small_url = base.get("base_url")
    else:
        small_key = base.get("small_api_key") or base.get("api_key")
        small_url = base.get("small_base_url") or base.get("base_url")
    return {
        "model_name": base.get("model_name"),
        "api_key": base.get("api_key"),
        "base_url": base.get("base_url"),
        "small_model_name": small_model_name,
        "small_api_key": small_key,
        "small_base_url": small_url,
    }


def _run_graph_extraction(
    *,
    config: AgentConfig,
    user_id: str,
    library_id: str,
    frontmatter_dir: Path,
    user_llm_config: dict[str, Any] | None = None,
    target_source_path: Path | None = None,
    target_is_dir: bool = False,
) -> None:
    """在后台线程中执行图谱抽取并更新进度。"""
    try:
        llm_config = _build_llm_config(config, user_llm_config=user_llm_config)
        if not llm_config.get("small_api_key") or not llm_config.get("small_model_name"):
            _update_graph_progress(
                user_id, library_id,
                status="failed",
                message="模型配置不完整，无法进行 LLM 语义抽取。请在「模型设置」中至少配置大模型的模型名和 API Key；小模型留空时会自动继承大模型。",
            )
            return

        svc = KnowledgeGraphService(config=config)
        paths = sorted(path for path in frontmatter_dir.rglob("*.json") if path.is_file()) if frontmatter_dir.exists() else []
        if target_source_path is not None:
            paths = [
                path
                for path in paths
                if _frontmatter_path_matches_target(
                    path=path,
                    target_source_path=target_source_path,
                    target_is_dir=target_is_dir,
                )
            ]
        total = len(paths)
        print(f"\n{'='*60}")
        print(f"  知识图谱抽取开始 | 共 {total} 个文档")
        print(f"  frontmatter_dir={frontmatter_dir}")
        if target_source_path is not None:
            print(f"  target_source_path={target_source_path}")
        print(f"{'='*60}\n")

        docs: list[dict] = []
        pending_paths: list[Path] = []
        document_ids_seen: set[str] = set()
        need_extract = 0
        skipped_count = 0
        for path in paths:
            doc_data = KnowledgeGraphService._load_document(path)
            document_ids_seen.add(doc_data.document_id)
            total_sections = len(doc_data.sections) if doc_data.sections else 0
            is_current = svc._is_document_current(
                user_id=user_id,
                library_id=library_id,
                document_id=doc_data.document_id,
                source_hash=doc_data.source_hash,
            )
            if is_current:
                skipped_count += 1
                print(f"  SKIP {doc_data.title or path.name} [hash not changed]")
            else:
                docs.append(_graph_progress_doc_entry(
                    document=doc_data,
                    frontmatter_path=path,
                    frontmatter_dir=frontmatter_dir,
                    status="pending",
                    progress=0,
                    total_sections=total_sections,
                ))
                pending_paths.append(path)
                need_extract += 1

        _update_graph_progress(
            user_id, library_id,
            status="running",
            total=need_extract,
            current=0,
            message=f"需抽取 {need_extract}/{total} 个文档",
            docs=docs,
        )

        svc.sync_document_nodes_frontmatter_dir(
            user_id=user_id,
            library_id=library_id,
            frontmatter_dir=frontmatter_dir,
        )
        print(f"  [同步] 文档节点同步完成, 开始 LLM 抽取\n")

        extractor = LLMKnowledgeGraphExtractor(
            config=config,
            llm_config=llm_config,
            user_id=user_id,
            library_id=library_id,
        )
        circuit_breaker_hit = False
        completed_count = 0
        failed_count = 0
        total_entities = 0
        total_relations = 0
        doc_index = 0

        for di, doc_entry in enumerate(docs):
            if circuit_breaker_hit:
                print(f"\n  [BREAKER] circuit breaker hit, stopping")
                break
            path = pending_paths[di]
            document = KnowledgeGraphService._load_document(path)

            docs[di]["status"] = "processing"
            _update_graph_progress(
                user_id, library_id,
                status="running",
                total=need_extract,
                current=doc_index + 1,
                message=f"处理文档 {doc_index + 1}/{need_extract}: {document.title}",
                docs=docs,
            )

            title_display = document.title or path.name
            print(f"  [{di+1:3d}/{total}] --> {title_display[:60]:60s} "
                  f"(sections: {len(document.sections)})")

            try:
                svc.delete_document_graph(user_id=user_id, library_id=library_id, document_id=document.document_id)
                svc._write_document_node(user_id=user_id, library_id=library_id, document=document)
                entities_by_key: dict[tuple[str, str], EntityCandidate] = {}
                relations: list[tuple[RelationCandidate, StructuredKnowledgeSection]] = []
                for si, section in enumerate(document.sections):
                    docs[di]["progress"] = int((si + 1) / len(document.sections) * 100)
                    _update_graph_progress(
                        user_id, library_id,
                        status="running",
                        total=need_extract,
                        current=doc_index,
                        message=f"处理文档 {doc_index + 1}/{need_extract} 第 {si + 1}/{len(document.sections)} 段",
                        docs=docs,
                    )
                    section_title = section.title_path[-1] if section.title_path else f"section_{si}"
                    print(f"    |-- section {si+1}/{len(document.sections)}: {section_title[:50]} -> LLM...", end="")
                    payload = extractor.extract(document=document, section=section)
                    time.sleep(0.5)  # 限流: 每段间等待 500ms 避免 429
                    section_entities = svc._sanitize_entities(payload.get("entities"))
                    for entity in section_entities:
                        entities_by_key[(svc._normalize_label(entity.name), entity.entity_type)] = entity
                    section_entity_names = {entity.name for entity in section_entities}
                    section_relations = svc._sanitize_relations(
                        payload.get("relations"),
                        section_text=section.content,
                        allowed_entity_names=section_entity_names,
                    )
                    relations.extend(
                        (relation, section)
                        for relation in section_relations
                    )
                    print(f" entities={len(section_entities)} relations={len(section_relations)}")

                # 语义去重: 合并不同 section 中同名但不同表述的实体
                if isinstance(extractor, LLMKnowledgeGraphExtractor) and entities_by_key:
                    entity_list = list(entities_by_key.values())
                    dedup_result = extractor.deduplicate_entities(entity_list, document=document)
                    merged_entities = dedup_result.get("entities", entity_list)
                    name_mapping = dedup_result.get("name_mapping", {})
                    if name_mapping:
                        entities_by_key = {
                            (svc._normalize_label(e.name), e.entity_type): e
                            for e in merged_entities
                        }
                        remapped: list[tuple[RelationCandidate, StructuredKnowledgeSection]] = []
                        for relation, section in relations:
                            new_source = name_mapping.get(relation.source, relation.source)
                            new_target = name_mapping.get(relation.target, relation.target)
                            if new_source == new_target:
                                continue
                            relation.source = new_source
                            relation.target = new_target
                            remapped.append((relation, section))
                        relations = remapped

                # 库级增量去重: embedding 检索 + 小模型裁决
                if isinstance(extractor, LLMKnowledgeGraphExtractor) and entities_by_key:
                    entity_list = list(entities_by_key.values())
                    cross_mapping = svc._deduplicate_entities_incremental(
                        user_id=user_id, library_id=library_id,
                        new_entities=entity_list, extractor=extractor, document=document,
                    )
                    if cross_mapping:
                        new_keyed: dict[tuple[str, str], EntityCandidate] = {}
                        for entity in entity_list:
                            new_name = cross_mapping.get(entity.name, entity.name)
                            if svc._normalize_label(new_name) != svc._normalize_label(entity.name):
                                entity.name = new_name
                            key = (svc._normalize_label(entity.name), entity.entity_type)
                            if key not in new_keyed or entity.confidence > new_keyed[key].confidence:
                                new_keyed[key] = entity
                        entities_by_key = new_keyed
                        remapped2: list[tuple[RelationCandidate, StructuredKnowledgeSection]] = []
                        for relation, section in relations:
                            new_src = cross_mapping.get(relation.source, relation.source)
                            new_tgt = cross_mapping.get(relation.target, relation.target)
                            if new_src == new_tgt:
                                continue
                            relation.source = new_src
                            relation.target = new_tgt
                            remapped2.append((relation, section))
                        relations = remapped2

                written_entities, written_relations = svc._write_graph(
                    user_id=user_id,
                    library_id=library_id,
                    document=document,
                    entities=list(entities_by_key.values()),
                    relations=relations,
                )
                svc._write_status(
                    user_id=user_id,
                    library_id=library_id,
                    document=document,
                    status="completed" if written_entities or written_relations else "skipped",
                    message="" if written_entities or written_relations else "no valid graph candidates",
                    entity_count=written_entities,
                    relation_count=written_relations,
                )
                if written_entities or written_relations:
                    completed_count += 1
                    total_entities += written_entities
                    total_relations += written_relations
                    docs[di]["status"] = "done"
                    docs[di]["progress"] = 100
                    print(f"    ++ DONE: {written_entities} entities, {written_relations} relations")
                else:
                    skipped_count += 1
                    docs[di]["status"] = "skipped"
                    docs[di]["progress"] = 100
                    print(f"    -- SKIP: no valid entities/relations")

            except Exception as exc:
                exc_msg = str(exc)
                failed_count += 1
                docs[di]["status"] = "failed"
                docs[di]["progress"] = 100
                logger.warning("知识图谱抽取失败 | document=%s error=%s", document.document_id, exc_msg)
                svc._write_status(
                    user_id=user_id,
                    library_id=library_id,
                    document=document,
                    status="failed",
                    message=exc_msg[:1000],
                    entity_count=0,
                    relation_count=0,
                )
                print(f"    !! FAIL: {exc_msg[:120]}")
                if "熔断" in exc_msg or "circuit breaker" in exc_msg.lower() or "MISSING API KEY" in exc_msg or "insufficient balance" in exc_msg.lower() or "exceeded_current_quota" in exc_msg or "suspended" in exc_msg.lower():
                    circuit_breaker_hit = True

            doc_index += 1
            _update_graph_progress(
                user_id, library_id,
                status="running",
                total=need_extract,
                current=doc_index,
                message=f"处理完成 {doc_index}/{need_extract}: {document.title}",
                docs=docs,
            )
            # 限流: 每文档间等待 1s,让 API 有喘息时间
            time.sleep(1.0)

        if target_source_path is None:
            svc.delete_graph_except_documents(
                user_id=user_id,
                library_id=library_id,
                keep_document_ids=document_ids_seen,
            )

        print(f"\n{'='*60}")
        print(f"  图谱抽取完成!")
        print(f"  |-- total docs: {total}")
        print(f"  |-- completed:  {completed_count}")
        print(f"  |-- failed:     {failed_count}")
        print(f"  |-- skipped:    {skipped_count}")
        print(f"  |-- entities:   {total_entities}")
        print(f"  |-- relations:  {total_relations}")
        if circuit_breaker_hit:
            print(f"  !! some docs skipped due to circuit breaker")
        print(f"{'='*60}\n")

        if failed_count > 0 and completed_count == 0:
            _update_graph_progress(
                user_id, library_id,
                status="failed",
                total=need_extract,
                current=doc_index,
                message=f"图谱抽取失败：{failed_count} 个文档抽取失败，请检查模型配置或 API Key。",
                docs=docs,
            )
        elif circuit_breaker_hit:
            _update_graph_progress(
                user_id, library_id,
                status="completed",
                total=need_extract,
                current=need_extract,
                message="图谱抽取完成（部分文档因模型调用限流或熔断已跳过）",
                docs=docs,
            )
        else:
            _update_graph_progress(
                user_id, library_id,
                status="completed",
                total=need_extract,
                current=need_extract,
                message="图谱抽取完成",
                docs=docs,
            )
    except Exception as exc:
        logger.exception("图谱抽取整体失败")
        print(f"\n  !! Graph extraction failed: {exc}\n")
        _update_graph_progress(
            user_id, library_id,
            status="failed",
            message=f"抽取失败: {exc}",
        )


def _frontmatter_path_matches_target(*, path: Path, target_source_path: Path, target_is_dir: bool) -> bool:
    """判断 frontmatter 文档的原始源文件是否落在右键指定的文件/文件夹范围内。"""

    try:
        document = KnowledgeGraphService._load_document(path)
    except Exception:
        return False
    raw_source_path = document.source_path or document.source_uri
    if not raw_source_path:
        return False
    try:
        source_path = Path(raw_source_path).resolve(strict=False)
    except (OSError, ValueError):
        return False
    target = target_source_path.resolve(strict=False)
    source_key = _normalize_graph_scope_path(source_path)
    target_key = _normalize_graph_scope_path(target)
    if not target_is_dir:
        return source_key == target_key
    return source_key == target_key or source_key.startswith(f"{target_key}\\")


def _graph_progress_doc_entry(
    *,
    document: StructuredKnowledgeDocument,
    frontmatter_path: Path,
    frontmatter_dir: Path,
    status: str,
    progress: int,
    total_sections: int,
) -> dict[str, Any]:
    """Build one graph progress doc row using the source-file relative path."""

    return {
        "path": _graph_progress_relative_path(
            document=document,
            frontmatter_path=frontmatter_path,
            frontmatter_dir=frontmatter_dir,
        ),
        "name": document.title or Path(document.source_path or frontmatter_path.stem).stem,
        "status": status,
        "progress": progress,
        "total_sections": total_sections,
    }


def _graph_progress_relative_path(
    *,
    document: StructuredKnowledgeDocument,
    frontmatter_path: Path,
    frontmatter_dir: Path,
) -> str:
    """Return the knowledge-tree path for one frontmatter document."""

    relative_path = str(document.metadata.get("relative_path") or "").replace("\\", "/").strip("/")
    if relative_path:
        return relative_path
    try:
        return frontmatter_path.relative_to(frontmatter_dir).as_posix()
    except ValueError:
        return frontmatter_path.name


def _normalize_graph_scope_path(path: Path) -> str:
    """归一化 Windows 路径用于图谱右键抽取范围比较。"""

    return str(path).replace("/", "\\").rstrip("\\").lower()

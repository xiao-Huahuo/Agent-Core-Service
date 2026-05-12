"""
记忆时效性解析服务。
功能说明:
本文件实现 `MemoryResolver`,负责把自然语言摘要中的关键事实解析为结构化事实单元,并根据事实类别
执行新旧覆盖、值追加或状态过期处理。它是“信息时效性”真正落地的业务层: 不是单纯依赖向量相似度
排序,而是显式维护事实状态。
使用说明:
summary_service 在写入 `session_summary` 后,应调用 `MemoryResolver.resolve_summary(...)`。
该方法会从摘要中提取结构化 facts,生成 `session_fact` 记忆,并对旧事实执行 superseded/expired 处理。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate, LongTermMemorySpecOut
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService


@dataclass(slots=True)
class MemoryFact:
    """
    结构化事实单元。
    namespace: 事实命名空间,用于区分业务域。
    key: 事实键名,用于定义单值/多值槽位。
    value: 事实值。
    category: 事实类别,支持 `single_value`、`multi_value`、`temporal`。
    status: 事实状态,支持 `active`、`superseded`、`expired`。
    valid_from: 事实生效时间。
    valid_until: 事实失效时间。
    value_type: 事实值类型。
    """

    namespace: str
    key: str
    value: str
    category: str
    status: str = "active"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    value_type: str = "string"

    def to_metadata(self) -> dict[str, Any]:
        """将事实单元转换为长期记忆 metadata。"""

        return {
            "namespace": self.namespace,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "status": self.status,
            "value_type": self.value_type,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
        }

    def render_content(self) -> str:
        """生成可直接写入记忆正文的事实文本。"""

        if self.namespace == "project" and self.key == "project_code":
            return f"当前项目代号为{self.value}。"
        if self.namespace == "project" and self.key == "owner_module":
            return f"当前负责模块为{self.value}。"
        return f"{self.namespace}.{self.key} = {self.value}"


class MemoryResolver:
    """
    记忆时效性解析器。
    config: 全局配置对象。
    memory_service: 长期记忆服务,用于创建事实记忆和更新旧事实状态。
    embedding_service: Embedding 服务,用于为结构化事实记忆生成向量。
    """

    PROJECT_CODE_PATTERNS = (
        re.compile(
            r"(?:\u5f53\u524d)?\u9879\u76ee\u4ee3\u53f7"
            r"(?:\u5df2\u7ecf\u4ece[^\s\uff0c\u3002]+\u6539\u6210|\u5df2\u66f4\u65b0\u4e3a|\u66f4\u65b0\u4e3a|"
            r"\u5df2\u786e\u8ba4\u4e3a|\u5df2\u786e\u8ba4|\u786e\u8ba4|\u4e3a|\u662f)"
            r"\s*[\uff1a:]?\s*[\"“]?([A-Za-z0-9_-]+)[\"”]?"
        ),
    )
    OWNER_MODULE_PATTERNS = (
        re.compile(
            r"(?:\u8d1f\u8d23\u6a21\u5757|(?:\u5f53\u524d)?\u8d1f\u8d23\u6a21\u5757)"
            r"(?:\u5df2\u66f4\u65b0\u4e3a|\u4e3a|\u662f)"
            r"\s*[\uff1a:]?\s*[\"“]?([A-Za-z0-9_.-]+)[\"”]?"
        ),
    )

    def __init__(
        self,
        *,
        config: AgentConfig,
        memory_service: LongTermMemoryService | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """初始化记忆时效性解析器。"""

        self.config = config
        self.memory_service = memory_service or LongTermMemoryService(config=config)
        self.embedding_service = embedding_service or EmbeddingService(config=config)
        self.model = self._build_model()

    def resolve_summary(
        self,
        *,
        user_id: str,
        session_id: str,
        summary_memory: LongTermMemorySpecOut,
    ) -> list[LongTermMemorySpecOut]:
        """
        从摘要记忆中提取结构化事实并执行时效性解析。
        user_id: 用户 ID。
        session_id: 当前摘要所属 session ID。
        summary_memory: 已写入的自然语言摘要记忆。
        """

        facts = self.extract_facts(summary_memory.content)
        resolved_memories: list[LongTermMemorySpecOut] = []
        for fact in facts:
            if fact.valid_from is None:
                fact.valid_from = summary_memory.created_at
            fact_memory = self._create_fact_memory(
                user_id=user_id,
                session_id=session_id,
                fact=fact,
                summary_memory=summary_memory,
            )
            self._apply_fact_resolution(new_fact_memory=fact_memory)
            resolved_memories.append(fact_memory)
        return resolved_memories

    def extract_facts(self, summary: str) -> list[MemoryFact]:
        """
        从摘要文本中提取结构化事实。
        summary: 当前 session 的自然语言摘要。
        """

        normalized = summary.strip()
        if not normalized:
            return []
        llm_facts = self._extract_facts_via_model(normalized)
        if llm_facts:
            return llm_facts
        extracted: list[MemoryFact] = []
        project_code = self._extract_first_match(normalized, self.PROJECT_CODE_PATTERNS)
        if project_code:
            extracted.append(
                MemoryFact(
                    namespace="project",
                    key="project_code",
                    value=project_code,
                    category="single_value",
                )
            )
        owner_module = self._extract_first_match(normalized, self.OWNER_MODULE_PATTERNS)
        if owner_module:
            extracted.append(
                MemoryFact(
                    namespace="project",
                    key="owner_module",
                    value=owner_module,
                    category="single_value",
                )
            )
        return extracted

    def _extract_facts_via_model(self, summary: str) -> list[MemoryFact]:
        """
        使用 LLM 按 schema 从摘要中提取结构化事实。
        summary: 当前 session 的自然语言摘要。
        """

        response = self.model.invoke(
            [
                SystemMessage(
                    content=(
                        "你负责从记忆摘要中抽取结构化事实。"
                        "只允许输出 JSON 数组,不要输出额外解释。"
                        "已知事实 schema 如下:"
                        "["
                        "{\"namespace\":\"project\",\"key\":\"project_code\",\"category\":\"single_value\"},"
                        "{\"namespace\":\"project\",\"key\":\"owner_module\",\"category\":\"single_value\"}"
                        "]。"
                        "如果摘要里没有明确事实,返回 []。"
                    )
                ),
                HumanMessage(
                    content=(
                        "请从下面摘要中提取 facts,字段固定为 "
                        "namespace,key,value,category,status,value_type。"
                        "status 固定填 active,value_type 固定填 string。\n"
                        f"摘要: {summary}"
                    )
                ),
            ]
        )
        content = str(response.content).strip()
        if not content:
            return []
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        facts: list[MemoryFact] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            namespace = str(item.get("namespace", "")).strip()
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            category = str(item.get("category", "")).strip()
            if not namespace or not key or not value or not category:
                continue
            facts.append(
                MemoryFact(
                    namespace=namespace,
                    key=key,
                    value=value,
                    category=category,
                    status=str(item.get("status", "active")).strip() or "active",
                    value_type=str(item.get("value_type", "string")).strip() or "string",
                )
            )
        return facts

    def _create_fact_memory(
        self,
        *,
        user_id: str,
        session_id: str,
        fact: MemoryFact,
        summary_memory: LongTermMemorySpecOut,
    ) -> LongTermMemorySpecOut:
        """
        为结构化事实创建独立长期记忆。
        user_id: 用户 ID。
        session_id: 当前 session ID。
        fact: 结构化事实单元。
        summary_memory: 来源摘要记忆。
        """

        content = fact.render_content()
        vector = self.embedding_service.embed_text(content)
        return self.memory_service.create_memory(
            LongTermMemorySpecCreate(
                user_id=user_id,
                session_id=session_id,
                tag=self.config.constants.memory_tag,
                memory_type="session_fact",
                content=content,
                source_type="session_summary",
                source_id=summary_memory.memory_id,
                source_hash=summary_memory.source_hash,
                source_range_json={"summary_memory_id": summary_memory.memory_id},
                metadata_json={
                    "fact": fact.to_metadata(),
                    "summary_memory_id": summary_memory.memory_id,
                    "fact_status": fact.status,
                },
                valid_from=fact.valid_from,
                valid_until=fact.valid_until,
                confidence=0.9,
                importance=0.9,
                authority=0.6,
                embedding_model=self.config.model.embedding_model_name,
                embedding_vector_json=vector,
            )
        )

    def _apply_fact_resolution(self, *, new_fact_memory: LongTermMemorySpecOut) -> None:
        """
        根据事实类别执行新旧覆盖或状态过期处理。
        new_fact_memory: 新写入的事实记忆。
        """

        fact = self._read_fact(new_fact_memory.metadata_json)
        if fact is None:
            return
        if fact.category == "temporal":
            if new_fact_memory.valid_until and new_fact_memory.valid_until <= self._utc_now():
                self.memory_service.update_fact_status(
                    memory_id=new_fact_memory.memory_id,
                    fact_status="expired",
                    valid_until=new_fact_memory.valid_until,
                )
            return
        active_memories = self.memory_service.list_active_fact_memories(
            user_id=new_fact_memory.user_id,
            namespace=fact.namespace,
            key=fact.key,
            exclude_memory_id=new_fact_memory.memory_id,
        )
        if fact.category == "single_value":
            for old_memory in active_memories:
                self.memory_service.update_fact_status(
                    memory_id=old_memory.memory_id,
                    fact_status="superseded",
                    valid_until=new_fact_memory.valid_from or self._utc_now(),
                    superseded_by_memory_id=new_fact_memory.memory_id,
                )
            return
        if fact.category == "multi_value":
            for old_memory in active_memories:
                old_fact = self._read_fact(old_memory.metadata_json)
                if old_fact is not None and old_fact.value == fact.value:
                    self.memory_service.update_fact_status(
                        memory_id=new_fact_memory.memory_id,
                        fact_status="superseded",
                        valid_until=new_fact_memory.valid_from or self._utc_now(),
                        superseded_by_memory_id=old_memory.memory_id,
                    )
                    return

    @staticmethod
    def _extract_first_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
        """
        按给定模式列表提取第一个匹配值。
        text: 摘要文本。
        patterns: 用于结构化提取的正则模式集合。
        """

        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _read_fact(metadata_json: dict[str, Any]) -> MemoryFact | None:
        """
        从长期记忆 metadata 中恢复结构化事实。
        metadata_json: 长期记忆扩展元数据。
        """

        fact_payload = metadata_json.get("fact")
        if not isinstance(fact_payload, dict):
            return None
        valid_from = MemoryResolver._parse_datetime(fact_payload.get("valid_from"))
        valid_until = MemoryResolver._parse_datetime(fact_payload.get("valid_until"))
        return MemoryFact(
            namespace=str(fact_payload["namespace"]),
            key=str(fact_payload["key"]),
            value=str(fact_payload["value"]),
            category=str(fact_payload["category"]),
            status=str(fact_payload.get("status", "active")),
            valid_from=valid_from,
            valid_until=valid_until,
            value_type=str(fact_payload.get("value_type", "string")),
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """将 metadata 中的 ISO 时间字符串解析为 datetime。"""

        if not value:
            return None
        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    @staticmethod
    def _utc_now() -> datetime:
        """返回当前 UTC 时间。"""

        return datetime.now(timezone.utc)

    def _build_model(self) -> ChatOpenAI:
        """
        创建事实提取用 LLM。
        目前复用主模型配置,避免第一版增加单独的事实解析模型配置。
        """

        if not self.config.model.model_name:
            raise ValueError("config.model.model_name 不能为空。")
        if not self.config.model.api_key:
            raise ValueError("config.model.api_key 不能为空。")
        if not self.config.model.base_url:
            raise ValueError("config.model.base_url 不能为空。")
        return ChatOpenAI(
            model=self.config.model.model_name,
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url,
            temperature=0.0,
            timeout=self.config.model.timeout_seconds,
        )

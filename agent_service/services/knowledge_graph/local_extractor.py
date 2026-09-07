"""本地优先的知识图谱候选抽取器。

完整章节只传给进程内 LocalQwenService；确定性规则补充明确关系。高置信候选直接
返回，低置信候选丢弃，只有灰区候选及其最短原文证据会交给可选的联网裁决器。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.services.local_qwen import get_local_qwen_service

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "local-qwen-v1"
RULE_VERSION = "explicit-relations-v1"
RESULT_VERSION = "graph-payload-v1"

_LOCAL_SYSTEM_PROMPT = (
    "你是运行在用户本机的知识图谱抽取器。只抽取原文明确出现的实体和实体关系，不要推断。"
    "只输出合法 JSON：{\"entities\":[],\"relations\":[]}。"
    "实体字段为 name,type,aliases,description,confidence；关系字段为 source,target,type,evidence,confidence。"
    "每条关系的 evidence 必须是原文中的连续短语，confidence 必须是 0 到 1。"
)

_RELATION_LABELS = {
    "depends on": "depends_on",
    "uses": "uses",
    "calls": "calls",
    "creates": "creates",
    "contains": "contains",
    "defines": "defines",
    "produces": "produces",
    "consumes": "consumes",
    "configures": "configures",
    "依赖于": "depends_on",
    "依赖": "depends_on",
    "使用": "uses",
    "调用": "calls",
    "创建": "creates",
    "包含": "contains",
    "定义": "defines",
    "生成": "produces",
    "消费": "consumes",
    "配置": "configures",
}


class LocalFirstKnowledgeGraphExtractor:
    """组合本地 Qwen、确定性规则和可选联网灰区裁决。"""

    extractor_version = EXTRACTOR_VERSION
    rule_version = RULE_VERSION
    result_version = RESULT_VERSION

    def __init__(
        self,
        *,
        config: Any,
        local_service: Any | None = None,
        remote_adjudicator: Any | None = None,
    ) -> None:
        """保存复用的本地服务和只接收灰区候选的联网裁决器。"""

        self.config = config
        self.local_service = local_service or get_local_qwen_service(config)
        self.remote_adjudicator = remote_adjudicator

    def extract(self, *, document: Any, section: Any) -> dict[str, Any]:
        """本地扫描完整章节，并仅将灰区候选的最短证据送去联网裁决。"""

        local_payload = self._extract_with_local_model(document=document, section=section)
        combined = self._merge_payloads(local_payload, self._extract_explicit_relations(section.content))
        accepted, pending = self._partition_candidates(combined)
        pending = self._remote_candidate_payload(pending)
        evidence_context = self._minimal_evidence_context(section.content, pending)
        if self._has_candidates(pending) and self.remote_adjudicator is not None:
            try:
                adjudicated = self.remote_adjudicator.adjudicate_candidates(
                    document=document,
                    section=section,
                    candidates=pending,
                    evidence_context=evidence_context,
                )
                accepted = self._merge_payloads(accepted, adjudicated)
                pending = self._empty_payload()
            except Exception as exc:  # noqa: BLE001 - remote failure must degrade to local results
                logger.warning(
                    "图谱灰区联网裁决失败，保留本地结果 | document=%s section=%s error=%s",
                    getattr(document, "document_id", ""),
                    getattr(section, "section_id", ""),
                    exc,
                )
        result = self._merge_payloads(accepted)
        result["_pending_candidates"] = pending
        if self._has_candidates(pending):
            result["_pending_candidates"]["evidence_context"] = evidence_context
        return result

    def extract_batch(self, *, document: Any, sections: list[Any]) -> dict[str, dict[str, Any]]:
        """逐章节调用串行本地模型，保持批处理调用方所需的 section_id 映射。"""

        return {
            section.section_id: self.extract(document=document, section=section)
            for section in sections
        }

    def retry_pending(
        self,
        *,
        document: Any,
        section: Any,
        accepted_payload: dict[str, Any],
        pending_candidates: dict[str, Any],
    ) -> dict[str, Any]:
        """复用缓存的本地结果，只重试此前失败的最小灰区候选。"""

        pending = {
            "entities": list(pending_candidates.get("entities", [])),
            "relations": list(pending_candidates.get("relations", [])),
        }
        evidence_context = str(pending_candidates.get("evidence_context") or "")
        if not self._has_candidates(pending) or self.remote_adjudicator is None:
            return {**self._merge_payloads(accepted_payload), "_pending_candidates": dict(pending_candidates)}
        try:
            adjudicated = self.remote_adjudicator.adjudicate_candidates(
                document=document,
                section=section,
                candidates=pending,
                evidence_context=evidence_context,
            )
            return {**self._merge_payloads(accepted_payload, adjudicated), "_pending_candidates": self._empty_payload()}
        except Exception as exc:  # noqa: BLE001 - cached local results remain authoritative
            logger.warning(
                "图谱灰区候选重试失败 | document=%s section=%s error=%s",
                getattr(document, "document_id", ""),
                getattr(section, "section_id", ""),
                exc,
            )
            return {**self._merge_payloads(accepted_payload), "_pending_candidates": dict(pending_candidates)}

    def _extract_with_local_model(self, *, document: Any, section: Any) -> dict[str, Any]:
        """调用本地 Qwen；模型不可用时安全降级为确定性规则结果。"""

        content = str(section.content or "").strip()
        if not content:
            return self._empty_payload()
        prompt = (
            f"文档标题: {document.title}\n"
            f"标题路径: {' / '.join(section.title_path)}\n"
            f"section_id: {section.section_id}\n正文:\n{content}"
        )
        try:
            response = self.local_service.chat(
                messages=[SystemMessage(content=_LOCAL_SYSTEM_PROMPT), HumanMessage(content=prompt)],
                temperature=0.0,
                max_new_tokens=self.config.limits.graph_local_max_output_tokens,
            )
            return self._parse_json_object(str(response.content or ""))
        except Exception as exc:  # noqa: BLE001 - rules still provide zero-cost extraction
            logger.warning(
                "本地图谱模型不可用，降级为确定性规则 | document=%s section=%s error=%s",
                getattr(document, "document_id", ""),
                getattr(section, "section_id", ""),
                exc,
            )
            return self._empty_payload()

    def _partition_candidates(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """按服务级置信度阈值拆分本地接受、联网灰区和直接丢弃候选。"""

        accepted = self._empty_payload()
        pending = self._empty_payload()
        low = float(self.config.limits.graph_candidate_low_confidence)
        high = float(self.config.limits.graph_candidate_high_confidence)
        for kind in ("entities", "relations"):
            for item in payload.get(kind, []):
                if not isinstance(item, dict):
                    continue
                try:
                    confidence = float(item.get("confidence", 0.7))
                except (TypeError, ValueError):
                    confidence = 0.7
                compact = self._compact_candidate(kind=kind, item=item, confidence=confidence)
                if confidence >= high:
                    accepted[kind].append(compact)
                elif confidence >= low:
                    pending[kind].append(compact)
        return accepted, pending

    @staticmethod
    def _remote_candidate_payload(pending: dict[str, Any]) -> dict[str, Any]:
        """移除联网裁决不需要的描述字段，只保留候选身份、置信度与关系证据。"""

        return {
            "entities": [
                {key: value for key, value in item.items() if key in {"name", "type", "aliases", "confidence"}}
                for item in pending.get("entities", [])
                if isinstance(item, dict)
            ],
            "relations": [dict(item) for item in pending.get("relations", []) if isinstance(item, dict)],
        }

    @staticmethod
    def _compact_candidate(*, kind: str, item: dict[str, Any], confidence: float) -> dict[str, Any]:
        """白名单化候选字段并限制长度，防止本地模型把正文复制进联网请求。"""

        if kind == "entities":
            raw_aliases = item.get("aliases", [])
            aliases = raw_aliases if isinstance(raw_aliases, list) else []
            return {
                "name": str(item.get("name") or "")[:80],
                "type": str(item.get("type") or item.get("entity_type") or "other")[:64],
                "aliases": [str(alias)[:80] for alias in aliases[:5]],
                "description": str(item.get("description") or "")[:240],
                "confidence": confidence,
            }
        return {
            "source": str(item.get("source") or "")[:80],
            "target": str(item.get("target") or "")[:80],
            "type": str(item.get("type") or item.get("relation_type") or "related_to")[:64],
            "evidence": str(item.get("evidence") or "")[:500],
            "confidence": confidence,
        }

    def _minimal_evidence_context(self, content: str, pending: dict[str, Any]) -> str:
        """只返回包含灰区名称或证据的原文句子，禁止以完整章节兜底。"""

        needles = {
            str(item.get(field) or "").strip()
            for kind in ("entities", "relations")
            for item in pending.get(kind, [])
            if isinstance(item, dict)
            for field in (("name",) if kind == "entities" else ("source", "target", "evidence"))
        }
        needles.discard("")
        sentences = re.split(r"(?<=[.!?。！？])\s*|[\r\n]+", content)
        matched = [sentence.strip() for sentence in sentences if sentence.strip() and any(needle in sentence for needle in needles)]
        limit = max(int(self.config.limits.graph_remote_evidence_chars), 1)
        return "\n".join(dict.fromkeys(matched))[:limit]

    @classmethod
    def _extract_explicit_relations(cls, content: str) -> dict[str, Any]:
        """从明确的中英文谓词句中补充无需模型裁决的高置信候选。"""

        payload = cls._empty_payload()
        entity_names: set[str] = set()
        english_predicates = "|".join(re.escape(item) for item in _RELATION_LABELS if item.isascii())
        english_pattern = re.compile(
            rf"(?P<source>[A-Za-z_][\w.:-]{{0,79}})\s+(?P<predicate>{english_predicates})\s+"
            rf"(?P<target>[A-Za-z_][\w.:-]{{0,79}})",
            flags=re.IGNORECASE,
        )
        chinese_predicates = "|".join(
            re.escape(item) for item in sorted((item for item in _RELATION_LABELS if not item.isascii()), key=len, reverse=True)
        )
        chinese_pattern = re.compile(
            rf"(?P<source>[A-Za-z0-9_\u4e00-\u9fff.:-]{{1,40}}?)\s*"
            rf"(?P<predicate>{chinese_predicates})\s*"
            rf"(?P<target>[A-Za-z0-9_\u4e00-\u9fff.:-]{{1,40}})(?=$|[，。；、!?！？\s])"
        )
        for pattern in (english_pattern, chinese_pattern):
            for match in pattern.finditer(content):
                source = match.group("source").strip(" \t.,;:，。；：!?！？")
                target = match.group("target").strip(" \t.,;:，。；：!?！？")
                predicate = match.group("predicate").lower()
                if source == target:
                    continue
                entity_names.update((source, target))
                payload["relations"].append({
                    "source": source,
                    "target": target,
                    "type": _RELATION_LABELS[predicate],
                    "evidence": match.group(0).strip(),
                    "confidence": 0.95,
                })
        payload["entities"] = [
            {"name": name, "type": cls._infer_entity_type(name), "aliases": [], "confidence": 0.95}
            for name in sorted(entity_names)
        ]
        return payload

    @staticmethod
    def _infer_entity_type(name: str) -> str:
        """根据稳定的代码标识符后缀提供保守实体类型，其他名称归为 concept。"""

        lowered = name.lower()
        if lowered.endswith("service"):
            return "class"
        if lowered.endswith((".py", ".ts", ".vue", ".md")):
            return "file"
        if "." in name and not lowered.endswith("."):
            return "module"
        return "concept"

    @classmethod
    def _merge_payloads(cls, *payloads: dict[str, Any]) -> dict[str, Any]:
        """按实体标识和关系证据合并多个候选来源。"""

        merged = cls._empty_payload()
        seen_entities: set[tuple[str, str]] = set()
        seen_relations: set[tuple[str, str, str, str]] = set()
        for payload in payloads:
            for item in payload.get("entities", []):
                if not isinstance(item, dict):
                    continue
                key = (str(item.get("name") or "").strip().casefold(), str(item.get("type") or "other"))
                if not key[0] or key in seen_entities:
                    continue
                seen_entities.add(key)
                merged["entities"].append(item)
            for item in payload.get("relations", []):
                if not isinstance(item, dict):
                    continue
                key = tuple(str(item.get(field) or "").strip().casefold() for field in ("source", "target", "type", "evidence"))
                if not key[0] or not key[1] or key in seen_relations:
                    continue
                seen_relations.add(key)
                merged["relations"].append(item)
        return merged

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        """解析本地模型 JSON，兼容 Markdown 代码围栏。"""

        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                return LocalFirstKnowledgeGraphExtractor._empty_payload()
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                return LocalFirstKnowledgeGraphExtractor._empty_payload()
        return payload if isinstance(payload, dict) else LocalFirstKnowledgeGraphExtractor._empty_payload()

    @staticmethod
    def _empty_payload() -> dict[str, list[Any]]:
        """返回互不共享列表的空候选结构。"""

        return {"entities": [], "relations": []}

    @staticmethod
    def _has_candidates(payload: dict[str, Any]) -> bool:
        """判断候选结构中是否仍有实体或关系。"""

        return bool(payload.get("entities") or payload.get("relations"))

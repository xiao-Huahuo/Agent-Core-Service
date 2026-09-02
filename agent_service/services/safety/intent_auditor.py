"""
意图审核层 (Layer 2)。

功能说明:
本文件实现 `IntentAuditor`,在敏感词初检通过后,使用小模型对用户意图做语义级安全审核。
主要检测:
- 用户是否有恶意攻击意图(越狱、注入、诈骗)
- 用户请求是否涉及非法或高危内容
- 用户是否试图绕过安全限制

审核结果分为: pass(通过) / block(拦截) / suspect(可疑,降级处理)

使用说明:
auditor = IntentAuditor(config=config, task_scheduler=scheduler)
result = auditor.audit(user_input="...")
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.core.context_budget import capacity_overrides_from_mapping
from agent_service.services.scheduler import (
    FOREGROUND_AGENT_TASK,
    LLMTaskScheduler,
    SMALL_MODEL_TIER,
    get_llm_task_scheduler,
)


BLOCK_CONFIDENCE_THRESHOLD = DEFAULT_BUSINESS_LIMITS.safety_block_confidence_threshold


@dataclass(slots=True)
class IntentAuditResult:
    """意图审核结果。"""

    verdict: str  # "pass" | "block" | "suspect"
    risk_type: str
    confidence: float
    reason: str

    @property
    def blocked(self) -> bool:
        """仅高置信度的 block 才真正拦截,低置信度降级为 suspect 放行。"""
        return self.verdict == "block" and self.confidence >= BLOCK_CONFIDENCE_THRESHOLD

    @property
    def suspect(self) -> bool:
        return self.verdict == "suspect" or (self.verdict == "block" and self.confidence < BLOCK_CONFIDENCE_THRESHOLD)

    @classmethod
    def default_pass(cls) -> "IntentAuditResult":
        return cls(verdict="pass", risk_type="正常请求", confidence=1.0, reason="敏感词初检通过,跳过意图审核")

    @classmethod
    def from_error(cls, reason: str = "意图审核调用失败") -> "IntentAuditResult":
        return cls(verdict="suspect", risk_type="未知", confidence=0.0, reason=reason)


class IntentAuditor:
    """意图审核器,使用小模型对用户输入做语义安全判断。"""

    def __init__(self, *, config: AgentConfig, task_scheduler: LLMTaskScheduler | None = None) -> None:
        self.config = config
        self._task_scheduler = task_scheduler

    def audit(self, user_input: str, *, llm_config: dict[str, Any] | None = None) -> IntentAuditResult:
        """对用户输入执行意图安全审核。"""

        if not self._should_run_intent_audit():
            return IntentAuditResult.default_pass()

        if self._is_low_risk_input(user_input):
            return IntentAuditResult.default_pass()

        if self._is_file_operation_request(user_input):
            return IntentAuditResult.default_pass()

        scheduler = self._task_scheduler or get_llm_task_scheduler(self.config)
        system_prompt = self.config.prompts.safety_intent_audit_system_prompt.format(
            max_reason_chars=self.config.limits.safety_error_reason_chars
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]
        api_key, base_url, small_api_key, small_base_url = resolve_llm_overrides_from_config(llm_config)
        context_window_tokens, max_output_tokens = capacity_overrides_from_mapping(
            llm_config,
            model_tier=SMALL_MODEL_TIER,
        )
        try:
            response = scheduler.invoke_chat(
                task_type=FOREGROUND_AGENT_TASK,
                messages=messages,
                temperature=0.0,
                model_tier=SMALL_MODEL_TIER,
                timeout_seconds=self.config.limits.safety_intent_timeout_seconds,
                api_key=api_key,
                base_url=base_url,
                small_api_key=small_api_key,
                small_base_url=small_base_url,
                context_window_tokens=context_window_tokens,
                max_output_tokens=max_output_tokens,
            )
            parsed = self._parse_response(str(response.content))
            return parsed
        except Exception as exc:
            return IntentAuditResult.from_error(
                reason=str(exc)[:self.config.limits.safety_error_reason_chars]
            )

    @staticmethod
    def _parse_response(raw: str) -> IntentAuditResult:
        """解析小模型返回的 JSON 审核结果。"""

        try:
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return IntentAuditResult(
                verdict=data.get("verdict", "suspect"),
                risk_type=data.get("risk_type", "未知"),
                confidence=float(data.get("confidence", 0.0)),
                reason=str(data.get("reason", "")),
            )
        except (json.JSONDecodeError, ValueError):
            if "block" in raw.lower():
                return IntentAuditResult(verdict="block", risk_type="未知", confidence=0.8, reason="非标准输出,疑似风险")
            if "pass" in raw.lower():
                return IntentAuditResult(verdict="pass", risk_type="正常请求", confidence=0.5, reason="非标准输出,倾向安全")
            return IntentAuditResult(verdict="suspect", risk_type="未知", confidence=0.0, reason="无法解析审核结果")

    @staticmethod
    def _is_low_risk_input(user_input: str) -> bool:
        """
        启发式判断输入是否为低风险内容,跳过大模型意图审核。

        规则: 短文本(≤15字)且不含高危关键词(政治/暴力/色情/越狱/注入等),直接放行。
        """
        text = user_input.strip()
        if len(text) > DEFAULT_BUSINESS_LIMITS.safety_low_risk_input_max_chars:
            return False
        high_risk_keywords = (
            "习近平", "共产党", "政府", "台湾", "西藏", "新疆",
            "法轮功", "六四", "天安门", "民主", "自由",
            "暴力", "杀人", "炸弹", "毒品", "色情",
            "jailbreak", "ignore", "bypass", "system prompt",
            "越狱", "注入", "绕过", "忽略指令",
        )
        text_lower = text.lower()
        return not any(kw.lower() in text_lower for kw in high_risk_keywords)

    @staticmethod
    def _is_file_operation_request(user_input: str) -> bool:
        """检测是否为纯文件操作请求,跳过 LLM 意图审核减少误判。"""

        text = user_input.strip()
        file_op_patterns = [
            "创建文件", "新建文件", "创建文件夹", "新建文件夹", "建立文件",
            "删除文件", "删掉文件", "删掉.*\\.txt", "删掉.*\\.md",
            "重命名", "改名为",
            "读取文件", "读.*文件", "阅读.*文件", "查看.*文件",
            "列出文件", "文件列表",
            "写.*文件", "写入.*文件", "保存文件",
            "知识库.*创建", "知识库.*删除",
        ]
        for pattern in file_op_patterns:
            if re.search(pattern, text):
                return True
        # 纯文件路径/扩展名指令: 包含 .txt .md .py 等扩展名,且无非安全关键词
        if re.search(r'\.(txt|md|py|js|ts|json|yaml|yml|css|html)', text):
            return True
        return False

    def _should_run_intent_audit(self) -> bool:
        """判断是否需要执行意图审核(小模型已配置则执行)。"""

        return bool(self.config.model.small_model_name or self.config.model.model_name)


def resolve_llm_overrides_from_config(
    llm_config: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """从用户 LLM 配置解析运行时覆盖项,small 配置缺省时回退到主模型配置。"""

    if not llm_config:
        return None, None, None, None
    api_key = _normalize_optional_str(llm_config.get("api_key"))
    base_url = _normalize_optional_str(llm_config.get("base_url"))
    small_api_key = _normalize_optional_str(llm_config.get("small_api_key")) or api_key
    small_base_url = _normalize_optional_str(llm_config.get("small_base_url")) or base_url
    return api_key, base_url, small_api_key, small_base_url


def _normalize_optional_str(value: Any) -> str | None:
    """把空字符串配置归一为 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None

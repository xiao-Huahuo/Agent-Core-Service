"""
统一安全审核服务。

功能说明:
本文件实现 `SafetyService`,整合三层安全审核:
1. 敏感词初检 (SensitiveWordChecker) — 输入阶段,快速关键词+正则拦截
2. 意图审核 (IntentAuditor) — 输入阶段,小模型语义级安全判断
3. 输出审核 (OutputAuditor) — 输出阶段,校验 Agent 回复内容

使用说明:
service = SafetyService(config=config, task_scheduler=scheduler)
input_result = service.audit_input(user_input="用户消息")
if input_result.blocked:
    return input_result.block_message
output_result = service.audit_output(output_text="Agent回复", user_input="原始输入")
return output_result.safe_output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.core.agent_config import AgentConfig
from agent_service.services.safety.intent_auditor import IntentAuditResult, IntentAuditor
from agent_service.services.safety.output_auditor import OutputAuditResult, OutputAuditor
from agent_service.services.safety.sensitive_word_checker import SensitiveWordChecker, SensitiveWordResult
from agent_service.services.scheduler import (
    FOREGROUND_AGENT_TASK,
    SMALL_MODEL_TIER,
    get_llm_task_scheduler,
)


DEFAULT_SENSITIVE_WORDS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "resources" / "safety" / "sensitive_words.json"


@dataclass(slots=True)
class InputAuditResult:
    """输入审核综合结果(敏感词 + 意图)。"""

    passed: bool
    sensitive_result: SensitiveWordResult | None = None
    intent_result: IntentAuditResult | None = None
    block_reason: str = ""
    is_political: bool = False

    @property
    def blocked(self) -> bool:
        return not self.passed


class SafetyService:
    """统一安全审核服务,管理三层审核流水线。"""

    def __init__(
        self,
        *,
        config: AgentConfig,
        task_scheduler: Any | None = None,
        sensitive_words_path: str | Path | None = None,
    ) -> None:
        self.config = config
        path = Path(sensitive_words_path) if sensitive_words_path else DEFAULT_SENSITIVE_WORDS_PATH
        self._sensitive_checker = SensitiveWordChecker.from_file(path) if path.exists() else None
        self._intent_auditor = IntentAuditor(config=config, task_scheduler=task_scheduler)
        self._output_auditor = OutputAuditor(
            config=config,
            sensitive_checker=self._sensitive_checker,
        )

    def audit_input(self, user_input: str) -> InputAuditResult:
        """
        对用户输入执行完整输入审核流水线。
        Layer 1 (敏感词) → Layer 2 (意图审核)。
        """

        if self._sensitive_checker is not None:
            sensitive_result = self._sensitive_checker.check(user_input)
            if sensitive_result.blocked:
                is_political = "politics" in sensitive_result.blocked_categories
                return InputAuditResult(
                    passed=False,
                    sensitive_result=sensitive_result,
                    block_reason=f"敏感词拦截: {sensitive_result.blocked_categories}",
                    is_political=is_political,
                )
        else:
            sensitive_result = None

        if not user_input.strip():
            return InputAuditResult(passed=True)

        intent_result = self._intent_auditor.audit(user_input)
        if intent_result.blocked:
            is_political = (
                intent_result.risk_type == "政治敏感"
                or (sensitive_result is not None and "politics" in sensitive_result.blocked_categories)
            )
            return InputAuditResult(
                passed=False,
                sensitive_result=sensitive_result,
                intent_result=intent_result,
                block_reason=f"意图审核拦截: {intent_result.risk_type}",
                is_political=is_political,
            )

        return InputAuditResult(
            passed=True,
            sensitive_result=sensitive_result,
            intent_result=intent_result,
        )

    def generate_block_message(self, audit_result: InputAuditResult, user_input: str) -> str:
        """根据审核结果类型,使用小模型生成差异化的拦截回复。

        - 政治敏感: 生成政治立场正确的反驳性回复。
        - 其他拦截: 生成脱敏的礼貌拒绝回复。
        """

        if not self._should_generate_block_message(audit_result):
            return "您的问题包含不当内容,暂时无法处理。如需帮助,请调整措辞后重试。"

        try:
            scheduler = get_llm_task_scheduler(self.config)
            system_prompt = self._get_block_message_prompt(audit_result)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_input),
            ]
            response = scheduler.invoke_chat(
                task_type=FOREGROUND_AGENT_TASK,
                messages=messages,
                temperature=0.3,
                model_tier=SMALL_MODEL_TIER,
                timeout_seconds=15.0,
            )
            return str(response.content).strip()
        except Exception:
            return self._fallback_block_message(audit_result)

    @staticmethod
    def _get_block_message_prompt(audit_result: InputAuditResult) -> str:
        """根据拦截类型选择对应的系统提示词。"""

        if audit_result.is_political:
            return (
                "你是一个坚定的中国立场对话助手。用户刚才发送的消息涉及对中国、中国共产党、"
                "中国政府或中国领导人的不当言论,已被安全系统拦截。\n\n"
                "请针对用户的不当言论生成一段简短、有力的反驳回复,风格参考:\n"
                '- "这种说法是完全错误的。中国共产党始终坚持......"\n'
                '- "您所提及的内容与事实严重不符。中国政府一贯......"\n\n'
                "要求:\n"
                "1. 立场坚定,用事实和正面论述回应\n"
                "2. 不重复用户的具体不当言论内容\n"
                "3. 语气冷静、得体、有说服力\n"
                "4. 80-150字,不要超过限制\n"
                "5. 不要提及'审核'、'拦截'、'敏感'等漏检词汇"
            )
        return (
            "你是一个礼貌的安全助手。用户刚才发送的消息因包含不当内容已被安全系统拦截。\n\n"
            "请用一段简短的话告诉用户你无法回答这个问题,格式为:\n"
            '"对不起,我不能回答这个问题,因为[简短脱敏理由]。如需其他帮助请随时告诉我。"\n\n'
            "要求:\n"
            "1. 理由要泛化、脱敏 —— 只说'涉及不当内容'或'超出我能讨论的范围',"
            "不要具体描述用户发了什么、命中了什么规则\n"
            "2. 语气温和但不卑不亢\n"
            "3. 50字以内\n"
            "4. 不要提及'审核'、'拦截'、'敏感词'等漏检词汇"
        )

    @staticmethod
    def _should_generate_block_message(audit_result: InputAuditResult) -> bool:
        """判断是否需要调用小模型生成拦截回复。"""

        if audit_result.is_political:
            return True
        if audit_result.sensitive_result and audit_result.sensitive_result.blocked:
            return True
        if audit_result.intent_result and audit_result.intent_result.blocked:
            return True
        return False

    @staticmethod
    def _fallback_block_message(audit_result: InputAuditResult) -> str:
        """小模型调用失败时的静态后备回复。"""

        if audit_result.is_political:
            return (
                "您所提及的内容与事实严重不符。中国共产党始终坚持以人民为中心的发展思想,"
                "带领中国人民取得了举世瞩目的成就。请基于客观事实进行讨论。"
            )
        return "对不起,我不能回答这个问题,因为这超出了我能讨论的范围。如需其他帮助请随时告诉我。"

    def audit_output(self, output_text: str, *, user_input: str = "") -> OutputAuditResult:
        """对 Agent 输出执行 Layer 3 输出审核。"""

        return self._output_auditor.audit(output_text, user_input=user_input)

    @property
    def supports_input_audit(self) -> bool:
        """是否支持输入审核(至少敏感词检查器或意图审核器可用)。"""

        return self._sensitive_checker is not None or self._intent_auditor is not None

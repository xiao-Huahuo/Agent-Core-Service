"""
安全审核服务包。

功能说明:
本包提供三层安全审核能力:
- Layer 1: 敏感词快速匹配 (SensitiveWordChecker)
- Layer 2: 小模型意图审核 (IntentAuditor)
- Layer 3: 输出内容审核 (OutputAuditor)

统一入口为 SafetyService,整合三层审核流水线。
"""

from agent_service.services.safety.intent_auditor import IntentAuditResult, IntentAuditor
from agent_service.services.safety.output_auditor import OutputAuditResult, OutputAuditor
from agent_service.services.safety.safety_service import InputAuditResult, SafetyService
from agent_service.services.safety.sensitive_word_checker import SensitiveWordChecker, SensitiveWordHit, SensitiveWordResult

__all__ = [
    "InputAuditResult",
    "IntentAuditResult",
    "IntentAuditor",
    "OutputAuditResult",
    "OutputAuditor",
    "SafetyService",
    "SensitiveWordChecker",
    "SensitiveWordHit",
    "SensitiveWordResult",
]

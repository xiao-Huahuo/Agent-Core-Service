"""模型能力解析与动态上下文预算。

本模块只负责把模型能力、服务 ceiling 和集中比例转换为不可变预算对象。
具体消息选择仍由 ``ContextBuilder`` 负责，避免节点和工具各自复制预算公式。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

from agent_service.core.agent_config import AgentConfig


def capacity_overrides_from_mapping(
    values: dict[str, Any] | None,
    *,
    model_tier: str,
) -> tuple[int | None, int | None]:
    """从用户或服务模型配置中读取当前层级的正整数容量覆盖。"""

    source = values or {}

    def positive_int(value: Any) -> int | None:
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    prefix = "small_model" if model_tier == "small" else "model"
    context_tokens = positive_int(source.get(f"{prefix}_context_window_tokens"))
    output_tokens = positive_int(source.get(f"{prefix}_max_output_tokens"))
    if model_tier == "small" and not str(source.get("small_model_name") or "").strip():
        context_tokens = context_tokens or positive_int(source.get("model_context_window_tokens"))
        output_tokens = output_tokens or positive_int(source.get("model_max_output_tokens"))
    return context_tokens, output_tokens


@dataclass(frozen=True, slots=True)
class ModelCapacity:
    """一次真实模型调用可使用的上下文与输出能力。"""

    model_name: str
    context_window_tokens: int
    max_output_tokens: int
    source: str

    @classmethod
    def resolve(
        cls,
        *,
        config: AgentConfig,
        model_name: str,
        model_tier: str,
        context_window_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> "ModelCapacity":
        """按请求覆盖、模型表、服务配置、服务 ceiling 默认值的顺序解析能力。"""

        requested_context = int(context_window_tokens or 0)
        requested_output = int(max_output_tokens or 0)
        if requested_context > 0 or requested_output > 0:
            return cls(
                model_name=model_name,
                context_window_tokens=requested_context or config.memory.context_window_tokens,
                max_output_tokens=requested_output or config.memory.context_unknown_output_fallback_tokens,
                source="request_override",
            )

        profile = config.model.model_capabilities.get(model_name.strip().casefold())
        if profile is None:
            profile = config.model.model_capabilities.get(model_name.strip())
        if isinstance(profile, dict):
            profile_context = int(profile.get("context_window_tokens") or 0)
            profile_output = int(profile.get("max_output_tokens") or 0)
            if profile_context > 0 or profile_output > 0:
                return cls(
                    model_name,
                    profile_context or config.memory.context_window_tokens,
                    profile_output or config.memory.context_unknown_output_fallback_tokens,
                    "model_profile",
                )

        if model_tier == "small":
            configured_context = config.model.small_model_context_window_tokens
            configured_output = config.model.small_model_max_output_tokens
        else:
            configured_context = config.model.model_context_window_tokens
            configured_output = config.model.model_max_output_tokens
        if configured_context > 0 or configured_output > 0:
            return cls(
                model_name,
                configured_context or config.memory.context_window_tokens,
                configured_output or config.memory.context_unknown_output_fallback_tokens,
                "service_config",
            )

        return cls(
            model_name=model_name,
            context_window_tokens=config.memory.context_window_tokens,
            max_output_tokens=config.memory.context_unknown_output_fallback_tokens,
            source="service_ceiling_default",
        )


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """由有效模型窗口推导出的单次请求 token 预算。"""

    model_name: str
    capacity_source: str
    service_ceiling_tokens: int
    model_window_tokens: int
    effective_window_tokens: int
    output_reserve_tokens: int
    safety_margin_tokens: int
    input_budget_tokens: int
    compression_trigger_tokens: int
    compression_target_tokens: int
    max_single_block_tokens: int
    policy_version: str

    @classmethod
    def from_config(
        cls,
        *,
        config: AgentConfig,
        capacity: ModelCapacity,
        request_context_tokens: int | None = None,
        requested_output_tokens: int | None = None,
    ) -> "ContextBudget":
        """使用设计文档中的统一公式构造请求预算。"""

        service_ceiling = max(int(config.memory.context_window_tokens), 1)
        request_ceiling = int(request_context_tokens or 0)
        effective_window = min(
            service_ceiling,
            max(int(capacity.context_window_tokens), 1),
            request_ceiling if request_ceiling > 0 else service_ceiling,
        )
        default_output = ceil(effective_window * config.memory.context_output_reserve_ratio)
        output_target = int(requested_output_tokens or 0) or default_output
        output_reserve = min(
            max(int(capacity.max_output_tokens), 1),
            max(output_target, 1),
            max(effective_window - 1, 1),
        )
        safety_margin = min(
            ceil(effective_window * config.memory.context_safety_margin_ratio),
            max(effective_window - output_reserve - 1, 0),
        )
        input_budget = max(effective_window - output_reserve - safety_margin, 1)
        trigger = max(1, round(input_budget * config.memory.context_compression_trigger_ratio))
        target = max(
            1,
            min(
                trigger - 1 if trigger > 1 else 1,
                round(input_budget * config.memory.context_compression_target_ratio),
            ),
        )
        max_single_block = max(
            1,
            min(input_budget, round(input_budget * config.memory.context_max_single_block_ratio)),
        )
        return cls(
            model_name=capacity.model_name,
            capacity_source=capacity.source,
            service_ceiling_tokens=service_ceiling,
            model_window_tokens=capacity.context_window_tokens,
            effective_window_tokens=effective_window,
            output_reserve_tokens=output_reserve,
            safety_margin_tokens=safety_margin,
            input_budget_tokens=input_budget,
            compression_trigger_tokens=trigger,
            compression_target_tokens=target,
            max_single_block_tokens=max_single_block,
            policy_version=config.memory.context_budget_policy_version,
        )

    def to_dict(self) -> dict[str, Any]:
        """返回可安全写入 Debug 快照的预算账本。"""

        return {
            "model_name": self.model_name,
            "capacity_source": self.capacity_source,
            "service_ceiling_tokens": self.service_ceiling_tokens,
            "model_window_tokens": self.model_window_tokens,
            "effective_window_tokens": self.effective_window_tokens,
            "output_reserve_tokens": self.output_reserve_tokens,
            "safety_margin_tokens": self.safety_margin_tokens,
            "input_budget_tokens": self.input_budget_tokens,
            "compression_trigger_tokens": self.compression_trigger_tokens,
            "compression_target_tokens": self.compression_target_tokens,
            "max_single_block_tokens": self.max_single_block_tokens,
            "policy_version": self.policy_version,
        }

"""用户定制 Skill 生命周期测试。

使用说明:
验证 Agent 工具复用的创建、读取、更新、验证、路由测试和删除全部作用于当前
active 知识库的 ``.agents/skills`` 目录。
"""

from __future__ import annotations

from pathlib import Path

from agent_service.core.agent_config import AgentConfig
from agent_service.services.skill_service import SkillService


class _SettingsStub:
    """为 SkillService 提供隔离的 active 知识库。"""

    def __init__(self, root: Path) -> None:
        """保存临时知识库根目录。"""

        self.root = root

    def get_active_knowledge_library(self, *, user_id: str) -> dict[str, str]:
        """返回当前用户的临时知识库。"""

        return {"library_id": "library-1", "knowledge_dir": str(self.root)}

    def ensure_user_profile(self, user_id: str) -> dict[str, str]:
        """提供服务 fallback 所需的最小用户资料。"""

        return {"user_id": user_id, "knowledge_dir": str(self.root)}


def test_user_skill_full_lifecycle(tmp_path: Path) -> None:
    """用户 Skill 必须可以创建、更新、验证、测试匹配并安全删除。"""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    service = SkillService(config=config, settings_service=_SettingsStub(tmp_path))

    created = service.create_user_skill(
        user_id="u1",
        name="文献总结",
        description="总结论文和研究文献",
        body="读取论文后输出研究问题、方法和结论。",
    )
    skill_id = str(created["skill_id"])
    updated = service.update_user_skill(
        user_id="u1",
        skill_id=skill_id,
        description="总结论文、研究文献和实验结果",
        body="读取论文后输出问题、方法、结果和局限。",
    )
    validation = service.validate_user_skill(user_id="u1", skill_id=skill_id)
    tested = service.test_user_skill(user_id="u1", skill_id=skill_id, prompt="请总结这篇研究论文的实验结果")
    deleted = service.delete_user_skill(user_id="u1", skill_id=skill_id)

    assert "实验结果" in updated["description"]
    assert validation["valid"] is True
    assert tested["matched"] is True
    assert tested["score"] > 0
    assert deleted == {"skill_id": skill_id, "deleted": True}
    assert service.read_skill_body(user_id="u1", skill_ref=skill_id) is None

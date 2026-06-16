"""
Skill Registry
==============
Singleton registry that loads and exposes all skills.
"""

from __future__ import annotations

from typing import Optional

_registry: Optional["SkillRegistry"] = None


class SkillRegistry:
    def __init__(self):
        self._skills: dict = {}

    def register(self, skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str):
        return self._skills.get(name)

    def all_names(self) -> list[str]:
        return list(self._skills.keys())

    def all(self) -> list:
        return list(self._skills.values())

    def descriptions(self) -> dict[str, str]:
        return {n: s.description for n, s in self._skills.items()}


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def _build_registry() -> SkillRegistry:
    registry = SkillRegistry()

    _try_register(registry, "skills.market_strategy.skill", "MarketStrategySkill")
    _try_register(registry, "skills.product_solution.skill", "ProductSolutionSkill")
    _try_register(registry, "skills.compliance.skill", "ComplianceSkill")
    _try_register(registry, "skills.client_simulator.skill", "ClientSimulatorSkill")
    _try_register(registry, "skills.design.skill", "DesignSkill")

    print(f"[SkillRegistry] Loaded: {registry.all_names()}")
    return registry


def _try_register(registry: SkillRegistry, module_path: str, class_name: str) -> None:
    try:
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        registry.register(cls())
    except Exception as e:
        print(f"Warning: Could not load {class_name} from {module_path}: {e}")

"""Agente coreógrafo: decisão via LLM (Groq) ou stub."""

from __future__ import annotations

from dataclasses import dataclass

from environment import Environment
from llm_client import choreographer_json


@dataclass
class ChoreographerDecision:
    formation: str
    center_row: int
    center_col: int
    scale: int
    note: str
    source: str
    stub_reason: str | None = None


class ChoreographerAgent:
    """Traduz percepção textual em intenção de formação (arquitetura deliberativa + LLM)."""

    def decide(self, env: Environment) -> ChoreographerDecision:
        perception = env.perception_summary()
        obj, source, stub_reason = choreographer_json(perception, env.beat)

        formation = str(obj.get("formation", "line"))
        try:
            cr = int(obj.get("center_row", env.formation_center[0]))
            cc = int(obj.get("center_col", env.formation_center[1]))
            sc = int(obj.get("scale", env.formation_scale))
        except (TypeError, ValueError):
            cr, cc, sc = env.formation_center[0], env.formation_center[1], env.formation_scale

        note = str(obj.get("note", "")).strip()
        return ChoreographerDecision(
            formation=formation,
            center_row=cr,
            center_col=cc,
            scale=max(1, min(3, sc)),
            note=note,
            source=source,
            stub_reason=stub_reason,
        )

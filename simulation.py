"""Um passo da simulação: planejamento (sem mover) e aplicação do movimento."""

from __future__ import annotations

from agents.choreographer import ChoreographerAgent, ChoreographerDecision
from agents.pilot import ModelBasedPilotAgent, align_targets_to_drones
from environment import Environment


def plan_step(
    env: Environment,
    choreographer: ChoreographerAgent,
    pilot: ModelBasedPilotAgent,
    stuck_replan_after_beats: int = 0,
) -> tuple[ChoreographerDecision | None, list[tuple[int, int]], list[str]]:
    """
    O coreógrafo só redefine a formação:
    - na primeira vez (choreography_pending), ou
    - na transição em que todos passam a estar nos alvos (antes não estavam, agora estão), ou
    - opcionalmente, se passaram N beats sem completar a formação (desbloqueio).

    `prev_step_formation_matched` guarda se, ao fim do plan_step anterior, os drones já batiam os alvos;
    a nova coreografia dispara na transição “antes não / agora sim”, não a cada beat parado na formação.
    """
    decision: ChoreographerDecision | None = None
    matched_start = env.formation_achieved()
    newly_completed = matched_start and not env.prev_step_formation_matched

    beats_since = env.beat - env.last_choreography_beat
    stuck = (
        stuck_replan_after_beats > 0
        and not env.choreography_pending
        and not matched_start
        and env.last_choreography_beat >= 0
        and beats_since >= stuck_replan_after_beats
    )
    need_choreo = env.choreography_pending or newly_completed or stuck

    if need_choreo:
        decision = choreographer.decide(env)
        env.set_formation(
            decision.formation,
            decision.center_row,
            decision.center_col,
            decision.scale,
        )
        env.choreography_pending = False
        env.last_choreography_beat = env.beat

    targets_raw = env.targets_for_formation()
    targets = align_targets_to_drones(list(env.drone_positions), targets_raw)
    moves = pilot.plan_moves(env, targets_raw)
    # Após nova coreografia, não marcar "já formado" neste mesmo passo (evita travar o próximo gatilho).
    if decision is not None:
        env.prev_step_formation_matched = False
    else:
        env.prev_step_formation_matched = env.formation_achieved()
    return decision, targets, moves


def apply_planned_moves(env: Environment, moves: list[str]) -> None:
    env.apply_moves(moves)

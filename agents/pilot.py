"""Piloto baseado em modelo: mapa interno + BFS para próximo passo."""

from __future__ import annotations

from collections import deque

from environment import COLS, DELTAS, ROWS, Environment, manhattan


def align_targets_to_drones(
    drone_positions: list[tuple[int, int]],
    targets: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """
    Cada drone recebe um alvo distinto por proximidade (greedy em ordem de índice),
    para reduzir permutações estáveis (vários HOLD) quando o slot i não bate com o alvo i.
    """
    n = min(len(drone_positions), len(targets))
    if n == 0:
        return []
    remaining = list(targets[:n])
    aligned: list[tuple[int, int]] = []
    for i in range(n):
        pos = drone_positions[i]
        best = min(remaining, key=lambda t: manhattan(pos, t))
        remaining.remove(best)
        aligned.append(best)
    return aligned


def _bfs_first_step(
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked: set[tuple[int, int]],
) -> str:
    """Retorna um movimento em N,S,E,W,HOLD aproximando start -> goal."""
    if start == goal:
        return "HOLD"
    if goal in blocked:
        # meta ocupada: aproxima ao vizinho livre mais próximo da meta
        best: tuple[int, int] | None = None
        best_d = 10**9
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = goal[0] + dr, goal[1] + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in blocked:
                d = manhattan(start, (nr, nc))
                if d < best_d:
                    best_d = d
                    best = (nr, nc)
        if best is None:
            return "HOLD"
        goal = best

    q: deque[tuple[int, int]] = deque([start])
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            break
        for name, (dr, dc) in DELTAS.items():
            if name == "HOLD":
                continue
            nr, nc = r + dr, c + dc
            if not (0 <= nr < ROWS and 0 <= nc < COLS):
                continue
            if (nr, nc) in blocked:
                continue
            if (nr, nc) not in parent:
                parent[(nr, nc)] = (r, c)
                q.append((nr, nc))

    if goal not in parent:
        return "HOLD"

    cur = goal
    while parent[cur] is not None and parent[cur] != start:
        cur = parent[cur]  # type: ignore[assignment]
    if parent[cur] != start:
        return "HOLD"
    dr = cur[0] - start[0]
    dc = cur[1] - start[1]
    for name, (ddr, ddc) in DELTAS.items():
        if name != "HOLD" and (ddr, ddc) == (dr, dc):
            return name
    return "HOLD"


class ModelBasedPilotAgent:
    """
    Agente com modelo do mundo (grade, obstáculos, posições alvo).
    Planeja movimento greedy por drone com BFS e evita colisões com ordem fixa.
    """

    def plan_moves(self, env: Environment, targets: list[tuple[int, int]]) -> list[str]:
        moves: list[str] = []
        obstacles = env.blocked_static()
        current = list(env.drone_positions)
        planned_next: set[tuple[int, int]] = set()
        aligned = align_targets_to_drones(current, targets)

        for i, pos in enumerate(current):
            tgt = aligned[i] if i < len(aligned) else pos
            blocked = obstacles | planned_next | set(current[:i]) | set(current[i + 1 :])
            # permite ficar na própria célula
            blocked.discard(pos)
            step = _bfs_first_step(pos, tgt, blocked)
            dr, dc = DELTAS[step]
            nr, nc = pos[0] + dr, pos[1] + dc
            planned_next.add((nr, nc))
            moves.append(step)
        return moves

"""Ambiente da simulação: grade, obstáculos, drones e formações."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

ROWS = 10
COLS = 14
NUM_DRONES = 4

# Movimentos: delta (row, col)
DELTAS = {"N": (-1, 0), "S": (1, 0), "W": (0, -1), "E": (0, 1), "HOLD": (0, 0)}

FORMATION_OFFSETS: dict[str, list[tuple[int, int]]] = {
    "line": [(0, 0), (0, 1), (0, 2), (0, 3)],
    "v": [(0, 0), (1, -1), (1, 1), (2, -2)],
    "diamond": [(0, 1), (1, 0), (1, 2), (2, 1)],
    "circle": [(0, 0), (0, 2), (2, 0), (2, 2)],
    "scatter": [(0, 0), (0, 3), (3, 0), (3, 3)],
}


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _cells_in_bounds(cells: list[tuple[int, int]]) -> bool:
    return all(0 <= r < ROWS and 0 <= c < COLS for r, c in cells)


@dataclass
class Environment:
    beat: int = 0
    obstacles: set[tuple[int, int]] = field(default_factory=set)
    drone_positions: list[tuple[int, int]] = field(default_factory=list)
    formation_name: str = "line"
    formation_center: tuple[int, int] = (ROWS // 2, COLS // 2)
    formation_scale: int = 1
    last_choreographer_note: str = ""
    # Coreógrafo: primeira vez obrigatória; depois só quando todos chegarem aos alvos atuais
    choreography_pending: bool = True
    last_choreography_beat: int = -1
    # Fim do plan_step anterior: drones já batiam os alvos da formação (para detectar "acabaram de chegar")
    prev_step_formation_matched: bool = False

    def __post_init__(self) -> None:
        if not self.obstacles:
            self._default_obstacles()
        if not self.drone_positions:
            self._default_spawns()

    def _default_obstacles(self) -> None:
        # Mapa mais denso: vários blocos e um corredor estreito; spawns na linha 1 permanecem livres.
        self.obstacles = {
            # Bloco central (original + extensão)
            (2, 5),
            (2, 6),
            (3, 5),
            (3, 6),
            (2, 8),
            (3, 8),
            # Parede vertical à esquerda do centro
            (4, 2),
            (5, 2),
            (6, 2),
            # Cluster meio-direita
            (4, 9),
            (4, 10),
            (5, 10),
            # Faixa média esquerda
            (6, 3),
            (6, 4),
            # Canto inferior direito (maior)
            (7, 10),
            (7, 11),
            (8, 10),
            (8, 11),
            # Barreira em baixo ao centro
            (8, 5),
            (8, 6),
            (9, 5),
            # Topo e extremo direito (força rotas longas)
            (0, 9),
            (0, 10),
            (1, 12),
            (5, 12),
            (6, 12),
        }

    def _default_spawns(self) -> None:
        self.drone_positions = [(1, 1), (1, 3), (1, 5), (1, 7)]

    def set_formation(self, name: str, center_row: int, center_col: int, scale: int) -> None:
        key = name.lower().strip() if name else "line"
        if key not in FORMATION_OFFSETS:
            key = "line"
        self.formation_name = key
        cr = _clamp(center_row, 0, ROWS - 1)
        cc = _clamp(center_col, 0, COLS - 1)
        self.formation_center = (cr, cc)
        self.formation_scale = _clamp(scale, 1, 3)

    def _nearest_assignable_target(
        self,
        ideal: tuple[int, int],
        taken: set[tuple[int, int]],
    ) -> tuple[int, int]:
        """
        Célula livre mais próxima (BFS na grade) ao ponto ideal, fora de obstáculos
        e não usada por outro alvo já atribuído.
        """
        ir = _clamp(ideal[0], 0, ROWS - 1)
        ic = _clamp(ideal[1], 0, COLS - 1)
        obs = self.obstacles
        q: deque[tuple[int, int]] = deque([(ir, ic)])
        seen: set[tuple[int, int]] = {(ir, ic)}
        while q:
            r, c = q.popleft()
            if (r, c) not in obs and (r, c) not in taken:
                return (r, c)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < ROWS and 0 <= nc < COLS):
                    continue
                if (nr, nc) in seen:
                    continue
                if (nr, nc) in obs:
                    continue
                seen.add((nr, nc))
                q.append((nr, nc))
        for r in range(ROWS):
            for c in range(COLS):
                if (r, c) not in obs and (r, c) not in taken:
                    return (r, c)
        return (ir, ic)

    def targets_for_formation(self) -> list[tuple[int, int]]:
        offsets = FORMATION_OFFSETS[self.formation_name]
        s = self.formation_scale
        cr, cc = self.formation_center
        raw = [(cr + dr * s, cc + dc * s) for (dr, dc) in offsets]
        # Ajusta para caber na grade (empurra centro se necessário)
        for _ in range(8):
            if _cells_in_bounds(raw):
                break
            cr = _clamp(cr, 1, ROWS - 2)
            cc = _clamp(cc, 1, COLS - 2)
            self.formation_center = (cr, cc)
            raw = [(cr + dr * s, cc + dc * s) for (dr, dc) in offsets]
        # Dentro da grade; depois desloca alvos que cairiam em obstáculo (ou conflito)
        clamped = [(_clamp(r, 0, ROWS - 1), _clamp(c, 0, COLS - 1)) for r, c in raw]
        taken: set[tuple[int, int]] = set()
        resolved: list[tuple[int, int]] = []
        for cell in clamped:
            t = self._nearest_assignable_target(cell, taken)
            taken.add(t)
            resolved.append(t)
        return resolved

    def drones_match_formation_targets(self) -> bool:
        """Cada drone i está na célula-alvo i da formação atual (após resolução de obstáculos)."""
        targets = self.targets_for_formation()
        if len(self.drone_positions) < len(targets):
            return False
        for i in range(len(targets)):
            if self.drone_positions[i] != targets[i]:
                return False
        return True

    def formation_achieved(self) -> bool:
        """
        True se o conjunto de células dos drones coincide com o conjunto de alvos da formação.
        Usa multiconjunto (sorted) para não travar quando os drones permutam slots equivalentes.
        """
        targets = self.targets_for_formation()
        n = len(targets)
        if len(self.drone_positions) < n:
            return False
        pos = [self.drone_positions[i] for i in range(n)]
        return sorted(pos) == sorted(targets)

    def blocked_static(self) -> set[tuple[int, int]]:
        return set(self.obstacles)

    def perception_summary(self) -> str:
        """Texto para o coreógrafo (LLM ou stub)."""
        lines = [
            f"Compasso (beat): {self.beat}",
            f"Grade: {ROWS} linhas x {COLS} colunas (0..{ROWS - 1}, 0..{COLS - 1}).",
            f"Obstáculos (#): {sorted(self.obstacles)}",
        ]
        for i, (r, c) in enumerate(self.drone_positions):
            lines.append(f"Drone {i + 1} em (row={r}, col={c}).")
        lines.append(
            f"Formação atual desejada: {self.formation_name}, "
            f"centro=({self.formation_center[0]},{self.formation_center[1]}), "
            f"escala={self.formation_scale}."
        )
        return "\n".join(lines)

    def apply_moves(self, moves: list[str]) -> None:
        """Aplica uma jogada por drone; ordem do índice resolve empates."""
        blocked = self.blocked_static()
        next_pos: list[tuple[int, int] | None] = [None] * len(self.drone_positions)
        used: set[tuple[int, int]] = set()

        for i, m in enumerate(moves):
            if i >= len(self.drone_positions):
                break
            d = DELTAS.get(m.upper(), (0, 0))
            r, c = self.drone_positions[i]
            nr, nc = r + d[0], c + d[1]
            if not (0 <= nr < ROWS and 0 <= nc < COLS):
                nr, nc = r, c
            if (nr, nc) in blocked:
                nr, nc = r, c
            next_pos[i] = (nr, nc)

        # Resolve colisões drone-drone: quem tem índice menor mantém intenção
        for i in range(len(self.drone_positions)):
            if next_pos[i] is None:
                continue
            pos = next_pos[i]
            assert pos is not None
            for j in range(i):
                if next_pos[j] == pos:
                    next_pos[i] = self.drone_positions[i]
                    pos = next_pos[i]
                    assert pos is not None
                    break
            if pos in used:
                next_pos[i] = self.drone_positions[i]
                pos = next_pos[i]
                assert pos is not None
            used.add(pos)

        self.drone_positions = [p if p is not None else self.drone_positions[k] for k, p in enumerate(next_pos)]
        self.beat += 1

    def render_ascii(self) -> str:
        grid = [["." for _ in range(COLS)] for _ in range(ROWS)]
        for r, c in self.obstacles:
            grid[r][c] = "#"
        labels = ["1", "2", "3", "4"]
        for i, (r, c) in enumerate(self.drone_positions):
            ch = labels[i] if i < len(labels) else "D"
            if grid[r][c] == ".":
                grid[r][c] = ch
            else:
                grid[r][c] = "X"
        lines = ["".join(row) for row in grid]
        legend = "# obstáculo | 1-4 drones | . livre | X conflito"
        return "\n".join(lines) + f"\n{legend}"


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

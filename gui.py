"""
Visualização do show de drones (Tkinter — biblioteca padrão no Windows/macOS).
Linux: pode ser necessário instalar o pacote python3-tk do sistema.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.choreographer import ChoreographerAgent, ChoreographerDecision
from agents.pilot import ModelBasedPilotAgent
from environment import COLS, NUM_DRONES, ROWS, Environment
from simulation import apply_planned_moves, plan_step

# Paleta (show noturno)
BG = "#0f0f1a"
CELL_FREE = "#16213e"
OBSTACLE = "#3d3d5c"
GRID_LINE = "#252540"
TARGET_RING = "#f4d35e"
DRONE_COLORS = ("#e63946", "#457b9d", "#2a9d8f", "#f4a261")
LABEL_FG = "#eaeaea"
ACCENT = "#7b68ee"
ARM_COLOR = "#080812"
MOTOR_FILL = "#151528"


def draw_drone_icon(
    canvas: object,
    xm: int,
    ym: int,
    size: int,
    body_color: str,
    label: str,
    *,
    label_fg: str = LABEL_FG,
) -> list[int]:
    """
    Vista de cima: braços em cruz, 4 motores/hélices e casco central (sem arquivos de imagem).
    """
    import tkinter as tk

    ids: list[int] = []
    arm = max(7, int(size * 0.36))
    mrad = max(3, int(size * 0.12))
    hub = max(5, int(size * 0.17))
    arm_w = max(2, max(1, size // 12))

    ids.append(
        canvas.create_line(
            xm - arm,
            ym,
            xm + arm,
            ym,
            fill=ARM_COLOR,
            width=arm_w,
            capstyle=tk.ROUND,
        )
    )
    ids.append(
        canvas.create_line(
            xm,
            ym - arm,
            xm,
            ym + arm,
            fill=ARM_COLOR,
            width=arm_w,
            capstyle=tk.ROUND,
        )
    )

    for dx, dy in ((-arm, 0), (arm, 0), (0, -arm), (0, arm)):
        mx, my = xm + dx, ym + dy
        ids.append(
            canvas.create_oval(
                mx - mrad,
                my - mrad,
                mx + mrad,
                my + mrad,
                fill=MOTOR_FILL,
                outline=label_fg,
                width=1,
            )
        )
        pr = mrad + 2
        ids.append(canvas.create_line(mx - pr, my, mx + pr, my, fill=label_fg, width=1))
        ids.append(canvas.create_line(mx, my - pr, mx, my + pr, fill=label_fg, width=1))

    ids.append(
        canvas.create_oval(
            xm - hub,
            ym - hub,
            xm + hub,
            ym + hub,
            fill=body_color,
            outline=label_fg,
            width=2,
        )
    )
    fz = max(8, size // 4)
    ids.append(
        canvas.create_text(
            xm,
            ym,
            text=label,
            fill=label_fg,
            font=("Segoe UI", fz, "bold"),
        )
    )
    return ids


def run_visual(
    steps: int,
    stuck_replan_after_beats: int,
    cell: int,
    pause_ms: int,
    phase_ms: int,
) -> None:
    import tkinter as tk
    from tkinter import font as tkfont

    env = Environment()
    choreographer = ChoreographerAgent()
    pilot = ModelBasedPilotAgent()

    root = tk.Tk()
    root.title("Show de drones — orquestra em grade")
    root.configure(bg=BG)

    pad = 16
    cw = cell
    ch = cell
    canvas_w = pad * 2 + COLS * cw
    canvas_h = pad * 2 + ROWS * ch

    header = tk.Frame(root, bg=BG)
    header.pack(fill=tk.X, padx=12, pady=(10, 4))

    title_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
    sub_font = tkfont.Font(family="Segoe UI", size=10)
    tk.Label(
        header,
        text="Orquestra de drones",
        font=title_font,
        fg=LABEL_FG,
        bg=BG,
    ).pack(anchor=tk.W)
    status_var = tk.StringVar(value="Iniciando…")
    tk.Label(header, textvariable=status_var, font=sub_font, fg=ACCENT, bg=BG, wraplength=canvas_w - 24, justify=tk.LEFT).pack(
        anchor=tk.W, pady=(4, 0)
    )

    canvas = tk.Canvas(root, width=canvas_w, height=canvas_h, bg=BG, highlightthickness=0)
    canvas.pack(padx=10, pady=(0, 10))

    legend = tk.Frame(root, bg=BG)
    legend.pack(fill=tk.X, padx=12, pady=(0, 12))
    tk.Label(
        legend,
        text="■ obstáculo  ○ alvo da formação  ✈ vista de cima: quadricóptero (1–4)",
        font=sub_font,
        fg="#8888aa",
        bg=BG,
    ).pack(anchor=tk.W)

    rect_ids: list[int] = []
    target_ids: list[int] = []
    drone_ids: list[int] = []

    def cell_origin(r: int, c: int) -> tuple[int, int]:
        x0 = pad + c * cw
        y0 = pad + r * ch
        return x0, y0

    def draw_grid() -> None:
        for i in rect_ids:
            canvas.delete(i)
        rect_ids.clear()
        for r in range(ROWS):
            for c in range(COLS):
                x0, y0 = cell_origin(r, c)
                x1, y1 = x0 + cw - 1, y0 + ch - 1
                fill = OBSTACLE if (r, c) in env.obstacles else CELL_FREE
                rid = canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=GRID_LINE, width=1)
                rect_ids.append(rid)

    def draw_targets(targets: list[tuple[int, int]]) -> None:
        for i in target_ids:
            canvas.delete(i)
        target_ids.clear()
        for idx, (r, c) in enumerate(targets):
            if idx >= NUM_DRONES:
                break
            x0, y0 = cell_origin(r, c)
            xm, ym = x0 + cw // 2, y0 + ch // 2
            rad = min(cw, ch) // 3
            oid = canvas.create_oval(xm - rad, ym - rad, xm + rad, ym + rad, outline=TARGET_RING, width=2, dash=(4, 3))
            target_ids.append(oid)

    def draw_drones() -> None:
        for i in drone_ids:
            canvas.delete(i)
        drone_ids.clear()
        for i, (r, c) in enumerate(env.drone_positions):
            if i >= len(DRONE_COLORS):
                break
            x0, y0 = cell_origin(r, c)
            xm, ym = x0 + cw // 2, y0 + ch // 2
            sz = min(cw, ch)
            for cid in draw_drone_icon(canvas, xm, ym, sz, DRONE_COLORS[i], str(i + 1), label_fg=LABEL_FG):
                drone_ids.append(cid)

    def format_decision(d: ChoreographerDecision | None) -> str:
        if d is None:
            return ""
        src = "Groq" if d.source == "groq" else "demonstração"
        return f"{d.formation} | centro ({d.center_row},{d.center_col}) | escala {d.scale} | {src}"

    step_index = 0
    pending_moves: list[str] | None = None
    pending_decision: ChoreographerDecision | None = None
    last_source = ""

    def finish_step() -> None:
        nonlocal step_index, pending_moves, last_source
        if pending_moves is None:
            return
        apply_planned_moves(env, pending_moves)
        if pending_decision is not None:
            last_source = pending_decision.source
        pending_moves = None
        draw_grid()
        draw_drones()
        step_index += 1
        if step_index >= steps:
            status_var.set(f"Show encerrado. Última fonte do coreógrafo: {last_source or '—'}")
            return
        root.after(pause_ms, tick)

    def tick() -> None:
        nonlocal pending_moves, pending_decision
        if step_index >= steps:
            return
        decision, targets, moves = plan_step(env, choreographer, pilot, stuck_replan_after_beats)
        pending_moves = moves
        pending_decision = decision

        parts = [f"Passo {step_index + 1}/{steps} · beat {env.beat}"]
        if decision is None:
            if env.formation_achieved():
                parts.append("Coreógrafo: mantém intenção — alvos já ocupados; novo desenho no próximo disparo")
            else:
                parts.append("Coreógrafo: mantém formação — drones em deslocamento")
        else:
            parts.append(format_decision(decision))
            if decision.note:
                parts.append(decision.note[:120] + ("…" if len(decision.note) > 120 else ""))
        parts.append(f"Movimentos: {moves}")
        status_var.set(" · ".join(parts))

        draw_grid()
        draw_targets(targets)
        draw_drones()
        root.after(phase_ms, finish_step)

    draw_grid()
    draw_drones()
    root.after(200, tick)
    root.mainloop()


def main_visual_argv(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Show de drones — modo visual (Tkinter)")
    p.add_argument("--steps", type=int, default=40)
    p.add_argument(
        "--stuck-replan-after",
        "--replan-every",
        type=int,
        default=0,
        dest="stuck_replan_after",
        help="Após N beats sem formação completa, força coreógrafo (0=desligado)",
    )
    p.add_argument("--cell", type=int, default=34, help="Tamanho de cada célula em pixels")
    p.add_argument("--pause-ms", type=int, default=280, help="Pausa entre passos (ms)")
    p.add_argument("--phase-ms", type=int, default=220, help="Tempo mostrando alvos antes de mover (ms)")
    args = p.parse_args(argv)

    try:
        import tkinter as tk  # noqa: F401
    except ImportError:
        print(
            "Tkinter não está disponível neste Python. No Linux: sudo apt install python3-tk (Debian/Ubuntu).",
            file=sys.stderr,
        )
        return 1

    run_visual(
        steps=args.steps,
        stuck_replan_after_beats=args.stuck_replan_after,
        cell=args.cell,
        pause_ms=args.pause_ms,
        phase_ms=args.phase_ms,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main_visual_argv())

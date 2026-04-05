#!/usr/bin/env python3
"""
Simulação: show de drones em grade.
- Coreógrafo: LLM (Groq) ou stub sem GROQ_API_KEY.
- Piloto: agente baseado em modelo (BFS + mapa da grade).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.choreographer import ChoreographerAgent
from agents.pilot import ModelBasedPilotAgent
from environment import Environment
from simulation import apply_planned_moves, plan_step


def _configure_stdio() -> None:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except OSError:
            pass


def main() -> None:
    _configure_stdio()
    p = argparse.ArgumentParser(description="Simulação de drones — Agentes Inteligentes")
    p.add_argument("--steps", type=int, default=24, help="Número de passos (beats) a simular")
    p.add_argument(
        "--stuck-replan-after",
        "--replan-every",
        type=int,
        default=0,
        metavar="N",
        dest="stuck_replan_after",
        help="Opcional: após N beats sem todos chegarem aos alvos, força novo coreógrafo (pode mudar alvos no meio do voo). Padrão 0 = só replaneja quando a formação estiver completa",
    )
    p.add_argument("--quiet", action="store_true", help="Menos saída (só resumo final)")
    p.add_argument(
        "--visual",
        action="store_true",
        help="Abre janela gráfica (Tkinter, sem pip). Linux pode precisar do pacote python3-tk",
    )
    p.add_argument("--cell", type=int, default=34, help="[--visual] Tamanho da célula em pixels")
    p.add_argument("--pause-ms", type=int, default=280, help="[--visual] Pausa entre passos (ms)")
    p.add_argument("--phase-ms", type=int, default=220, help="[--visual] Tempo exibindo alvos antes de mover (ms)")
    args = p.parse_args()

    if args.visual:
        from gui import run_visual

        run_visual(
            steps=args.steps,
            stuck_replan_after_beats=args.stuck_replan_after,
            cell=args.cell,
            pause_ms=args.pause_ms,
            phase_ms=args.phase_ms,
        )
        return

    env = Environment()
    choreographer = ChoreographerAgent()
    pilot = ModelBasedPilotAgent()
    last_source = ""

    if not args.quiet:
        print("=== Show de drones (grade) ===")
        print(
            "Coreógrafo: com GROQ_API_KEY usa Groq; se a API falhar, estourar limite ou o JSON "
            "vier inválido, cai automaticamente no modo demonstração (stub).\n"
            "Novo coreógrafo só quando todos os drones chegam aos alvos atuais "
            "(use --stuck-replan-after N se quiser forçar após N beats sem completar).\n"
        )

    for k in range(args.steps):
        decision, targets, moves = plan_step(env, choreographer, pilot, args.stuck_replan_after)
        if decision is not None:
            last_source = decision.source
            if not args.quiet:
                if decision.source == "groq":
                    src = "Groq"
                elif decision.stub_reason:
                    src = f"modo demonstração — {decision.stub_reason}"
                else:
                    src = "modo demonstração"
                print(f"\n--- Beat {env.beat} | Coreógrafo ({src}) ---")
                print(
                    f"Formação: {decision.formation} | centro ({decision.center_row},{decision.center_col}) | escala {decision.scale}"
                )
                if decision.note:
                    print(f"Nota: {decision.note}")

        if not args.quiet:
            print(f"\nPasso {k + 1}/{args.steps} | beat={env.beat}")
            print("Alvos:", targets)
            print("Movimentos:", moves)
            print(env.render_ascii())

        apply_planned_moves(env, moves)

    if args.quiet:
        print(env.render_ascii())
    print(f"\nÚltima fonte do coreógrafo: {last_source or '—'}")


if __name__ == "__main__":
    main()

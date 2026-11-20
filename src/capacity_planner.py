"""Planificador de capacidad: escalamiento vertical (v1.0) frente a horizontal (v2.0).

Para un número de sucursales dado responde: ¿cabe el batch en la ventana nocturna?,
¿cuántos workers necesita v2.0? y ¿qué tendría que hacer v1.0 (scale-up)?
Salida: outputs/capacity_plan.json
"""
from __future__ import annotations

import argparse
import math

from common import OUTPUT_DIR, write_json, load_configs

WINDOW_MIN = 360          # 23:00 a 05:00
SAFETY_MARGIN_MIN = 60    # holgura que exige el SLA (objetivo p50 de 300 min)


def plan(branches: int) -> dict:
    cfg = load_configs("base")
    bw, lv, op = cfg["scaling"]["batch_window"], cfg["scaling"]["levers"], cfg["scaling"]["operation"]
    series = branches * op["skus"]

    # v1.0: un solo servidor; el tiempo crece lineal con las series.
    v1_minutes = bw["v1_p50_minutes"] * branches / 140
    v1_fits = v1_minutes <= WINDOW_MIN - SAFETY_MARGIN_MIN
    v1_scale_up_minutes = v1_minutes / 2  # VM con 2×GPU

    # v2.0: throughput por worker medido en la prueba de carga (series/min/worker).
    per_worker = (140 * op["skus"]) / bw["v2_p50_minutes"] / lv["batch_workers"]
    workers = math.ceil(series / (per_worker * bw["v2_p50_minutes"]))
    v2_minutes = series / (per_worker * workers)

    return {
        "branches": branches,
        "series": series,
        "v1": {"strategy": "vertical (scale-up)", "batch_p50_min": round(v1_minutes, 1), "fits_window": v1_fits,
               "action": "Ninguna" if v1_fits else f"Migrar a VM 2×GPU (≈{v1_scale_up_minutes:.0f} min) y pagarla 24/7"},
        "v2": {"strategy": "horizontal (scale-out)", "workers": workers, "throughput_per_worker_series_min": round(per_worker, 1),
               "batch_p50_min": round(v2_minutes, 1), "fits_window": v2_minutes <= WINDOW_MIN - SAFETY_MARGIN_MIN,
               "action": f"Job indexado con parallelism={workers} sobre nodos spot"},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Capacidad del batch nocturno por número de sucursales.")
    ap.add_argument("--branches", type=int, nargs="+", default=[140, 180, 220, 280])
    args = ap.parse_args()
    plans = [plan(n) for n in args.branches]
    write_json(OUTPUT_DIR / "capacity_plan.json", plans)
    print("\n=== CAPACIDAD DEL BATCH NOCTURNO ===")
    for p in plans:
        print(f"{p['branches']} sucursales | v1.0: {p['v1']['batch_p50_min']:>6.1f} min ({'cabe' if p['v1']['fits_window'] else 'NO cabe'})"
              f" | v2.0: {p['v2']['workers']} workers, {p['v2']['batch_p50_min']:.1f} min")


if __name__ == "__main__":
    main()

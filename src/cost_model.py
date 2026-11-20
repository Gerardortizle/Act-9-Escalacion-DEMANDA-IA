"""Modelo de costos FinOps: deployment actual (v1.0) frente al rediseño (v2.0).

Reproduce las hojas Costos_Actual, Costos_Propuesto y Comparativo del anexo técnico.
Salidas: outputs/cost_report.json y outputs/cost_lines.csv
"""
from __future__ import annotations

import argparse
import math

import pandas as pd

from common import OUTPUT_DIR, SCENARIOS, load_configs, write_json


def effective_rates(cfg: dict) -> tuple[float, float]:
    r, lv = cfg["scaling"]["rates_usd"], cfg["scaling"]["levers"]
    cpu = r["cpu_node_spot_hour"] * (1 - lv["cpu_ondemand_fallback_share"]) + r["cpu_node_ondemand_hour"] * lv["cpu_ondemand_fallback_share"]
    gpu = r["gpu_node_spot_hour"] * (1 - lv["gpu_ondemand_fallback_share"]) + r["gpu_node_ondemand_hour"] * lv["gpu_ondemand_fallback_share"]
    return cpu, gpu


def lines_v1(cfg: dict) -> list[dict]:
    op, r = cfg["scaling"]["operation"], cfg["scaling"]["rates_usd"]
    h = op["hours_per_month"]
    return [
        {"category": "Cómputo", "resource": "VM GPU monolítica 24/7 (ETL, entrenamiento, batch y API)", "qty": h, "rate": r["vm_gpu_monolith_hour"]},
        {"category": "Base de datos", "resource": "PostgreSQL 16 vCPU / 128 GB, una zona", "qty": h, "rate": r["postgres_v1_hour"]},
        {"category": "Almacenamiento", "resource": "SSD 4 TB con 3 años de tickets en caliente", "qty": 4000, "rate": 0.10},
        {"category": "Almacenamiento", "resource": "Snapshots sin retención", "qty": 3000, "rate": 0.05},
        {"category": "Red", "resource": "Extracción completa diaria entre regiones (GB)", "qty": 3600, "rate": 0.09},
        {"category": "Observabilidad", "resource": "Logs sin filtrar, 90 días (GB)", "qty": 600, "rate": 0.30},
        {"category": "QA e integración", "resource": "Ambientes de QA e integración 24/7 (Act. 3 C04)", "qty": 1, "rate": 250},
    ]


def lines_v2(cfg: dict) -> list[dict]:
    op, r, lv = cfg["scaling"]["operation"], cfg["scaling"]["rates_usd"], cfg["scaling"]["levers"]
    h, nights = op["hours_per_month"], op["nights_per_month"]
    cpu, gpu = effective_rates(cfg)
    disc = lv["commitment_discount"]
    # Los workers crecen en proporción a las sucursales (escalamiento horizontal).
    # El costo usa horas-nodo proporcionales; el número entero de workers se reporta aparte.
    scale = op["branches"] / 140
    workers_hours = lv["batch_workers"] * scale
    workers = math.ceil(workers_hours)
    etl_nodes = lv["etl_nodes"] * scale
    return [
        {"category": "Inferencia", "resource": f"Batch: {workers} workers CPU spot, ONNX INT8", "qty": workers_hours * lv["batch_hours_per_night"] * nights, "rate": cpu},
        {"category": "Cómputo", "resource": "Reentrenamiento en nodo GPU spot con checkpoints", "qty": lv["gpu_training_hours_month"], "rate": gpu},
        {"category": "Cómputo", "resource": "ETL y features incrementales en nodos spot", "qty": etl_nodes * lv["etl_hours_per_night"] * nights, "rate": cpu},
        {"category": "Inferencia", "resource": "API: 2 nodos base con compromiso de 1 año", "qty": 2 * h, "rate": r["api_node_hour"] * (1 - disc)},
        {"category": "Inferencia", "resource": "API: nodos extra por autoescalado en picos", "qty": 2 * 3 * nights, "rate": r["api_node_hour"]},
        {"category": "Inferencia", "resource": "Caché Redis multi-AZ (2 nodos)", "qty": 2 * h, "rate": r["redis_node_hour"]},
        {"category": "Cómputo", "resource": "Plano de control Kubernetes/OpenShift", "qty": h, "rate": r["k8s_control_plane_hour"]},
        {"category": "Red", "resource": "Balanceador de carga", "qty": 1, "rate": 30},
        {"category": "Base de datos", "resource": "PostgreSQL 4 vCPU multi-AZ con compromiso", "qty": h, "rate": r["postgres_v2_hour"] * (1 - disc)},
        {"category": "Almacenamiento", "resource": "Objetos caliente: agregados 3 años (Parquet)", "qty": 600, "rate": 0.023},
        {"category": "Almacenamiento", "resource": "Objetos infrecuente: tickets disociados", "qty": 1400, "rate": 0.0125},
        {"category": "Almacenamiento", "resource": "Archivo y copia de recuperación (R11)", "qty": 2000, "rate": 0.002},
        {"category": "Almacenamiento", "resource": "SSD de la base de datos", "qty": 500, "rate": 0.115},
        {"category": "Almacenamiento", "resource": "Snapshots con ciclo de vida de 35 días", "qty": 800, "rate": 0.05},
        {"category": "Red", "resource": "CDC incremental en región México (GB)", "qty": 300, "rate": 0.05},
        {"category": "Red", "resource": "Enlaces privados al ERP (2)", "qty": 2, "rate": 7.30},
        {"category": "Observabilidad", "resource": "Logs filtrados 30 días y métricas (GB)", "qty": 150, "rate": 0.30},
        {"category": "Observabilidad", "resource": "Tableros FinOps, drift y fairness", "qty": 1, "rate": 40},
        {"category": "Gobernanza", "resource": "Registro de modelos, linaje y bitácora inmutable", "qty": 1, "rate": 60},
        {"category": "QA e integración", "resource": "Ambientes de QA efímeros por liberación", "qty": 1, "rate": 120},
    ]


def total(lines: list[dict]) -> float:
    return sum(l["qty"] * l["rate"] for l in lines)


def growth_table(cfg: dict) -> list[dict]:
    """Costo al crecer: v1.0 necesita scale-up cuando el batch excede la ventana; v2.0 agrega workers."""
    base = load_configs("base")
    t_v1, v2_lines = total(lines_v1(base)), lines_v2(base)
    t_v2 = total(v2_lines)
    elastic = v2_lines[0]["qty"] * v2_lines[0]["rate"] + v2_lines[2]["qty"] * v2_lines[2]["rate"]
    r, bw = base["scaling"]["rates_usd"], base["scaling"]["batch_window"]
    rows = []
    for n in (140, 180, 220, 280):
        batch_v1 = bw["v1_p50_minutes"] * n / 140
        scale_up = batch_v1 > bw["target_p50_minutes"]
        cost_v1 = t_v1 + ((r["vm_gpu_scaleup_2x_hour"] - r["vm_gpu_monolith_hour"]) * 730 if scale_up else 0)
        cost_v2 = t_v2 + elastic * (n / 140 - 1)
        rows.append({"branches": n, "batch_v1_min": round(batch_v1, 1), "v1_requires_scale_up": scale_up,
                     "cost_v1_usd": round(cost_v1, 2), "workers_v2": math.ceil(24 * n / 140),
                     "batch_v2_min": bw["v2_p50_minutes"], "cost_v2_usd": round(cost_v2, 2),
                     "cost_per_branch_v2_usd": round(cost_v2 / n, 2)})
    return rows


def run(scenario: str = "base") -> dict:
    cfg = load_configs(scenario)
    op, fx = cfg["scaling"]["operation"], cfg["scaling"]["operation"]["fx_mxn_per_usd"]
    l1, l2 = lines_v1(cfg), lines_v2(cfg)
    t1, t2 = total(l1), total(l2)
    forecasts = op["branches"] * op["skus"] * op["horizon_days"] * op["nights_per_month"]

    cats = sorted({l["category"] for l in l1 + l2})
    by_cat = []
    for c in cats:
        a = sum(l["qty"] * l["rate"] for l in l1 if l["category"] == c)
        p = sum(l["qty"] * l["rate"] for l in l2 if l["category"] == c)
        by_cat.append({"category": c, "v1_usd": round(a, 2), "v2_usd": round(p, 2),
                       "savings_pct": round(100 * (a - p) / a, 1) if a else None})

    report = {
        "scenario": scenario,
        "branches": op["branches"],
        "v1_monthly_usd": round(t1, 2),
        "v2_monthly_usd": round(t2, 2),
        "savings_pct": round(100 * (1 - t2 / t1), 1),
        "forecasts_per_month": forecasts,
        "v1_cost_per_million_usd": round(t1 / forecasts * 1e6, 3),
        "v2_cost_per_million_usd": round(t2 / forecasts * 1e6, 3),
        "v2_cost_per_branch_usd": round(t2 / op["branches"], 2),
        "annual_savings_mxn": round((t1 - t2) * 12 * fx, 0),
        "by_category": by_cat,
        "growth": growth_table(cfg),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [{"version": "v1", **l, "monthly_usd": round(l["qty"] * l["rate"], 2)} for l in l1]
    rows += [{"version": "v2", **l, "monthly_usd": round(l["qty"] * l["rate"], 2)} for l in l2]
    pd.DataFrame(rows).to_csv(OUTPUT_DIR / "cost_lines.csv", index=False)
    write_json(OUTPUT_DIR / "cost_report.json", report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Costos v1.0 vs v2.0 (FinOps).")
    ap.add_argument("--scenario", default="base", choices=list(SCENARIOS))
    args = ap.parse_args()
    rep = run(args.scenario)
    print(f"\n=== COSTOS · escenario {rep['scenario']} ===")
    print(f"v1.0: USD {rep['v1_monthly_usd']:,.2f}/mes   v2.0: USD {rep['v2_monthly_usd']:,.2f}/mes   ahorro: {rep['savings_pct']:.1f} %")
    print(f"Costo por millón de pronósticos: v1.0 USD {rep['v1_cost_per_million_usd']:.2f} -> v2.0 USD {rep['v2_cost_per_million_usd']:.2f}")
    for c in rep["by_category"]:
        print(f"  {c['category']:<18} {c['v1_usd']:>9,.2f} -> {c['v2_usd']:>9,.2f}")


if __name__ == "__main__":
    main()

"""Orquestador: costos → capacidad → desempeño → fairness → gate → dashboard → MLflow.

Uso:
    python src/run_pipeline.py --scenario base --phase full_rollout
"""
from __future__ import annotations

import argparse
import time
import uuid

import capacity_planner
import cost_model
import dashboard
import fairness_audit
import governance_gate
import performance_report
from common import OUTPUT_DIR, SCENARIOS, load_configs, log_event, write_json, write_trace


def log_mlflow(cfg: dict, trace_id: str, cost: dict, perf: dict, fair: dict, gate: dict) -> None:
    ml = cfg["scaling"].get("mlflow", {})
    if not ml.get("enabled", False):
        return
    try:
        import mlflow
    except ImportError:
        print("ADVERTENCIA: MLflow no está instalado; los reportes locales sí se generaron.")
        return
    from common import ROOT
    mlflow.set_tracking_uri(f"sqlite:///{(ROOT / 'mlflow.db').resolve().as_posix()}")
    mlflow.set_experiment(ml.get("experiment_name", "Act9_Escalacion_DEMANDA-IA"))
    with mlflow.start_run(run_name=f"{cost['scenario']}_{gate['phase']}_{trace_id}"):
        mlflow.log_params({"scenario": cost["scenario"], "phase": gate["phase"], "deployed_model": fair["deployed_model"],
                           "branches": cost["branches"], "decision": gate["decision"], **cfg["scaling"]["levers"]})
        mlflow.log_metrics({
            "cost_v1_usd_month": cost["v1_monthly_usd"], "cost_v2_usd_month": cost["v2_monthly_usd"],
            "savings_pct": cost["savings_pct"], "cost_per_million_v2_usd": cost["v2_cost_per_million_usd"],
            **{f"sla_{k}": float(v) for k, v in perf["versions"]["v2"].items()},
            **{f"fair_{k}": float(v) for k, v in fair["versions"][fair["deployed_model"]]["indicators"].items()},
            "gate_failed_checks": len(gate["failed_checks"]),
        })
        for f in ("cost_report.json", "performance_report.json", "fairness_report.json", "gate_decision.json", "dashboard.png"):
            if (OUTPUT_DIR / f).exists():
                mlflow.log_artifact(str(OUTPUT_DIR / f), artifact_path="act9")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pipeline completo de la Actividad 9.")
    ap.add_argument("--scenario", default="base", choices=list(SCENARIOS))
    ap.add_argument("--phase", default="full_rollout", choices=["pilot", "full_rollout"])
    args = ap.parse_args()
    cfg = load_configs(args.scenario)
    trace_id = uuid.uuid4().hex[:12]

    def stage(name, fn, *a):
        t = time.perf_counter()
        out = fn(*a)
        write_trace(trace_id, name, (time.perf_counter() - t) * 1000)
        return out

    cost = stage("cost_model", cost_model.run, args.scenario)
    branches = cfg["scaling"]["operation"]["branches"]
    cap = stage("capacity_planner", lambda: [capacity_planner.plan(branches)])
    write_json(OUTPUT_DIR / "capacity_plan.json", cap)
    perf = stage("performance_report", performance_report.run, args.scenario)
    fair = stage("fairness_audit", fairness_audit.run, args.scenario)
    gate = stage("governance_gate", governance_gate.decide, args.scenario, args.phase)
    stage("dashboard", dashboard.main)
    log_mlflow(cfg, trace_id, cost, perf, fair, gate)
    log_event("pipeline_run", {"trace_id": trace_id, "scenario": args.scenario, "phase": args.phase,
                               "decision": gate["decision"], "failed_checks": [c["check"] for c in gate["failed_checks"]]})

    print(f"\n=== ACTIVIDAD 9 · DEMANDA-IA · {args.scenario} / {args.phase} ===")
    print(cfg["scenario"]["description"])
    print(f"Trace ID: {trace_id}")
    print(f"Costo: USD {cost['v1_monthly_usd']:,.2f} → {cost['v2_monthly_usd']:,.2f} al mes (ahorro {cost['savings_pct']:.1f} %),"
          f" USD {cost['v2_cost_per_million_usd']:.2f} por millón de pronósticos")
    print(f"SLA v2.0: {'cumple' if perf['v2_meets_sla'] else 'NO cumple'}"
          f" | batch p50 {perf['versions']['v2']['batch_p50_min']} min | API p95 {perf['versions']['v2']['api_p95_ms']} ms")
    ind = fair["versions"][fair["deployed_model"]]["indicators"]
    print(f"Fairness (modelo {fair['deployed_model']}): brecha WAPE {ind['wape_gap_pp']} pp | TPR C/A {ind['tpr_ratio']}"
          f" | quiebre esenciales C/A {ind['essential_stockout_ratio']}")
    print(f"Capacidad: {cap[0]['v2']['workers']} workers para {branches} sucursales")
    print(f"GATE: {gate['decision']}")
    for c in gate["failed_checks"]:
        print(f"  FALLA [{c['dimension']}] {c['check']} = {c['value']} (límite {c['limit']})")
    print(f"Evidencia en: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

"""Corre todos los escenarios y arma una tabla comparativa de evidencia.

Salida: outputs/scenario_comparison.csv
"""
from __future__ import annotations

import pandas as pd

import cost_model
import fairness_audit
import governance_gate
import performance_report
from common import OUTPUT_DIR, SCENARIOS


def main() -> None:
    rows = []
    for name in SCENARIOS:
        cost = cost_model.run(name)
        perf = performance_report.run(name)
        fair = fairness_audit.run(name)
        gate = governance_gate.decide(name, "full_rollout")
        ind = fair["versions"][fair["deployed_model"]]["indicators"]
        rows.append({
            "escenario": name,
            "sucursales": cost["branches"],
            "costo_v2_usd_mes": cost["v2_monthly_usd"],
            "ahorro_pct": cost["savings_pct"],
            "usd_por_millon": cost["v2_cost_per_million_usd"],
            "api_p95_ms": perf["versions"]["v2"]["api_p95_ms"],
            "sla_v2": "cumple" if perf["v2_meets_sla"] else "no cumple",
            "tpr_ratio_CA": ind["tpr_ratio"],
            "quiebre_ratio_CA": ind["essential_stockout_ratio"],
            "gate": gate["decision"],
            "checks_fallidos": "; ".join(c["check"] for c in gate["failed_checks"]) or "-",
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_DIR / "scenario_comparison.csv", index=False)
    # Deja los reportes del escenario base como estado final.
    cost_model.run("base"); performance_report.run("base"); fairness_audit.run("base"); governance_gate.decide("base", "full_rollout")
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))
    print(f"\nTabla guardada en {OUTPUT_DIR / 'scenario_comparison.csv'}")


if __name__ == "__main__":
    main()

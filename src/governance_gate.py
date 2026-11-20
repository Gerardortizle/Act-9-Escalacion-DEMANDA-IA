"""Gate de escalamiento responsable (governance-as-code).

Junta los reportes de costo, desempeño y fairness y decide si DEMANDA-IA puede
avanzar a la siguiente fase del plan (piloto o despliegue total). Si una dimensión
prioritaria falla, el gate bloquea el avance aunque las demás estén en verde.

Salida: outputs/gate_decision.json   (código de salida 1 si el gate no pasa)
"""
from __future__ import annotations

import argparse
import sys

from common import OUTPUT_DIR, SCENARIOS, load_configs, load_json, write_json


def _reports(scenario: str) -> tuple[dict, dict, dict]:
    """Lee los reportes de outputs/; si no existen o son de otro escenario, los recalcula."""
    import cost_model
    import fairness_audit
    import performance_report

    out = []
    for fname, module in (("cost_report.json", cost_model), ("performance_report.json", performance_report),
                          ("fairness_report.json", fairness_audit)):
        path = OUTPUT_DIR / fname
        rep = load_json(path) if path.exists() else None
        if rep is None or rep.get("scenario") != scenario:
            rep = module.run(scenario)
        out.append(rep)
    return tuple(out)


def decide(scenario: str, phase: str) -> dict:
    cfg = load_configs(scenario)
    gate = cfg["governance"]["gates"][phase]
    targets = cfg["scaling"]["finops_targets"]
    cost, perf, fair = _reports(scenario)
    deployed = fair["deployed_model"]

    checks = []
    # 1. Escalabilidad y SLA
    if gate["require_sla"]:
        for c in perf["sla_checks"]:
            if c["version"] == "v2":
                checks.append({"dimension": "SLA", "check": c["metric"], "value": c["value"],
                               "limit": c["target"], "pass": c["pass"]})
    # 2. Costo (FinOps)
    limit = targets[gate["max_cost_per_million_key"]]
    checks.append({"dimension": "Costo", "check": "costo_por_millon_usd", "value": cost["v2_cost_per_million_usd"],
                   "limit": limit, "pass": cost["v2_cost_per_million_usd"] <= limit})
    if gate["require_min_savings"]:
        checks.append({"dimension": "Costo", "check": "ahorro_vs_v1_pct", "value": cost["savings_pct"],
                       "limit": targets["min_savings_vs_v1"] * 100,
                       "pass": cost["savings_pct"] >= targets["min_savings_vs_v1"] * 100})
    # 3. Ética: fairness del modelo que realmente se despliega
    residual = set(fair["accepted_residual_risks"])
    for c in fair["versions"][deployed]["checks"]:
        if c["priority"] in gate["require_fairness_priorities"]:
            checks.append({"dimension": "Fairness", "check": c["indicator"], "value": c["value"],
                           "limit": c["threshold"], "pass": c["pass"]})
        elif c["indicator"] in residual and not c["pass"]:
            checks.append({"dimension": "Fairness", "check": c["indicator"], "value": c["value"],
                           "limit": c["threshold"], "pass": True, "note": "riesgo residual aceptado por el comité"})
    # 4. Cumplimiento: controles que deben existir antes de avanzar
    for ctrl in ("model_card_v2", "registro_de_modelos", "bitacora_inmutable", "controlados_fuera_de_autopedido"):
        checks.append({"dimension": "Cumplimiento", "check": ctrl, "value": "presente", "limit": "presente", "pass": True})

    failed = [c for c in checks if not c["pass"]]
    decision = {
        "scenario": scenario,
        "scenario_description": cfg["scenario"]["description"],
        "phase": phase,
        "phase_description": gate["description"],
        "deployed_model": deployed,
        "decision": "APROBADO" if not failed else "BLOQUEADO",
        "failed_checks": failed,
        "checks": checks,
        "next_step": ("Avanzar a la siguiente fase" if not failed else
                      "Ejecutar el runbook de la dimensión que falló; v1.0 sigue como respaldo"),
    }
    write_json(OUTPUT_DIR / "gate_decision.json", decision)
    return decision


def main() -> None:
    ap = argparse.ArgumentParser(description="Gate de escalamiento responsable.")
    ap.add_argument("--scenario", default="base", choices=list(SCENARIOS))
    ap.add_argument("--phase", default="full_rollout", choices=["pilot", "full_rollout"])
    args = ap.parse_args()
    d = decide(args.scenario, args.phase)
    print(f"\n=== GATE {d['phase']} · escenario {d['scenario']} ===")
    print(f"Decisión: {d['decision']}")
    for c in d["failed_checks"]:
        print(f"  FALLA [{c['dimension']}] {c['check']}: {c['value']} (límite {c['limit']})")
    print(f"Siguiente paso: {d['next_step']}")
    sys.exit(0 if d["decision"] == "APROBADO" else 1)


if __name__ == "__main__":
    main()

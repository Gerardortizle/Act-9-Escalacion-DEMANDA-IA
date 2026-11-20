"""Auditoría de fairness por grupo de marginación (T22).

Calcula, para cada versión del modelo y cada grupo de sucursales:
WAPE, sesgo (MFE), tasa de quiebre de esenciales, TPR / precisión / FPR de la alerta
de riesgo de quiebre y fill rate. Después compara el grupo protegido (C) contra el
de referencia (A) con los umbrales de config/governance_config.json.

Salida: outputs/fairness_report.json
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from common import DATA_DIR, OUTPUT_DIR, SCENARIOS, load_configs, write_json


def group_metrics(df: pd.DataFrame) -> dict:
    err = df["forecast_units"] - df["demand_units"]
    tot = df["demand_units"].sum()
    ess = df[df["essential"] == 1]
    tp = int(((df.alert_flag == 1) & (df.stockout_event == 1)).sum())
    fp = int(((df.alert_flag == 1) & (df.stockout_event == 0)).sum())
    fn = int(((df.alert_flag == 0) & (df.stockout_event == 1)).sum())
    tn = int(((df.alert_flag == 0) & (df.stockout_event == 0)).sum())
    return {
        "wape": float(np.abs(err).sum() / tot),
        "mfe": float(err.sum() / tot),
        "essential_stockout_rate": float(ess["stockout_essential"].mean()),
        "tpr": tp / (tp + fn),
        "precision": tp / (tp + fp),
        "fpr": fp / (fp + tn),
        "fill_rate": float(df["served_units"].sum() / tot),
    }


def indicators(groups: dict, ref: str, prot: str) -> dict:
    a, c = groups[ref], groups[prot]
    return {
        "wape_gap_pp": round((c["wape"] - a["wape"]) * 100, 2),
        "underforecast_abs_mfe": round(abs(c["mfe"]), 4),
        "tpr_ratio": round(c["tpr"] / a["tpr"], 3),
        "precision_ratio": round(c["precision"] / a["precision"], 3),
        "fpr_ratio": round(c["fpr"] / a["fpr"], 3),
        "essential_stockout_ratio": round(c["essential_stockout_rate"] / a["essential_stockout_rate"], 3),
        "fill_rate_ratio": round(c["fill_rate"] / a["fill_rate"], 3),
    }


def evaluate(ind: dict, thresholds: dict) -> list[dict]:
    out = []
    for k, rule in thresholds.items():
        val = ind[k]
        ok = val <= rule["threshold"] if rule["direction"] == "max" else val >= rule["threshold"]
        out.append({"indicator": k, "value": val, "threshold": rule["threshold"], "direction": rule["direction"],
                    "t22_metric": rule["t22_metric"], "priority": rule["priority"], "pass": bool(ok)})
    return out


def run(scenario: str = "base") -> dict:
    cfg = load_configs(scenario)
    gov = cfg["governance"]
    ref, prot = gov["reference_group"], gov["protected_group"]
    df = pd.read_csv(DATA_DIR / "backtest.csv")

    versions = {}
    for v in ("v1", "v2"):
        sub = df[df.model_version == v]
        groups = {g: {k: round(val, 4) for k, val in group_metrics(sub[sub.group == g]).items()} for g in sorted(sub.group.unique())}
        weights = {g: gov["groups"][g]["volume_share"] for g in groups}
        glob = {k: round(sum(weights[g] * groups[g][k] for g in groups), 4) for k in groups[ref]}
        ind = indicators(groups, ref, prot)
        versions[v] = {"by_group": groups, "global_volume_weighted": glob, "indicators": ind,
                       "checks": evaluate(ind, gov["fairness_thresholds"])}

    deployed = cfg["scenario"]["fairness_model"]
    report = {"scenario": scenario, "deployed_model": deployed, "reference_group": ref, "protected_group": prot,
              "versions": versions, "accepted_residual_risks": gov["accepted_residual_risks"]}
    write_json(OUTPUT_DIR / "fairness_report.json", report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Auditoría de fairness por grupo de sucursales.")
    ap.add_argument("--scenario", default="base", choices=list(SCENARIOS))
    rep = run(ap.parse_args().scenario)
    print(f"\n=== FAIRNESS · escenario {rep['scenario']} (modelo desplegado: {rep['deployed_model']}) ===")
    for v in ("v1", "v2"):
        print(f"\nModelo {v}:")
        for g, m in rep["versions"][v]["by_group"].items():
            print(f"  Grupo {g}: WAPE {m['wape']:.3f} | MFE {m['mfe']:+.3f} | quiebre esenciales {m['essential_stockout_rate']:.3f}"
                  f" | TPR {m['tpr']:.2f} | fill {m['fill_rate']:.3f}")
        for c in rep["versions"][v]["checks"]:
            print(f"    {c['indicator']:<26} {c['value']:>7} ({c['t22_metric']}) -> {'cumple' if c['pass'] else 'NO cumple'}")


if __name__ == "__main__":
    main()

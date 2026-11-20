"""Métricas de desempeño (latencia, throughput y uso de recursos) contra el SLA.

Lee data/batch_nights.csv y data/api_requests.csv.
Salida: outputs/performance_report.json
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from common import DATA_DIR, OUTPUT_DIR, SCENARIOS, check, load_configs, write_json

WINDOW_MIN = 360


def version_metrics(nights: pd.DataFrame, api: pd.DataFrame, series: int, platform: dict) -> dict:
    b = nights["batch_minutes"]
    on_time = (nights["delivery_minutes_after_23h"] <= WINDOW_MIN).mean() * 100
    lat = api["latency_ms"]
    return {
        "batch_p50_min": round(float(b.quantile(0.50)), 1),
        "batch_p95_min": round(float(b.quantile(0.95)), 1),
        "on_time_nights_pct": round(float(on_time), 1),
        "batch_throughput_series_min": round(series / float(b.quantile(0.50)), 0),
        "api_p50_ms": round(float(lat.quantile(0.50)), 1),
        "api_p95_ms": round(float(lat.quantile(0.95)), 1),
        "api_p99_ms": round(float(lat.quantile(0.99)), 1),
        "api_error_rate_pct": round(float(api["is_error"].mean() * 100), 2),
        "cache_hit_pct": round(float(api["cache_hit"].mean() * 100), 1),
        **platform,
    }


def run(scenario: str = "base") -> dict:
    cfg = load_configs(scenario)
    nights = pd.read_csv(DATA_DIR / "batch_nights.csv")
    api = pd.read_csv(DATA_DIR / "api_requests.csv")
    series = cfg["scaling"]["operation"]["branches"] * cfg["scaling"]["operation"]["skus"]
    plat = cfg["sla"]["observed_platform"]

    api_v2 = api[api.model_version == "v2"].copy()
    if not cfg["scenario"]["cache_available"]:
        # Sin caché, cada consulta llega al microservicio: se remuestrea la latencia de las consultas no cacheadas.
        misses = api_v2.loc[api_v2.cache_hit == 0, "latency_ms"].to_numpy()
        rng = np.random.default_rng(7)
        api_v2["latency_ms"] = rng.choice(misses, size=len(api_v2), replace=True)
        api_v2["cache_hit"] = 0

    result = {"scenario": scenario, "versions": {
        "v1": version_metrics(nights[nights.model_version == "v1"], api[api.model_version == "v1"], series, plat["v1"]),
        "v2": version_metrics(nights[nights.model_version == "v2"], api_v2, series, plat["v2"]),
    }}
    checks = []
    for metric, rule in cfg["sla"]["sla"].items():
        for v in ("v1", "v2"):
            val = result["versions"][v].get(metric)
            if val is not None:
                checks.append({"metric": metric, "version": v, "value": val, "target": rule["target"],
                               "direction": rule["direction"], "pass": bool(check(val, rule))})
    result["sla_checks"] = checks
    result["v2_meets_sla"] = all(c["pass"] for c in checks if c["version"] == "v2")
    result["v1_meets_sla"] = all(c["pass"] for c in checks if c["version"] == "v1")
    write_json(OUTPUT_DIR / "performance_report.json", result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Desempeño frente al SLA.")
    ap.add_argument("--scenario", default="base", choices=list(SCENARIOS))
    rep = run(ap.parse_args().scenario)
    print(f"\n=== DESEMPEÑO · escenario {rep['scenario']} ===")
    print(f"{'métrica':<26}{'v1.0':>10}{'v2.0':>10}  SLA")
    rules = load_configs("base")["sla"]["sla"]
    for m, rule in rules.items():
        v1, v2 = rep["versions"]["v1"].get(m), rep["versions"]["v2"].get(m)
        ok = "cumple" if check(v2, rule) else "NO cumple"
        sign = "≤" if rule["direction"] == "max" else "≥"
        print(f"{m:<26}{v1:>10}{v2:>10}  {sign} {rule['target']}  -> v2.0 {ok}")
    print(f"v2.0 cumple todo el SLA: {rep['v2_meets_sla']}")


if __name__ == "__main__":
    main()

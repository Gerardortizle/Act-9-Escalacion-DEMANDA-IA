"""Genera los datos simulados de la Actividad 9.

Crea tres archivos en data/:
- backtest.csv:      backtest de 26 semanas por sucursal y SKU para los modelos v1.0 y v2.0 (fairness).
- batch_nights.csv:  30 noches de ejecución del batch por versión (latencia del pipeline nocturno).
- api_requests.csv:  10,000 consultas a la API por versión (latencia, caché y errores).

Los datos están calibrados para reproducir las cifras del anexo técnico
(Act. 9. Anexo técnico DEMANDA-IA JGOL.xlsx). Son datos sintéticos: no hay
información de clientes ni de pacientes.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import DATA_DIR, load_configs  # noqa: E402

SEED = 2026
SKUS_SAMPLE = 30          # SKUs muestreados por sucursal para el backtest
WEEKS = 26
ESSENTIAL_SHARE = 0.30    # proporción de SKUs de la lista de medicamentos esenciales
API_REQUESTS = 10_000

# Objetivos por grupo: WAPE, MFE (sesgo), quiebre de esenciales, TPR, precisión, FPR y fill rate de la alerta.
# Fuente: hoja Fairness del anexo técnico.
FAIRNESS_TARGETS = {
    "v1": {"A": (0.162, -0.011, 0.021, 0.87, 0.71, 0.05, 0.930),
           "B": (0.196, -0.034, 0.035, 0.80, 0.68, 0.06, 0.900),
           "C": (0.279, -0.096, 0.082, 0.62, 0.66, 0.04, 0.840)},
    "v2": {"A": (0.164, -0.007, 0.020, 0.87, 0.70, 0.06, 0.965),
           "B": (0.188, -0.015, 0.027, 0.84, 0.69, 0.07, 0.958),
           "C": (0.210, -0.026, 0.029, 0.81, 0.67, 0.11, 0.950)},
}


def _solve_noise_scale(demand: np.ndarray, z: np.ndarray, mfe: float, wape: float) -> float:
    """Busca la escala de ruido que da exactamente el WAPE objetivo (bisección)."""
    lo, hi = 0.0, 2.0
    for _ in range(80):
        mid = (lo + hi) / 2
        err = demand * (mfe + mid * z)
        value = np.abs(err).sum() / demand.sum()
        lo, hi = (mid, hi) if value < wape else (lo, mid)
    return (lo + hi) / 2


def _exact_flags(rng: np.random.Generator, n: int, k: int) -> np.ndarray:
    flags = np.zeros(n, dtype=int)
    flags[rng.choice(n, size=max(0, min(n, k)), replace=False)] = 1
    return flags


def make_backtest(rng: np.random.Generator, groups: dict) -> pd.DataFrame:
    frames = []
    for version, targets in FAIRNESS_TARGETS.items():
        for group, (wape, mfe, stockout, tpr, prec, fpr, fill) in targets.items():
            info = groups[group]
            n_br = info["branches"]
            # Volumen por sucursal proporcional a la participación del grupo en ventas.
            scale = 1000 * info["volume_share"] / n_br
            branch = np.repeat(np.arange(n_br), SKUS_SAMPLE * WEEKS)
            sku = np.tile(np.repeat(np.arange(SKUS_SAMPLE), WEEKS), n_br)
            week = np.tile(np.arange(1, WEEKS + 1), n_br * SKUS_SAMPLE)
            n = len(branch)
            demand = rng.lognormal(mean=math.log(scale * 10), sigma=0.6, size=n).round(2) + 1.0

            # Error del pronóstico: uniforme acotado para que el pronóstico nunca sea negativo.
            z = rng.uniform(-math.sqrt(3), math.sqrt(3), size=n)
            z = z - np.average(z, weights=demand)
            s = _solve_noise_scale(demand, z, mfe, wape)
            forecast = demand * (1 + mfe + s * z)

            essential = (sku < int(SKUS_SAMPLE * ESSENTIAL_SHARE)).astype(int)
            ess_idx = np.flatnonzero(essential)
            stockout_ess = np.zeros(n, dtype=int)
            stockout_ess[ess_idx] = _exact_flags(rng, len(ess_idx), round(stockout * len(ess_idx)))

            # Evaluación de la alerta de riesgo de quiebre (matriz de confusión exacta).
            prevalence = fpr * prec / (tpr * (1 - prec) + fpr * prec)
            positives = round(prevalence * n)
            event = _exact_flags(rng, n, positives)
            pos_idx, neg_idx = np.flatnonzero(event == 1), np.flatnonzero(event == 0)
            alert = np.zeros(n, dtype=int)
            alert[rng.choice(pos_idx, size=round(tpr * len(pos_idx)), replace=False)] = 1
            alert[rng.choice(neg_idx, size=round(fpr * len(neg_idx)), replace=False)] = 1

            # Unidades surtidas: fill rate exacto ponderado por demanda.
            k = rng.uniform(0.97, 1.03, size=n)
            k = k / np.average(k, weights=demand)
            served = demand * fill * k

            frames.append(pd.DataFrame({
                "model_version": version, "group": group, "branch_id": [f"{group}{b:03d}" for b in branch],
                "sku_id": sku, "week": week, "essential": essential,
                "demand_units": demand, "forecast_units": forecast, "served_units": served,
                "stockout_essential": stockout_ess, "stockout_event": event, "alert_flag": alert,
            }))
    return pd.concat(frames, ignore_index=True)


def _nights(sorted_values: list[float], etl_min: float, rng: np.random.Generator, version: str) -> pd.DataFrame:
    values = np.array(sorted_values, dtype=float)
    rng.shuffle(values)
    return pd.DataFrame({"model_version": version, "night": np.arange(1, len(values) + 1),
                         "etl_minutes": etl_min, "batch_minutes": values,
                         "delivery_minutes_after_23h": etl_min + values})


def make_batch_nights(rng: np.random.Generator) -> pd.DataFrame:
    # v1.0: p50 275 min, p95 340 min; con la extracción completa (40 min), 3 noches pasan de las 05:00.
    v1 = list(np.linspace(238, 272, 14)) + [274, 276] + list(np.linspace(280, 318, 11)) + [332, 346.5454545, 355]
    # v2.0: p50 85 min, p95 112 min; ETL incremental de 60 min.
    v2 = list(np.linspace(72, 84, 14)) + [84.5, 85.5] + list(np.linspace(88, 104, 11)) + [108, 115.2727273, 121]
    return pd.concat([_nights(v1, 40, rng, "v1"), _nights(v2, 60, rng, "v2")], ignore_index=True)


def _shape_latency(base: np.ndarray, anchors: dict) -> np.ndarray:
    """Transformación monótona que fija p50, p95 y p99 en los valores objetivo."""
    qs = [0.0, 0.5, 0.95, 0.99, 1.0]
    src = np.quantile(base, qs)
    dst = [anchors["min"], anchors["p50"], anchors["p95"], anchors["p99"], anchors["max"]]
    return np.interp(base, src, dst)


def make_api_requests(rng: np.random.Generator) -> pd.DataFrame:
    frames = []
    specs = {
        "v1": {"lat": {"min": 60, "p50": 180, "p95": 420, "p99": 950, "max": 2400}, "err": 0.018, "cache": 0.0},
        "v2": {"lat": {"min": 4, "p50": 18, "p95": 85, "p99": 160, "max": 420}, "err": 0.002, "cache": 0.92},
    }
    for version, sp in specs.items():
        base = rng.lognormal(mean=0, sigma=0.8, size=API_REQUESTS)
        latency = _shape_latency(base, sp["lat"])
        # Las consultas resueltas en caché son las más rápidas; las demás llegan al modelo.
        order = np.argsort(np.argsort(latency))
        cache_hit = (order < round(sp["cache"] * API_REQUESTS)).astype(int)
        is_error = _exact_flags(rng, API_REQUESTS, round(sp["err"] * API_REQUESTS))
        frames.append(pd.DataFrame({"model_version": version, "request_id": np.arange(API_REQUESTS),
                                    "latency_ms": latency.round(2), "cache_hit": cache_hit, "is_error": is_error}))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    cfg = load_configs("base")
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    backtest = make_backtest(rng, cfg["governance"]["groups"])
    nights = make_batch_nights(rng)
    api = make_api_requests(rng)

    backtest.to_csv(DATA_DIR / "backtest.csv", index=False)
    nights.to_csv(DATA_DIR / "batch_nights.csv", index=False)
    api.to_csv(DATA_DIR / "api_requests.csv", index=False)

    print("Datos simulados generados:")
    print(f"- {DATA_DIR / 'backtest.csv'}  ({len(backtest):,} filas)")
    print(f"- {DATA_DIR / 'batch_nights.csv'}  ({len(nights)} filas)")
    print(f"- {DATA_DIR / 'api_requests.csv'}  ({len(api):,} filas)")


if __name__ == "__main__":
    main()

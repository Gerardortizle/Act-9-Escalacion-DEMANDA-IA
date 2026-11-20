"""Dashboard de escalamiento responsable: costo, SLA, fairness y crecimiento.

Lee los reportes de outputs/ y genera outputs/dashboard.png
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import OUTPUT_DIR, load_json

RED, GREEN, GREY = "#B03A2E", "#1E6B45", "#5B6770"


def main() -> None:
    for f in ("cost_report.json", "performance_report.json", "fairness_report.json"):
        if not (OUTPUT_DIR / f).exists():
            raise FileNotFoundError(f"Falta outputs/{f}. Ejecuta primero src/run_pipeline.py")
    cost = load_json(OUTPUT_DIR / "cost_report.json")
    perf = load_json(OUTPUT_DIR / "performance_report.json")
    fair = load_json(OUTPUT_DIR / "fairness_report.json")
    gate_path = OUTPUT_DIR / "gate_decision.json"
    gate = load_json(gate_path)["decision"] if gate_path.exists() else "sin evaluar"

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f"DEMANDA-IA · escalamiento responsable · escenario {cost['scenario']} · gate: {gate}",
                 fontsize=14, fontweight="bold")

    # 1. Costo por categoría
    ax = axes[0, 0]
    cats = [c["category"] for c in cost["by_category"]]
    x = np.arange(len(cats))
    ax.bar(x - 0.2, [c["v1_usd"] for c in cost["by_category"]], 0.4, label="v1.0", color=RED)
    ax.bar(x + 0.2, [c["v2_usd"] for c in cost["by_category"]], 0.4, label="v2.0", color=GREEN)
    ax.set_xticks(x, cats, rotation=30, ha="right")
    ax.set_ylabel("USD / mes")
    ax.set_title(f"Costo mensual: USD {cost['v1_monthly_usd']:,.0f} → {cost['v2_monthly_usd']:,.0f} (−{cost['savings_pct']:.1f} %)")
    ax.legend()

    # 2. SLA: valor observado como % del objetivo (≤100 % es bueno para 'max'; ≥100 % para 'min')
    ax = axes[0, 1]
    v2 = [c for c in perf["sla_checks"] if c["version"] == "v2"]
    names = [c["metric"] for c in v2]
    ratio = [100 * c["value"] / c["target"] for c in v2]
    colors = [GREEN if c["pass"] else RED for c in v2]
    ax.barh(names, ratio, color=colors)
    ax.axvline(100, color=GREY, ls="--")
    ax.set_xlabel("Observado / objetivo del SLA (%)")
    ax.set_title("SLA de v2.0 (verde = cumple)")
    ax.invert_yaxis()

    # 3. Fairness: indicadores C frente a A
    ax = axes[1, 0]
    ind = ["tpr_ratio", "essential_stockout_ratio", "fill_rate_ratio", "precision_ratio", "fpr_ratio"]
    labels = ["TPR C/A", "Quiebre esenciales C/A", "Fill rate C/A", "Precisión C/A", "FPR C/A"]
    v1i = fair["versions"]["v1"]["indicators"]; v2i = fair["versions"]["v2"]["indicators"]
    thr = {c["indicator"]: c["threshold"] for c in fair["versions"]["v2"]["checks"]}
    x = np.arange(len(ind))
    ax.bar(x - 0.2, [v1i[k] for k in ind], 0.4, label="modelo v1", color=RED)
    ax.bar(x + 0.2, [v2i[k] for k in ind], 0.4, label="modelo v2", color=GREEN)
    ax.scatter(x, [thr[k] for k in ind], marker="_", s=900, color="black", label="umbral", zorder=3)
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_title(f"Fairness grupo C vs A (modelo desplegado: {fair['deployed_model']})")
    ax.legend()

    # 4. Crecimiento
    ax = axes[1, 1]
    g = cost["growth"]
    n = [r["branches"] for r in g]
    ax.plot(n, [r["cost_v1_usd"] for r in g], marker="o", color=RED, label="v1.0 (vertical)")
    ax.plot(n, [r["cost_v2_usd"] for r in g], marker="o", color=GREEN, label="v2.0 (horizontal)")
    for r in g:
        ax.annotate(f"{r['workers_v2']} workers", (r["branches"], r["cost_v2_usd"]), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8, color=GREEN)
    ax.set_xlabel("Sucursales")
    ax.set_ylabel("USD / mes")
    ax.set_title("Costo al crecer la cadena")
    ax.legend()

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = OUTPUT_DIR / "dashboard.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Dashboard generado: {out}")


if __name__ == "__main__":
    main()

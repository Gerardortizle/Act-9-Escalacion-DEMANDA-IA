"""Pruebas de consistencia: el código debe reproducir las cifras del anexo técnico."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import capacity_planner  # noqa: E402
import cost_model  # noqa: E402
import fairness_audit  # noqa: E402
import governance_gate  # noqa: E402
import performance_report  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def demo_data():
    if not (ROOT / "data" / "backtest.csv").exists():
        subprocess.run([sys.executable, str(ROOT / "data" / "generate_demo_data.py")], check=True)


def test_costos_coinciden_con_anexo():
    rep = cost_model.run("base")
    assert rep["v1_monthly_usd"] == pytest.approx(4260.50, abs=0.01)
    assert rep["v2_monthly_usd"] == pytest.approx(1395.22, abs=0.01)
    assert rep["savings_pct"] == pytest.approx(67.3, abs=0.05)
    assert rep["v2_cost_per_million_usd"] == pytest.approx(2.97, abs=0.01)


def test_sensibilidad():
    assert cost_model.run("spot_conservador")["v2_monthly_usd"] == pytest.approx(1983.86, abs=0.01)
    assert cost_model.run("spot_pesimista")["v2_monthly_usd"] == pytest.approx(2395.74, abs=0.01)


def test_crecimiento_horizontal():
    plan = capacity_planner.plan(180)
    assert plan["v2"]["workers"] == 31
    assert not plan["v1"]["fits_window"]
    assert cost_model.run("crecimiento_180")["v2_monthly_usd"] == pytest.approx(1453.29, abs=0.01)


def test_sla_v2():
    rep = performance_report.run("base")
    v2 = rep["versions"]["v2"]
    assert v2["batch_p50_min"] == pytest.approx(85, abs=0.5)
    assert v2["batch_p95_min"] == pytest.approx(112, abs=0.5)
    assert v2["api_p95_ms"] == pytest.approx(85, abs=0.5)
    assert rep["v2_meets_sla"] and not rep["v1_meets_sla"]


def test_fairness_indicadores():
    rep = fairness_audit.run("base")
    v1, v2 = rep["versions"]["v1"]["indicators"], rep["versions"]["v2"]["indicators"]
    assert v1["wape_gap_pp"] == pytest.approx(11.7, abs=0.1)
    assert v2["wape_gap_pp"] == pytest.approx(4.6, abs=0.1)
    assert v2["tpr_ratio"] == pytest.approx(0.93, abs=0.01)
    assert v2["essential_stockout_ratio"] == pytest.approx(1.45, abs=0.01)
    assert v2["fpr_ratio"] > 1.25  # riesgo residual aceptado


@pytest.mark.parametrize("scenario,expected", [
    ("base", "APROBADO"),
    ("crecimiento_180", "APROBADO"),
    ("spot_pesimista", "BLOQUEADO"),
    ("sesgo_sin_mitigacion", "BLOQUEADO"),
    ("cache_caido", "BLOQUEADO"),
])
def test_gate(scenario, expected):
    assert governance_gate.decide(scenario, "full_rollout")["decision"] == expected

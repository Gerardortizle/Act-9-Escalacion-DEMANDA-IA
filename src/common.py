"""Utilidades compartidas: rutas, configuración, escenarios, logs y trazas."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"

SCENARIOS = {
    "base": {
        "description": "Rediseño v2.0 con los supuestos del anexo técnico.",
    },
    "spot_conservador": {
        "description": "La mitad de las horas spot cae a bajo demanda, no se firma el compromiso y el batch tarda 2.5 h.",
        "levers": {"cpu_ondemand_fallback_share": 0.50, "gpu_ondemand_fallback_share": 0.50,
                   "commitment_discount": 0.0, "batch_hours_per_night": 2.5},
    },
    "spot_pesimista": {
        "description": "Sin capacidad spot, sin compromiso y batch de 3 h.",
        "levers": {"cpu_ondemand_fallback_share": 1.0, "gpu_ondemand_fallback_share": 1.0,
                   "commitment_discount": 0.0, "batch_hours_per_night": 3.0},
    },
    "crecimiento_180": {
        "description": "La cadena crece a 180 sucursales; v2.0 agrega workers en proporción.",
        "operation": {"branches": 180},
    },
    "sesgo_sin_mitigacion": {
        "description": "Se despliega la infraestructura v2.0 pero sin las mitigaciones de sesgo (modelo v1.0).",
        "fairness_model": "v1",
    },
    "cache_caido": {
        "description": "La caché Redis no responde: todas las consultas llegan al microservicio del modelo.",
        "cache_available": False,
    },
}


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_configs(scenario: str = "base") -> dict:
    """Carga los tres archivos de configuración y aplica el escenario elegido."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Escenario desconocido: {scenario}. Opciones: {', '.join(SCENARIOS)}")
    cfg = {
        "scaling": load_json(CONFIG_DIR / "scaling_config.json"),
        "sla": load_json(CONFIG_DIR / "sla_config.json"),
        "governance": load_json(CONFIG_DIR / "governance_config.json"),
    }
    cfg = copy.deepcopy(cfg)
    sc = SCENARIOS[scenario]
    cfg["scaling"]["levers"].update(sc.get("levers", {}))
    cfg["scaling"]["operation"].update(sc.get("operation", {}))
    cfg["scenario"] = {
        "name": scenario,
        "description": sc["description"],
        "fairness_model": sc.get("fairness_model", "v2"),
        "cache_available": sc.get("cache_available", True),
    }
    return cfg


def check(value: float, rule: dict, key: str = "target") -> bool:
    """True si el valor cumple la regla (direction max/min)."""
    limit = float(rule[key])
    return value <= limit if rule["direction"] == "max" else value >= limit


def log_event(event: str, payload: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    line = {"timestamp": time.time(), "event": event, **payload}
    with (OUTPUT_DIR / "pipeline_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def write_trace(trace_id: str, stage: str, duration_ms: float, status: str = "ok") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    line = {"trace_id": trace_id, "stage": stage, "duration_ms": round(duration_ms, 3),
            "status": status, "timestamp": time.time()}
    with (OUTPUT_DIR / "traces.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

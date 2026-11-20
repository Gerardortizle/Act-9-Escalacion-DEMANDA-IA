param(
    [ValidateSet("data", "pipeline", "pilot", "costs", "capacity", "performance", "fairness", "spot", "growth", "bias", "cache", "scenarios", "dashboard", "test", "ui")]
    [string]$Step = "pipeline"
)

$ErrorActionPreference = "Stop"
$PY = ".\.venv\Scripts\python.exe"
$env:MLFLOW_DISABLE_AGENT_HINT = "1"

switch ($Step) {
    "data"        { & $PY data\generate_demo_data.py }
    "pipeline"    { & $PY src\run_pipeline.py --scenario base --phase full_rollout }
    "pilot"       { & $PY src\run_pipeline.py --scenario base --phase pilot }
    "costs"       { & $PY src\cost_model.py }
    "capacity"    { & $PY src\capacity_planner.py }
    "performance" { & $PY src\performance_report.py }
    "fairness"    { & $PY src\fairness_audit.py }
    "spot"        { & $PY src\run_pipeline.py --scenario spot_pesimista }
    "growth"      { & $PY src\run_pipeline.py --scenario crecimiento_180 }
    "bias"        { & $PY src\run_pipeline.py --scenario sesgo_sin_mitigacion }
    "cache"       { & $PY src\run_pipeline.py --scenario cache_caido }
    "scenarios"   { & $PY src\simulate_scenarios.py }
    "dashboard"   { & $PY src\dashboard.py }
    "test"        { & $PY -m pytest -q tests }
    "ui"          { & $PY -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000 }
}

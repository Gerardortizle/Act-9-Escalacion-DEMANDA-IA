"""Plantilla para conectar DEMANDA-IA con datos reales en lugar de los simulados.

El resto del código espera tres tablas con estas columnas. Si tienes la exportación
del ERP y del backtest real, transfórmalas aquí y guárdalas en data/.

backtest.csv
    model_version, group, branch_id, sku_id, week, essential,
    demand_units, forecast_units, served_units,
    stockout_essential, stockout_event, alert_flag

batch_nights.csv
    model_version, night, etl_minutes, batch_minutes, delivery_minutes_after_23h

api_requests.csv
    model_version, request_id, latency_ms, cache_hit, is_error

Reglas:
- `group` sale del índice de marginación (CONAPO) del municipio de la sucursal: A, B o C.
- No incluyas datos de clientes ni de pacientes: trabaja con ventas agregadas por SKU,
  sucursal y semana (LFPDPPP, riesgo R05 de la Actividad 3).
- En los días con quiebre, `demand_units` debe ser la demanda reconstruida, no la venta
  registrada (riesgo R01).
"""
from __future__ import annotations

import pandas as pd


def build_backtest(erp_sales: pd.DataFrame, forecasts: pd.DataFrame, branch_groups: pd.DataFrame) -> pd.DataFrame:
    """Ejemplo de unión: ventas reales + pronósticos + grupo de cada sucursal."""
    df = erp_sales.merge(forecasts, on=["branch_id", "sku_id", "week"]).merge(branch_groups, on="branch_id")
    required = ["model_version", "group", "branch_id", "sku_id", "week", "essential", "demand_units",
                "forecast_units", "served_units", "stockout_essential", "stockout_event", "alert_flag"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas para el backtest: {missing}")
    return df[required]

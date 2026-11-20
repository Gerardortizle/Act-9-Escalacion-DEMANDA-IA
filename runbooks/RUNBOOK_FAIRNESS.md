# Runbook - Indicador de fairness fuera de umbral

## 1. Señal que activa el runbook
- Métricas: `tpr_ratio`, `essential_stockout_ratio`, `wape_gap_pp`, `underforecast_abs_mfe`, `fill_rate_ratio`
  (grupo C frente a grupo A) en `outputs/fairness_report.json`.
- Umbral: los de `config/governance_config.json`. Prioridad "prioritaria" o "alta".
- Severidad: P1 si falla `tpr_ratio` o `essential_stockout_ratio` (acceso a medicamentos esenciales); P2 en los demás.
- Reproducir: `python src/run_pipeline.py --scenario sesgo_sin_mitigacion`.

## 2. Impacto esperado
Sucursales rurales con quiebres repetidos de insulina, antihipertensivos u otros esenciales.
El sistema no decide sobre personas, pero sí reparte disponibilidad de medicamentos entre comunidades.

## 3. Diagnóstico inicial
1. Revisar qué indicador falló y desde qué reentrenamiento.
2. Confirmar que la reconstrucción de demanda censurada (R01) se ejecutó en el pipeline de datos.
3. Revisar si la función de pérdida volvió a ponderarse por ingreso (R04).
4. Separar drift real (PSI > 0.2 en la región) de un error del pipeline.

## 4. Acción principal
- El gate bloquea la promoción del modelo; el orquestador mantiene la versión aprobada anterior.
- Mientras se corrige: revisión humana obligatoria del pedido en sucursales del grupo C.
- Corregir la mitigación faltante y reentrenar; volver a pasar el backtest por grupo.

## 5. Validación de recuperación
Todos los indicadores prioritarios y altos en verde en el backtest y durante 2 semanas en producción.

## 6. Evidencia a conservar
`fairness_report.json`, `gate_decision.json`, run de MLflow, acta del oficial de ética.

## 7. Mejora posterior
Agregar la prueba que faltó al pipeline de entrenamiento para que el error no llegue al gate.

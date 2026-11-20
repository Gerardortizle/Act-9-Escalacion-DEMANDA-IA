# Runbook - Costo fuera de meta (falta de capacidad spot o compromiso sin firmar)

## 1. Señal que activa el runbook
- Métrica: `costo_por_millon_usd` del gate o `ahorro_vs_v1_pct` del tablero FinOps.
- Umbral: costo por millón > USD 3.25 en operación (> 3.50 en el piloto) o ahorro < 50 %.
- Severidad: P2 (no afecta el servicio, sí el caso de negocio).
- Reproducir: `python src/run_pipeline.py --scenario spot_conservador` o `--scenario spot_pesimista`.

## 2. Impacto esperado
El pedido sigue llegando a tiempo, pero el ahorro frente a v1.0 cae. Con el escenario pesimista
(sin spot y sin compromiso) el ahorro baja a 43.8 % y el gate bloquea el despliegue total.

## 3. Diagnóstico inicial
1. Revisar en `outputs/cost_lines.csv` qué renglones subieron (batch, ETL o reentrenamiento).
2. Confirmar la fracción de horas que cayó a bajo demanda en las últimas 4 semanas.
3. Verificar si el compromiso de 1 año para la API y la base de datos ya está firmado.

## 4. Acción principal
- Si falta spot: ampliar el pool a otras familias de instancia y a otra zona antes de pagar bajo demanda.
- Si falta el compromiso: presentar a Finanzas las 8 semanas de consumo base estable y firmarlo.
- Si el batch tarda más: revisar particiones desbalanceadas antes de agregar workers.

## 5. Validación de recuperación
Costo por millón ≤ USD 3.25 y ahorro ≥ 50 % durante 4 semanas seguidas en el tablero FinOps.

## 6. Evidencia a conservar
`cost_report.json` antes y después, captura del tablero FinOps, decisión de Finanzas.

## 7. Mejora posterior
Alertas de presupuesto al 80 % y 100 % por etiqueta `component`; revisión semanal FinOps.

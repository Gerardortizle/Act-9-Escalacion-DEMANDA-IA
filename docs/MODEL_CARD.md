# Model card · DEMANDA-IA v2.0

| Campo | Contenido |
|---|---|
| Propósito | Pronosticar la demanda por SKU y sucursal a 14 días para generar el pedido sugerido del ERP |
| Usuarios | Área de compras y gerentes de sucursal (revisión humana del pedido) |
| Fuera de alcance | Decisiones sobre personas; pedido automático de medicamentos controlados (grupos I–III) |
| Modelo | Ensamble LightGBM + Temporal Fusion Transformer, exportado a ONNX INT8 con pruning de 30 % |
| Datos | Ventas agregadas por SKU, sucursal y día; demanda reconstruida en días con quiebre; sin datos personales |
| Reentrenamiento | Mensual, o antes si el PSI de una región supera 0.2 |
| Clasificación de riesgo | Mínimo según el AI Act; tratado internamente como de alto impacto por el acceso a medicamentos |

## Métricas (backtest de 26 semanas)

| Indicador | v1.0 | v2.0 | Umbral |
|---|---|---|---|
| WAPE global | 18.7 % | 17.7 % | ≤ 22 % |
| Brecha de WAPE C − A | 11.7 pp | 4.6 pp | ≤ 5 pp |
| Razón de TPR de alerta C/A | 0.71 | 0.93 | ≥ 0.80 |
| Razón de quiebre de esenciales C/A | 3.90 | 1.45 | ≤ 1.50 |
| Razón de fill rate C/A | 0.90 | 0.98 | ≥ 0.98 |
| Razón de FPR C/A | 0.80 | 1.83 | ≤ 1.25 (riesgo residual aceptado) |

Los valores se recalculan con `python src/fairness_audit.py`.

## Limitaciones conocidas
- Sucursales con menos de 6 meses de historia: revisión humana obligatoria durante 12 semanas.
- Eventos locales (fiestas patronales, temporada de dengue) se modelan con calendario, pero con menor precisión.
- El piso de stock de esenciales en el grupo C aumenta las alertas falsas (sobreinventario aceptado).

## Responsables
Ciencia de datos (modelo), MLOps (operación y reversión), oficial de ética y gobierno de IA (fairness),
responsable sanitario (controlados), comité de IA responsable (aprobación de cada versión).

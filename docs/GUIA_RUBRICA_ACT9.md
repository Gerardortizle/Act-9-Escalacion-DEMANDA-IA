# Correspondencia con la rúbrica de la Actividad 9

| Criterio | Evidencia en el reporte técnico | Evidencia en este repositorio |
|---|---|---|
| 1. Análisis y rediseño de escalabilidad | Secciones 1 y 2, Tablas 2–6, Figura 1, sección 3.4 | `src/capacity_planner.py`, `deployment/k8s/` (Job indexado y HPA horizontales, entrenamiento vertical acotado), `docs/img/diagrama_arquitectura.png` |
| 2. Optimización de costos y enfoque FinOps | Secciones 2.3–2.5 y 3.1–3.5, Tablas 7–12 | `src/cost_model.py`, `config/scaling_config.json`, escenarios `spot_conservador` y `spot_pesimista`, etiquetas FinOps en los manifiestos |
| 3. Auditoría de gobernanza, ética y cumplimiento | Sección 4, Tablas 13–20 | `src/fairness_audit.py`, `config/governance_config.json`, `docs/MODEL_CARD.md`, `runbooks/RUNBOOK_FAIRNESS.md` |
| 4. Plan de escalamiento responsable | Sección 5, Tablas 21–24 | `src/governance_gate.py` (gates como código), `src/run_pipeline.py`, escenario `sesgo_sin_mitigacion`, runbooks |

## Cómo demostrarlo en 5 minutos

```bash
bash demo.sh data
bash demo.sh pipeline     # escenario base: gate APROBADO
bash demo.sh bias         # sin mitigaciones de sesgo: gate BLOQUEADO
bash demo.sh scenarios    # tabla comparativa de todos los escenarios
bash demo.sh test         # las cifras coinciden con el anexo técnico
bash demo.sh ui           # runs en MLflow
```

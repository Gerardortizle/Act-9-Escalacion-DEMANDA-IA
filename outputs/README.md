# outputs/

Esta carpeta recibe la evidencia generada localmente:

- `cost_report.json` y `cost_lines.csv`: costo v1.0 vs v2.0, costo unitario y crecimiento.
- `capacity_plan.json`: workers necesarios y si el batch cabe en la ventana.
- `performance_report.json`: latencia, throughput y uso de recursos contra el SLA.
- `fairness_report.json`: métricas por grupo de marginación y umbrales de T22.
- `gate_decision.json`: decisión del gate de escalamiento (APROBADO / BLOQUEADO).
- `scenario_comparison.csv`: resultado de todos los escenarios.
- `dashboard.png`: tablero de costo, SLA, fairness y crecimiento.
- `pipeline_log.jsonl` y `traces.jsonl`: logs y trazas de cada corrida.

Los archivos de ejecución están excluidos de Git; se regeneran con `bash demo.sh pipeline`.

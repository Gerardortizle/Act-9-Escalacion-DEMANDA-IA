# Cómo adaptar la configuración

| Archivo | Qué controla | Cuándo cambiarlo |
|---|---|---|
| `scaling_config.json` | Sucursales, SKUs, tarifas de nube, uso de spot, compromiso, workers, metas FinOps | Cuando llegue la cotización real del proveedor o cambie el tamaño de la cadena |
| `sla_config.json` | Objetivos del SLA y métricas de plataforma observadas | Cuando se renegocie el SLA con compras o haya nuevas pruebas de carga |
| `governance_config.json` | Grupos de sucursales, umbrales de fairness, riesgos aceptados y reglas de los gates | Cuando el comité de IA responsable apruebe nuevos umbrales |

## Ejemplos

Probar otra tarifa spot:

```json
"cpu_node_spot_hour": 0.15
```

Exigir que el gate del piloto también pida el 50 % de ahorro:

```json
"pilot": { "require_min_savings": true }
```

Los valores actuales son los del escenario simulado de la Actividad 9. **No los copies a un caso real sin justificarlos.**

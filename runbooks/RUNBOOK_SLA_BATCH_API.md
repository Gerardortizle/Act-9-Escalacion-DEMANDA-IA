# Runbook - SLA en riesgo (batch nocturno o API de consulta)

## 1. Señal que activa el runbook
- Métricas: `batch_p95_min`, `on_time_nights_pct`, `api_p95_ms`, `cache_hit_pct`, `api_availability_pct`.
- Umbral: los de `config/sla_config.json` (p. ej. batch p95 ≤ 330 min, API p95 ≤ 300 ms, caché ≥ 85 %).
- Severidad: P1 si el pedido no llega al ERP antes de las 05:00; P2 en la API.
- Reproducir: `python src/run_pipeline.py --scenario cache_caido`.

## 2. Impacto esperado
Batch tarde: las sucursales reciben el pedido sugerido después del ciclo de compra.
Caché caída: toda consulta llega al microservicio; la latencia sube y la API escala a su máximo.

## 3. Diagnóstico inicial
1. Revisar `outputs/traces.jsonl` para ver qué etapa se alargó.
2. Batch: contar particiones reintentadas y nodos spot perdidos.
3. API: confirmar el estado de Redis y la tasa de aciertos de caché.

## 4. Acción principal
- Batch: el orquestador lanza nodos bajo demanda a los 10 min si no hay spot; si a las 04:00 no terminó,
  se publica el pedido del día anterior ajustado y se avisa a compras.
- API: failover de Redis a la réplica; precargar la caché con los pronósticos publicados.

## 5. Validación de recuperación
Batch p95 ≤ 330 min y 100 % de noches a tiempo durante 7 noches; API p95 ≤ 300 ms y caché ≥ 85 % durante 24 h.

## 6. Evidencia a conservar
`performance_report.json`, trazas, captura del dashboard, registro del incidente.

## 7. Mejora posterior
Alertas por presupuesto de error del SLA y prueba de carga trimestral.

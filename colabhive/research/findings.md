# Hallazgos — pruebas reales contra ColabHive (2026-09-17)

Cliente: Mac M2 → `https://api.colabhive.com/v1`, streaming, `scripts/smoke_test.py`.
Datos crudos: `research/live/smoke-*.json` / `*.log`.

## Resultados

| | gpt-oss-20b | Qwen3-Coder-30B-A3B (AWQ) |
|---|---|---|
| Estado inicial | cached (5 nodos) | cached (3 nodos) |
| **Warmup cached → primer token** | **197 s** | **444 s** |
| Tool calling (streaming) | ✅ `read_file({"path","start_line"})`, `finish=tool_calls` | ✅ idem |
| Stream mode | `live` | `live` |
| TTFT warm (5 requests chicas, mediana) | 3.5 s | 3.6 s |
| Velocidad de generación warm | ~179 tok/s | ~141 tok/s |
| Reasoning separado | sí (`reasoning_content`) | no aplica |

Baseline de red: TCP connect ~0.22 s, TLS ~0.45 s, `/health` TTFB ~0.67 s, `/v1/models` ~0.78 s.

## Conclusiones

1. **Tool calling OK** en ambos modelos vía la API OpenAI-compatible con streaming → compatible con OpenCode.
2. **Warmup de 3–7 min incluso desde cached.** Obligatorio fijar los modelos del equipo
   (`scaling_mode: minimum`, `min_replicas >= 1`, `required_node_ids`).
3. **Overhead fijo de ~3.5 s por request con el modelo warm**, independiente del modelo y del tamaño del prompt
   (prompt de ~10 tokens, 40 max_tokens). Red + TLS explican ~0.7 s; **~2.8 s son dispatch
   gateway → orchestrator → node (WebSocket) → container**.
   - OpenCode hace una request por cada paso del loop de herramientas: una tarea de 30 pasos
     suma ~1:45 min solo de overhead, más la generación.
   - Es el principal cuello de botella para la experiencia de agente, más que la velocidad de los modelos.
4. La generación en sí es rápida (140–180 tok/s): los modelos MoE chicos van bien como coder/worker.

## Acciones sugeridas para la plataforma (equipo ColabHive)

- Fast path para LLMs warm: ruteo directo/sticky del gateway al replica residente sin pasar por la cola de tasks.
- Medir dónde se van los ~2.8 s (auth, scheduling, WebSocket round-trip, container proxy).
- Exponer parámetros de serving por modelo (tool/reasoning parser, max_model_len, TP) en la API pública.
- Reportar tiempos de carga medidos en `/inference/models?include_readiness=true` (hoy `estimated_latency_ms` es fijo por estado: 300/8000/60000).
- Documentar/exponer la ruta de nodos (UUIDs para `required_node_ids`) y el token HF en la Builder API.

## Re-medición 20:29 (misma sesión, ~7 h después)

Ambos modelos siguen `warm` (1 nodo cada uno). Cola vacía.

| | mediana TTFT | rango |
|---|---|---|
| gpt-oss-20b | 3.3 s | 2.8 – 7.4 s |
| Qwen3-Coder-30B | 4.3 s (10 requests) | 3.6 – 8.6 s |

- Gateway solo (`/v1/models`, sin nodo): 0.76–0.95 s, con TLS nuevo cada vez (~0.45 s).
- El overhead de dispatch no bajó y ahora además **es inestable**: ~1 de cada 3 requests salta a 7–8.5 s.
- Churn de residencia: a las 13:00 había 41 modelos `cached`; a las 20:29 quedan 13, con 71 `cold`.
  Los modelos se desalojan solos → otra razón para fijar los del equipo con `scaling_mode: minimum`.

## Prefix caching — activado y verificado (2026-09-20, 22:15 UTC)

Qwen3.8-27B FP8 (1af07b1f), prompt de 55k tokens, prefijo único por corrida:

| caso | TTFT | cached_tokens |
|---|---|---|
| prefijo nuevo (frío) | 42.8 s | 0 |
| el mismo, repetido | 2.7 s | 100% |
| **mismo prefijo, final distinto** | **2.6 s** | 100% |
| **prefijo + 500 palabras nuevas** | **3.1 s** | 99% |

16× más rápido, y sirve para el caso real de un agente (historial que crece).
`usage.prompt_tokens_details.cached_tokens` ya se reporta.
Impacto: una tarea de 30 pasos con 55k de contexto pasa de ~21 min de prefill a ~2 min.

Notas de la jornada:
- Ventana del 27B: 36.736 → 127.552 (el reemplazo cuesta un warm de ~20 min).
- Qwen3-Coder-30B declara 223.680; gpt-oss-20b 126.357.
- Tope de payload del gateway: 1 MB → 3.9 MB.
- `/v1/models` ahora trae `max_model_len` + `max_model_len_source` (resident/configured).
- gpt-oss-20b hace prefill a ~21.000 tok/s; el 27B, a ~1.280 tok/s (17×). Con caching
  importa menos, pero sigue abierto en qué nodo corre cada uno.

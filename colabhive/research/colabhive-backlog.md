# ColabHive — backlog para uso como backend de agentes de código (OpenCode)

Evidencia: `research/findings.md` + `research/live/*.json` (mediciones 2026-09-17/18 desde un Mac en
Argentina contra `api.colabhive.com`, streaming, modelos warm, prompt de 1 token).

Estado actual tras el wheel nuevo: TTFT mediana 1.2–2.2 s (keep-alive: 1.8 s en Qwen3-Coder-30B).
Red ida y vuelta: ~0.22 s. Prefill con prompt corto: ~0 s. **Queda ~1 s de overhead de plataforma.**
Objetivo razonable: **0.4–0.6 s de TTFT**.

---

## P0 — Instrumentación (sin esto, lo demás es adivinar)

1. **Header `X-Timing` (o `Server-Timing`) en `/v1/chat/completions`** con los tramos:
   `auth`, `endpoint_resolve`, `schedule`, `node_dispatch` (round-trip WS), `container_connect`,
   `model_ttft`. Permite al cliente ver dónde se va el segundo, sin acceso al cluster.
2. **Histogramas Prometheus por tramo** (no solo latencia total) y por nodo/modelo.
3. **Correlación**: `X-Request-ID` ya existe en Builder; propagarlo al node runtime y al log del container.

Sin (1) no se puede cerrar el gap de ~1 s desde afuera; es lo primero.

## P0 — Hot path para chat con réplica warm

El camino actual (gateway → orchestrator → WS al nodo → container) paga scheduling y un salto extra
en **cada** request, incluso cuando hay una réplica residente y ociosa.

4. **Fast path**: si el endpoint tiene réplica `warm` y no está saturada, proxy directo
   gateway → container, sin pasar por la cola de tasks ni por una decisión de scheduling completa.
5. **Cache en memoria del mapeo** `endpoint_id → (node, container, url)` con TTL corto + invalidación
   por evento, para no resolver config/DB por request.
6. **Cache de auth** (hash de API key → cuenta/permisos) con TTL, en vez de ir a la DB cada vez.
7. **Pool de conexiones persistentes** gateway→nodo (HTTP/2 o WS multiplexado ya abierto), en vez de
   negociar por request; `TCP_NODELAY` en el proxy de streaming.
8. **Passthrough real del stream**: verificar que no haya buffering intermedio que retenga el primer chunk.

## P1 — Lo que más rinde para agentes de código

9. **Prefix caching de vLLM activado y visible.** Un agente manda el mismo system prompt + historia
   creciente en cada paso: con prefix caching el prefill deja de pagarse entero cada vez.
   Reportar `usage.prompt_tokens_details.cached_tokens` (formato OpenAI) para poder medirlo.
10. **Sticky routing por conversación**: rutear las requests de una misma sesión a la misma réplica
    (hash de un `session_id` o del prefijo del prompt). Sin esto, el prefix cache se pierde al saltar de nodo.
11. **Exponer parámetros de serving por modelo** en el registro/import: `max_model_len`,
    `tool_call_parser`, `reasoning_parser`, `tensor_parallel_size`, `gpu_memory_utilization`,
    `enable_prefix_caching`, `chunked_prefill`. Hoy no hay forma pública de setearlos y el tool calling
    depende de que el parser coincida con el modelo.
12. **Contexto real en el catálogo**: `/v1/models` y `/inference/models` no devuelven `max_model_len`.
    OpenCode necesita el límite para decidir cuándo compactar.

## P1 — Residencia y warmup

Medido: de `cached` a warm, **197 s (gpt-oss-20b)** y **444 s (Qwen3-Coder-30B)**. Churn alto:
41 modelos `cached` a las 13:00 → 13 a las 20:29, con 71 en `cold`.

13. **Fijar modelos desde la Console** (hoy `scaling_mode: minimum` + `required_node_ids` es solo API).
14. **Ruta pública para listar nodos** (UUID, GPUs, VRAM, estado). Sin ella no se puede usar
    `required_node_ids`, que es justamente lo que evita el churn.
15. **Política de eviction que respete lo fijado** y que no desaloje por modelos de un solo uso.
16. **`estimated_latency_ms` real**: hoy es un valor fijo por estado (300/8000/60000). Reportar la
    carga medida por modelo/nodo (p50/p95) sirve para decidir timeouts y para elegir modelo.
17. **Pre-warm explícito**: `POST /endpoints/{id}/warm` (idempotente) en vez de tener que mandar una
    inferencia trucha.
18. **Cachear `/inference/models?include_readiness=true`**: llegó a tardar 11.2 s para 91 modelos.

## P1 — Deploys sin tirar la inferencia

Durante un deploy medimos TTFT de 20–500 s y modelos que no devolvían tokens.

19. **Drain/cordon por nodo** y rolling deploy: sacar el nodo de la rotación, esperar a que termine lo
    que tiene, actualizar, devolverlo. Nunca todos a la vez.
20. **Failover a otra réplica** cuando un nodo deja de responder, en vez de esperar el timeout.
21. **Hedging opcional**: si no hay primer token en N segundos y existe otra réplica warm, disparar copia.
22. **Estado de deploy visible** (`/health` o status page) para que los clientes sepan que la
    degradación es esperada.

## P2 — Documentación y consistencia

23. **Nombres del catálogo que mienten**: `hf-Qwen-Qwen3-Coder-30B-A3B-Instruct-FP8` sirve
    `QuantTrio/...-AWQ`; `hf-microsoft-phi-4` sirve `phi-4-mini-instruct`.
24. **Token de HF para modelos gated**: la ruta existe solo en el Orchestrator
    (`/api/v1/inference/credentials/huggingface`), sin base URL pública documentada.
25. **Import de HF desde la Console** (hoy es solo API/SDK).
26. **Imports siempre `visibility=public`**: documentar por qué, y permitir privado por cuenta.
27. **Self-host**: docs dicen "pausado", home y pricing siguen ofreciendo MIT self-hosting.
28. **Guía de OpenCode**: agregar el caso de agentes (varios modelos, subagentes, timeouts,
    manejo de 503/Retry-After) y aclarar que Claude Code habla protocolo Anthropic, no OpenAI.

---

## Los 5 primeros, en orden

1. `X-Timing` por tramo (P0-1) — habilita todo lo demás.
2. Fast path para réplicas warm + caches de auth/resolución (P0-4,5,6).
3. Prefix caching + sticky routing por sesión (P1-9,10) — el mayor impacto en agentes reales.
4. Ruta de nodos + fijar modelos desde la Console (P1-13,14).
5. Rolling deploy con drain (P1-19).

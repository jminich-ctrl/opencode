# Hallazgos — pruebas reales contra ColabHive

Mediciones hechas desde afuera, como cliente: un Mac M2 contra `https://api.colabhive.com/v1`,
con streaming. **Cada número tiene fecha y la plataforma cambió desde entonces**: antes de
decidir algo con estos datos, volvé a medir con los scripts de `../scripts/`
(`smoke_test.py`, `check_cache.py`, `concurrencia.py`). Los datos crudos que genera
`smoke_test.py` quedan en `research/live/`, que no se versiona.

## 2026-09-17 · Primer contacto

`scripts/smoke_test.py`, dos modelos que arrancaron en estado `cached`.

| | gpt-oss-20b | Qwen3-Coder-30B-A3B (AWQ) |
|---|---|---|
| **De `cached` al primer token** | **197 s** | **444 s** |
| Tool calling (streaming) | ✅ `read_file({"path","start_line"})`, `finish=tool_calls` | ✅ idem |
| TTFT con el modelo caliente (mediana de 5) | 3.5 s | 3.6 s |
| Velocidad de generación | ~179 tok/s | ~141 tok/s |
| Razonamiento separado | sí (`reasoning_content`) | no aplica |

Red: TCP ~0.22 s, TLS ~0.45 s, `/v1/models` ~0.78 s.

Lo que sacamos:

1. **El tool calling anda** en los dos modelos por la API compatible con OpenAI, con
   streaming. Eso es lo que OpenCode necesita.
2. **Un modelo frío tarda minutos en despertar**, incluso desde `cached`. Antes de una tanda
   hay que calentarlo (`oc --warm`), o la primera tarea se come la espera.
3. **Cada paso del agente paga un costo fijo** además de la generación: ese día, ~3.5 s por
   request con el modelo caliente. OpenCode hace una request por cada paso del loop de
   herramientas, así que en una tarea de 30 pasos eso pesa más que la velocidad del modelo.
4. La generación en sí es rápida (140–180 tok/s): los MoE chicos van bien como ejecutores.

## 2026-09-18 · El costo fijo por paso bajó

Con la misma medición (prompt de 1 token, streaming, modelos calientes), después de una
actualización de la plataforma: **TTFT mediana 1.2–2.2 s**, y 1.8 s en Qwen3-Coder-30B
reutilizando la conexión (`scripts/keepalive_burst.py`).

## 2026-09-20 · Prefix caching, verificado

Qwen3.8-27B FP8, prompt de 55k tokens con un prefijo único por corrida
(`scripts/check_cache.py`):

| caso | TTFT | cached_tokens |
|---|---|---|
| prefijo nuevo (frío) | 42.8 s | 0 |
| el mismo, repetido | 2.7 s | 100% |
| **mismo prefijo, final distinto** | **2.6 s** | 100% |
| **prefijo + 500 palabras nuevas** | **3.1 s** | 99% |

16× más rápido, y vale para el caso real de un agente: un historial que crece.
`usage.prompt_tokens_details.cached_tokens` lo reporta en cada respuesta.
Una tarea de 30 pasos con 55k de contexto pasa de ~21 min de prefill a ~2 min.

Otras cosas de ese día:

- `/v1/models` trae `max_model_len` y `max_model_len_source` (`resident` = la réplica que
  está corriendo, `configured` = lo que declara el catálogo). `scripts/sync_limits.py` lo usa.
- **La ventana de un modelo puede cambiar cuando se reemplaza su réplica**: la del 27B pasó
  de 36.736 a 127.552; la de gpt-oss-20b, de 126.357 ese día a 75.904 el 21. Por eso `sync_limits.py`
  va en el chequeo previo a cada tanda.
- Prefill sin caché: gpt-oss-20b ~21.000 tok/s, el 27B ~1.280 tok/s. Con caching importa
  mucho menos.

## Septiembre 2026 · Concurrencia

La tabla está en [../../INFRAESTRUCTURA.md](../../INFRAESTRUCTURA.md). Una primera medición
(Qwen3-8B) daba cola recién pasadas las 16 requests; la del 2026-09-21 (gpt-oss-20b) muestra que una
réplica admite 8 a la vez y el resto espera turno. Por eso el runner lanza 8 por defecto.

## 2026-09-21 · Quién contesta primero

El mismo pedido 4 veces por modelo, mediana (pedido que pide una búsqueda con una herramienta, y un
título de 5 palabras):

| | tool call | título |
|---|---|---|
| gpt-oss-20b | 4/4 · **1.1 s** | **1.8 s** |
| Qwen3-8B | 4/4 · 12.8 s | 18.2 s |

Qwen3-8B era el modelo más chico del equipo y el más lento en contestar: razona antes de cada respuesta.
Por eso `explore`, `title` y `summary` pasaron a gpt-oss-20b, y el equipo quedó en tres modelos.
**El tamaño no predice la latencia; si el modelo delibera, sí.**

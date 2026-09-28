# Pedido a ColabHive: que la plataforma conozca la topología del nodo y la use

Contexto: el nodo Orion tiene 2× Xeon 6787P (Granite Rapids, 86 núcleos c/u, 344 hilos),
~1 TB de RAM en **4 nodos NUMA** (SNC2 activado) y 6× Arc Pro B70. Hoy la plataforma
levanta réplicas sin saber nada de eso, y ahí hay entre **1,5× y 7× de TTFT** tirados.

Evidencia: *"Characterizing CPU-Induced Slowdowns in Multi-GPU LLM Inference"*
(Georgia Tech, arXiv 2603.22774): el TTFT mejora 1,47–7,11× **solo asignando bien los
recursos de CPU**, sin agregar GPUs. Las GPUs quedan ociosas *"no porque estén saturadas,
sino porque los CPU no logran mantenerlas ocupadas"*. Señalan la tokenización como
*"particularmente problemática en serving agentic"*, que es exactamente el caso de OpenCode.

---

## 1. Que el nodo reporte su topología en el heartbeat

Hoy reporta hardware (VRAM, RAM). Falta lo que permite ubicar bien un proceso:

```json
"topologia": {
  "sockets": 2,
  "nucleos_fisicos": 172,
  "hilos": 344,
  "numa_nodes": [
    {"id": 0, "cpus": "0-42,172-214", "ram_mb": 257485, "gpus": ["0000:xx:00.0"]},
    {"id": 1, "cpus": "43-85,215-257", "ram_mb": 258019, "gpus": []}
  ],
  "snc": 2,
  "memoria": {"canales": 8, "tipo": "DDR5", "mts": 6400, "mrdimm": false},
  "cpu_flags": ["amx_tile", "amx_bf16", "amx_int8", "avx512_bf16", "avx512_fp16"]
}
```

Se obtiene con `lscpu`, `numactl -H`, `dmidecode -t memory` y, lo más importante,
la afinidad real de cada GPU:

```bash
cat /sys/class/drm/card*/device/numa_node      # a qué nodo NUMA cuelga cada placa
```

**El dato que más vale es el último.** Si un worker corre en el nodo 0 y su GPU cuelga
del socket 1, cada transferencia cruza el enlace entre sockets: la mitad de ancho de
banda y el triple de latencia (medido en otros Xeon: 554 GB/s local vs 247 GB/s cruzado,
130 ns vs 410–449 ns).

## 2. Que el scheduler use esa topología al levantar una réplica

1. **Fijar cada worker a los núcleos y la memoria del nodo NUMA de su GPU.**
   vLLM ya lo soporta: `--numa-bind` con el mapeo explícito de GPU a nodo.
2. **Nunca repartir un modelo entre sockets.** Una réplica en TP vive dentro de un
   socket, o el enlace entre sockets se convierte en el cuello.
3. **Reservar núcleos para el frontend de cada réplica** (tokenización, armado de
   prompts, streaming). Con 172 núcleos físicos sobra: ~8 por réplica y queda más de la
   mitad libre.
4. **Escalar el API server** (`--api-server-count`) cuando el procesamiento de entrada
   sea el cuello, que es el caso de los agentes con contexto largo.

## 3. Que la elección de backend mire los flags del CPU

Si el nodo tiene `amx_int8` / `amx_bf16`, hay trabajo que conviene mandar a CPU y hoy
ocupa GPU sin necesidad:

| Carga | Dónde | Por qué |
|---|---|---|
| **Embeddings** (indexado, ingesta) | **CPU con AMX INT8** | Queda en el orden de una A10. Libera una GPU entera |
| **Clasificadores / guardias** (BERT-class) | **CPU** | 12–14 ms por llamada |
| **Modelos chicos no interactivos** (títulos, resúmenes, ruteo) | **CPU**, 8B a ~30 tok/s | Le saca carga al modelo rápido de GPU |
| **Reranker** | **GPU** | En CPU tarda segundos: no va |
| **Cualquier modelo del loop de agentes** | **GPU** | El prefill en CPU es 20–75× más lento |

La plataforma ya tiene backends de CPU (`transformers-cpu`, `specialist-cpu-optimized`).
Falta que el scheduler los prefiera **cuando el nodo tiene AMX y la carga es de las de
arriba**, en vez de ocupar VRAM.

## 4. Data parallel antes que tensor parallel

En el nodo de 6 GPUs, **TP=6 es inusable**: TP tiene que dividir los KV heads, y los
candidatos tienen 8, 20, 4 y 2. Además llm-scaler reporta **escalado casi lineal con
data parallel (3,58× en 4 GPUs)**.

Para un equipo de agentes —muchas tareas cortas en paralelo, no una sola gigante—
**tres réplicas en TP=2 rinden más que un modelo en TP=4**, y además tolera mejor que
una réplica se caiga.

Sugerencia: que el scheduler, al ubicar un modelo, prefiera **más réplicas chicas dentro
de un socket** antes que una réplica grande cruzando sockets.

## 5. KV cache en RAM (con cuidado)

Con 1 TB hay lugar de sobra para un tier de KV cache en memoria: **2× a 22× de TTFT en
los aciertos**, y los agentes son el caso ideal porque reenvían el mismo prefijo todo el
tiempo. `--kv-offloading-size` en llm-scaler.

**Pero** hay un bug abierto (llm-scaler issue #720, 18/09/2026): con `kv_offloading`
nativo en Arc, **crashea con 24 clientes concurrentes o más** (`AssertionError` en
`_build_store_jobs`, después `EngineDeadError`). Estable con 8–16. Sin respuesta del
mantenedor. Habría que probarlo a la concurrencia real antes de habilitarlo por defecto.

## 6. Exponer la topología por API

Que `GET /nodes` (o el equivalente) devuelva la topología junto con el estado. Hoy no hay
ruta pública para listar nodos, que además es lo que bloquea usar `required_node_ids`.
Con la topología expuesta, un cliente puede pedir "esta réplica en el nodo con AMX" o
"separada del modelo grande".

---

## Cómo se mide que sirvió

Antes y después, con la misma prueba:

```bash
python3 scripts/concurrencia.py <endpoint> 1,8,16
python3 scripts/check_cache.py <endpoint>
```

Lo que tiene que moverse: **TTFT p50 y p95 con 8 y 16 concurrentes**. Si el NUMA binding
hace lo que promete la evidencia, se ve ahí y no hace falta discutirlo.

## Orden sugerido

1. **Reportar topología en el heartbeat** (no cambia nada, habilita todo lo demás).
2. **NUMA binding al levantar réplicas** ← la ganancia grande, y es configuración.
3. **Exponer nodos por API** (desbloquea `required_node_ids`, que pedimos hace rato).
4. **Backend de CPU para embeddings y clasificadores** cuando el nodo tiene AMX.
5. **Preferir DP sobre TP** al ubicar réplicas.
6. **KV cache en RAM**, después de reproducir el bug de concurrencia.

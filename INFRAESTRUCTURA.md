# Infraestructura: correr los agentes

Cómo está armado el entorno de ejecución y qué hay que saber para no perder tiempo.
Las mediciones, con fecha, están en [`colabhive/research/findings.md`](colabhive/research/findings.md).
`$AGENTES` es la carpeta donde clonaste este repo (ver [EMPEZAR.md](EMPEZAR.md)).

---

## 1. Las piezas

```
OpenCode (tu máquina)  ──►  api.colabhive.com/v1  ──►  modelos servidos por ColabHive
   TUI o `run`              OpenAI-compatible
```

- **OpenCode** es el agente: lee el repo, usa herramientas, edita archivos.
- **ColabHive** sirve los modelos. API compatible con OpenAI, así que OpenCode habla
  con ella como si fuera cualquier proveedor.
- Config en `~/.config/opencode/opencode.json` (enlazada desde `colabhive/config/` de este repo).
  El detalle campo por campo está en **[OPENCODE.md](OPENCODE.md)**.

## 2. El equipo de modelos

| Rol en OpenCode | Modelo | Contexto | Para qué |
|---|---|---|---|
| `plan` | gpt-oss-20b | 69k | Entender el pedido, repartir. Razona antes de responder |
| `build` | Qwen3-Coder-30B-A3B | 204k | Implementar tareas: instruct, actúa en vez de deliberar |
| `explore` (subagente) | gpt-oss-20b | 69k | Buscar en el código: el que antes llama a la herramienta |
| `reviewer` (subagente) | Qwen3.8-27B FP8 | 117k | Revisar diffs, sin permiso de edición |
| `tester` (subagente) | Qwen3-Coder-30B-A3B | 204k | Escribir y correr tests |
| `small_model`, `title`, `summary` | gpt-oss-20b | 69k | Títulos y resúmenes: un modelo que delibera tarda segundos en un título |

El agente por defecto de OpenCode es `build` (el que usan la TUI, `oc "tarea"` y el runner);
`plan` se elige con Tab en la TUI. El contexto es el `limit.context` de [`colabhive/config/opencode.json`](colabhive/config/opencode.json):
la ventana real de cada réplica menos un 8% de margen, sincronizada el 2026-09-21. Se corrige
sola con `sync_limits.py` (abajo).

**Pocos modelos y siempre calientes** es mejor que muchos especialistas: cargar un
modelo cuesta minutos, y la plataforma descarga lo que no se usa.

### Cómo elegir el modelo de cada rol

Lo que decide no es el puesto en un benchmark, es **si el modelo actúa o delibera**:

- **Ejecutor: un modelo que no piense.** Los "pensantes" (Qwen3.x por defecto, GLM en
  modo preservado, Nemotron) escriben cientos de líneas de razonamiento antes de llamar
  a una herramienta, y se quedan sin pasos. Buscá modelos instruct afinados para código
  (Qwen3-Coder, Devstral) o, mejor, los que **no tienen modo pensante en absoluto**
  (Qwen3-Coder-Next no genera bloques `<think>`).
  Si no hay opción, se puede apagar del lado del servidor:
  `--default-chat-template-kwargs '{"enable_thinking": false}'`.
- **Reviewer y planner: ahí sí conviene el pensante.** Es el mismo modelo que fracasa
  ejecutando: su deliberación, frente a un diff, es exactamente lo que querés.
- **Tareas chicas (explorar, títulos, resúmenes): el que antes contesta**, no el más chico.
  Qwen3-8B tardaba 12,8 s en llamar a una herramienta y gpt-oss-20b 1,1 s: el 8B delibera.

Medilo, no lo supongas: `scripts/comparar-modelos.sh` corre la misma tarea con varios
modelos y compara herramientas usadas contra líneas de deliberación. Ese cociente
predice el rendimiento como ejecutor, y **ningún benchmark público lo mide**.

## 3. Lo que hay que saber antes de lanzar

### Los modelos se enfrían

Un modelo sin uso vuelve a `cached` o `cold`. Despertarlo tarda **3 a 20 minutos**.
Si una tarea cae sobre un modelo frío, se queda esperando ese tiempo (con streaming, el
gateway sostiene la conexión hasta 20 minutos mientras carga).

```bash
oc --status     # ● warm  ◐ cached  ○ cold
oc --warm       # los despierta a todos y espera
```

**Antes de una tanda de tareas, siempre `oc --warm`.** Los estados, los tiempos medidos
y cómo tener un modelo siempre caliente están en [OPENCODE.md §6](OPENCODE.md#6-principios-de-residencia-warm).

### El contexto real se consulta, no se supone

`/v1/models` devuelve `max_model_len` por modelo. Si OpenCode cree que hay más contexto
del que hay, la sesión muere a mitad de camino con un 400.

```bash
python3 $AGENTES/colabhive/scripts/sync_limits.py          # muestra el drift
python3 $AGENTES/colabhive/scripts/sync_limits.py --write  # lo corrige
```

### El prefix caching cambia todo

Sin caching, cada paso del agente reprocesa el historial entero: con 55k de contexto,
**43 s por paso**. Con caching, **2,6 s**. Una tarea de 30 pasos pasa de 21 minutos de
espera a 2.

```bash
python3 $AGENTES/colabhive/scripts/check_cache.py   # verifica que siga activo
```

Si una tanda de tareas se puso lenta sin razón, esto es lo primero que hay que mirar.

### Cuántas tareas en paralelo (medido)

Una réplica procesa varios pedidos en el mismo lote; pasado el tamaño de ese lote, los demás esperan
turno. Medido el 2026-09-21 sobre una réplica de gpt-oss-20b, pedidos cortos iguales y 256 tokens de
salida:

| Paralelas | Tiempo total | Mediana | La más lenta | Throughput |
|---|---|---|---|---|
| 1 | 2.7 s | 2.7 s | 2.7 s | 93 tok/s |
| 4 | 3.7 s | 3.7 s | 3.7 s | 275 tok/s |
| **8** | **4.4 s** | **4.0 s** | **4.4 s** | **461 tok/s** |
| 12 | 7.3 s | 5.3 s | 7.2 s | 423 tok/s |
| 16 | 8.6 s | 5.7 s | 8.6 s | 477 tok/s |

**Regla:** hasta 8 por modelo, sumar tareas multiplica el throughput y casi no mueve la latencia.
Pasado 8 las respuestas se parten en dos grupos (a 16: ocho en ~4 s y ocho en ~8 s): la réplica admitió
8 y el resto esperó. Por eso el runner lanza **8 a la vez** por defecto (`PARALELAS=8`).

Mirá siempre **la más lenta**, no la mediana: la cola aparece ahí primero. El tamaño del lote es por
réplica y por modelo y la API no lo publica: medilo para tu caso con `$AGENTES/colabhive/scripts/concurrencia.py`.

Una medición anterior, sobre Qwen3-8B con prompts de 2k tokens, daba cola recién pasadas las 16 (a 24,
la peor request saltaba de 3 s a 12,6 s). Con otro modelo y otro momento de la plataforma el número
cambia: por eso se mide.

**El límite de tu key también cuenta.** Todas las tareas que usan la misma key comparten su tope de
pedidos por minuto: 60 en Starter, 300 en Pro, 1000 en Team. Un agente manda un pedido por paso, cada
pocos segundos; ocho tareas en paralelo pasan 60 por minuto enseguida. Pasado el tope la API contesta
`429` con `Retry-After`, y cada respuesta trae `X-RateLimit-Remaining`.

El límite práctico también es tu máquina: muchos procesos de OpenCode a la vez pesan.

### Paralelismo: una base de datos por tarea

OpenCode guarda su estado en **una sola SQLite** (`~/.local/share/opencode/opencode.db`).
Dos `opencode run` simultáneos chocan con `Error: database is locked`.

El runner lo resuelve dándole a cada tarea su propio directorio de datos:

```bash
export XDG_DATA_HOME="$worktree/.opencode-data"
```

**Nunca aislar `XDG_CONFIG_HOME`**: la config tiene que ser la misma para todas, o las
tareas se quedan sin provider ni modelos.

### Vigilar progreso de tokens, no el estado

Un motor puede colgarse con el endpoint marcado como sano: deja de emitir tokens y desde
afuera parece que sigue trabajando. **La única señal confiable es el progreso**: una request
que no emite un chunk en N segundos está colgada, diga lo que diga el estado.

Mientras el modelo carga, el gateway manda comentarios SSE `: keep-alive`; eso mantiene viva
la conexión, pero también hace que el `chunkTimeout` de OpenCode no dispare. Si una tarea no
muestra salida nueva en varios minutos con el modelo caliente, cortala y relanzala.

### No medir durante un deploy

Si la plataforma está desplegando, las latencias van de 20 a 500 segundos y algunos
modelos no responden. Cualquier medición hecha ahí no sirve, y peor, lleva a conclusiones
falsas. Pasó tres veces. Si algo que tardaba 1 s tarda minutos, asumí mantenimiento y esperá.

---

## 4. Trampas que ya nos costaron tiempo

| Síntoma | Causa | Solución |
|---|---|---|
| `database is locked` | Dos `opencode run` a la vez | `XDG_DATA_HOME` por tarea |
| 400 "maximum context length" | `limit.context` mal en la config | `sync_limits.py --write` |
| Una tarea tarda 20 min sin salida | Modelo frío | `oc --warm` antes de lanzar |
| `"auto" tool choice requires...` | El modelo no tiene tool calling habilitado | Usar otro; no todos lo tienen (`tool_calling_configured` en `/v1/models`) |
| El agente dice "listo" y no hizo nada | Le creíste al modelo en vez de al gate | El gate decide, siempre |
| `opencode run --agent explore` no usa explore | Los subagentes no se invocan desde la CLI | Cae al agente por defecto |

---

## 5. Chequeo previo a una tanda

```bash
oc --status                                             # ¿están calientes?
python3 $AGENTES/colabhive/scripts/sync_limits.py     # ¿el contexto está bien?
python3 $AGENTES/colabhive/scripts/check_cache.py     # ¿el caching anda?
```

Tres comandos, dos minutos. Evita perder una tanda entera.

---

## 6. Si en vez de ColabHive usás modelos locales

El método no cambia; cambia el proveedor. Con Ollama o vLLM local, en `opencode.json`:

```json
{ "provider": { "local": { "npm": "@ai-sdk/openai-compatible",
  "options": { "baseURL": "http://localhost:11434/v1", "apiKey": "local" },
  "models": { "qwen2.5-coder:32b": { "tool_call": true,
    "limit": { "context": 32000, "output": 4096 } } } } } }
```

Lo único que hay que verificar sí o sí: **que el modelo tenga tool calling habilitado**.
Sin eso, el agente no puede leer ni editar archivos, y falla con un 400 en la primera
herramienta que intente usar.

---

## 7. Los CPU del nodo: para qué sirven de verdad

Research de septiembre 2026. Intel promociona fuerte el Xeon para "agentic AI", pero
**su propia arquitectura pone la inferencia en la GPU y el CPU como plano de control**.
El dato que lo aclara: el CPU que más promocionan para agentic (Xeon 6+ Clearwater Forest,
288 núcleos) **no tiene AMX ni AVX-512**. No puede hacer la matemática que publicitan.

**El número que ordena todo:** las 6 GPUs del nodo tienen ~1,8× el ancho de banda de
memoria de todo el complejo Xeon, y **20 a 75× su throughput de prefill**. El trabajo del
CPU es alimentar las GPUs, no servir tokens.

### Lo que sí rinde, en orden

| Acción | Ganancia | Nota |
|---|---|---|
| **Fijar CPU/NUMA para el frontend de vLLM** (`--numa-bind`, escalar API server) | **1,5–7× TTFT** | Paper de Georgia Tech, sin afiliación a Intel: las GPUs quedan ociosas porque el CPU no las alimenta |
| **Tokenizador rápido en Rust** (`fastokens`) | hasta **40% TTFT** | 17× arriba de 50k tokens. Los agentes viven ahí |
| **KV cache en RAM** para reutilizar prefijos | **2–22× TTFT** en aciertos | Bug abierto en llm-scaler: crashea con ≥24 clientes concurrentes |
| **Embeddings + búsqueda vectorial + clasificadores a CPU** | libera VRAM | El reranker **no**: se queda en GPU |
| **RAM como staging de pesos** | segundos en vez de minutos al cambiar de modelo | Gratis, solo evitar almacenamiento de red |

La tokenización es el cuello específico de los agentes: el contexto acumulado crece
(más trabajo de CPU) mientras el prefix caching reduce el trabajo de GPU.

### Lo que es perder el tiempo

`--cpu-offload-gb` (19× más lento, medido) · `--swap-space` (ya no existe en vLLM) ·
esperar offload de expertos MoE (nada mergeado en v0.30) · **IPEX-LLM (archivado en
enero 2026)** · OpenVINO HETERO CPU+GPU (rechazado en el código) · draft models en CPU
para speculative decoding · correr un GGUF de 200B+ y pretender programar contra él
(7,8 tok/s, y 2,4 con contexto largo).

### Forma del nodo de 6 GPUs

**TP=6 no sirve**: TP tiene que dividir los KV heads, y los candidatos tienen 8, 20, 4 y 2.
Además llm-scaler reporta **escalado casi lineal con data parallel (3,58× en 4 GPUs)**.
Para un equipo de agentes —muchas tareas en paralelo, no una sola gigante— **DP rinde más
que TP**: varias réplicas en TP=2 antes que un solo modelo en TP=4.

---

## Dos correcciones de infraestructura (2026-10-01)

Las dos salieron de leer el código de vLLM y la documentación de Intel, no de probar.

### La regla de tensor parallelism que usábamos estaba mal

Veníamos diciendo "TP tiene que dividir la cantidad de cabezas KV". **La regla real tiene
dos ramas**, y la que corta primero es otra:

1. **Siempre**: `cabezas_de_atención % TP == 0`. Es el chequeo duro, en tiempo de
   configuración, y el que falla en la práctica.
2. Después, sobre las KV: si `TP >= cabezas_KV`, hace falta `TP % cabezas_KV == 0`; si
   `TP < cabezas_KV`, hace falta `cabezas_KV % TP == 0`.

La diferencia importa: **KV=2 no bloquea TP=8** — las cabezas KV se replican cuando son
menos que TP, por diseño. Lo que bloquea casi siempre es la cantidad de cabezas de
**consulta**.

**Y TP=6 sigue siendo inservible**, pero por el otro motivo: 16, 20, 32, 64 y 80 no son
divisibles por 6, y los dos conteos que sí lo son (24 y 48) después fallan la segunda rama.
De ocho candidatos revisados, **ninguno admite TP=6**.

### El nodo de 6×B70 no son 192 GB: son tres réplicas de 64 GB

La documentación de Intel para llm-scaler **sólo usa `-tp=1` y `-tp=2`**; no hay un solo
ejemplo con TP=4 ni TP=8. TP=4 es legal para vLLM en siete de los ocho candidatos, pero está
fuera de lo documentado por Intel: es experimental.

> **Topología recomendada: TP=2 × DP=3.** Tres réplicas independientes de 64 GB, que además
> calzan con el equipo de tres modelos: arquitecto, ejecutor y rápidos, uno por réplica.

Y dos trampas de cuantización en este hardware, verificadas contra la tabla de llm-scaler:

- **NVFP4 no nos sirve**: es sólo Blackwell. Varios de los repos **más descargados** de los
  modelos que nos interesan son NVFP4 — el contador de descargas no elige el repo.
- **AutoRound no está soportado**, confirmado: la tabla lista MXFP4, FP8 online, `sym_int4`
  online, y AWQ o GPTQ pre-cuantizados. AutoRound no aparece.
- **AWQ y GPTQ pre-cuantizados sí andan, y se autodetectan** del `config.json`: no hace falta
  pasar `--quantization`. En las 3090, preferilos sobre FP8: Ampere no tiene cómputo FP8, así
  que un FP8 corre por dequantización y no gana nada.

---

## La "regresión de velocidad" no era el motor: eran arranques en frío (2026-10-03)

Medimos durante días entre **0,4 y 2,2 tok/s** contra una línea base de 178, lo reportamos
tres veces como regresión del motor, y **estaba mal medido**. Lo que medíamos era el arranque.

En el mismo endpoint, separando las dos cosas:

| | |
|---|---|
| arranque en frío | **253 s** |
| en caliente | 3,62 s para 74 tokens = **20,4 tok/s** |

Con `min_replicas = 0` cada pedido levanta una réplica de cero: pesos, init del motor, y si
la imagen no está en el nodo, 19 GB de pull. Nuestros "178 s para 12 tokens" eran eso: un
arranque, no generación.

### Y la parte que sí es un problema, con evidencia

Nuestros endpoints **están configurados para no hacer eso** y lo hacen igual. Leído directo
de la API:

```
scaling_mode     = "minimum"
min_replicas     = 1
current_replicas = 0        ← ninguna réplica corriendo
warm_nodes       = null
status           = "active"
```

Los tres modelos del equipo, igual. O sea: el anclaje está puesto —`anclar.sh` lo configuró—
y la plataforma no lo mantiene.

**Y después del warmup: `actuales=1` en los tres.** Entonces el comportamiento exacto es
este, y es la regla operativa que importa:

> **`min_replicas: 1` no se auto-repone.** Una vez que la réplica está arriba, se mantiene;
> pero si se cayó o nunca arrancó, la plataforma **no la levanta sola**. Hay que mandar un
> pedido que la despierte.

Por eso `oc --warm` antes de cada tanda **no es una comodidad, es un requisito**: sin él, la
primera tarea de la tanda paga 253 segundos y todas las mediciones de esa tanda quedan
contaminadas. El propio `warm.sh` lo dice al terminar; le faltaba estar acá.

### Cuánto es la regresión de verdad, medida bien

Con el protocolo de la línea base —**mediana de 5 pedidos, en caliente**— el 2026-10-03:

| | hoy | línea base | |
|---|---|---|---|
| gpt-oss-20b | **18,1** tok/s | 179 | **10× más lento** |
| Qwen3-Coder-30B | **28,9** tok/s | 141 | **5× más lento** |

**Hay regresión real, de 5 a 10×** — no de 100×, como reportamos durante días. Y la línea
base estaba bien medida: era en caliente y con mediana de 5. El error fue todo nuestro.

### Y lo peor no es la media: es la varianza

Las cinco corridas de cada modelo, en caliente y consecutivas:

```
gpt-oss-20b       21  12  18  24  12   tok/s
Qwen3-Coder-30B   11  32  29  14  36   tok/s
```

**Un factor de 3× entre pedidos consecutivos del mismo modelo.** Eso no se parece a un motor
más lento: se parece a contención o a planificación. Y tiene una consecuencia inmediata:
**un pedido único no mide nada.** Nuestros "56–59 tok/s" de más temprano ese mismo día eran
una tirada afortunada de esa misma distribución.

### Las tres reglas de medición que nos faltaban

Teníamos escrita *"no medir durante cambios"*. Faltaban estas:

> 1. **Separá el arranque de la generación.** Un tok/s sobre un pedido único contra un
>    endpoint que escala a cero es el tiempo de carga dividido por los tokens.
> 2. **Mediana de cinco, nunca uno.** Con 3× de varianza, un pedido te da el número que
>    quieras.
> 3. **Compará con el mismo protocolo con que se midió la línea base**, o no estás
>    comparando. Nuestra "regresión de 100×" eran dos protocolos distintos.

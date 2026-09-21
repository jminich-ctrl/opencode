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

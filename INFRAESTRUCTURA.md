# Infraestructura: correr los agentes

Cómo está armado el entorno de ejecución y qué hay que saber para no perder tiempo.
Todo lo medido acá viene de `~/colabhive-opencode/research/findings.md`.

---

## 1. Las piezas

```
OpenCode (tu Mac)  ──►  api.colabhive.com/v1  ──►  modelos en el cluster propio
   TUI o `run`          OpenAI-compatible           14 GPUs (RTX 3090 + Intel Arc)
```

- **OpenCode** es el agente: lee el repo, usa herramientas, edita archivos.
- **ColabHive** sirve los modelos. API compatible con OpenAI, así que OpenCode habla
  con ella como si fuera cualquier proveedor.
- Config en `~/.config/opencode/opencode.json` (enlazada desde `~/colabhive-opencode/config/`).

## 2. El equipo de modelos

| Rol en OpenCode | Modelo | Contexto | Para qué |
|---|---|---|---|
| `plan` (por defecto) | gpt-oss-20b | 116k | Entender el pedido, repartir. Razona antes de responder |
| `build` | Qwen3.8-27B FP8 | 117k | Implementar tareas |
| `explore` (subagente) | Qwen3-8B | 37k | Buscar en el código, barato |
| `reviewer` (subagente) | Qwen3.8-27B FP8 | 117k | Revisar diffs, sin permiso de edición |
| `tester` (subagente) | Qwen3-Coder-30B | 205k | Escribir y correr tests |
| `small_model` | Qwen3-8B | 37k | Títulos y resúmenes |

**Pocos modelos y siempre calientes** es mejor que muchos especialistas: cargar un
modelo cuesta minutos, y la plataforma desaloja por VRAM lo que no se usa.

## 3. Lo que hay que saber antes de lanzar

### Los modelos se enfrían

Un modelo sin uso vuelve a `cached` o `cold`. Despertarlo tarda **3 a 20 minutos**.
Si una tarea cae sobre un modelo frío, se queda esperando ese tiempo.

```bash
oc --status     # ● warm  ◐ cached  ○ cold
oc --warm       # los despierta a todos y espera
```

**Antes de una tanda de tareas, siempre `oc --warm`.**

### El contexto real se consulta, no se supone

`/v1/models` devuelve `max_model_len` por modelo. Si OpenCode cree que hay más contexto
del que hay, la sesión muere a mitad de camino con un 400.

```bash
python3 ~/colabhive-opencode/scripts/sync_limits.py          # muestra el drift
python3 ~/colabhive-opencode/scripts/sync_limits.py --write  # lo corrige
```

### El prefix caching cambia todo

Sin caching, cada paso del agente reprocesa el historial entero: con 55k de contexto,
**43 s por paso**. Con caching, **2,6 s**. Una tarea de 30 pasos pasa de 21 minutos de
espera a 2.

```bash
python3 ~/colabhive-opencode/scripts/check_cache.py   # verifica que siga activo
```

Si una tanda de tareas se puso lenta sin razón, esto es lo primero que hay que mirar.

### Paralelismo: una base de datos por tarea

OpenCode guarda su estado en **una sola SQLite** (`~/.local/share/opencode/opencode.db`).
Dos `opencode run` simultáneos chocan con `Error: database is locked`.

El runner lo resuelve dándole a cada tarea su propio directorio de datos:

```bash
export XDG_DATA_HOME="$worktree/.opencode-data"
```

**Nunca aislar `XDG_CONFIG_HOME`**: la config tiene que ser la misma para todas, o las
tareas se quedan sin provider ni modelos.

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
| `"auto" tool choice requires...` | El modelo no tiene tool calling habilitado | Usar otro; no todos lo tienen |
| El agente dice "listo" y no hizo nada | Le creíste al modelo en vez de al gate | El gate decide, siempre |
| `opencode run --agent explore` no usa explore | Los subagentes no se invocan desde la CLI | Cae al agente por defecto |

---

## 5. Chequeo previo a una tanda

```bash
oc --status                                             # ¿están calientes?
python3 ~/colabhive-opencode/scripts/sync_limits.py     # ¿el contexto está bien?
python3 ~/colabhive-opencode/scripts/check_cache.py     # ¿el caching anda?
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

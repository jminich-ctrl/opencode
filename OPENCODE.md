# Configuración de OpenCode, pieza por pieza

Cómo está armada la config que usamos, qué hace cada campo y por qué está puesto así.
Los números vienen de mediciones propias, con fecha, en [`colabhive/research/findings.md`](colabhive/research/findings.md).

> **¿Querés lo mínimo?** `pip install -U colabhive && colabhive agents init` escribe un provider
> de ColabHive con un modelo probado en tu `opencode.json`, sin tocar lo demás. Esta página
> explica la config completa del equipo de tres modelos. Es uno u otro: `agents init` después
> de instalar esta config reemplaza el symlink y reescribe el provider `colabhive`
> (`colabhive agents doctor`, en cambio, sólo lee).

---

## 1. Dónde vive

```
colabhive/config/opencode.json      ← el archivo real, versionado en este repo
colabhive/config/prompts/*.md       ← el prompt de cada agente
~/.config/opencode/opencode.json    → symlink al primero
~/.config/opencode/prompts          → symlink al directorio de prompts
```

**Los dos symlinks son necesarios.** `{file:./prompts/plan.md}` se resuelve contra
`~/.config/opencode/`, no contra el destino del symlink: si enlazás solo el JSON,
OpenCode falla con `bad file reference`.

La key de ColabHive nunca va en el config: se lee del entorno con `{env:COLABHIVE_API_KEY}`,
que carga `~/.config/colabhive/env` (chmod 600, fuera de todo repo).

---

## 2. El bloque `provider`

Conecta OpenCode con cualquier API compatible con OpenAI.

```json
"provider": {
  "colabhive": {
    "npm": "@ai-sdk/openai-compatible",
    "name": "ColabHive",
    "options": {
      "baseURL": "https://api.colabhive.com/v1",
      "apiKey": "{env:COLABHIVE_API_KEY}",
      "headerTimeout": 900000,
      "chunkTimeout": 120000,
      "timeout": false
    },
    "models": { "<id-del-endpoint>": { ... } }
  }
}
```

| Campo | Por qué ese valor |
|---|---|
| `headerTimeout: 900000` | 15 min esperando los headers (el default de OpenCode es 5 min) |
| `chunkTimeout: 120000` | 2 min sin un chunk = algo se colgó. **Ojo: no cortó un run colgado de 52 min**: mientras espera, el gateway manda comentarios `: keep-alive` y el reloj se reinicia. No es defensa suficiente |
| `timeout: false` | sin tope total del lado de OpenCode (el default es 5 min, poco para el primer pedido a un modelo que carga). El gateway corta igual a los 20 min |

Los tres existen en el [schema de OpenCode](https://opencode.ai/config.json). Si preferís un tope,
`"timeout": 1200000` (20 min) es lo que escribe `colabhive agents init`.

### Cada modelo

```json
"f5d76140-...": {
  "name": "Qwen3-Coder-30B-A3B · ejecutor (build/tester)",
  "tool_call": true,
  "reasoning": false,
  "temperature": true,
  "limit": { "context": 204000, "output": 16384 }
}
```

- **La clave es el id del endpoint**, no el nombre del modelo. Sale de `GET /v1/models`.
- **`tool_call: true` es obligatorio** para un agente. Si el servidor no levantó el modelo
  con un parser de tool calls, la primera herramienta falla con un 400 y la sesión muere.
  `/v1/models` lo dice en `tool_calling_configured`, pero eso es configuración, no capacidad:
  probalo con un tool call real (`colabhive agents init` lo hace antes de escribir la config).
- **`limit.context` tiene que ser menor al real.** Si mentís para arriba, la sesión muere
  a mitad de camino. Se sincroniza solo:
  `python3 $AGENTES/colabhive/scripts/sync_limits.py --write` (lee `max_model_len` de
  `/v1/models` y deja un 8% de margen).
- **Poné el rol en el `name`.** Cuando cambiás un modelo de rol, el nombre viejo confunde.
  El nuestro dice explícitamente `reviewer (razona, NO ejecuta)`.

---

## 3. El bloque `agent`

Cada agente es un modelo + un prompt + permisos. Los nombres `plan`, `build`, `explore`,
`title`, `summary` y `compaction` son los que OpenCode ya usa; cualquier otro nombre crea
un agente nuevo.

```json
"agent": {
  "build":    { "model": "...", "temperature": 0.2, "steps": 80,
                "prompt": "{file:./prompts/build.md}" },
  "reviewer": { "mode": "subagent", "model": "...", "temperature": 0.1,
                "description": "Revisa un diff buscando bugs. Solo lee.",
                "prompt": "{file:./prompts/reviewer.md}",
                "permission": { "edit": "deny", "bash": "ask" } }
}
```

- **`mode`**: `primary` (se invoca desde la CLI) o `subagent` (se invoca con `@nombre`
  dentro de una sesión). **`opencode run --agent reviewer` NO usa reviewer**: los
  subagentes no se invocan desde la CLI y cae silenciosamente al agente por defecto.
- **`description`** es lo que el modelo lee para decidir a qué subagente delegar. Escribila
  pensando en eso, no como documentación.
- **`permission`** es la defensa real: al reviewer le negamos `edit`, así no puede
  "arreglar" lo que debería solo reportar.
- **`temperature`**: 0.1 para revisar y explorar, 0.2 para implementar, 0.3 para planificar.
- **`steps`**: tope de iteraciones. Subilo si el agente se queda corto, pero si se queda
  sin pasos **deliberando**, el problema es el modelo, no el tope.

### El equipo actual

| Rol | Modelo | Contexto | Por qué |
|---|---|---|---|
| `plan` | gpt-oss-20b | 69k | razona antes de repartir, y es el más rápido |
| `build` | Qwen3-Coder-30B-A3B | 204k | instruct, actúa en vez de deliberar |
| `reviewer` | Qwen3.8-27B FP8 | 117k | pensante: acá su deliberación suma |
| `tester` | Qwen3-Coder-30B-A3B | 204k | mismo ejecutor |
| `explore`, `title`, `summary` | gpt-oss-20b | 69k | el que antes contesta: un modelo que delibera tarda segundos en un título |

El agente por defecto de OpenCode es `build`: es el que usan la TUI, `oc "tarea"` y el runner.
El `model` de primer nivel (gpt-oss-20b) sólo se usa para lo que no declara un modelo propio.

**El criterio no es el benchmark, es si actúa o delibera.** Ver
[INFRAESTRUCTURA.md](INFRAESTRUCTURA.md#cómo-elegir-el-modelo-de-cada-rol).

---

## 4. Los prompts

Uno por agente, en `config/prompts/`. Lo que aprendimos que hay que incluir:

- **En el ejecutor, una regla de ritmo.** Sin esto, un modelo mediano planifica en prosa
  hasta quedarse sin pasos: *"leé 2 o 3 archivos como máximo antes de escribir; si dudás
  entre dos formas, elegí la simple y seguí; el código se corrige corriendo los tests,
  no pensándolo de antemano"*.
- **En el planner, que delegue la búsqueda** al subagente explorador en vez de leer
  decenas de archivos él mismo.
- **En el reviewer, que cada hallazgo necesite un caso concreto** que lo dispare, y que
  si no encuentra nada lo diga en vez de rellenar.
- **En el tester, que muestre la salida real** de los tests, incluso si fallan.

---

## 5. El resto del config

```json
"share": "disabled",          // nada sale a un servidor de terceros
"autoupdate": "notify",       // avisa, no actualiza solo a mitad de una tanda
"compaction": { "auto": true },
"instructions": ["AGENTS.md", "CLAUDE.md", ".opencode/rules/*.md"]
```

`instructions` incluye `CLAUDE.md` a propósito: los repos ya tienen ahí sus reglas y no
hace falta duplicarlas en un `AGENTS.md`.

---

## 6. Principios de residencia (warm)

Esta es la parte que más tiempo hace perder si no se entiende.

### Los estados

```
cold ──descarga──▶ cached ──carga──▶ warm ──▶ running ──▶ idle ──▶ evicted ──▶ cold
```

| Estado | Qué significa | Latencia al primer token (medido) |
|---|---|---|
| `warm` | cargado en GPU | **1 a 4 s** |
| `cached` | los pesos están en disco del nodo | **197 s a 444 s** |
| `cold` | no está en ningún nodo | minutos, más la descarga |

### Las tres cosas que hay que saber

**1. Los modelos se desalojan solos.** La plataforma carga y descarga los modelos del
catálogo según la demanda. Lo vimos en vivo: dos de los nuestros se enfriaron en menos de
una hora **sin que nadie los tocara**.

**2. Un modelo frío no falla, espera.** Con streaming, el gateway sostiene la request
mientras el modelo carga (hasta 20 minutos, carga y generación incluidas). Para un agente
eso es peor que un error, porque parece que está trabajando. Un `opencode run` nuestro
estuvo **52 minutos** así.

**3. Los modelos del catálogo compartido no se pueden anclar.** Los administra la
plataforma: `PATCH /endpoints/{endpoint_id}/scaling` sobre un endpoint público devuelve `404`,
porque solo la cuenta dueña de un endpoint cambia su política de escala.

Para tener un modelo **siempre caliente**, servilo desde tu cuenta:
[importá](https://docs.colabhive.com/guides/import-from-huggingface) un repo de Hugging Face
que no esté ya en el catálogo y, con una key de rol operator o superior, fijalo:

```bash
PATCH /api/builder/v1/endpoints/{endpoint_id}/scaling
{ "scaling_mode": "minimum", "min_replicas": 1, "max_replicas": 1 }
```

`minimum` convierte `min_replicas` en un compromiso: el modelo queda residente. Detalle en
[Known limits](https://docs.colabhive.com/guides/agents/known-limits).

### Con el catálogo compartido: precalentar

```bash
oc --status     # ● warm  ◐ cached  ○ cold
oc --warm       # manda un ping con streaming a cada modelo y espera la carga
```

**Antes de cada tanda de tareas, `oc --warm`.** Tarda lo que tarde la carga, pero se paga
una vez y no en medio de una tarea. Después de un deploy de la plataforma, obligatorio.

### Vigilar progreso, no `/health`

Un motor puede colgarse con el endpoint marcado como sano. La única señal confiable es el
progreso de tokens: si una request no emite un chunk en N segundos con el modelo caliente,
está colgada aunque todo parezca sano. Ver [INFRAESTRUCTURA.md](INFRAESTRUCTURA.md).

---

## 7. Las herramientas

```bash
oc                  # abre la TUI, avisando antes qué modelos están fríos
oc "arreglá X"      # una tarea suelta
oc --status         # estado de residencia del equipo
oc --warm           # despierta a los tres

python3 $AGENTES/colabhive/scripts/sync_limits.py [--write]      # contexto real
python3 $AGENTES/colabhive/scripts/check_cache.py                # ¿hay prefix caching?
python3 $AGENTES/colabhive/scripts/concurrencia.py <id> 1,4,8,12 # techo de paralelismo
python3 $AGENTES/colabhive/scripts/smoke_test.py <id>            # tool calling + tokens/s
```

**Chequeo previo a una tanda**, tres comandos y dos minutos:

```bash
oc --status && python3 $AGENTES/colabhive/scripts/sync_limits.py \
             && python3 $AGENTES/colabhive/scripts/check_cache.py
```

Vale la pena porque las tres cosas se rompen solas: los modelos se enfrían, las réplicas
cambian de ventana al reemplazarse (vimos gpt-oss pasar de 126k a 76k sin aviso) y el
prefix caching depende de cómo se levantó el motor.

---

## 8. Trampas ya pagadas

| Síntoma | Causa | Solución |
|---|---|---|
| `bad file reference` al arrancar | falta el symlink de `prompts/` | enlazar también el directorio |
| `database is locked` | dos `opencode run` a la vez | `XDG_DATA_HOME` por tarea (nunca `XDG_CONFIG_HOME`) |
| 400 `maximum context length` | `limit.context` mentido | `sync_limits.py --write` |
| 400 `"auto" tool choice requires...` | el modelo no tiene tool calling | usar otro: no todos lo tienen |
| `external_directory, auto-rejecting` | le pasaste una ruta fuera del proyecto | rutas relativas al directorio de trabajo |
| El agente delibera y no produce | modelo pensante como ejecutor | cambiar de modelo o apagar el pensamiento |
| Una tarea tarda 20 min sin salida | modelo frío | `oc --warm` antes |
| `--agent reviewer` no usa reviewer | los subagentes no se invocan desde la CLI | usar `@reviewer` dentro de una sesión |

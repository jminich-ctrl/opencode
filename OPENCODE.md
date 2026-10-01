# Configuración de OpenCode, pieza por pieza

Cómo está armada la config que usamos, qué hace cada campo y por qué está puesto así.
Los números vienen de mediciones propias, con fecha, en [`colabhive/research/findings.md`](colabhive/research/findings.md).

> **¿Querés lo mínimo?** `pip install -U colabhive && colabhive agents init` escribe un provider
> de ColabHive con un modelo probado en tu `opencode.json`, sin tocar lo demás. Esta página
> explica la config completa del equipo de cinco modelos. Es uno u otro: `agents init` después
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

- **`mode`**: `primary` (se invoca desde la CLI con `--agent`) o `subagent` (se invoca con
  `@nombre` dentro de una sesión).

  **Declaralo siempre, incluso en los primarios.** Un agente propio que no declara `mode`
  **no se registra**: OpenCode no lo lista y `--agent ese-nombre` cae al agente por defecto
  sin decir nada. Así vivió semanas nuestro `arquitecto`: cada vez que le pedíamos un plan
  contestaba `build`. Se ve con:

  ```bash
  opencode agent list | grep -E '^\S+ \((primary|subagent)\)'
  ```

  Si un agente tuyo no aparece ahí, no existe. Los subagentes sí se registraban porque
  declaran `mode` por obligación; los primarios, no, y ese es justo el caso en que el
  silencio se confunde con que funcionó.

- **`opencode run --agent reviewer` tampoco usa reviewer**, pero por otro motivo: los
  subagentes no se invocan desde la CLI. Las dos fallas se ven igual —contesta el agente
  por defecto— y por eso conviene chequear la lista antes de culpar al prompt.
- **`description`** es lo que el modelo lee para decidir a qué subagente delegar. Escribila
  pensando en eso, no como documentación.
- **`permission`** es la defensa real: al reviewer le negamos `edit`, así no puede
  "arreglar" lo que debería solo reportar.

  Pero **`allow`/`deny` funcionan y el allowlist por comando no**. Le habíamos dado al
  arquitecto `"bash": {"ls*": "allow", …, "*": "ask"}`; en los permisos resueltos
  (`opencode agent list`) **no aparece ninguna regla `bash`**: se descartó entera. Y como en
  `opencode run` no hay nadie para contestar, cada `ask` se auto-rechaza y el agente
  abandona en el primer comando. Si una herramienta es riesgosa para un rol, **no se la des**
  (`"tools": {"bash": false}`); restringirla a medias es peor que las dos alternativas.
- **`temperature`**: 0.1 para revisar y explorar, 0.2 para implementar, 0.3 para planificar.
- **`steps`**: tope de iteraciones. Subilo si el agente se queda corto, pero si se queda
  sin pasos **deliberando**, el problema es el modelo, no el tope.

### El equipo actual

| Rol | Modelo | Por qué |
|---|---|---|
| `arquitecto`, `plan`, `reviewer`, `seguridad` | **Qwen3.8-27B** | pensante: acá la deliberación suma, y es el que lidera seguimiento de instrucciones (IFBench 79,5) y ejecución de horizonte largo (Terminal-Bench 2.1 73,0) entre los open-weight de su tamaño |
| `ejecutor`, `build`, `tester`, `devops`, `migrador` | **Qwen3-Coder-30B-A3B** | instruct de código: actúa en vez de deliberar |
| `title`, `summary`, `explore` | **gpt-oss-20b** | el único criterio es la velocidad: medido 1,1s contra 12,8s de Qwen3-8B para un título |

**Tres modelos, no cinco**, y eso importa más que la elección de cada uno: con cinco
anclados, despertar uno desalojaba a otro.

El agente por defecto de OpenCode es `build`: es el que usan la TUI y `oc "tarea"`.
**El runner usa `ejecutor`**, que es `build` con el harness recortado (§7).

### Lo que salió del equipo, y por qué

**gpt-oss-120b** era el arquitecto y quedó sin rol el 2026-10-01. Tres razones, la primera
mecánica y por eso la más fuerte:

1. **Su formato de tool call manda los argumentos como un único blob JSON.** Para llamar a
   `write`, el modelo tiene que emitir un archivo entero como string JSON escapado —cada
   salto de línea como `\n`, cada comilla escapada, en una sola tirada—. Es la forma más
   difícil posible justo para la única operación que el planificador necesita. El formato de
   Qwen es XML con el cuerpo **en texto crudo entre etiquetas**, sin escapar nada y con
   multilínea explícitamente soportada. Eso explica por qué el nuestro escribía prosa.
2. **La medición en su rango de tamaño dice que no paga.** Planificar le da a un 30B +11,6
   puntos en SWE-Bench Verified y a un 120B **ninguna ganancia consistente**.
3. **En Intel sólo corre en MXFP4.** No se puede cambiar precisión por caché KV como con
   Qwen3.8-27B, que tiene FP16, FP8 e INT4.

Se queda instalado por una razón: es el **único** modelo con receta publicada para Arc Pro
B70 (4×32 GB, TP=4, MXFP4), así que sirve como configuración conocida-buena para aislar un
problema de infraestructura.

**Qwen3-8B** salió porque para títulos y resúmenes razonaba antes de contestar: 12,8s contra
1,1s. El tamaño no predice la latencia; si el modelo delibera, sí.

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
oc --warm           # despierta a todo el equipo

python3 $AGENTES/colabhive/scripts/sync_limits.py [--write]      # contexto real
python3 $AGENTES/colabhive/scripts/check_cache.py                # ¿hay prefix caching?
python3 $AGENTES/colabhive/scripts/concurrencia.py <id> 1,4,8,12 # techo de paralelismo
python3 $AGENTES/colabhive/scripts/smoke_test.py <id>            # tool calling + tokens/s
python3 $AGENTES/colabhive/scripts/proxy_medidor.py              # ¿cuánto pesa el harness?
```

**Chequeo previo a una tanda**, tres comandos y dos minutos:

```bash
oc --status && python3 $AGENTES/colabhive/scripts/sync_limits.py \
             && python3 $AGENTES/colabhive/scripts/check_cache.py
```

Vale la pena porque las tres cosas se rompen solas: los modelos se enfrían, las réplicas
cambian de ventana al reemplazarse (vimos gpt-oss pasar de 126k a 76k sin aviso) y el
prefix caching depende de cómo se levantó el motor.

### Cuánto pesa el harness, y cómo pesarlo

Ninguna documentación dice cuánto contexto gasta OpenCode **antes** de que empiece la tarea.
`proxy_medidor.py` se pone entre OpenCode y ColabHive y anota una línea por request:

```bash
python3 colabhive/scripts/proxy_medidor.py &     # escucha en 8899
# apuntar el baseURL del provider a http://127.0.0.1:8899/v1
cat colabhive/research/live/harness.jsonl
```

Medido con el pedido más chico posible (`"Responde solo: OK"`, 19 caracteres):

| | `build` (10 herramientas) | `ejecutor` (6) |
|---|---|---|
| system prompt | 17.954 | **4.613** |
| esquemas de herramientas | 21.393 | **12.533** |
| **cuerpo del request** | **39.548** | **17.424** |

**−56%, unos 5.500 tokens por cada paso del agente.** Las herramientas que sacamos son
`webfetch`, `skill`, `task` y `todowrite`: un ejecutor no navega, no delega y no necesita
una lista de tareas para hacer una sola.

Dos cosas que no esperábamos:

1. **El ahorro grande no está en el esquema de la herramienta, está en el system prompt.**
   Bajó 13.341 caracteres al sacar cuatro herramientas, porque OpenCode inyecta el
   instructivo de cada una. `todowrite` sola arrastra una sección entera con ejemplos.
2. **Lo que quedó del system prompt es casi todo nuestro**: 4.613 caracteres ≈ los dos
   `AGENTS.md` (1.250 + 1.745) más el prompt del ejecutor (1.166). Sacando las herramientas
   que no usa, el peso de OpenCode se vuelve marginal frente al nuestro.

`build` queda intacto a propósito: es el único que puede delegar en `@reviewer`, y para eso
necesita `task`. Si una tarea necesita delegar, se lanza con `AGENTE=build`.

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
| `--agent arquitecto` contesta como `build` | el agente propio no declaraba `mode` y no se registró | `"mode": "primary"`, y verificar con `opencode agent list` |
| `reasoning_content` viene vacío | **el campo se llama `reasoning`**: vLLM lo renombró, y un cliente que lee el viejo ve vacío aunque el nuevo esté lleno | leer `message.reasoning`, y mandar `include_reasoning: true` en el request |
| `</think>` aparece dentro de `content` | el servidor tiene `--tool-call-parser` **sin** `--reasoning-parser`: el parser de herramientas se come el `</think>` y funde el razonamiento en el contenido | pedir a la plataforma que agregue `--reasoning-parser qwen3` (o el del modelo) |
| el modelo "escribe prosa" en vez de llamar a la herramienta | puede ser que **emita el tool call dentro de `<think>`**: el parser de herramientas sólo busca en `content`, nunca en el razonamiento | el `--reasoning-parser` correcto, y forzar la llamada con `tool_choice` por nombre |
| `auto-rejecting` y el agente abandona | un `permission.bash` por comando que OpenCode descartó en silencio; en modo no interactivo todo `ask` se auto-rechaza | no dar la herramienta (`"bash": false`) en vez de intentar restringirla |

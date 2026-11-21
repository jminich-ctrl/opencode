# Plan: lazo cerrado, medido, y que corra local

Abierto el 2026-11-21. **Cada intervención de acá lleva su predicción escrita ANTES de
correrla**, y su chequeo de manipulación: «¿la intervención hizo lo que decía hacer?» es una
pregunta distinta de «¿sirvió?», y confundirlas es cómo se confirma una hipótesis en vez de
probarla. Cuando una predicción falla, se anota que falló y no se reescribe.

Estado de cada fase acá abajo. Lo que ya está medido va a [`../MEDICION.md`](../MEDICION.md).

| Fase | Qué | Estado |
|---|---|---|
| 0 | La etapa que más falla no entra al informe, y su registro no es comparable | **hecha** |
| 1 | El arquitecto se corta a mitad del razonamiento | diseñada, falta correr |
| 2 | Contexto real contra el servidor, para local | diseñada |
| 3 | Subir K con el plan de clasificados | bloqueada por 1 |

---

## Fase 0 — Medir la etapa que no se mide

**Primero, una corrección.** Dije que la etapa no dejaba «una sola fila». Es falso: deja 19 en
`.metricas/veredictos.jsonl`. Fui a verificarlo antes de escribir el arreglo y el hueco real
resultó ser otro, y más interesante.

**Son dos registros con dos propósitos, y no se hablan.**

| | `intentos.csv` | `veredictos.jsonl` |
|---|---|---|
| qué es | la serie de medición | el insumo del dataset |
| quién lo lee | `metricas.sh` | `juntar_veredictos.py`, `particionar_veredictos.py` |
| quién lo escribe | `correr-tarea.sh`, `cerrar-tarea.sh` | `escribir-tests.sh` |
| tiene | modelo, segundos, **instrumento**, contextos, concurrencia | enunciado, test, dimensiones, motivo |

**Hueco 1:** `escribir-tests.sh` no escribe en el CSV, así que **`metricas.sh` no muestra una
sola fila de la etapa que más falla**: 19 rechazos el 2026-11-10 y el informe en blanco.

**Hueco 2, el peor:** el jsonl no tiene **ni un campo de comparabilidad** — ni modelo, ni
segundos, ni huella de instrumento, ni contextos. O sea 19 registros que no se comparan con
nada. Es la misma enfermedad que el CSV, donde 91 intentos se reparten en **13 huellas de
instrumento y 60 filas sin ninguna**, entrando por otra puerta. Un registro rico en contenido y
mudo sobre con qué se produjo no se puede usar dos veces.

**Hueco 3:** el registro no distingue la ETAPA. Mezclar escritura-de-tests con implementación
—poblaciones distintas, dificultad distinta— cambiaría «no medir» por «medir mal», que es peor
porque tiene cara de dato.

**Hueco 4:** `.metricas/` está en el `.gitignore`. Correcto para el worktree de una tarea,
falso para **la serie con la que se decide si un cambio del método sirvió**: no estaba
versionada en ningún lado.

**Criterio de terminado.** Una corrida de `escribir-tests.sh` deja fila en los dos registros,
las dos con etapa, huella de instrumento y contextos; la huella se calcula en un solo lugar; y
a las filas viejas no se les inventa la etapa, porque «no se registró» e «implementación» son
cosas distintas.

**Hecho.** 5 tests, verificados en los dos sentidos: con los cambios revertidos caen los 5.

---

## Fase 1 — El arquitecto no decide no escribir: se queda sin tokens

**Lo que creí y era falso.** Dije dos veces que el arquitecto no replanificaba porque la
restricción de alcance del prompt lo dejaba deliberando sobre permisos. Lo deduje leyendo los
transcripts por arriba, donde efectivamente delibera.

**Lo que dice la medición.** Los tres transcripts **cortan a mitad de palabra**:

| transcript | bytes | tokens ≈ | termina en |
|---|---|---|---|
| `replan-T04` | 17242 | 4310 | `…vuelve a pasar por tests` |
| `replan-T26` | 17262 | 4316 | `` …`backend/app/datos/conexion.py `` |
| `replan-T16` | 26872 | 6718 | `…let me reconsider. Maybe I` |

El tope de salida del arquitecto es **4096**. Dos de tres caen justo ahí. Un modelo no termina
tres de tres a mitad de palabra por casualidad: eso es un corte por presupuesto. Nunca llegó a
llamar a `write` porque se le acabó antes.

Es §26 y §30 otra vez: el Qwen3.8-27B **funde el razonamiento adentro de `content`**, así que el
tope de salida no corta la respuesta — corta el razonamiento, y lo que no salió todavía era la
acción. §25 ya subió el tope del juez a 10000 por este mismo motivo; el arquitecto quedó en 4096.

**Y un agravante.** El agente declara `chat_template_kwargs: {enable_thinking: False}`. Le
pedimos que no razone y razona igual, en inglés, dentro de `content`. El flag no está surtiendo
efecto, y eso es una hipótesis aparte que se mide aparte.

### El diseño

Dos mediciones distintas, y la distinción es el punto:

1. **Chequeo de manipulación — ¿dejó de cortarse?** Los transcripts ya no terminan a mitad de
   palabra. Esto dice si la intervención hizo lo que decía hacer, independientemente de si sirvió.
2. **Resultado — ¿escribió?** El criterio que el script ya tiene: *«el arquitecto no cambió
   nada: leyó la tarea y no la reescribió»*.

**Intervención:** subir `limit.output` del arquitecto de 4096 a 10000. Mismo número y mismo
motivo que §25.

**Predicción, escrita antes de correr:** los cuatro transcripts dejan de cortarse a mitad de
palabra, y el arquitecto escribe en **≥2 de 4** tareas (T04, T16, T26, T28).

**Qué significa cada resultado:**

| se cortó | escribió | lectura |
|---|---|---|
| no | ≥2 | la causa era el presupuesto. Confirmado. |
| no | 0–1 | el presupuesto era necesario y no suficiente: ahí sí vuelve el prompt como candidato, **con la hipótesis vieja ya refutada una vez** |
| sí | — | la intervención no hizo lo que decía: no se lee el resultado, se arregla el instrumento |

**La trampa de §30, chequeada antes:** el borde corta respuestas NO streameadas a los 300 s, y a
~30 tok/s 10000 tokens son ~333 s. Hay que confirmar que el pedido del agente va con streaming
antes de subir el tope, o estaríamos poniendo el techo del borde adentro del presupuesto —el
error exacto que §30 documenta—.

---

## Fase 2 — Para que corra local, el contexto se mide, no se pregunta

**El hecho medido por cinco harnesses distintos** (Aider, Cline, OpenCode, OpenHands, Zed):
Ollama y LM Studio traen 2k–4k de contexto por defecto y **descartan el resto en silencio**.

Es el mismo defecto que nos costó tres semanas con ColabHive —el ejecutor declaraba 153000 y le
servían 35000— pero **peor**: allá devolvía un 400 que al menos era un síntoma. Acá el modelo
contesta normal con medio prompt adentro, y lo que se ve es un agente que «entendió mal».

**Y el chequeo que nos salvó no transfiere.** `sync_limits.py` compara lo declarado contra el
`max_model_len` que publica `/v1/models`. Ollama no publica eso. O sea que el único control del
defecto más caro del proyecto **no existe justo donde el defecto es silencioso**.

**Diseño:** medirlo contra el servidor en vez de preguntárselo. Mandar un prompt con una marca
al principio y pedir que la devuelva; si el servidor truncó por adelante, la marca no está. Eso
no depende de que el proveedor publique nada y vale igual para ColabHive, vLLM y Ollama.

**Predicción:** contra un servidor con el contexto recortado a propósito, el chequeo lo detecta
y el método se niega a arrancar, con el mismo mensaje que ya da el drift de `sync_limits`.

---

## Fase 3 — Subir K

Bloqueada por la fase 1, no por falta de diseño: subir K es escribir ítems, escribir ítems es
terminar el plan de clasificados, y el plan no avanza mientras el lazo de replanificación no
cierre. Las tres decisiones humanas siguen en [`../ESTADO.md`](../ESTADO.md).

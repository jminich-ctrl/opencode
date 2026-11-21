# Plan: lazo cerrado, medido, y que corra local

Abierto el 2026-11-21. **Cada intervención de acá lleva su predicción escrita ANTES de
correrla**, y su chequeo de manipulación: «¿la intervención hizo lo que decía hacer?» es una
pregunta distinta de «¿sirvió?», y confundirlas es cómo se confirma una hipótesis en vez de
probarla. Cuando una predicción falla, se anota que falló y no se reescribe.

Estado de cada fase acá abajo. Lo que ya está medido va a [`../MEDICION.md`](../MEDICION.md).

| Fase | Qué | Estado |
|---|---|---|
| 0 | La etapa que más falla no entra al informe, y su registro no es comparable | **hecha** |
| 1 | El arquitecto se corta a mitad del razonamiento | **⊘ tanda inválida** por el gateway. Pared medida, tope a 6000, lista para re-correr |
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

### Lo que medí antes de tocar nada

**El flag que apaga el razonamiento es inerte.** El agente declara
`chat_template_kwargs: {enable_thinking: False}`. Mandé el mismo pedido con y sin el flag: las
dos respuestas arrancan igual —`"We need answer in Spanish..."`— y ninguna trae campo
`reasoning` aparte. El modelo razona igual, en inglés, dentro de `content`. Eso **cierra** la
hipótesis barata y deja el presupuesto como única palanca.

**La velocidad: 6,1 y 6,6 tok/s**, dos corridas contra el 27B FP8 caliente. No es ~30 como
supuso §30. Y eso cambia todo el aritmético:

| tope | segundos por turno (a 6,1) | con límite 1800 | con límite 3600 |
|---|---|---|---|
| 4096 | 671 s | entra, sobran 1129 s | entra |
| 8192 | 1343 s | entra, sobran **457 s** | entra, sobran 2257 s |
| 10000 | 1639 s | entra, sobran **161 s** ⚠ | entra, sobran 1961 s |

**El corte del borde para pedidos no streameados son 300 s = ~1830 tokens.** Los transcripts
del 10-11 emitieron bastante más que eso, así que **opencode sí streamea** y la trampa de §30
no aplica acá. Eso se verifica con el dato, no se supone.

**Intervención, y por qué NO es 10000.** Subir el tope a 10000 dejando el límite en 1800 s
daría 161 s para escribir: habría movido la falla de «cortado por tokens» a «matado por el
reloj», con un diagnóstico nuevo y el mismo resultado. Van los dos juntos:

- `limit.output` del arquitecto: **4096 → 8192**
- `LIMITE_AGENTE` de `replanificar.sh`: **1800 → 3600**
- y un guardia, `presupuesto_coherente`, que hace la división **antes de lanzar** y se niega
  a arrancar si no entra. Tercera vez que el tope y el reloj se contradicen y la primera que
  hay un chequeo en vez de un comentario. La velocidad vive ahí con su fecha, para que se
  note cuando envejezca.

**Predicción, escrita antes de correr:** los cuatro transcripts dejan de cortarse a mitad de
palabra, y el arquitecto escribe en **≥2 de 4** tareas (T04, T16, T26, T28).

**Qué significa cada resultado:**

| se cortó | escribió | lectura |
|---|---|---|
| no | ≥2 | la causa era el presupuesto. Confirmado. |
| no | 0–1 | el presupuesto era necesario y no suficiente: ahí sí vuelve el prompt como candidato, **con la hipótesis vieja ya refutada una vez** |
| sí | — | la intervención no hizo lo que decía: no se lee el resultado, se arregla el instrumento |

### Resultado: ⊘. La tabla de arriba no tenía la fila que pasó

**4 de 4 intentos murieron con `inference timed out or returned no result`.** Ninguno llegó a
un veredicto, así que **el experimento no midió la hipótesis**. No es una confirmación ni una
refutación: es una tanda inválida.

| tarea | transcript | antes (2026-11-10) | cómo terminó |
|---|---|---|---|
| T04 | 307 b | 17 242 b | timeout, sin emitir nada |
| T16 | 24 084 b | 26 872 b | emitió y después timeout |
| T26 | 42 564 b | 17 262 b | emitió **2,5×** y después timeout |
| T28 | 27 445 b | 24 927 b | emitió y después timeout |

**El chequeo de manipulación SÍ pasó, y eso es lo que queda en pie.** Ningún transcript corta
ya a mitad de palabra: terminan una frase y recién ahí viene el error de la plataforma. T26
emitió 2,5 veces más que con el tope viejo. O sea que **subir el presupuesto hizo exactamente
lo que decía hacer** — el arquitecto dejó de quedarse sin tokens. Haber separado esa pregunta
de «¿sirvió?» es lo único que permite afirmar eso con la tanda invalidada.

### La pared, medida: no era la inferencia, y estaba escrita en nuestra propia documentación

Primero creí que era un timeout de inferencia de la plataforma. **Lo medí y es falso.** Un
pedido streameado de 8192 tokens tardó **1231 s y la plataforma lo completó bien**
(`finish_reason: length`, cerró con `[DONE]`, 6,65 tok/s). La inferencia andaba perfecta.

La pared es **el gateway, que corta cualquier pedido a los 20 minutos**. Y está en
[`../OPENCODE.md`](../OPENCODE.md) desde octubre, escrito por nosotros:

> `timeout: false` — sin tope total del lado de OpenCode. **El gateway corta igual a los 20 min.**

8192 tokens a 6,1 tok/s son **1343 s**: 143 segundos por encima del gateway. Las cuatro
replanificaciones murieron ahí, y el mensaje que llega —`inference timed out`— **apunta a la
inferencia cuando la inferencia no tuvo nada que ver**.

Van tres relojes distintos en un día, y el tope de salida no entra en ninguno por la misma
razón: nadie hizo la división.

1. el nuestro, `LIMITE_AGENTE`;
2. el del borde, 300 s para pedidos no streameados (§30);
3. **el del gateway, 1200 s**, que es éste.

**Y el peor detalle: el guardia que escribí ESE MISMO DÍA para que esto no pasara sólo
chequeaba contra el reloj nuestro.** Nuestro límite eran 3600 s, holgado, así que dijo que sí.
El dato del gateway estaba declarado en nuestra documentación y el que lo tenía que recibir no
lo recibía — el patrón de `METODO.md`, cometido por el chequeo que existe para evitarlo.
Arreglado: ahora el guardia toma **el reloj más corto**, no el nuestro, y dice cuál manda.

### El techo duro, y lo que se deduce de él

A 6,1 tok/s, el gateway de 1200 s pone un techo de **7320 tokens de salida por pedido**. No es
negociable con prompt ni con presupuesto.

| tope | segundos | ¿entra en 1200 s? |
|---|---|---|
| 4096 (el viejo) | 671 s | sí, margen 529 s — pero truncaba el razonamiento |
| **6000 (el nuevo)** | **984 s** | **sí, margen 216 s** |
| 7320 | 1200 s | justo en la pared |
| 8192 (el que probé) | 1343 s | **no**, 143 s de más |

Queda en **6000**: 46 % más presupuesto que antes y adentro del gateway con margen para el
prefill, que también corre contra ese reloj.

**Lo que se deduce, y es el hallazgo que vale:** si la deliberación de este modelo no entra en
7320 tokens, no hay tope que la haga entrar. O se achica lo que el arquitecto tiene que
deliberar, o se cambia el modelo del papel — que es exactamente la pregunta de
[`modelos-por-papel.md`](modelos-por-papel.md), el experimento bloqueado por K. Llegamos a ella
por el otro lado, con un caso real en vez de un banco congelado.

**Lo que me equivoqué, en el diseño y no en la ejecución:** la tabla de predicciones tenía tres
filas y ninguna decía «el intento no llega a terminar». Un diseño que no prevé que el sujeto
pueda no responder cuenta las no-respuestas como si fueran respuestas, y acá habría contado
cuatro «no escribió» —que es la fila que confirma mi propia hipótesis vieja—. Lo salvó haber
escrito la predicción antes y haber mirado CÓMO terminó cada intento, no sólo si escribió.

**La trampa de §30 quedó chequeada arriba**, con el dato y no con el supuesto.

### Segunda corrida — predicción escrita antes, ahora CON la fila que me faltó

Tope 6000 (984 s, adentro del gateway con 216 s de margen), guardia que mira el reloj más
corto, mismas cuatro tareas, mismo criterio del script: escribió o no escribió.

**Predicción:** ningún intento muere por reloj, y el arquitecto escribe en **≥2 de 4**.

| cómo terminó | escribió | lectura |
|---|---|---|
| completó | ≥2 | la causa era el presupuesto. Hipótesis confirmada. |
| completó | 0–1 | el presupuesto era necesario y no suficiente. Ahí vuelve el prompt como candidato, con mi hipótesis vieja ya refutada una vez |
| completó, truncado a mitad de palabra | — | 6000 tampoco alcanza, y el techo duro son 7320: **no hay tope que lo arregle**, y la respuesta es el modelo del papel |
| **≥2 murieron por reloj o plataforma** | — | **⊘ tanda inválida otra vez.** No se lee el resultado: se arregla el instrumento. *Esta es la fila que no escribí la primera vez y que fue justo la que pasó.* |

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

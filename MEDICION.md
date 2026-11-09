# Validación de instrumentos

**Un instrumento roto no hace ruido. Produce resultados limpios.**

[`PRUEBAS.md`](PRUEBAS.md) trata al verificador que *deja de mirar*: el gate que no corrió
ningún test y dice verde, el chequeo sin material que da un falso rojo. Este documento trata la
clase complementaria y más cara: **el instrumento que sí mira, mide limpio, y mide otra cosa** —
y te lo informa con tres decimales.

Los errores de medición de una sola jornada de investigación tienen una firma única:
resultado reproducible, explicación coherente, conclusión falsa. Ninguno se cayó. Todos
*midieron*. En todos los casos el sujeto medido estaba bien.

Son **ocho**: uno por fila de la tarjeta de §1, y cada uno nombrado ahí con fecha recuperable
del repo. Están contados así a propósito. Una versión anterior de este documento decía «once»
tres veces y nombraba ocho —en el documento que hace de la trazabilidad su regla de admisión—, y
el primer intento de arreglarlo fue peor: decía «ocho más los tres de los paréntesis de §2», y
§2 tiene once paréntesis, así que no se puede saber cuáles tres. **Un cadáver que no se puede
nombrar no justifica una verificación**, y el conteo es parte de la verificación.

> La inversión en el instrumento se hace en la primera hora o se paga en el día completo.

---

## 1. La tarjeta: ocho preguntas, antes de correr

Cada una se contesta SÍ o NO **antes**, por escrito, en el encabezado del log. Un NO es una
parada, no una nota al pie.

**Una pregunta atrapa si y sólo si nombra un comando, no una creencia.** Ésa es la regla que
decidió qué queda y qué sale: de la primera versión de esta tarjeta, cuatro preguntas se podían
contestar SÍ de buena fe mientras el error pasaba igual, porque pedían un conocimiento que sólo
da la medición. Las que atrapan son las que piden un **acto**: leé el estado, corré el test ahí,
escribí el registro al empezar, mirá el esquema.

| # | Pregunta | Error que previene |
|---|---|---|
| 1 | ¿Cuántas veces corro cada celda, y cuánto varía el sujeto consigo mismo? **Un n=1 es una parada.** | La MISMA petición a `temperature 0` dio un `tool_call` una vez y prosa la siguiente. El éxito por corrida es una muestra, no un valor, y `temperature 0` **no** da determinismo en vLLM con batching continuo. Un banco de 6 casos con n=1 decidió asignaciones de papel. *(Reemplaza a «¿sé mi timeout y el peor caso del sujeto?», que no atrapaba nada: el peor caso que importaba era el de la **plataforma** informando su propio error, 68,4 s, y ése se conoce después. Ese contenido vive ahora en el código —`INACTIVIDAD=90`— y en el régimen de §5.)* |
| 2 | ¿El registro se escribe al **empezar** cada evento, no al terminarlo? | «El cliente nunca manda la petición»: el proxy anotaba al cerrar la respuesta, así que las peticiones que morían en vuelo no se anotaban. |
| 3 | ¿Tengo una corrida de control donde el resultado esperado es **conocido y distinto del nulo**? | Los 0 de 6 del modelo de un partner informados como «no sirve», cuando el pedido iba con `stream: false` y en ese modo **ningún** modelo emite llamadas a herramientas. |
| 4 | ¿El test **falla** contra el código sin arreglar, lo comprobé corriéndolo ahí, **y falla por el motivo correcto y no por otro**? | El test del método que pasaba porque matcheaba un comentario que ya estaba en el gate. Y el motivo: revertir pacman T14 da rojo por un `ImportError` que se lleva 21 tests ajenos, y clasificados T02 aborta la colección del backend entero — rojo, sí, pero no por lo que se quería medir. |
| 5 | ¿Verifiqué la precondición **leyendo el estado**, y corrí el **brazo nulo** (el sujeto reemplazado por un no-op, que tiene que dar rojo en todos)? | `git revert --no-commit <sha> -- <ruta>` acepta la ruta, la ignora en silencio y no revierte nada: las quince celdas de la matriz «pasaban» sin que los modelos hicieran nada. Y el caso en el que fallé escribiendo esta misma pregunta: la «implementación» de una tarea eran tres `__init__.py` vacíos —0 inserciones, 0 borrados—, de ahí deduje que revertirla no cambiaba nada, y no corrí el test. Lo corrí después: **falla**, porque git no versiona directorios vacíos y el test verifica que el directorio exista. Deducir la consecuencia de aplicar el parche no es correr el test. |
| 6 | ¿Medí la **precisión y el recall del corrector** contra 20–30 casos etiquetados a mano, con trampas? | El corrector concatenaba `content` + `reasoning` y puntuaba la mezcla: el pensamiento reformula la pregunta, así que contiene las palabras clave que el patrón busca. Daba ✓ a razonamientos que terminaban en una respuesta equivocada, e invalidó la campaña entera de dos modelos. *(Nombrar el campo —la versión anterior de esta pregunta— se contestaba SÍ de buena fe: «el campo es `content`, el razonamiento va en `reasoning`, el modelo declara `reasoning: false`». Las tres cosas eran ciertas y el error pasó igual. Lo que lo atrapa es medir el corrector, que es un acto.)* |
| 7 | ¿El diff de los dos pedidos crudos, **impreso por la máquina**, es de una línea — y el orden y el estado de caché son iguales entre brazos? | El A/B de «prompt corto vs. largo» que además cambiaba el directorio de trabajo y la cantidad de trabajo: quien lo corrió escribió «cambia el prompt» de buena fe, porque enumerar a mano sólo enumera lo que ya sabés que difiere. Y el caché de prefijo está medido a 16× en TTFT, con `cached_tokens` que la plataforma ya informa y que §5 no pedía. |
| 8 | ¿El esquema tiene **INVÁLIDO distinto de FALLA**, y tengo un sujeto que se sabe **MALO** que tiene que volver FALLA y no INVÁLIDO? | La respuesta vacía por modelo frío contada como respuesta equivocada. Y el espejo, que es peor: GLM-4.7-Flash contestó vacío 6 de 6 y **desapareció de la tabla de razonamiento publicada** en vez de sacar 0. Un instrumento que no puede reprobar a nadie hace pasar a todos. |

Las ocho caben en diez líneas de YAML arriba del log. Si no están, el número no se cita.

---

## 2. Los cinco mecanismos

Agrupados por **cómo fallan**, no por cómo se ven. Casi todos los síntomas de esa jornada se
veían como «cuelgue» o «el modelo no sabe»; los mecanismos son estos cinco.

**M1 — Terminación impuesta.** El instrumento corta al sujeto y la interrupción se lee como dato
del sujeto. *(El vigilante que corta antes del mensaje de error; el test cuyo sujeto termina
antes del momento en que se toma la decisión, y pasa por llegar tarde.)*
**Firma:** el resultado cambia si aflojás un límite que no es parte de la hipótesis.

**M2 — Observación incompleta.** El evento ocurrió; el registro no existe; la falta de registro
se lee como falta de evento. *(El proxy que anota al cerrar la respuesta.)*
**Firma:** tu conclusión es sobre algo que **no** aparece.

**M3 — Sujeto sustituido.** *(Y su variante más barata de cometer: el mensaje de error que
nombra un identificador que no es el tuyo. La plataforma reprobó una corrida con «Failed to
start inference server for `da003b52…`», un id que no está en nuestra config, y la lectura
inmediata fue «nuestro id quedó viejo». **Falso**: sondeados los dos, el nuestro responde 200 y
el del error da 404. Son dos espacios de ids —el de las peticiones y el interno de deployment—
y los errores usan el interno. La causa real era otra: VRAM agotada en ese instante. Sondear
los dos ids cuesta diez segundos y evita reescribir una config que estaba bien.)* Medís algo que no es lo que creés: otro campo, otro modo, otro
estado, otro archivo. *(Pensamiento en vez de respuesta; `stream: false` donde el fenómeno es
imposible; la reversión que no revirtió; el test que matchea un comentario en vez de la
conducta.)*
**Firma:** hay una corrida que debería dar negativa y da igual que la positiva.

**M4 — Oráculo que no discrimina.** El corrector no separa lo que dice separar. *(Regex sobre
palabras clave: falso positivo con razonamiento equivocado que menciona la palabra, falso
negativo con respuesta correcta redactada distinto; vacío clasificado como incorrecto.)*
**Firma:** nunca lo medíste contra etiquetas humanas.

**M5 — Contraste contaminado.** La diferencia existe, pero no es atribuible. *(Tres variables en
un A/B; antes/después sin testigo, con infraestructura que pudo cambiar en el medio.)*
**Firma:** no podés nombrar la única cosa que cambió.

M1 y M2 son la pareja más cara: **M1 fabrica el silencio, M2 lo hace invisible**, y juntos
producen una historia causal completa y falsa.

---

## 3. El control, por tipo de medición

El control va **en la misma corrida**, como brazo extra. No es una sesión aparte que se hace
«cuando haya tiempo», porque nunca hay.

| Tipo de medición | Control | Qué tiene que dar |
|---|---|---|
| Latencia / cuelgue | Brazo con el límite en 3× (o sin límite) y un sujeto de duración conocida | El sujeto conocido tarda lo que tarda. Si el límite cambia el veredicto, medíste el límite. |
| Capacidad del modelo | Positivo: configuración donde se sabe que el fenómeno aparece. Negativo: pedido imposible | Positivo ≠ nulo. Si todos dan cero, el cero es del arnés. |
| Capacidad del modelo, **el espejo** | Un sujeto que se sabe **MALO** (acá: CodeScout-1.7B devolviendo 8 caracteres) | Vuelve **FALLA**, no INVÁLIDO. Si vuelve INVÁLIDO, el instrumento no puede reprobar a nadie y la corrida se descarta. Ver §4. |
| Observabilidad | Evento sintético inyectado a mano | Aparece en el log, con su marca de inicio. |
| Test de regresión | El commit sin el arreglo | Rojo, **y por el motivo correcto**, no por otro. |
| Precondición / estado | Lectura directa del estado después de establecerlo, más un sujeto mutante que debería fallar | El mutante falla. |
| Corrector / oráculo | 20–30 casos etiquetados a mano, con trampas: correcta redactada distinto, incorrecta que menciona la palabra, vacía, razonamiento que reformula la pregunta | Precisión y recall medidos, versión del corrector anotada. |
| Antes / después | Brazo testigo sin el cambio, corriendo **intercalado** en la misma ventana | El testigo no se mueve. Si se mueve, se movió la infraestructura. |

**Cuando el control falla, el resultado se descarta entero.** No se interpreta, no se corrige, no
se «ajusta por», no se salva el brazo que te gustó. El control fallando es un hallazgo —sobre el
instrumento— y es el único hallazgo de esa corrida. Se arregla y se vuelve a correr **todo**,
incluidos los brazos que habían dado bien: si el instrumento estaba mal, su acierto también es
sospechoso.

Esto ya nos salvó un reporte: cinco fallas limpias y reproducibles del modelo de un partner iban
a salir como veredicto sobre el modelo. El control no se había movido —salidas idénticas carácter
por carácter en dos tandas separadas por horas—, y eso fue lo que mostró que la mejora de
plataforma era específica y no general.

---

## 4. «No se pudo medir» ≠ «se midió y dio mal»

Tres valores mínimos, obligatorios en el esquema: **PASA / FALLA / INVÁLIDO**.

Un INVÁLIDO contado como FALLA es la falla más cara que existe, y no por el error de un punto:
**porque se vuelve inmune a la revisión.** Un INVÁLIDO visible detiene la cadena ahí mismo. Un
INVÁLIDO disfrazado de FALLA entra en el promedio, se grafica, se cita en una decisión, y se
revisa recién cuando alguien pregunta por qué el modelo barato gana.

De los once errores de esa jornada, **cinco son invalidez disfrazada de resultado**: el
vigilante, el proxy, el vacío por frío, el modo sin llamadas y la reversión que no revirtió. Los
cinco eran «no se pudo medir» informados como «el sujeto falló».

**La carga de la prueba es del instrumento.** Ausencia de evidencia de éxito no es evidencia de
falla. Vacío, truncado, timeout, excepción del arnés, control caído o precondición no verificada
→ INVÁLIDO.

### Y el espejo, que es el que hace pasar a todos

Lo de arriba es unidireccional, y así escrito deja un agujero: **el ⊘ que tapa un resultado
real.** El instrumento contesta «no pude medir» cuando en verdad midió y el sujeto falló. Eso lo
vuelve incapaz de reprobar a nadie, y entonces todo pasa.

Está vivo y medido. GLM-4.7-Flash contestó vacío 6 de 6 y **no aparece** en la tabla de
razonamiento que publicamos: el camino del ⊘ lo hizo invisible en lugar de darle 0. El modelo
peor comportado desapareció del ranking. Y el paso 4 del gate —el único chequeo de que los
tests **distinguen**— tiene las dos mitades del problema: en `plantillas/gate.sh`, cuando no
puede acotar por clase de test, hace `vacuo` y sale con `exit 0`, o sea que **ahí el ⊘ sí es un
pase**, al revés de lo que esta sección dice. Y en el gate que los proyectos usan de verdad es
peor que un ⊘: exige sólo que falle la suite **entera**, y la suite de clasificados está roja en
HEAD por diseño (tests-first), así que imprime `✓ la suite falla al revertir …` **siempre**. Un
falso verde es un INVÁLIDO que ni se declara.

**El control que lo detecta es el espejo del control positivo: un brazo con un sujeto que se
sabe MALO, que tiene que volver FALLA.** Si vuelve INVÁLIDO, el instrumento no puede reprobar y
la corrida se descarta. En este repo el sujeto ideal existe: CodeScout-1.7B devolviendo 8
caracteres, 3 de 3, en dos tandas separadas por horas.

Y la regla de código que lo cierra, que ya está escrita en `scripts/_comun.sh`: **el veredicto
viaja por stdout, no por el código de salida.** `python3 … || return 2` hacía indistinguible el
«no está declarado» de un python que se cayó, y el chequeo contestaba ⊘ para el único caso que
existía para detectar.

Y la tasa de inválidos se informa **siempre, al lado del puntaje**. Un 70 % con 30 % de
inválidos no es un 70 %.

**Un inválido que se anota como reprobado es el mismo agujero por el otro lado.** Medido el
2026-10-19: el ejecutor escribió `<tool_call>` en el contenido en vez de pedir la herramienta
por su canal. Nadie la ejecutó, no recibió resultado, y la corrida murió sin tocar un archivo.
El gate dijo lo único que podía —«no hay ningún cambio: la tarea no se hizo»— y eso, en la
columna de `comparar-modelos.sh`, se cuenta como que **el modelo no pudo con la tarea**. Es un
fallo de protocolo entre el modelo y el arnés, y el mismo modelo había escrito bien el test de
esa misma tarea veinte minutos antes. Lo detecta `error_del_agente` en `scripts/_comun.sh`, y
está anclado a principio de línea a propósito: un detector que marca también a quien sólo
*menciona* `<tool_call>` marca a todos, y entonces no distingue a ninguno.

### Y los de casa: tres números que no podían fallar

La sección de arriba habla de medir modelos. El mismo día encontramos tres números del
**propio tablero** con el defecto, y los tres los había escrito yo:

| el número | por qué no podía fallar | cómo se arregló |
|---|---|---|
| «✓ gate VERDE» del runner | inserté el bloque de memoria entre `cerrar_con_gate` y su `local rc=$?`, y un `if` con condición falsa vale 0: imprimía VERDE **siempre** | capturar `$?` pegado a la llamada, y un test que reprueba cualquier cosa insertada en el medio |
| «tronco: ✗ ROJO» de `estado.sh` | durante una etapa tests-first el tronco está rojo por diseño, así que ese veredicto no podía dar **verde** mientras durara la etapa | declara el rojo de la etapa y **nombra** el test en vuelo. **Ese arreglo tampoco alcanzaba** (ver abajo): bastaba que existiera un test en vuelo para que las fallas reales no se imprimieran |
| el presupuesto de cortes por tarea | seguía contando después de que yo cambiara el enunciado, así que el contador mezclaba dos experimentos y lo que iba a frenar la etapa era él y no la tarea | si cambia la huella del enunciado que el agente va a leer, intentos y cortes vuelven a cero |

Los dos primeros son el mismo defecto en espejo: uno no podía dar rojo, el otro no podía dar
verde. El tercero es más fino y vale como pregunta propia: **¿este contador sigue hablando del
mismo sujeto?** Un presupuesto gastado contra un enunciado que ya cambié no limita al que
corre ahora, limita al que ya no existe.

La pregunta que los atrapa a los tres, y que no es la misma que la del ⊘: **¿hay algún estado
del mundo en el que este número salga distinto?** Si no lo hay, no es una medición, es una
constante con disfraz.

### Qué fila puede entrar a una tasa

La auditoría del 2026-10-20 sobre el aparato de medición encontró **tres clases de fila que no
hablan del ejecutor** y que el instrumento contaba como su rojo o como su verde. Las tres
estaban nombradas en este documento y ningún script las leía.

| la fila | el propio método ya decía | qué hacía el lector |
|---|---|---|
| **inválida del método** | `correr-suite.sh` declara `exit 3` = «defecto del método o del plan, no del código que se juzga», y §6.3 nombraba las cinco filas | las contaba como ROJO del modelo |
| **perdida por la plataforma** | el informe imprime «no cuentan contra el modelo» tres bloques más abajo | una fila `ERROR` hacía de «primer intento» de su tarea y la marcaba ✗ |
| **no atribuible a un modelo** | `cerrar-tarea.sh` escribe `modelo=humano` en el mismo registro | la contaba como verde del modelo |

El efecto, medido:

| proyecto | antes | ahora |
|---|---|---|
| clasificados | 47% | **50%** |
| pacman | 61% — «la descomposición funciona» | **44%** — «tareas demasiado grandes o criterios flojos» |

**El método no tenía ningún proyecto en el que la descomposición funcionara; tenía uno en el
que el instrumento lo decía.** El 61% del pacman se apoyaba en una fila con `segundos=0` y
`modelo=humano` más tres con la columna de modelo vacía.

Y una nota sobre auditar: el auditor estimó que arreglar la primera clase llevaba clasificados
de 47% a 60% y cambiaba la banda. **Verificado: no.** Al descartar el intento inválido, el que
pasa a ser «el primero» de esas tres tareas también es rojo. La dirección del hallazgo era
correcta y la magnitud no, y la diferencia importaba porque la magnitud era el argumento.
Un hallazgo que llega con su número todavía necesita que se corra el número.

#### La cuarta clase, que no se puede filtrar y por eso se arregla arriba

El 2026-10-26 apareció una cuarta: **el intento sobre una tarea que ya estaba hecha.**
`correr-plan.sh` relanzó una etapa entera de tareas integradas —las etapas DECLARADAS en el
plan no se filtraban por estado— y el registro quedó con cinco rojos de «no hay ningún cambio:
la tarea no se hizo». El informe los contó: «Verde al PRIMER intento: 3/5 (60%) → la
descomposición funciona», con tres de esas cinco filas midiendo un defecto del runner.

**Y no se puede filtrar con lo que el registro guarda.** Ese mismo motivo es la falla legítima
de un agente que no hizo nada —se quedó sin contexto, se confundió, contestó prosa— y ésa sí
cuenta contra el modelo. Distinguirlas necesita el ESTADO DE LA TAREA en el momento del
intento, que el registro no anota. Inventar el filtro por el texto del motivo descartaría
fallas reales del ejecutor, que es el error opuesto y peor.

Así que el arreglo va arriba, no en el lector: el runner ya no lanza lo que está hecho, y esas
filas no vuelven a escribirse. Queda anotado porque la tentación de filtrar era fuerte y el
precedente de las otras tres clases la hacía parecer obvia: **una clase de fila que no se puede
separar con los datos que hay no es una clase que se filtra, es un defecto que se arregla donde
se produce.**

### Dos cosas que un número de tiempo no puede llevar adentro

1. **El techo del propio vigilante.** 6 de las 16 filas que entraban a la mediana eran
   `ERROR`, 4 con «límite total 1200s» en el motivo. El «máximo» que se imprimía era un
   ROJO de 1855 s —más largo que el límite, porque el número incluye el gate— y el éxito más
   lento medía 970. Y es ese máximo el que el método mandaba mirar para dimensionar el
   presupuesto del agente: calibrar un presupuesto con el techo de la propia regla es
   medirse con la regla. Hoy el instrumento imprime una línea **«éxito más lento»** aparte.
2. **La ocupación de la plataforma.** La columna `concurrencia` existe para eso, y se estaba
   midiendo al CERRAR la corrida en vez de al arrancarla: cuatro tareas lanzadas en 12
   segundos, solapadas por completo, quedaron con 1, 2, 2 y 0 — valores que decrecen con el
   orden de finalización. La que compitió con tres durante sus 970 s enteros quedó anotada
   como la única serializada. **Una columna que se escribe en el momento equivocado miente
   con más autoridad que una que falta**, porque nadie la mira dos veces.

---

## 5. El régimen: qué va al lado de cada número

Un número sin régimen no es reinterpretable después, y «después» es cuando siempre se necesita.
Se registra en automático, junto al resultado, no en el acta de una reunión.

- Sujeto: commit / digest / id de modelo exacto, con fecha (el ruteo cambia sin avisar).
- **Modo de transporte**: `stream` sí o no. Explícito, siempre.
- **Campo leído**: ruta exacta de dónde salió el dato, y si se separó razonamiento de respuesta.
- Límites: timeouts, reintentos, topes de tokens, y **quién** los impone (tu arnés, el cliente,
  el proxy, la plataforma). El doble lugar de declaración es una fuente propia de errores
  (ver la tabla de entorno en [`METODO.md`](METODO.md)).
- Frío o caliente; cuántas corridas se descartaron como arranque.
- Vecinos: **concurrencia** (corridas vivas al arrancar, como columna y no como nota: toda fila
  con concurrencia > 1 queda fuera del análisis de tiempo **por construcción**, no por criterio
  del analista), y si había un deploy en curso. *Durante un deploy no se mide: la medición no
  sirve, hay que esperar.*
- **Estado de caché de prefijo**: `usage.prompt_tokens_details.cached_tokens`, que la plataforma
  ya informa y no estábamos guardando. Está medido a 16× en TTFT, y el brazo de control es por
  definición el mismo prompt siempre — así que es el más barato en reloj **y por eso mismo no
  mide lo mismo que un brazo frío**. Ese canje va declarado, no aprovechado en silencio.
- **Huella del instrumento**: `git rev-parse HEAD:scripts`. Dos filas con huellas distintas no
  se comparan (regla de parada, punto 7).
- Contexto de tarea: directorio de trabajo, cantidad de trabajo pedida, prompt con hash.
- Corrector: versión, y su precisión / recall contra las etiquetas humanas.
- Resultado del control, textual.
- Conteo de PASA / FALLA / **INVÁLIDO**.
- Marca de tiempo con huso.

---

## 6. Regla de parada

Dejá de medir y arreglá el instrumento cuando pase **cualquiera** de estas:

1. **El control falló.** Inmediato, sin excepción.
2. **El resultado es degenerado** (todos 0, todos 1, todos idénticos). Un resultado degenerado es
   culpa del instrumento hasta que se pruebe lo contrario.
3. **No sabés la tasa de inválidos**, o la tasa **difiere entre brazos en más de 5 pp** —y
   entonces se corre la sensibilidad con ⊘ contado como fallo, y se informa como amenaza.
   *No un umbral absoluto:* la tasa histórica real de este repo es **15 %** —9 de 60 intentos:
   `Cannot find native binding` de npm ×5, `No module named pymysql` ×1, `Failed to resolve
   import` ×1 y **2 sin motivo registrado**— y sube a **23 %** contando además los rojos cuyo
   motivo es del método y no del código (`falta el corredor de tests`, `la suite no corrió
   ningún test`: 5 filas más). Un umbral plano del 10 % manda parar siempre, y una
   regla que manda parar siempre no se respeta nunca — el costo no es que se ignore esa regla,
   es que entrena a saltear la lista entera. Lo que rompe la atribución es la **diferencia entre
   brazos**, no el nivel: los 9 vacíos del banco de herramientas no estaban parejos —GLM aportó
   6—, así que la regla diferencial habría disparado y la absoluta no distingue.
4. **El síntoma aparece en sujetos que no comparten nada.** Si tres modelos de tres proveedores
   se «cuelgan» igual, el cuelgue es tuyo.
5. **Un número sin su régimen se citó en una decisión.** Ésta es la forma ejecutable de «te
   escuchás explicando el resultado con una hipótesis sobre el sujeto antes de haber mirado el
   instrumento», que era la versión anterior y **no sirve**: no es verificable por nadie más que
   el propio medidor, §7 dice que no hay revisor humano, y el caso estrella del repo es uno
   donde la regla no disparó —horas descartando diez hipótesis sobre el sujeto, una por una y
   con prueba, mientras el cuelgue lo causaba el `perl -e 'alarm 90; exec'` del medidor—. No
   disparó en la persona que la escribió. La versión ejecutable es una columna:
   **ninguna fila con `control_ok` distinto de 1 entra en una cita.**
6. **No podés reproducir el fenómeno fuera del arnés** (a mano, con el comando crudo). Una
   corrida de intento; si no sale, el fenómeno es del arnés.
7. **Cambiaste el instrumento entre dos corridas.** No son comparables. No las compares «por
   ahora».

---

## 7. Que no se vuelva papeleo

- **Tiene que vivir en código, y hoy casi nada vive.** Hay que decirlo así: una versión
  anterior de esta sección afirmaba que «el runner se niega a arrancar si el brazo de control no
  está declarado» y que «emite el bloque de régimen solo». **Las dos cosas eran falsas**: no hay
  un solo brazo de control en ningún script, y de los trece ítems de régimen de §5 el registro
  escribe dos y medio. Un documento sobre instrumentos que describe un instrumento que no existe
  es el error que viene a prevenir.

  Lo que **sí** está en código hoy, con su test en `pruebas/test_metodo.py`:

  | Pregunta | Dónde vive |
  |---|---|
  | 1 (n y varianza) | `pruebas/bancos/razonamiento.py`: `REPS=3`, la mayoría en `resolver()`, e inestabilidad informada por caso. Las tres con test: una auditoría encontró que sólo `REPS=3` lo tenía, y la regla de mayoría estaba incrustada en el bucle de la campaña — o sea no ejercitable sin gastarla. Se sacó a función. |
  | 6 (el corrector) | el mismo banco: lee `content`, corta el pensamiento, y la campaña corre bajo `__main__` para poder ejercitar el corrector sin lanzarla |
  | 8 (INVÁLIDO ≠ FALLA) | el `vacuo()` del gate (`TestVacuidad`) y el `⊘` del banco, incluido el espejo: *contestó 2 de 3 y las dos mal* vuelve **FALLA**, no ⊘. Con la deuda de §4: en el paso 4 del gate el ⊘ todavía da `exit 0`, y en el gate que los proyectos usan da un ✓ que no verificó. |
  | el régimen, parcial | `anotar_intento` en `scripts/_comun.sh`, con el encabezado verificado contra lo que escribe el runner |
  | el tiempo que no se puede medir | `scripts/comparar-modelos.sh` (`SERIE=1`, y `SEGS = —` en paralelo) y `scripts/metricas.sh` (sin mediana si las corridas comparten ventana) |
  | «no es el modelo, es nuestra config» | `modelo_declarado` en `scripts/_comun.sh` |

  Y lo que faltaba cuando esto se escribió **ya está**, con su test:

  | Pregunta | Dónde vive |
  |---|---|
  | 3 (control con resultado conocido) | `scripts/comparar-modelos.sh` **se niega a arrancar sin `CONTROL=`** y lo corre siempre como un brazo más de la misma tanda. `CONTROL=ninguno` es la salida explícita, y queda escrita al pie de la tabla. |
  | 8, el espejo | `pruebas/bancos/razonamiento.py`: `MALO_CONOCIDO=<id>` corre un sujeto que se sabe malo **antes** de la campaña y la aborta si no reprueba. Un corrector que no puede reprobar a nadie no mide nada. |
  | el régimen, dos campos más | `anotar_intento` escribe **`concurrencia`** (corridas vivas al arrancar: lo que decide si la fila sirve para medir tiempo) y **`instrumento`** (`git rev-parse HEAD:scripts`: el punto 7 de la regla de parada, que antes no tenía cómo saberse). `metricas.sh` saca la mediana **sólo de las corridas con concurrencia 1** y declara las que no tienen el dato. |

  La aserción de encabezado ya atrapó su primer caso real, y fue mío: al agregar esas dos
  columnas, `metricas.sh` seguía esperando siete y lo dijo en la primera corrida.

  **Y el criterio de validez del control también está, desde el 2026-10-08**:
  `control_se_movio()` en `scripts/_comun.sh`, y el comparador **aborta con código 1** cuando
  el control se movió — informarlo no alcanzaba.

  La banda que el diseño proponía, ±2 ítems sobre 12, estaba calculada con p=0,83, que es la
  tasa de **tool-call**. La tasa de **verde** del control, medida en el registro, es **0,42 por
  corrida** (22 de 52), y con ésa ±2 descarta el **29 %** de los bloques buenos: el protocolo
  se auto-invalidaba sin parar. ±4 da 5,6 % y ±5 da 1,9 %, y una banda de ±5 sobre doce ítems
  ya no controla nada — ésa es la señal de que **un conteo binomial de doce no puede ser el
  control**. El criterio quedó continuo y sobre lo que tiene varianza baja: las llamadas a
  herramientas del control, más su veredicto. Si deja de actuar, se movió el arnés, y eso se ve
  con pocas corridas.

  La regla vive en una función y no dentro del comparador por el mismo motivo que la mayoría
  del banco: **una regla que decide el resultado tiene que poder ejercitarse sin correr la
  campaña.** Seis casos pineados, incluido el que evita el auto-sabotaje: una variación chica
  **no** descarta la tanda.
- **Ocho preguntas, no cuarenta.** Si crece, se poda. Una verificación que en tres meses no
  atrapó nada, sale.
- **Para entrar, una verificación necesita un cadáver con nombre y fecha.** Sin postmortem que
  la justifique, no entra. Y si crece, se poda: las cuatro preguntas que esta versión reemplazó
  salieron por no atrapar nada, no por falta de lugar.
- **El control se paga en la misma corrida — y no es «un brazo más».** También hay que decirlo:
  en el experimento de memoria los controles son **tres brazos extra** de cinco: de 160 llamadas
  a 400, **+150 %**. En el de modelos, un brazo de control por bloque más el brazo nulo suman
  ~17 corridas sobre las 81 de su fase principal, **+21 %**. No el 4 % que una versión anterior
  declaraba. *(Esa versión decía +58 % para el de modelos y no salía de ninguna cuenta: era un
  número sin procedencia en el documento que exige procedencia.)* Subestimar el costo del control ~10× es justo la
  condición bajo la cual a las dos de la mañana se saltea.

  Lo que lo vuelve pagable: **el control más barato es un no-op.** El brazo nulo reemplaza el
  sujeto por `con_limite 5 true` y cuesta sólo el gate; el brazo de control no necesita el banco
  completo, porque su trabajo es «¿se movió el arnés?» y con 3 ítems fijos por bloque alcanza
  —a cambio de reformular su criterio de validez, que hay que escribir—.
- **Sin revisor humano.** No hay aprobador ni checklist que alguien firma. Hay una sola regla
  social: **un número sin su régimen no se cita** —ni en un mensaje, ni en un gráfico, ni en una
  decisión—. Quien lo cita sin régimen tiene que volver a medir, y eso alcanza.

---

## 8. Dónde se aplica

Los dos experimentos diseñados contra este protocolo están en
[`experimentos/`](experimentos/): la memoria verificada y la evaluación de modelos por papel.
**Los dos están bloqueados, y los dos se bloquearon por este documento**: la pregunta 5 (leer el
estado, correr el brazo nulo) encontró que 13 de 21 ítems candidatos no son admisibles y que uno
de ellos deja la suite verde al revertirlo; la pregunta 1 (n y varianza) encontró que el n
efectivo de la campaña de memoria era 24 y no 168.

Eso es lo que esta tarjeta tiene que hacer: **gastarse en una tarde de lectura en lugar de en
cuatro días de clúster.** Las dos campañas juntas pedían 120 horas de máquina para producir
números limpios y falsos.

Y la deuda que este documento se cobra a sí mismo, medida corriendo los tres gates: el paso 4
—el chequeo de que los tests distinguen— **no existe** en el gate de pacman, y en el de
clasificados exige sólo que falle la suite **entera**, que está roja en HEAD por diseño
(tests-first). O sea que ahí da `✓` sin haber verificado nada. Y en la plantilla, cuando no
puede acotar por clase de test, hace `vacuo` y sale con `exit 0`.

§4 dice que un chequeo que no pudo correr no es un chequeo que pasó, y el código dice lo
contrario de las dos formas posibles: con un ⊘ que es un pase y con un ✓ que no verificó.
**Mientras siga así, «gate verde» no es una métrica primaria válida para ningún experimento de
este directorio**, y está escrito acá para que no se me pase.

## 9. El ensayo determinista: medir la orquestación sin modelos

Hasta el 2026-10-26, lo más largo que el pipeline había ejecutado de verdad eran **cinco
tareas**, y «un plan de veinte» era una afirmación. El problema no era el tiempo: era que con
modelos de verdad **la orquestación no se separa del modelo**. Un modelo contesta distinto cada
vez, así que una corrida roja no dice si falló el método o el ejecutor, y repetirla cuesta horas
de plataforma.

`scripts/ensayo.sh` cambia el sujeto: el agente es DETERMINISTA —un `opencode` que, en vez de
pedirle a un modelo, copia la implementación congelada de la tarea que el prompt nombra— y el
resto del pipeline es el de verdad. Lo que falle es del método.

**Lo que mide**: etapas, worktrees, `escribir-tests` con su validación, el gate, el cierre y el
merge, a cualquier escala, repetible y a cero tokens.
**Lo que NO mide**: si un modelo chico puede hacer la tarea. Eso es el banco de ítems
(`congelar-banco.sh`) y es otra pregunta — confundirlas es medir el eslabón equivocado.

### Medición 1 — veintiuna tareas, 3 etapas de 7 en paralelo (2026-10-26)

    GRUPOS=7 bash $AGENTES/scripts/ensayo.sh

| qué | resultado |
|---|---|
| tareas cerradas | **21 de 21**, un intento cada una (`intentos.csv`: 21 filas) |
| gates | 21 verdes, 0 rojos |
| integraciones | 21, **sin un solo conflicto de merge** con 7 ramas por etapa |
| suite del proyecto al final | 21 tests, verde |
| duración | 4 min 52 s · 0 tokens de modelo |

Es la primera vez que «veinte tareas» está medido y no afirmado. **Lo que sigue sin medirse es
ejecutarlas con modelos**: eso son veintiuna corridas de agente y es otro costo y otra clase de
falla.

### Medición 2 — ¿el gate atrapa cada forma de fabricar un verde falso? (2026-10-26)

    GRUPOS=1 COMPORTAMIENTO=miente bash $AGENTES/scripts/ensayo.sh

El comportamiento se elige **por fase**: si el agente falla escribiendo los tests, la etapa se
detiene ahí y el gate no llega a juzgar nada, así que para medir el gate los tests se escriben
bien y falla sólo la implementación. Son dos sujetos distintos.

| el agente | paso que lo atrapa | motivo del rojo |
|---|---|---|
| no escribe nada | 1, tests | «los tests de T01a siguen fallando», con el `ImportError` |
| **afirma «GATE VERDE»** | 1, tests | el mismo: el veredicto lo da el comando, no el agente |
| escribe fuera de su alcance | 2, alcance | nombra el archivo que no declaró, y al lado lo permitido: `src/datos/d1.py` |
| afloja el test que lo juzga | 0, integridad | «tocó archivos intocables: `tests/test_d1.py`» |

Cuatro formas, cuatro rojos por el paso que corresponde, **cero verdes falsos**. Y el ensayo se
juzga a sí mismo: con un comportamiento malo, PASA cuando el pipeline se detiene y ninguna tarea
cierra; si cerrara alguna, informa «es un VERDE FALSO» y sale ≠0. Verificado mutando el agente
para que «nada» cumpla: el ensayo lo cazó.

### Medición 3 — ¿el validador de tests atrapa un test que no verifica nada? (2026-10-26)

    GRUPOS=1 COMPORTAMIENTO_TESTS=tests_flojo bash $AGENTES/scripts/ensayo.sh

El gate ya estaba medido; el VALIDADOR DE TESTS no, y es la pieza que decide qué entra al
tronco — de ahí en adelante es el juez de todo lo demás. Sus cuatro afirmaciones están en el
encabezado de `escribir-tests.sh`, así que hay un comportamiento por afirmación:

| el test que escribe el agente | afirmación | ¿lo atrapó? |
|---|---|---|
| pasa contra el código actual (no prueba nada) | 1 | sí |
| no pasa ni con la implementación de referencia | 2 | sí |
| **pasa con la referencia y sobrevive a la mutación** | 3 | **NO — cerró las 3 tareas** |
| el archivo y la clase no son los del plan | 4 | sí |

Tres de cuatro. La cuarta **cerró las tres tareas con tres gates verdes** con un test que sólo
afirmaba `assertIsNotNone(leer1())` para una tarea cuyo contrato dice «devuelve 1».

La causa, y es más interesante que el síntoma: el paso de mutación **no tenía nada que mutar**.
`def leer1(): return 1` no produce candidatos —`Return` está excluido del borrado de sentencia,
no hay comparación ni booleano ni aritmética, y la heurística `hojas_todas_return` marcaba árida
la función entera— así que el paso informaba

    ⊘ no hubo nada que mutar … el tercero (¿distingue?) no pudo verificarse. No es un pase.
      ⊘ el diff no tiene nada que mutar con provecho (todo árido o sin operadores)
         No es un pase: no se probó ni un mutante.

y el validador **aceptaba igual**. El mensaje decía «no es un pase» y la decisión lo tomaba como
pase: §4 de este documento, violada en el punto donde se decide.

Y el ⊘ no era un borde: `return <literal>` es la forma NORMAL de una tarea chica, que son las
que este método apunta.

El arreglo no fue tocar la decisión —rechazar por ⊘ habría bloqueado también a los tests
BUENOS, que tenían el mismo ⊘— sino darle al mutador el operador que faltaba: **reemplazo de
constante** (`return 1` → `return 2`). Es el único mutante que separa los dos casos:

| el mutante | test que mira el valor | test que sólo mira «no es None» |
|---|---|---|
| borrar el `return` (devuelve None) | muere | **muere también** — no discrimina |
| `return 1` → `return 2` | muere | **sobrevive** — ahí está la diferencia |

Medido después del arreglo: `tests_flojo` queda rechazado por «sobreviven mutantes … [cambiar
el valor de la constante] return 1» y cierra 0 de 3; `cumple` sigue cerrando 3 de 3 con la
suite del proyecto en verde. Sin el control de la derecha, el arreglo podría haber sido
rechazar todo.

La aridez se hereda de la sentencia, y esa mitad me faltaba: la primera versión proponía mutar
el texto de un `logging.info('hola')` y el mensaje de un `raise ValueError(...)`, que son
mutantes que ningún test puede matar. Lo encontró la suite del método, no la lectura.

### Lo que encontró en su primera corrida

El gate le cobraba a la tarea un `.opencode-data` **vacío que crea el propio runner**: las
exclusiones del `find` sacaban a los hijos y dejaban al directorio. Dispara justo cuando el
agente no escribió nada —se cayó al arrancar o lo cortó el límite—, o sea que tapaba la causa
real con un rojo de higiene. Tres tareas, dos intentos cada una, punto muerto. Un instrumento
que en su primera corrida encuentra un defecto del instrumento anterior se paga solo.

### Medición 5 — veintiuna tareas con modelos de verdad (2026-10-27)

Lo que la Medición 1 dejó pendiente: las mismas 21 tareas, 3 etapas de 7 en paralelo, pero con
el ejecutor real en lugar del agente determinista. Es otra clase de falla y lo demostró.

| qué | resultado |
|---|---|
| tareas cerradas | **10** |
| en punto muerto | 4 (T01b, T03b, T04b, T06b) · la etapa 2 se detuvo ahí |
| de esos cuatro rojos, **del método** | **3** |
| del modelo | 1 (T06b: el ejecutor no escribió nada, el archivo quedó vacío) |

Los tres rojos del método son el hallazgo, y no es que el modelo falle: es que **el veredicto
quedó correlacionado al revés de lo correcto**.

Los siete tests de la etapa —escritos por el agente, antes de la implementación— parchearon el
módulo donde el nombre **se define**:

    with patch('src.datos.d1.leer1') as mock_leer1:
        mock_leer1.return_value = 5
        self.assertEqual(calcular1(), 50)

Y el enunciado de la tarea pedía, textualmente, «Usa `from src.datos.d1 import leer1`». Con
ese import el nombre queda ligado en `src.servicios.s1` **antes** de que el patch corra, así
que el patch no toca nada: `calcular1()` devuelve `1*10`, el test espera 50, rojo.

| tarea | qué escribió el ejecutor | ¿obedece el contrato? | veredicto |
|---|---|---|---|
| T01b, T03b, T04b | `from src.datos.dN import leerN` a nivel de módulo | **sí**, palabra por palabra | **ROJO** |
| T02b | `import src.datos.d2` + `d2.leer2()` | no | verde |
| T05b, T07b | el `from` adentro de la función | no | verde |

Las tres que pasaron ganaron una apuesta: eligieron una forma de import que deja el patch
efectivo. Las tres que leyeron el contrato al pie de la letra quedaron en **punto muerto —falló
dos veces por lo mismo**, que acusa al implementador, y las tres salidas que el punto muerto
ofrecía —relanzar, partir en dos, hacerla a mano— asumen las tres que el defecto está en la
tarea o en el modelo. Ninguna lo arregla.

**El arreglo** es `scripts/_mocks.py`, que corre en `escribir-tests.sh` —la puerta donde el
test todavía se puede reescribir gratis— y se repite en `explicar_punto_muerto` para cuando ya
pasó. La regla es exacta y no hace falta correr nada:

> si el test parchea `X.nombre`, y el módulo bajo prueba trae ese nombre con
> `from X import nombre` **a nivel de módulo**, el patch no puede tener efecto.

«A nivel de módulo» es la mitad que la hace angosta: el mismo `from` adentro de la función se
resuelve en cada llamada y ahí el patch **sí** pega, igual que `import X` + `X.nombre`. Un
chequeo que marcara esas dos muerde al test honesto.

**El brazo nulo**, que es lo único que hace al chequeo algo más que una opinión sobre
`unittest.mock`: correr los cuatro casos de verdad y comparar.

| caso real | `unittest` | `_mocks.py` |
|---|---|---|
| T01b, T03b, T04b | FAILED | rc=1 |
| T02b, T05b, T07b | OK | rc=0 |

Seis de seis, sin un falso positivo. Queda como test permanente
(`TestElRojoNoSabiaSiEraDelTestODeLaImplementacion`) con esos cuatro casos más dos que miden
el caso **normal** —la implementación todavía no existe, porque los tests van primero— y uno
que mide la angostura: `patch.object(d1, "leer1")` nombra el objeto que parchea y no entra.

Mi primera versión del chequeo **fallaba abierto justo en el escenario que vino a cubrir**:
deducía el módulo bajo prueba de que su `.py` existiera, y cuando `escribir-tests.sh` corre no
existe. Daba 0 y silencio. Lo encontró el caso E del par discriminante, no leer el código.

Y cuando el enunciado **no** declara con qué import se trae el nombre, el chequeo sale con 2
—«no se pudo verificar»—, porque ahí el test está apostando a una de tres formas y el defecto
es del contrato. Eso lo decide quien planifica; el método no lo infiere.

### Medición 6 — el chequeo se colaba por el chequeo (2026-10-27)

Con `_mocks.py` puesto y la regla nueva en `AGENTS.md`, las mismas 21 tareas otra vez con
modelos de verdad. Lo que salió en la primera tarea:

    ▶ T01b · ejecutor escribe tests/test_s1.py::TestS1
      ✓ falla sin la implementación
      ✓ pasa con la implementación
      ✓ los mutantes mueren: el test distingue
      ✓ T01b: tests/test_s1.py aceptado y copiado al tronco

Y el test aceptado traía, otra vez, `patch('src.datos.d1.leer1')`. Corrido a mano sobre ese
mismo archivo, el chequeo sale con 1. En la corrida había salido con 0.

**La causa**: en `escribir-tests.sh` la implementación que hay en el worktree es un BORRADOR
que el método descarta —el agente escribe test e implementación, y de los dos se queda sólo
con el test— y lo escribió **el mismo agente que escribió el test**, así que es coherente con
su test por construcción. El chequeo, que prefiere la implementación en disco sobre el
enunciado, le estaba preguntando al acusado.

El par entero, reproducido a mano y fijado como test:

| contra qué se corre el test | veredicto de `unittest` |
|---|---|
| el borrador del agente de tests (`from` adentro de la función) | **OK** |
| la implementación que el contrato manda (`from` a nivel de módulo) | **FAILED** |

Las dos implementaciones calculan lo mismo. La que decide si el test pasa es la forma del
import, y la que estaba en disco cuando el chequeo miró no era la que iba a juzgarlo.

**El arreglo** es la bandera `--segun-enunciado`, que `escribir-tests.sh` ahora pasa: en esa
puerta el único compromiso que existe sobre la implementación futura es el contrato. Sin la
bandera —en `explicar_punto_muerto`, donde la implementación ya es la de verdad— sigue
ganando el disco.

**Y lo que lo hizo invisible durante una corrida entera**: el chequeo no imprimía su testigo
cuando daba verde. El método tiene la doctrina del `· inspeccionó:` justamente por esto y acá
no la había seguido; ahora dice qué fuente miró, y eso solo habría mostrado el defecto en la
primera tarea. Queda como test.

### Lo que el log de esa corrida destapó además

`· línea base: 0` y `0 test(s) ya fallando`, en dos líneas. Es el `$(grep -c … || echo 0)`
—`grep -c` imprime el conteo **y** sale 1 cuando es cero, así que el `||` agrega un segundo
cero— que este repo ya había pagado tres veces: un «HTTP 000000» en la sonda, la guarda de
verde falso de `ensayo.sh` que no corría por un «integer expression expected», y un chequeo
de `correr-tarea.sh` que comparaba contra «0». El arreglo estaba en `correr-tarea.sh`, **con
el comentario que lo explica**, y `escribir-tests.sh` seguía con las dos mitades sin hacer:
el contador y la guarda que frena cuando la suite está roja y la línea base salió vacía —que
es la que evita gastar una corrida de agente para que el gate después le cobre a la tarea las
fallas de sus hermanas—.

Queda como invariante sobre todos los `.sh` del repo, con brazo nulo verificado: reintroducir
el patrón en cualquier script lo hace fallar. Y su primera versión marcó dos líneas que eran
**los comentarios que documentan este mismo defecto** — una regla más ancha que su defecto
acusa a la documentación del defecto. Tercera vez en el día con esa forma de error.

### Medición 7 — el chequeo funcionó y el rojo no se podía leer (2026-10-27)

Tercera corrida de las 21 con modelos de verdad, con `_mocks.py --segun-enunciado` puesto y
la regla del patch en `AGENTS.md`. Lo primero que hay que decir es que el arreglo hizo su
trabajo:

| qué | antes (medición 5) | ahora |
|---|---|---|
| dónde se detuvo la etapa de los `calcularN()` | en la fase de **implementación** | en la fase de **tests** |
| a quién acusaba el rojo | al implementador, con el contrato cumplido | al test, que es de quien era |
| corridas de implementación gastadas en el defecto | 4 tareas × 2 intentos | **0** |
| etapa 1 (las siete tareas de leer) | 7 gates verdes | 7 gates verdes |

Y el testigo del chequeo salió en cada tarea —`✓ los patch del test apuntan donde el patch
pega · inspeccionó: N patch(es)…`—, que es lo que prueba que corrió. La línea base, además,
ya sale entera: `· línea base: 0 test(s) ya fallando`.

**Pero cuatro de siete no pasaron la puerta**: T03b, T05b, T06b y T07b escribieron el mismo
`patch('src.datos.dN.leerN')` dos veces y quedaron en punto muerto en la fase de tests. Las
tres que pasaron lo hicieron por dos caminos distintos:

| tarea | qué hizo |
|---|---|
| T01b | corrigió el patch a `patch('src.servicios.s1.leer1')` |
| T02b, T04b | lo mismo, con decorador: `@patch("src.servicios.sN.leerN")` |

Los tres **corrigieron el objetivo del patch**; ninguno lo evitó. La primera versión de esta
medición decía que T02b y T04b habían resuelto la tarea sin mockear, y era un error de mi
grep: buscaba `patch('…')` con comillas simples y estos dos usan decorador con comillas
dobles. El error de extractor del catálogo —buscar una forma que el productor no emite—, esta
vez en la medición y no en el método. `_mocks.py` va por AST y las cubre; lo que faltaba era
el test que lo fija.

La causa de los cuatro no era el modelo. El reintento le pasaba al agente **sólo el titular**:

    Un intento anterior falló así: el test parchea un lugar donde el patch
    no va a tener efecto. No repitas ese camino.

El chequeo calcula e imprime el reemplazo exacto —`Parcheá donde se usa:
patch('src.servicios.s3.leer3')`— y eso se quedaba en el log del humano. Contado en los
transcripts de los cuatro: llegó al agente **cero veces**. Un rojo que el acusado no puede
leer no es accionable aunque sea correcto, y pedirle «no repitas ese camino» sin decirle cuál
es el otro camino deja al modelo adivinando entre tres formas de import.

Es la cuarta pregunta del método —¿quien decide lee lo mismo que el que mide dijo?— aplicada
al **agente**, que en esta puerta es quien tiene que arreglar. Las seis veces anteriores que
esa pregunta encontró algo, el que leía mal era un `case` de bash.

**El arreglo**: `malo` toma un segundo argumento con el detalle del chequeo, y el prompt del
reintento lo lleva. Vale para los tres chequeos que producen salida detallada —`_mocks.py`,
`_aserciones.py`, `_contrato.py`—, no sólo para el de patches.

Queda como test de punta a punta con un `opencode` falso que insiste siempre con el patch
equivocado: se exige que el prompt del **segundo** intento contenga el reemplazo concreto, y
que el del primero no reproche nada. Brazo nulo verificado: quitando el detalle del prompt,
el test falla mostrando el titular pelado, que es lo que recibieron los cuatro agentes.

Y el fixture tuvo su propia lección: la primera versión del `opencode` falso respondía igual
a `agent list` que a `run`, así que escribía el test antes de empezar y el script lo salteaba
con «ya declara TestS1 — no se toca». Un agente falso que no distingue el subcomando mide el
andamio. Lo encontró `bash -x`, no leer el fixture.

### Por qué el arreglo va en el prompt y no en más documentación

Medido sobre los transcripts de esa misma corrida: de los siete agentes de la fase de tests,
**ninguno abrió `AGENTS.md` con la herramienta de lectura**, y los siete leyeron su archivo de
tarea. La primera lectura —«no lo vio»— es falsa, y conviene decirlo porque es la que invita
al arreglo equivocado: la config declara `"instructions": ["AGENTS.md", "CLAUDE.md",
".opencode/rules/*.md"]`, así que OpenCode lo **inyecta** en el contexto del sistema. No lo
abrieron porque ya lo tenían.

O sea que la regla del patch llegó a los siete y **cuatro no la aplicaron**. Con los tamaños
que ya estaban medidos en OPENCODE.md —1.250 + 1.745 tokens de `AGENTS.md` contra 1.166 del
prompt del ejecutor, sobre 32.000 de ventana— no es un problema de espacio: es que la regla
número 13 de una lista de 15, en un documento inyectado, no compite con la instrucción
puntual del turno.

De ahí la forma del arreglo. Agregar la regla al documento ya estaba hecho y no alcanzó;
lo que faltaba era que el reemplazo concreto viajara en el prompt del reintento, que es el
único canal del que hay evidencia de que el modelo chico atiende. Para el método en general:
documentar una regla en `AGENTS.md` no es un canal confiable para un modelo chico, y una
corrección que el método ya calculó no se delega a que el agente la deduzca de una lista.


### Medición 8 — el reemplazo en el prompt, y 14 de 21 con modelos de verdad (2026-10-27)

El control estaba escrito antes de correr, que es lo que la vuelve una medición: con el
titular pelado, **0 de 4** tareas en punto muerto se recuperaron.

| | el reemplazo en el prompt del agente | se recuperaron | tests aceptados |
|---|---|---|---|
| titular pelado | **0 veces** | 0 de 4 | 3 de 7 |
| con el detalle | **sí** | **3 de 4** | **6 de 7**, los seis con el objetivo correcto |

La prueba de que el detalle llegó **al agente** no es el log del método —ahí sólo consta que
el método lo imprimió— sino la tabla `part` de la base de la sesión de OpenCode, que guarda
el mensaje tal como se envió. Lo conté primero en el log y eso no medía lo que dice medir:
el productor y el receptor son dos lugares distintos.

**El rojo que quedó es del modelo, y está probado.** El prompt del reintento de T05b llevaba
el reemplazo exacto **tres veces**, una por cada patch del archivo:

    Un intento anterior falló así: el test parchea un lugar donde el patch no va a tener
    efecto. El chequeo dijo exactamente esto, y dice qué poner en su lugar:
      tests/test_s5.py:7  patch('src.datos.d5.leer5') no va a tener efecto
         … Parcheá donde se usa:  patch('src.servicios.s5.leer5')
      tests/test_s5.py:14 … tests/test_s5.py:21 …

Y volvió a escribir los tres equivocados. Eso es lo que HUMANO.md §4 manda que decida una
persona: el test de T05b quedó escrito a mano, con el motivo en su docstring.

### El pipeline completo, con modelos de verdad

| etapa | qué cerró |
|---|---|
| `a` — leer (7 tareas) | **7 de 7**, gates verdes |
| `b` — calcular (7 tareas) | **7 de 7**, gates verdes |
| `c` — responder (7 tareas) | detenida: 4 tests aceptados, 3 no |
| **cerradas en el plan** | **14 de 21** |

Los tres rojos de la etapa `c` son legítimos y de tres clases distintas:

- **T01c, T02c**: agotaron sus dos intentos con un motivo **distinto en cada uno** —primero
  no escribieron la clase declarada, después el patch inefectivo—, así que no hubo punto
  muerto: hubo dos fallas diferentes.
- **T05c**: tocó `src/servicios/s5.py`, que es de la etapa anterior y no de su alcance. Dos
  veces lo mismo, punto muerto.

Y un resultado que no estaba buscado: **el chequeo de patches generalizó solo a la capa de
rutas**. Se escribió mirando `src/servicios/sN.py` y atrapó
`patch('src.servicios.s1.calcular1')` en un test de `src/rutas/r1.py`, porque la regla está
escrita sobre la relación entre el import y el objetivo, no sobre nombres de capas.

### Evidencia para §8.4 de INVESTIGACION.md: N=2 contra N=3 intentos

Esa pregunta estaba listada como no medida por nadie, incluido nosotros. Esta corrida da el
primer dato: de las tres tareas que no cerraron, **dos agotaron los intentos con motivos
distintos en cada uno**. Con N=2 y una falla nueva por intento, el presupuesto se consume sin
que el método pueda distinguir «no aprende» de «todavía no terminó de arreglar»: la huella
cambia, así que ni siquiera cuenta como punto muerto. N=3 las habría dejado seguir, y las dos
venían de arreglar lo que el intento anterior les señaló.

Lo que falta para que sea una medición y no una anécdota es el brazo de control: las mismas
tareas con N=3 y nada más cambiado. Es barato —son dos tareas— y el número de hoy, 14 de 21,
es la línea base contra la que se compara.

### Medición 9 — 21 de 21 con modelos de verdad, y lo que el resumen no decía (2026-10-27)

El brazo de control que pedía la medición 8: las mismas tareas, el mismo método congelado,
`REINTENTOS_TESTS=3` como única diferencia.

| | N=2 | N=3 |
|---|---|---|
| tareas cerradas | 14 de 21 | **21 de 21** |
| código de salida del pipeline | 1 (detenido) | **0** |

Las dos tareas que con N=2 agotaban el presupuesto con un motivo distinto en cada intento
—primero no escribir la clase declarada, después el patch inefectivo— cerraron con el tercero.
Y T05c, que con N=2 era punto muerto legítimo por tocar un archivo de la etapa anterior,
también cerró: su tercer intento respetó el alcance.

Es el primer dato real de la pregunta que §8.4 de INVESTIGACION.md tenía listada como no
medida por nadie. **No alcanza para fijar N=3 como regla**: es una corrida, un plan de
juguete y tres tareas, y lo que el dato dice es más preciso que «N=3 es mejor»:

> cuando cada intento falla por algo DISTINTO, la huella cambia, así que el método no lo
> llama punto muerto y el agente está arreglando de verdad lo que el intento anterior le
> señaló. Gastar el presupuesto ahí no es insistir: es avanzar. El criterio «falló dos veces
> por lo mismo» ya distingue los dos casos; lo que estaba mal calibrado era el techo.

### Y lo que el resumen de métricas no decía

La corrida que cerró el plan imprimió:

    Intentos: 21   ·   tareas intentadas: 21
    Verde al PRIMER intento: 21/21 (100%)

Las invocaciones reales del agente para llegar ahí fueron **68**, contadas en los logs:

| corrida | fase de tests | implementación |
|---|---|---|
| r23 | 21 | 7 |
| r24 | 7 | 0 |
| r25 | 13 | 7 |
| r26 (N=3) | 6 | 7 |
| **total** | **47** | **21** |

El registro tiene 21 filas porque `escribir-tests.sh` no anota. O sea que el resumen declara
el **31%** de las llamadas al modelo, y la frase «21/21 al primer intento (100%)» es cierta
sobre lo que el registro contiene y falsa como resumen del trabajo. No es cosmético: es el
número con que el método calibra el presupuesto de agente —el propio mensaje de punto muerto
remite a `metricas.sh` para eso—, así que subdeclararlo hace parecer barato lo que no lo es.

El arreglo no inventa el dato que falta: el titular dice **«fase de implementación»** y el
resumen declara el hueco con el comando que lo mide (`grep -c '· ejecutor escribe' <log>`),
que es lo que el método exige de cualquier chequeo que no pudo verificar algo. Queda como
test con brazo nulo: sin el arreglo, los dos tests fallan.

**Lo que sigue abierto**, y es el arreglo de fondo: que la fase de tests tenga su propio
registro. No se hizo ahora porque meter sus filas en `intentos.csv` contaminaría todas las
tasas que ese archivo sostiene —el 21/21 pasaría a contar tests como tareas— y eso se diseña
con una medición, no de apuro al final del día.

### El costo real, para que el número no se lea de más

Las 21 tareas cerraron, pero el camino tuvo **cuatro corridas** y dos intervenciones humanas:
el test de T05b escrito a mano (el agente recibió el reemplazo exacto tres veces en el prompt
y volvió a escribir los tres patches equivocados) y la decisión de subir el techo de
intentos. El método hizo lo que debía en los dos casos: frenó, dijo de quién era el defecto y
pidió una persona. Pero «21 de 21» sin esta línea sería la misma clase de titular que esta
medición vino a corregir.

### Medición 10 — tres brazos, y la hipótesis que se cayó (2026-10-27)

La pregunta de replicabilidad, la única que importa para llevar el método a un proyecto:
**¿cuántas de 21 tareas cierran en UNA corrida, sin intervención humana?** Hasta acá sólo
sabíamos 21 de 21 tras cuatro corridas y dos intervenciones, que no es lo mismo.

Tres brazos, un solo factor distinto cada uno, mismo método congelado (`98f7698`), proyectos
generados de cero:

| | B | A | C |
|---|---|---|---|
| reintentos de tests | 2 | 3 | 3 |
| contrato de las tareas `b` | mudo sobre el patch | mudo | **dice dónde parchear** |
| **cerradas / 21** | **7** | **7** | **7** |
| tests aceptados en la etapa `b` | 3 de 7 | **5 de 7** | 4 de 7 |
| rechazos por patch inefectivo | 8 | 9 | **8** |
| llamadas en fase de tests | 22 | 23 | 22 |
| gates verdes | 7 | 7 | 7 |

**Los tres se detienen en la misma etapa.** El método no cierra este plan sin intervención
humana, replicado tres veces, y el cuello de botella tiene nombre: el objetivo del `patch`.

**La hipótesis de C se cayó.** Decirle al agente en el contrato de la tarea dónde parchear
—declarando la consecuencia del import que el propio contrato manda— dio los **mismos 8
rechazos** que el contrato mudo. A mitad de corrida el brazo llevaba 1 y escribí que el dato
iba a favor; al cierre eran 8. Un conteo parcial de un proceso en curso no es una medición, y
esta vez lo dije antes de afirmarlo.

### Lo que queda medido: tres canales no corrigen el sesgo

| canal | efecto medido |
|---|---|
| la regla en `AGENTS.md`, que OpenCode **inyecta** | llegó a 7 de 7 agentes; **4 no la aplicaron** |
| el reemplazo exacto en el prompt del reintento | mejora la **recuperación** (0 de 4 → 3 de 4), no la primera pasada |
| el contrato de la tarea | **ningún efecto** sobre los rechazos (8 contra 8) |

El modelo chico tiene un sesgo fuerte y sistemático a parchear donde el nombre se **define**
—8 o 9 rechazos sobre siete tareas, en los tres brazos— y la instrucción textual no lo mueve
por ninguno de los tres canales. Es un resultado negativo y vale más que si hubiera salido al
revés: cierra tres arreglos que parecían obvios y que habrían costado trabajo cada uno.

Lo que sí funciona es lo que ya está puesto: **el chequeo mecánico**, que lo atrapa el 100% de
las veces y convierte 8 tests malos en 8 rechazos en la puerta donde se arreglan gratis, en
vez de 8 rojos que paga el implementador dos etapas después. Y subir el techo de intentos
mejora los tests aceptados (3 → 5) al mismo costo en llamadas (22 → 23), aunque con un brazo
por condición ese número es débil.

**Lo que queda abierto**, y ahora con la evidencia de que no se arregla hablándole al modelo:
o el plan no pide tests que mockeen la dependencia —y entonces lo decide quien planifica—, o
el método corrige el objetivo del patch él mismo. Lo segundo es mecánico y el chequeo ya
calcula el reemplazo exacto; lo que falta medir es si un método que **reescribe** el test del
agente sigue midiendo al agente, que es la pregunta que hace falta responder antes de
escribir una línea de eso.

### Medición 11 — los ocho rechazos eran correctos salvo una ruta (2026-10-27)

Sobre los tests que los tres brazos rechazaron y quedaron en disco, contado por árbol
sintáctico —clase declarada, aserciones presentes, objetivo del patch—:

| brazo | tests rechazados | fallaban SÓLO por el objetivo del patch |
|---|---|---|
| B | 3 | 3 |
| A | 2 | 2 |
| C | 3 | 3 |
| **total** | **8** | **8** |

Ocho de ocho. Con el defecto dominante contenido pero no resuelto, los tres brazos cerraban 7
de 21 y se detenían en la misma etapa; la diferencia entre eso y cerrar el plan era una ruta
de import por test.

Con eso y con los tres canales ya descartados —`AGENTS.md` inyectado, el prompt del reintento
y el contrato de la tarea—, el método **corrige** el objetivo del patch y lo declara. Lo que
se decidió, y por qué de esta forma y no de otra:

- **Se toca una ruta, no un test.** Un test de la suite fija que el diff sea exactamente eso:
  aserciones, valores esperados, nombres de casos y docstrings quedan idénticos. Si alguien
  amplía la reparación, ese test falla. Es el límite entre «el método juzga» y «el método
  escribe los tests», puesto como comando y no como intención.
- **Sirve, medido de punta a punta**: el test del agente falla contra la implementación que el
  contrato manda, y corregido pasa. Los cinco pasos que preguntan si el test distingue corren
  después, sobre el test corregido, y siguen pudiendo reprobarlo.
- **Deja constancia en tres lugares**: el log dice `✎ … lo hizo el método, no el agente`;
  `.metricas/correcciones.csv` guarda tarea, línea, origen y destino; y el test original queda
  en `.metricas/del-agente/`. Si no puede registrar, **revierte**. Corregir en silencio sería
  el método tapando la señal que vino a medir: el sesgo del modelo es parte del dataset.
- **El original va a `.metricas/`** y no al lado del test, porque ahí ya está ignorado y
  filtrado por los tres gates. Dejarlo en `tests/` se lo cobraría a la tarea como archivo
  fuera de alcance, y obligaría a tocar dos listas que un test de esta suite cruza.
- **Sin la bandera sigue siendo juez puro**: no toca nada y reprueba, que es lo que
  corresponde en `explicar_punto_muerto`, donde la implementación ya está escrita.

Lo que falta medir es si con esto los brazos cierran el plan en una corrida. El número a
batir está fijo: **7 de 21**, replicado tres veces.

### Lo que la suite destapó al poner la corrección: un arreglo que deja sin efecto a otro

El lote de la medición 11 lo rechazó un test del lote de la medición 8 —el que exige que el
reintento le pase al agente el reemplazo concreto y no sólo el titular—. Y el rechazo era
correcto: **con `--corregir` ya no hay reintento**. El log del fallo lo muestra entero:

    ▶ T01b · tester escribe tests/test_s1.py::TestS1
      ✓ sólo tocó el test y los archivos de la tarea
      ✎ corregí el objetivo de algún patch — lo hizo el método, no el agente
      ✓ falla sin la implementación
      ✓ pasa con la implementación
      ✓ T01b: tests/test_s1.py aceptado y copiado al tronco

Una sola llamada al agente. El arreglo de la medición 8 quedó **sin efecto para este
defecto**, porque el de la medición 11 lo precede: el método repara antes de que exista un
intento anterior del que hablar.

No es un test mal escrito ni un arreglo de más. Es que **un arreglo posterior puede volver
inalcanzable el camino que un test anterior protege**, y entonces ese test pasa a custodiar un
comportamiento que ya no existe. Si se lo «arregla» aflojándolo, se pierden las dos cosas: la
medición vieja y la nueva.

Lo que quedó, que es la forma de no perder ninguna de las dos:

- el detalle en el prompt se mide ahora con un chequeo que **no repara** —una aserción que no
  puede fallar, que `_aserciones.py` rechaza y nadie corrige—, porque ahí el reintento sigue
  siendo el único canal y el hallazgo de la medición 8 sigue vigente;
- y el comportamiento nuevo se fija aparte: con el patch corregido **no se gasta un
  reintento**, el test se acepta en el primer intento, y eso es exactamente lo que en tres
  brazos de 21 tareas costó que ninguno pasara de 7 cerradas.

### Medición 12 — corregir la ruta no movió el resultado, y movió la causa (2026-10-27/28)

Cuarto brazo, un solo factor distinto: el método **corrige** el objetivo del patch.

| | B | A | C | D |
|---|---|---|---|---|
| reintentos de tests | 2 | 3 | 3 | 3 |
| contrato dice dónde parchear | no | no | **sí** | no |
| el método corrige la ruta | no | no | no | **sí** |
| **cerradas / 21** | **7** | **7** | **7** | **7** |
| rechazos por patch inefectivo | 8 | 11 | 9 | **0** |
| rechazos «no pasa ni con la implementación del propio agente» | — | — | — | **8** |
| llamadas en fase de tests | 22 | 27 | 26 | 21 |

El defecto que el chequeo rechazaba desapareció —**0** rechazos por patch, contra 8, 11 y 9— y
el total de tareas cerradas **no se movió**. Lo que cambió es la causa del freno, y la nueva
es una interacción que no estaba prevista:

> el método corrige la ruta **según el contrato** —`from X import n` a nivel de módulo, así
> que hay que parchear el módulo bajo prueba— y después el paso «pasa con la implementación»
> valida contra el **borrador del agente**, que puede traer el nombre de otra forma. Con eso
> el patch corregido no pega contra ese borrador y el test se rechaza.

Es la quinta pregunta del método otra vez —¿contra qué material se compara, y es el mismo que
el veredicto va a usar?— apareciendo **dentro del arreglo nuevo**: corrige mirando un sujeto y
valida mirando otro. El mismo defecto que la medición 6 encontró en la versión anterior de
este chequeo, en el otro sentido.

**Lo que queda por decidir, con el dato en la mano**: si el método ajusta también el borrador
—que se descarta de todos modos— para que la validación mida el escenario del contrato, o si
esto dice que el paso «pasa con la implementación» no puede usar el borrador para nada. Lo
primero es barato y lo segundo es más honesto; las dos cambian qué mide el validador de tests,
así que no se eligen de apuro. El brazo E repite la corrida para confirmar que el 8 no fue
casualidad antes de tocar nada.

### Y el arreglo de hoy perdía la evidencia justo donde servía

En esa misma corrida el método corrigió **27** rutas y sobrevivieron **4**: las de las tareas
que FALLARON. `_mocks.py` escribía la constancia en `./.metricas`, el CWD durante la fase de
tests es el worktree de la tarea, y el worktree de un test **aceptado se borra al aceptarlo**.
La evidencia se destruía en los casos exitosos, que son los que más le interesan al dataset
—es el defecto que este método persigue, dentro del arreglo que existía para no cometerlo—.

Ahora `--registro` lo pasa quien llama, apuntando al tronco del proyecto, y **sin registro no
corrige**: corregir en silencio es lo único que esa función no puede hacer.

Mi primer brazo nulo de eso dio verde tres veces seguidas por tres razones distintas, y cada
una vale anotarse: un `grep -c | tail` que devolvió un 0 plausible (quinta vez en el día con
el código de salida de un pipe); una mutación que no verifiqué que se aplicara —«0 mutantes
probados informado como ✓»—; y, cuando ya se aplicaba, un test que encontraba el registro que
había dejado **su propia corrida anterior**, porque lo escribía en `d.parent` y `d` sale de
`mkdtemp`, o sea el directorio temporal del sistema. El caso de prueba pasaba por el andamio.

### Medición 13 — el 2x2 completo: el arreglo es del plan, no del chequeo (2026-10-28)

Cuatro celdas, **dos corridas cada una**, 21 tareas, modelos de verdad, método congelado:

| | contrato mudo | contrato que dice dónde parchear |
|---|---|---|
| **sin corregir** | **7** (A) | **21** (C) · **21** (C2) |
| **el método corrige la ruta** | **14** (E) | **7** (F) |

Dos resultados, y el segundo va contra el arreglo que yo mismo escribí ayer:

**1. El contrato que declara la consecuencia de su propio import cierra el plan. Replicado,
dos de dos.** Es el único arreglo de toda la sesión con señal repetida, y es del
**planificador**: no hay chequeo nuevo, no hay código del método. El contrato dice

    Usa `from src.datos.d1 import leer1`.

    Si el test necesita controlar lo que devuelve `leer1()`, parcheá
    `src.servicios.s1.leer1` —el módulo donde se USA—, no `src.datos.d1.leer1`.

y con eso 21 de 21, dos veces, sin intervención humana.

**2. Corregir la ruta sólo ayuda cuando el contrato es malo, y arruina el caso bueno.**
7 → 14 con el contrato mudo; **21 → 7** con el contrato bueno. La causa cierra con lo medido:
con el contrato enriquecido el agente acierta el patch casi siempre, y cuando no, lo arregla
él en el reintento —eso ya estaba medido en la §8: 0 de 4 → 3 de 4 con el detalle en el
prompt—. Si el método se lo corrige antes, aparece el conflicto entre la ruta corregida —que
sigue al contrato— y el **borrador** del agente, que puede traer el nombre de otra forma: 24
rechazos de «el test no pasa ni con la implementación del propio agente» en E, 16 en su
primera corrida, 15 en D.

Por eso `--corregir` queda **apagado por omisión** y prendible con `CORREGIR_PATCH=1`. La
maquinaria se queda porque está toda medida —el límite de tocar sólo la ruta, la constancia en
tres lugares, el brazo nulo— y porque el 7 → 14 es real en proyectos cuyo contrato no declare
la consecuencia. Un arreglo que mejora un caso y empeora otro se deja prendible, no prendido.

### Y lo que esta medición dice de cómo leí los datos durante el día

Sobre la misma hipótesis me equivoqué dos veces en direcciones opuestas:

- **A mediodía la declaré refutada**: «decirle al agente en el contrato dónde parchear no
  reduce los rechazos, 8 contra 8». Era cierto *de la primera pasada* y lo escribí como
  juicio del contrato. El contrato no reduce los rechazos **y** cierra el plan: las dos cosas
  a la vez, y yo medí una y concluí sobre la otra.
- **A las 22:30 dije que era el que más rendía** con un brazo por celda, y estuve a punto de
  reportar que mi corrección «empeora el método» comparándola con C, que tiene otro factor
  cambiado. El control de E era A, no C.

Las dos veces el error fue el mismo que esta sesión persigue en el método: **medir un sujeto y
concluir sobre otro**. Y las dos veces el que lo corrigió fue el dato siguiente, no releer lo
escrito.

### Medición 14 — el 21 no se replicó, y lo refutó la medición que lo iba a confirmar (2026-10-28)

El brazo G midió la configuración recomendada **sobre el método commiteado** y no sobre un
parche: generador con el contrato enriquecido, `--corregir` apagado, `HEAD` en `1064071`.
Verificó sus tres condiciones antes de arrancar y las pasó.

| celda «contrato enriquecido, sin corregir», 2 corridas cada una | cerradas /21 |
|---|---|
| C (contrato como parche a `98f7698`) | 21 |
| C2 (mismo parche, proyecto nuevo) | 21 |
| **G (contrato commiteado, método de `1064071`)** | **7** |

**21, 21, 7.** El contrato generado es **idéntico** en los tres —comparado con `diff`— y los
motivos de rechazo son los mismos: el patch inefectivo domina igual (9 en C2, 10 en G).
Ninguno de los cuatro commits intermedios toca ese camino con la corrección apagada. Así que
la diferencia es **varianza entre proyectos generados**, y mi «cierra el plan, dos de dos» era
cierto de los dos que corrí y falso como generalización.

Lo que queda en pie, y es menos de lo que escribí a las 22:30:

- **El contrato NO reduce los rechazos del chequeo de patches.** Eso está medido tres veces
  (16, 9, 10) y era exactamente la conclusión que saqué a mediodía y después creí refutada.
  La de mediodía era la correcta.
- **Con la línea, 2 de 3 proyectos cerraron el plan; sin la línea, 0 de 2.** Es una señal, no
  una garantía, y con esta varianza hacen falta más corridas para decir algo más fuerte.
- **El 7 de 21 en una sola corrida sigue siendo el número replicado**: todas las celdas, todos
  los proyectos, siempre 7 en la primera vuelta.

### Lo que esto dice del día

Sobre la misma hipótesis cambié de opinión tres veces, y cada vez con datos: refutada a
mediodía (midiendo la primera pasada), confirmada a las 22:30 (con n=2 y corridas desiguales),
y ahora degradada a «señal débil» por un tercer proyecto. Las tres veces el error no fue el
dato sino **el tamaño de la afirmación**: escribí «se cayó», «es el que más rinde» y «dos de
dos» cuando lo que tenía era un brazo, dos brazos y dos brazos con una corrida extra.

La medición que lo corrigió la diseñé yo para **confirmar** la recomendación, y la refutó
treinta minutos después de commitearla. Eso es lo único de esta sesión que funcionó como
tiene que funcionar, y el texto de `plantillas/TAREA.md` ya dice 2 de 3 en vez de 2 de 2.

### Medición 15 — la tasa, por fin con n: 4 de 5 cierran con hasta cuatro pasadas (2026-10-28)

Doce proyectos de 21 tareas, modelos de verdad, método commiteado con el contrato que declara
dónde parchear y `--corregir` apagado. La tabla está partida por el **tope de corridas**,
porque ese tope es un parámetro y no una propiedad del método:

| tope | proyectos | cerraron las 21 | corridas que necesitaron los que cerraron |
|---|---|---|---|
| 2 | 7 | 3 | 2, 2, 2 |
| **4** | **5** | **4** | **2, 4, 4, 4** |

**Con hasta cuatro pasadas, 4 de 5 proyectos cierran el plan completo sin intervención
humana.** Tres de los cuatro necesitaron la tercera o la cuarta; uno cerró en dos. El que no
cerró agotó las cuatro.

Eso convierte la pregunta de replicabilidad en una operativa y respondible: no «¿el método
cierra un plan?» sino **«¿cuántas pasadas presupuestar?»** — y la respuesta medida es cuatro.
Compárese con lo que teníamos ayer a la mañana: las 21 cerraron tras cuatro corridas Y dos
intervenciones humanas; estas cuatro no necesitaron ninguna.

### Y lo que no cambia en ninguno de los doce

El cuello es **siempre** la etapa de los `calcularN()` —las tareas que necesitan mockear la
dependencia— y nunca el resto del plan. Las siete tareas de leer cierran en la primera pasada
en los doce proyectos; las de responder, cuando llegan. Eso es más accionable que la tasa: no
hay que mejorar el método en general, hay que mirar esa etapa.

Y ningún proyecto se trabó por el mismo motivo dos veces seguidas de forma predecible: C2
cerró con una sola tarea trabada y otro no cerró con una sola. Con los datos de estos doce
**no hay predictor** de cuál va a cerrar: la variabilidad está en si el modelo resuelve esa
tarea en la pasada siguiente, y eso no se deduce del log anterior.

### Cómo se llegó a este número, que es la parte que cuesta

Sobre esta misma celda afirmé cuatro cosas distintas en doce horas, cada una con datos y cada
una desmentida por la medición siguiente:

1. «el contrato no sirve» — midiendo sólo la primera pasada;
2. «cierra el plan, dos de dos» — con n=2 y corridas desiguales;
3. «el 21 no se replica» — cuando el tercer proyecto dio 7 con tope 2;
4. «el que no cierra en dos tampoco en cuatro» — con un solo caso, refutado por el siguiente.

Las cuatro veces el error estuvo en el **tamaño de la afirmación**, no en el dato. Y las
cuatro las corrigió la corrida siguiente, no releer lo escrito. El tope de dos corridas, que
yo elegí sin pensarlo, fue lo que hizo parecer binario un resultado que no lo es.

### Un test que ejecuta un demonio no lo prueba: lo pone en producción (2026-10-28)

Al traer el vigilante al repo escribí un test que verifica que **no arranque sin `DONDE`**, el
directorio de la cola. Mientras verificaba su brazo nulo —reintroducir la ruta de sesión que
el script tenía clavada cuando vivía en el scratchpad— la corrida se colgó, y el log del
vigilante que estaba trabajando de verdad registró un arranque que nadie había ordenado:

    11:35:12  ▶ watchdog arriba · ciclo 120s · tope 6/hora

Lo que pasó: con la ruta clavada, mi test ejecutó el script **y el script hizo su trabajo**.
Levantó un segundo vigilante, apuntando al mismo directorio que el real, compartiendo su log
y su cola, y entró en su bucle `while :` — de ahí el cuelgue. Dos vigilantes sobre una misma
cola pueden lanzar la misma entrada dos veces, que es gastar una corrida de agente por un
test.

Dos lecciones, y la segunda es la que vale fuera de este caso:

1. **Un test que lanza un proceso que puede no terminar lleva tope o es una trampa para la
   próxima corrida.** El de abajo tiene 20 segundos. Sin eso, el día que el vigilante deje de
   exigir `DONDE` la suite entera se cuelga en ese test.
2. **Un script con una ruta absoluta adentro no se puede probar sin efectos.** Mientras la
   ruta estaba clavada, ejecutarlo ERA operarlo; no había forma de verificar su comportamiento
   sin tocar el sistema real. Por eso `DONDE` es obligatorio y hay un test que verifica que no
   quede ninguna ruta de sesión en el script: los escribí por prolijidad y resultó que
   previenen el incidente que yo mismo causé veinte minutos antes de escribirlos.

El selector de la cola, en cambio, **sí** se prueba sin efectos: los tests lo extraen del
script por sus marcas y lo ejercitan con una cola de juguete. Ejercitar el código y no una
copia es deliberado —una copia del criterio divergiría, que es el defecto que este repo
cuenta diez veces en un día— y permitió cubrir los dos defectos históricos del vigilante por
sus casos exactos: tres entradas de texto idéntico, y una cola reemplazada con ids nuevos.

### §16 — El canal: dónde está escrita la regla decide si se cumple (2026-10-28)

El sesgo es el mismo de §5 a §15: en la etapa de los `calcularN()` el test del agente parchea
`src.datos.dN.leerN` —donde el nombre se define— y el módulo bajo prueba lo trae con
`from src.datos.dN import leerN` a nivel de módulo, así que el patch no pega. Tres canales ya
habían fallado en corregirlo (`AGENTS.md` inyectado, el prompt del reintento, el contrato que
lo declara). Faltaban dos, y son los que separan «decirlo» de «mostrarlo donde el agente
mira».

**Brazo H — una referencia de test que mockea bien, sembrada en `tests/test_s0.py`.** Resultado
**nulo por invalidez**: en siete repeticiones el agente **no abrió el archivo ni una vez**. Su
nombre aparece en un listado de directorio (`./tests/test_s0.py`, línea 19 de un transcript) y
nada más: cero `Read`, cero menciones en el razonamiento. Las tres repeticiones de la segunda
tanda cerraron 21/21 en 3, 2 y 2 pasadas, con 14, 12 y 11 rechazos por objetivo del patch — la
banda de siempre. **Un archivo en el repo no es un canal.**

**Brazo I — el mismo ejemplo, dentro del archivo de tarea.**

| | cerradas | pasadas | rechazos por objetivo del patch |
|---|---|---|---|
| sin ejemplo (base, tope 4) | 4/5 | 2, 4, 4, 4 | 8, 9, 10, 16 |
| H · referencia en `tests/` (nunca leída) | 3/3 | 3, 2, 2 | 14, 12, 11 |
| **I · ejemplo en el archivo de tarea** | **3/3** | **1, 2, 4** | **6, 4, 6** |

La banda de I queda entera por debajo de la de H y del mínimo de la base. Y hay literatura que
lo explica, no sólo acompaña: el factorial de adherencia (arXiv 2605.10039, 1.650 sesiones,
16.050 funciones) mide el cumplimiento de una instrucción trivial verificable por AST en
**54,9%-57,7%**, y su efecto más grande es **intra-sesión**: cada función que el agente genera
baja las chances de cumplir 5,6% (OR 0,944, IC95% [0,937, 0,951]). Ninguna de las cuatro
variables de estructura del archivo de configuración tuvo efecto. Si la obediencia decae con la
posición, una regla que viaja en el archivo de tarea —leído inmediatamente antes de escribir—
tiene que ganarle a la misma regla en un archivo del repo. El brazo I no es un truco: es la
predicción de ese modelo. Y de paso le da a la descomposición un argumento nuevo: si cada
función cuesta 5,6% de obediencia, una tarea de tres funciones es estructuralmente más obediente
que una de doce.

#### El control está adentro de la misma corrida, y es el dato más fuerte del día

El ejemplo lo siembra el generador **sólo en las siete tareas `b`** (las de `calcularN`, que
mockean a la capa de datos). Las siete `c` —`responderN`, que traen `calcularN` con
`from src.servicios.sN import calcularN` a nivel de módulo— tienen **el mismo problema
estructural y ningún ejemplo**. Así que cada corrida trae su propio control, sin comparar entre
corridas ni entre días:

| clase de tarea | ¿tiene el ejemplo? | H · rechazos por objetivo del patch / intentos | I · rechazos / intentos |
|---|---|---|---|
| `a` (leer, no mockea) | no hace falta | 0 / 53 | 0 / 42 |
| **`b` (calcular, mockea)** | **sí en I** | 21 / 70 = **0,30** | 2 / 46 = **0,043** |
| `c` (responder, mockea) | **no**, en ninguno | 16 / 64 = 0,25 | 14 / 74 = 0,19 |

**El efecto cae exactamente donde está el ejemplo y no donde no está**: siete veces menos
rechazos en la clase tratada, y la clase sin tratar queda igual dentro del ruido. Es la misma
corrida, el mismo modelo, el mismo contrato y el mismo gate, así que no hay varianza entre
corridas que explique la diferencia —que es justo lo que arruinó la lectura del §14, donde el
mismo contrato dio 21 y 7—.

Y **corrige una afirmación mía de §15**: escribí que «el cuello es siempre la etapa de los
`calcularN()`». No es la etapa: es **la capa cuyo test tiene que mockear y no tiene ejemplo**.
Con el ejemplo puesto, `calcularN` deja de ser el cuello y el cuello pasa a `responderN`, que
es la que quedó sin ejemplo. La afirmación vieja confundía el lugar del problema con el lugar
donde lo habíamos visto primero.

#### El cuello se movió, y eso es el hallazgo que deja trabajo

Clases de rechazo contadas sobre los seis logs completos:

| Clase | H (3 corridas) | I (3 corridas) |
|---|---|---|
| el test parchea donde el patch no pega | **37** | **16** |
| tocó archivos que no le corresponden a esta etapa | 1 | **12** |
| el test no pasa ni con la implementación del propio agente | 5 | 3 |
| no escribió el archivo de test que el plan pedía | 4 | 3 |
| sobreviven mutantes | 1 | 0 |

Los 12 de alcance son todos la misma forma: en la etapa de tests de `T03c` —que debe escribir
`tests/test_r3.py`— el agente **además edita `src/servicios/s3.py`**, la implementación del
colaborador, para que su test pase. Los **dos únicos puntos muertos** de los tres brazos I
salieron de ahí. Bajar el primer bloqueo dejó visible el segundo, que ya estaba y quedaba
tapado.

Quedan encolados dos brazos, y las dos predicciones se escriben **antes** de correrlos:

- **Brazo K** — la misma vía, el archivo de tarea, con la regla que falta: «en esta etapa
  escribís SÓLO el test; si necesitás que `leerN()` devuelva otra cosa, es con el patch, no
  editando su implementación». Columna nueva, `rechazos_alcance`. **Predicción:** los 12
  rechazos por alcance bajan a la banda de 0-3, y los dos puntos muertos desaparecen.
- **Brazo L** — el mismo ejemplo del patch, puesto **también en las siete tareas `c`**, que son
  las que quedaron sin él. **Predicción:** los rechazos de la clase `c` caen de 0,19 por intento
  a la banda de la `b` tratada (0,04), y entonces el canal queda confirmado dos veces, en dos
  capas distintas, con el control adentro de cada corrida. Si **no** cae, lo que funcionó en `b`
  no era el ejemplo sino algo propio de esa capa, y hay que buscar qué.

Los dos contadores por clase de tarea se validaron antes de usarlos, contra un resultado que ya
se conocía: sobre los tres logs del brazo I dan `b=1,c=5`, `b=1,c=3` y `b=0,c=6`, y cada par suma
exactamente el total de rechazos por patch de su corrida (6, 4 y 6). Un instrumento nuevo que no
se verifica contra un caso conocido es la mitad de los errores de medición de este repo.

#### Dos experimentos que se cayeron antes de gastar una corrida

Los dos los bajó una medición sobre los datos que ya estaban en disco, y eso es lo que hay que
repetir: **antes de encolar tres corridas, verificar que el fenómeno que se quiere mover existe
en este sustrato.**

1. **Mutación como feedback.** MutGen (arXiv 2506.02954, Llama-3.3 70B local, la configuración
   publicada más parecida a la nuestra) sube el mutation score de 77,9% a 89,5% devolviéndole al
   modelo el mutante que sobrevivió. Nuestro gate corre mutación como puerta y nunca devuelve el
   mutante, así que parecía once puntos tirados. Conté los veredictos: **14 de 14 mutantes
   mueren por corrida, y en seis corridas hay un solo rechazo por «sobreviven mutantes»**. No
   hay superficie donde actuar en este sustrato. Para medirlo haría falta un proyecto donde los
   tests dejen mutantes vivos.
2. **El borrador descartado (§8.7 de INVESTIGACION.md).** Esperaba reconstruirlo de los
   transcripts: el log del éxito registra `Write src/servicios/s1.py` **sin el contenido**. Y el
   camino del éxito no guarda parche: **42 transcripts de éxito contra 19 parches, y los 19
   están en tareas que habían fallado.** O sea que el método conserva la evidencia de lo que
   falla y tira la de lo que pasa, que es justo al revés de lo que este experimento necesita.
   Necesita un cambio chico en `escribir-tests.sh` y una corrida.

---

### §17 — El juez: medido con sus controles, y por qué el número anterior no valía (2026-10-31)

Acá se cierra el hilo del juez, y se corrige una medición mía que había salido al revés.

#### Lo que estaba mal medido

| cuándo | formato | apareo | n | resultado | qué pasaba |
|---|---|---|---|---|---|
| primera | pointwise («¿acepta o rechaza?») | — | — | **50% de acuerdo** | rechazaba todo: 50% es lo que acierta contestar siempre lo mismo |
| segunda | pareado, dos órdenes | **por corrida** | 3 | 3/3, 0 inconsistentes | n=3, y el apareo se podía ganar sin juzgar |
| **ésta** | pareado, dos órdenes | **por tarea** | **28** | **41% bien, 37% cambió con el orden** | con sus dos controles |

La segunda me hizo escribir que «el formato era el problema, no el modelo». **Con n=28 y apareo
honesto eso no se sostiene.** El formato pareado sí es mejor que pointwise —pointwise estaba en
la clase mayoritaria— pero el reviewer sin afinar no es un juez usable.

Los dos defectos del instrumento, los dos del tipo que **no falla, sólo devuelve un número
mejor**:

1. **Apareaba dentro de la corrida, no de la tarea.** Así el test rechazado podía pertenecer a
   otra tarea, y entonces se delata solo contra el enunciado que se le muestra —otra clase, otro
   archivo— y el juez acierta notando el desajuste. Reproduje el defecto a propósito sobre el
   caso de prueba: con el apareo viejo fabrica 3 pares de 4 registros de tareas distintas y
   reporta **100% bien**. Esa es la magnitud de la inflación.
2. **Imprimía «el azar acierta 50%»** sobre una métrica de **dos** preguntas, donde el azar
   reparte 25% bien / 25% mal / 50% inconsistente. Con esa referencia un 41% se leía como «está
   en el azar» cuando está arriba.

#### La medición, con el reservado que recién alcanzó

Reservado: 12 de 39 familias (~30%, fracción declarada antes de mirar), `--dedup`, **sin fuga**.
163 registros reservados, de los que salen **28 pares intra-tarea**; 95 registros quedan afuera
porque su tarea no tiene las dos clases, y eso se declara en vez de rellenarse apareando contra
otra tarea.

| | resultado | azar |
|---|---|---|
| eligió bien en los **dos** órdenes | **11/27 = 41%** | 25% |
| eligió mal en los dos | 6/27 = 22% | 25% |
| **cambió con el orden** | **10/27 = 37%** | 50% |
| sólo entre los 17 consistentes | 11/17 = 65% | 50% |

#### Los dos controles, que son lo que hace legible ese 41%

El número «eligió el que el gate aceptó» se puede ganar por tres vías y sólo una es juicio:
juzgando calidad, prefiriendo una posición, o puntuando la forma del test sin mirar el enunciado.
Cada control apaga una y deja las otras.

| control | qué apaga | resultado |
|---|---|---|
| **posición** — el mismo test en A y en B | no queda nada que juzgar | **14 A / 14 B, desbalance 0%** |
| **enunciado ajeno** — el par verdadero con el enunciado de otra tarea | el enunciado | **25% bien, 50% inconsistente** |

El de posición descarta que el 41% sea suerte de colocación. El de enunciado ajeno es el que
vale: quitándole el enunciado, el juez cae a **exactamente** el azar en las dos cifras (25% y
50%). O sea que **sí usa el enunciado**: hay señal real, y es señal de contrato, no de forma.

#### El veredicto, y qué se hace con él

Hay señal y es del tipo correcto, pero **no alcanza para un gate**, y el motivo no es el 41%
sino el 37%: más de un tercio de los veredictos cambia según en qué orden se pregunte. En un
gate eso es un dictamen que depende de cómo se formuló, no de lo que se juzgó. **Para un gate,
«cambió con el orden» cuenta como no sirve, no como empate.**

Y con n=28 el 41% contra 25% está en el borde de lo afirmable (≈1,9 desvíos). La dirección se
afirma; la magnitud, no. Lo que hay que hacer crecer es el reservado, no la conclusión.

> **Creció, y estos números quedaron viejos el mismo día siguiente: ver §19.** Con n=120 el 41%
> baja a 35% (la dirección pasa a p=0,0093) y el 65% entre consistentes baja a 58% con un IC que
> contiene al 50%. El 41% de acá tenía IC [24,5% · 59,3%]: contenía al 35%, así que no hay
> contradicción, había una estimación imprecisa reportada como número.

Coherente con lo que está medido afuera (§ quinta vuelta de INVESTIGACION.md): el techo de un
juez aprendido es acuerdo moderado con correr los tests (κ ≤ 0,60), y lo que compra entrenarlo
son **menos falsos positivos a TPR fijo**, no exactitud. Entonces la métrica de la próxima vuelta
es FPR, y la línea base contra la que se compara es **correr los tests**, que es gratis y no se
equivoca.

#### Lo que queda en el repo

`scripts/juez_pareado.py` y `scripts/juez_controles.py`, con modo `--guion`: un juez de fixture
que no llama a ningún modelo, igual que `_ensayo_agente.sh` para el ejecutor. Los dos defectos de
arriba están fijados por tests que **se vieron reprobar** la versión con el defecto, no sólo
aprobar la buena.

### §18 — El ⊘ no es neutral: es una deuda, y una de cada cinco detona en otra tarea (2026-11-01)

Corrida `f1793535892`, 21 tareas, modelos de verdad, ejecutor Qwen3-Coder-30B-A3B con el
contexto ya sincronizado (32.000 → 153.000). **21 de 21 tests pasaron el gate.** La etapa de
implementación se detuvo en **T03c**, y durante media hora creí que era el cuarto caso de
instrumento que reprueba al brazo bueno. No lo era: el gate tenía razón, y la causa estaba
**tres tareas más atrás**.

#### La cadena, entera

| cuándo | qué pasó |
|---|---|
| T03b | escribe `tests/test_s3.py` con `patch('src.datos.d3.leer3')` y el import diferido adentro del test |
| T03b · gate | `⊘ no pude determinar si patch('src.datos.d3.leer3') tiene efecto sobre src.servicios.s3: todavía no existe, y el enunciado no declara con qué import lo va a traer` |
| T03b · gate | y aun así: **✓ falla sin la implementación · ✓ pasa con la implementación · ✓ los mutantes mueren · ✓ el brazo nulo falla**. Aceptado y copiado al tronco. |
| T03c | escribe `src/rutas/r3.py`. No toca `s3` ni `d3`. |
| T03c · gate | `✗ rompiste tests que andaban antes de esta tarea: FAIL: tests.test_s3.TestS3.test_calcular3` |
| runner | dos intentos, etapa detenida, «decide un humano» — **sobre la tarea inocente** |

Por qué el test de T03b pasaba: corría **solo**. Con `sys.modules` vacío, el import diferido
se resuelve después del patch y el patch pega. El test de T03c, en cambio, importa a nivel de
módulo, así que **en el momento de la colección** precarga `src.servicios.s3` con el `leer3`
de verdad ligado. A partir de ahí el import diferido encuentra el módulo en caché, el patch no
toca nada y `calcular3()` devuelve 30 donde el test espera 50.

Reproducido a mano, sin modelos, en tres líneas:

```
tests/test_s3.py                      → OK
tests/test_r3.py tests/test_s3.py     → AssertionError: 30 != 50
patch('src.servicios.s3.leer3')       → OK de las dos formas
```

#### El alcance, contado

De los siete servicios de la corrida, **uno** traía la bomba:

| forma | servicios | el patch pega |
|---|---|---|
| `patch` donde el nombre **se usa** | s1, s4, s5 | siempre |
| `import src.datos.dN` adentro de la función | s2, s6, s7 | siempre |
| `from src.datos.dN import leerN` a nivel de módulo + `patch` al módulo de origen | **s3** | **sólo si corre solo** |

O sea: 1 de 7 tareas de la capa que mockea cargaba un rojo diferido, y el ⊘ del gate lo había
nombrado con precisión cuatro horas antes de que explotara.

#### Qué estaba mal, y qué no

Lo que **no** estaba mal: el chequeo. `_mocks.py --segun-enunciado` mira el contrato y no el
borrador del propio agente, y eso está medido (§ Medición 6: mirarle el borrador es
preguntarle al acusado). Tampoco estaba mal el 2x2 de §13, que dice que corregir la ruta sólo
paga cuando el contrato es mudo. Y no corresponde que el método **infiera** la forma del
import: eso lo fija el contrato y lo escribe el planificador.

Lo que estaba mal es que el ⊘ **no costaba nada y no dejaba rastro**. Un ⊘ es una deuda: el
método declara que no puede saber si el test es válido, lo acepta igual, y cuando la deuda
vence el rojo se lo cobra al vecino. Es el defecto de siempre de este método —el veredicto
nombra al sujeto equivocado— ahora con tres tareas de distancia entre la causa y la factura.

#### El arreglo: contabilidad, no criterio

1. **`scripts/_mocks.py`** — el ⊘ deja constancia en el TRONCO del proyecto
   (`.metricas/deuda-mocks.csv`: fecha, tarea, test, objetivo, destino, línea). El tronco y no
   el worktree, por lo mismo que `--registro` ya existía: el worktree de un test aceptado se
   borra. Si no puede anotar, lo dice en voz alta en vez de perder la atribución en silencio.
2. **`plantillas/gate.sh`** — antes de acusar a la tarea, pregunta si la falla nueva es de un
   test anotado **y** si ese test **pasa corrido solo**. Las dos condiciones, y ninguna
   alcanza sola: la constancia dice quién debe, y «pasa solo, falla con la suite» es la
   observación que distingue una deuda que detonó de una regresión honesta. Emite
   `DEUDA_DE_MOCK`.
3. **`scripts/correr-plan.sh`** — reconoce el marcador y no reintenta contra la tarea, igual
   que `ENTORNO_MOVIDO`.

No ablanda nada: **sigue siendo rojo y la etapa sigue deteniéndose.** Lo único que cambia es a
quién se le cobra, que es exactamente lo que estuvo mal en nueve de los doce defectos de la
semana del 21 de octubre y vuelve a estar mal acá.

La rama que distingue la deuda de la regresión no enumera causas de falla: **vuelve a correr el
test solo y mira**. Enumerar síntomas es la trampa que este archivo ya documenta dos veces
(la lista de siete `*Error`, la lista de firmas de MySQL), y acá no hacía falta: la propiedad
que define el caso —depender del orden de colección— es directamente observable.

#### Lo que queda fijado

`pruebas/test_metodo.py::TestLaDeudaDelMockSeLeCobraAQuienLaDebe`, 10 tests. Cuatro **se vieron
reprobar** la versión sin el arreglo; los otros seis son el cadáver reproducido y los guardias,
y pasan en las dos versiones a propósito:

- el escenario es real: el mismo test pasa solo y falla acompañado, por `30 != 50`;
- el arreglo del contrato funciona: con el patch donde el nombre se usa, pasa de las dos formas;
- una **regresión honesta** del mismo test anotado sigue siendo de la tarea (si no, la rama
  sería un perdón automático, y un instrumento que perdona todo es peor que ninguno);
- una deuda anotada sobre **otro** test no excusa esta falla;
- un patch que apunta bien **no deja deuda** (si cualquier test dejara constancia, la tabla no
  distinguiría nada);
- el marcador que el gate emite es el mismo literal que el runner busca — una cadena copiada en
  dos archivos es la clase de defecto que esta suite ya cazó dos veces.

#### Cuántas veces avisa el ⊘ y cuántas tenía razón

El titular de esta sección —«el ⊘ es una deuda»— hay que leerlo con su tasa, porque **avisa
más de lo que acierta**. En esta corrida el ⊘ se disparó sobre **cinco** objetivos distintos
(`d2→s2`, `d3→s3`, `d6→s6`, `d7→s7`, `r6→s6`; 14 líneas contando reintentos) y **uno** terminó
en rojo. Los otros cuatro quedaron sanos porque la implementación final trajo el nombre con
`import src.datos.dN` adentro de la función, que deja el patch efectivo.

O sea: el ⊘ es **condición necesaria y no suficiente**. Por eso la rama del gate exige las
**dos** cosas —estar anotado Y pasar corrido solo—: con la constancia sola, cuatro de cinco
veces estaría perdonando una tarea que sí rompió algo. Y por eso tampoco corresponde convertir
el ⊘ en rojo: 1 de 5 no alcanza para detener cuatro tareas buenas.

De paso, el reparto completo del chequeo en la corrida: **71** rechazos («el patch no va a
tener efecto»), **17** verdes, **14** ⊘. El trabajo principal del chequeo sigue siendo rechazar,
no dudar.

#### §8.7 contestado: ¿contra qué implementación se valida un test? (n=14)

La pregunta de §8.7 de INVESTIGACION.md —conservar el borrador descartado y medir en cuántas
tareas difiere de la implementación final *de un modo que invierte el veredicto*— tiene
respuesta con el material de esta corrida: 21 borradores conservados, 14 con implementación
final (los 7 de la capa `c` no la tienen porque la etapa se detuvo).

| borrador vs implementación final | tareas |
|---|---|
| idénticos byte a byte | **11 de 14** |
| difieren sólo en una línea en blanco | 2 (T01b, T05b) |
| **difieren de verdad** | **1 (T03b)** |

Y la única diferencia de fondo es **exactamente** la que invierte el veredicto:

| implementación de `s3` | `test_s3` sola | `test_s3` con `test_r3` colectado antes |
|---|---|---|
| **el borrador** con que el gate validó (`import src.datos.d3` adentro de la función) | OK | **OK** |
| **la final** de la etapa 1 (`from src.datos.d3 import leer3` a nivel de módulo) | OK | **FALLA** |

El borrador era **robusto** y la implementación final **frágil**. El gate validó el test contra
una implementación que lo hacía válido, y la de verdad lo hizo inválido. Es §6 otra vez —mirarle
el borrador es preguntarle al acusado— pero con el signo invertido respecto de la primera vez:
ahí el borrador era cómplice del test, acá era mejor que el final.

**Lo que queda medido, y es el número que §8.7 pedía: 13 de 14 veces el borrador es un buen
proxy de la implementación final; 1 de 14 no lo es, y esa vez costó la corrida.** Un 7% de
tareas en las que validar contra el borrador da un veredicto que la implementación real no
sostiene. Con n=14 eso no es una tasa publicable, es un orden de magnitud: no es «casi nunca»
ni «la mitad de las veces».

> **Cifra superada (2026-11-03, §21).** El n de este párrafo sale de buscar la implementación
> final en el TRONCO, o sea sólo en las etapas que integraron enteras. Mirando también las
> ramas `tarea/<id>` —que sobreviven cuando la etapa no integra— el acumulado es de 68 pares, y
> en la capa que mockea son **2 inversiones de veredicto en 20 pares**, no 1 en 14. El párrafo
> queda como lo que se midió ese día; la cifra vigente está en INVESTIGACION.md §8.7.

#### Y lo que esto dice del dataset

Los 40 veredictos de la corrida (21 aceptados / 19 rechazados) entran al dataset con una
etiqueta que antes no existía: **cuál de ellos venía con deuda**. Un juez entrenado con el
«aceptado» de T03b estaría aprendiendo a aprobar un test que tres tareas después detiene el
plan. El ⊘ anotado es, además de atribución, la columna que separa «aceptado» de «aceptado sin
poder verificarlo».

### §19 — El juez con 4x el n: la dirección se afirma, la magnitud baja, y lo que serviría sigue sin afirmarse (2026-11-01)

§17 midió con **n=28** y dijo «la dirección se afirma; la magnitud, no. Lo que hay que hacer
crecer es el reservado, no la conclusión». Creció. Y la conclusión cambió para peor.

El reservado del 30% de la partición nativa da sólo **15** pares intra-tarea, pero el dataset
entero da **274**, y para un juez **SIN AFINAR no hay fuga posible**: ningún parámetro vio
nada. Así que se midió ahí, con muestra **al azar de 120 de 274, semilla 1 declarada antes de
mirar**, huella del conjunto `8f3e2497`. Mismo juez (`1af07b1f`, Qwen3.8-27B FP8), mismo
formato pareado con orden invertido.

| | n=28 (§17) | **n=120 (hoy)** | azar |
|---|---|---|---|
| eligió bien en los DOS órdenes | 41% | **35%** | 25% |
| eligió mal en los dos | 22% | 25% | 25% |
| cambió con el orden | 37% | **40%** | 50% |
| entre los consistentes | 65% | **58%** | 50% |

Con las cifras que hacen falta para leerlo:

| medición | p exacto contra el azar | IC 95% |
|---|---|---|
| 42/120 bien en los dos órdenes | **0,0093** | [27,1% · 43,9%] |
| 42/72 entre los consistentes | 0,097 | **[46,8% · 69,0%]** |
| 48/120 inconsistentes | — | [31,7% · 48,9%] |

#### Qué cambió, exactamente

**La dirección pasó de insinuada a afirmada.** A n=28 el 41% contra 25% daba p=0,053: el
borde. A n=120 el 35% contra 25% da **p=0,0093**. Hay señal y ya no se discute.

**La magnitud bajó, y el IC viejo lo había avisado.** El 41% de §17 tenía IC [24,5% · 59,3%]
—contenía al 35% de hoy—, así que no hay contradicción: había una estimación imprecisa que yo
reporté como un número. Es la cuarta vez que un n chico me da una magnitud que el n grande
corrige hacia abajo.

**Y lo que de verdad importaba sigue sin afirmarse.** El número que decidiría si esto sirve
para un gate es el acierto **cuando el juez se compromete**: 58%, con IC **[46,8% · 69,0%]**,
que **contiene al 50%**. O sea: podría estar tirando una moneda entre los pares en que no se
contradice. A n=28 eso era 65% con p=0,17; a n=120 es 58% con p=0,097. Cuadruplicar el n no lo
movió del lado de «no se puede afirmar».

**La inconsistencia no bajó: subió.** 37% → 40%, con IC que llega a 48,9%, casi el 50% del
azar. Cuatro de cada diez veredictos cambian según en qué orden se pregunte.

#### El veredicto, que es el mismo de §17 y ahora con n

**No sirve para un gate, y ya no es «falta medir»: está medido.** Un juez que acierta 35%
donde el azar acierta 25% tiene señal, pero el 40% que cambia con el orden la vuelve
inutilizable para decidir, y entre los que no cambian no se distingue de una moneda.

Lo que esto cierra: **el camino de usar este reviewer sin afinar como juez de tarea está
cerrado**, y no por falta de datos. Lo que queda abierto es si afinarlo lo mueve, y para eso el
reservado de 15 pares sigue sellado —nunca se midió nada contra él— más las corridas que
vengan. La métrica sigue siendo **FPR a TPR fijo contra correr los tests**, que es gratis y no
se equivoca.

Y una nota de instrumento, porque esta medición no se podía hacer antes de arreglarlo: `--tope`
cortaba los **primeros** pares, y los pares salen ordenados por corrida. Con 41 corridas, los
primeros 120 son casi todos de las campañas viejas —las del exportador parseado, que además
traen el enunciado contaminado—. O sea que una medición con tope no medía al juez: medía **con
qué campañas se armó el dataset**, y lo informaba como habilidad. Ahora es muestra al azar con
semilla y huella del conjunto, y las dos cosas salen impresas al lado del número.

---

## §20 — La prueba de campo de la deuda del mock: no se disparó, y eso es el dato

Corrida `f1793561182` (semilla 1793561182, método en `d888c67`, árbol limpio, 4 vueltas,
**7/21 cerradas**, se detuvo en la etapa 2). Lo que iba a probar: la rama `DEUDA_DE_MOCK` de
§18, con modelos de verdad y sin ayuda mía.

#### El anotador anda; la rama no se ejecutó

`proy/.metricas/deuda-mocks.csv` quedó escrito: **17 líneas, 5 objetivos distintos**
(`d1→s1`, `d2→s2`, `d3→s3`, `d4→s4`, `d7→s7`) en 5 tareas (T01b, T02b, T03b, T04b, T07b). El
lado que registra funciona en producción.

La rama que **cobra** el rojo al deudor no se disparó **ni una vez**. Ninguno de los cuatro
rojos de la corrida fue «rompiste tests que andaban antes»:

| tarea | por qué quedó en rojo | de quién es |
|---|---|---|
| T01b | `archivos fuera del alcance: src/datos/d1.py` | agente |
| T02b | `no hay ningún cambio: la tarea no se hizo` | agente |
| T05b | `no hay ningún cambio: la tarea no se hizo` | agente |
| T07b | los tests de la tarea siguen fallando (×2 → punto muerto) | agente |

Por qué no se disparó: la detonación de §18 necesita que **otro** test precargue `sys.modules`
con un import a nivel de módulo, y ese import lo trae la capa `c`. Esta corrida se detuvo en la
capa `b`. **La rama sigue sin prueba de campo** —tiene los 13 tests de la suite, incluido el que
la corre una vez por cada una de las tres copias del gate, pero no tiene un caso real—. Dicho
sin adorno: lo que se verificó hoy es que el anotador escribe y que la rama **no produce falsos
positivos** en una corrida de 25 veredictos; que atribuya bien cuando toque, sigue apoyado sólo
en la reproducción de laboratorio.

#### Lo que sí pasó: la misma bomba se cobró en su propia tarea, por dos chequeos distintos

- **T03b** escribió `patch('src.datos.d3.leer3')` y una implementación con `from … import` a
  nivel de módulo. El paso **«pasa con la implementación del propio agente»** falló con el
  **mismo `AssertionError: 30 != 50`** de §18 —el mismo cadáver, tres etapas antes—. Dos
  intentos iguales → punto muerto, la tarea vuelve a una persona. El ⊘ se había emitido en los
  dos intentos y el test igual no pasó: acá el ⊘ y el rojo cayeron en la misma tarea.
- **T06b** cayó por el chequeo **definido**, no por el ⊘: «el test parchea un lugar donde el
  patch no va a tener efecto». Lo definido se puede afirmar porque la implementación ya existía
  cuando se validó el test. Punto muerto también.

Tasa del ⊘, actualizada y con la cuenta separada: esta corrida marcó **5 objetivos** con ⊘ y
**1 se cobró en el acto (T03b), 0 quedaron diferidos**; T06b no cuenta acá, porque cayó por el
chequeo *definido* y no por el ⊘. La corrida anterior marcó 5 y **1 detonó tres tareas después**.
Entre las dos: **10 objetivos marcados con ⊘, 2 se cobraron —uno en su propia tarea, uno tres
tareas más allá— y 8 no rompieron nada.** El ⊘ sigue siendo **condición necesaria y no
suficiente**, y ahora con el doble de n: las 14 líneas que marcó sobre T04b no rompieron nada y
la tarea pasó el gate en verde.

#### Cuántos de los ⊘ estaban de verdad armados

«8 de 10 ⊘ no rompieron nada» es verdad y no dice nada: la mitad de esos ⊘ estaban sobre
implementaciones donde el patch **no podía** fallar. El ⊘ se emite por lo que el enunciado no
declara, no por lo que la implementación hace; una vez que la implementación existe se puede
mirar, y ahí la pregunta tiene respuesta. Lo que decide no es la forma del import sola: es el
**par** (a dónde apunta el `patch`, cómo trae el nombre la implementación). Con el ⊘ ya emitido
—o sea, con el test apuntando a `src.datos.dN.leerN`—:

- `import src.datos.dN` **adentro de la función** → el patch pega siempre, en cualquier orden de
  colección. **No hay bomba.**
- `from src.datos.dN import leerN` **a nivel de módulo** → `sN` se queda con su propia
  referencia; el patch sólo pega si `sN` todavía no estaba importado. **Bomba armada**, y detona
  cuando otro test lo precarga en la colección.

Y el mismo `from` a nivel de módulo es inofensivo si el test apunta a `src.servicios.sN.leerN`,
que es donde el nombre se usa: en `f1793535892`, `s1`, `s4` y `s5` terminaron con el `from` de
módulo y **nunca** emitieron ⊘ ni rompieron nada, porque sus tests parcheaban ahí. La forma
frágil del import no es el defecto; el desajuste entre las dos cosas lo es.

Clasificando los diez ⊘ de las dos corridas por la forma que terminó teniendo la
implementación:

| corrida | ⊘ sobre | forma del import | ¿armada? | qué pasó |
|---|---|---|---|---|
| `f1793535892` | `s2` | dentro de la función | no | nada |
| `f1793535892` | `s3` | **módulo** (el final; el borrador era de los de adentro) | **sí** | **detonó en T03c** |
| `f1793535892` | `s6` | dentro de la función | no | nada |
| `f1793535892` | `s7` | dentro de la función | no | nada |
| `f1793535892` | `s6` (desde `r6`) | dentro de la función | no | nada |
| `f1793561182` | `s1` | **módulo** | **sí** | no detonó: la capa `c` no corrió |
| `f1793561182` | `s2` | dentro de la función | no | nada |
| `f1793561182` | `s3` | dentro de la función | no | nada |
| `f1793561182` | `s4` | dentro de la función | no | nada |
| `f1793561182` | `s7` | dentro de la función | no | nada |

**2 de 10 ⊘ estaban armados; 8 estaban sobre código donde el patch pegaba en cualquier orden.**
De los dos armados, uno detonó y el otro no —y no por mérito del método, sino porque la etapa
que lo habría detonado nunca corrió—. Caveat del instrumento: `s1` se clasifica por el
**borrador aceptado**, porque la capa `b` de esa corrida no integró y no hay implementación
final; y §8.7 acaba de mostrar que en la capa que mockea el borrador difiere del final 1 de 7
veces, justo en esta característica (recontado el 2026-11-03: **2 inversiones en 20 pares**, y
las dos en direcciones opuestas — ver §21 y INVESTIGACION.md §8.7; el caveat se sostiene igual,
porque lo que lo motiva es que el borrador pueda diferir, no cuánto). O sea que ese «sí» es el dato que tengo, no una
certificación.

Lo que esto cambia en la lectura del ⊘: no es «el gate grita cinco veces por corrida y acierta
una». Es **el gate grita cinco veces porque el enunciado no le dice, y una de esas cinco veces
hay una bomba real**. Bajar los gritos no se hace calibrando el gate: se hace arreglando el
enunciado, que es lo único que convierte el ⊘ en un chequeo definido.

Y queda una lectura que no esperaba: el caso malo de §18 —el rojo que viaja y le cae a un
inocente— **necesita que la tarea deudora pase**. Las dos veces que la bomba se cobró en su
propia tarea fue porque el gate la paró ahí. O sea que el arreglo de §18 no es un reemplazo del
chequeo de paso 2: es la red para cuando el paso 2 **no puede** ver la bomba, que es exactamente
cuando la tarea corre sola.

#### §8.7 con la corrida nueva: n=21, y de dónde vino ese n

> **Recontado el 2026-11-03 (§21): este n estaba limitado por el instrumento, no por los
> datos.** El par se buscaba en el tronco, así que sólo existía para las etapas que integraron
> enteras — y la integración es todo-o-nada, de modo que las capas difíciles no podían producir
> evidencia. Las ramas `tarea/<id>` sobreviven cuando la etapa no integra y tenían el código
> adentro. Acumulado real: **68 pares (35 `a` / 20 `b` / 13 `c`) y 2 inversiones de veredicto,
> las dos en la capa `b` y en direcciones opuestas.** La frase «la capa `c` sigue en cero
> pares» de más abajo era cierta sobre el tronco y falsa sobre el disco: hoy son 13 pares con
> cero diferencias. Lo que sigue queda como lo que se midió ese día.

Esta corrida aporta **7 pares** —la capa `a`, la única que integró; la capa `b` no tiene
implementación final porque la etapa nunca cerró—:

| borrador vs final | acumulado | capa `a` (sin mock) | capa `b` (mockea) |
|---|---|---|---|
| pares | 21 | 14 | 7 |
| idénticos byte a byte | 18 | **14 de 14** | 4 de 7 |
| difieren sólo en una línea en blanco | 2 | 0 | 2 |
| **difieren de verdad** | **1** | **0** | **1 de 7** |

Y acá me tengo que atajar a mí mismo: **los siete pares nuevos son todos de la capa `a`**, que
no mockea nada —`dN.py` es una función pura, el test no lleva `patch`—. El n creció justo donde
el riesgo no existe. Escribir «20 de 21» sería cierto y sería la cifra equivocada: promedia 14
casos que no podían fallar. **La tasa que decide es la de la capa que mockea, y sigue en 1 de
7**, con el mismo único caso (T03b de `f1793535892`). La capa `c` sigue en **cero pares**: no
integró en ninguna de las dos corridas, así que de la capa donde la bomba detona no tenemos ni
un par.

La conclusión operativa no se mueve: el borrador sirve para armar dataset, y no sirve para dar
por buena la implementación.

Dataset tras cosechar: **1400 registros** (817 aceptados / 583 rechazados), **42 corridas**,
25 nativos nuevos. Evidencia en `pares-8.7/f1793561182/` (14 borradores, 13 parches, 5 tareas
con los dos lados, y el `deuda-mocks.csv` de la corrida).

Y una comprobación que hay que hacer cada vez que el dataset crece: la partición
`--dedup --reservadas 12` sobre los 1400 da **41 familias → 29 entrenamiento / 12 reservado**,
638 registros de entrenamiento y 137 reservados, sin fuga. Las doce familias reservadas son
**exactamente las mismas** que con 1375 registros (`diff` de las dos listas: vacío): la corrida
nueva cayó del lado de entrenamiento. O sea que el reservado sigue sellado **y** sigue siendo
comparable con lo que se mida después; si hubiera cambiado, cualquier número contra él dejaría
de ser comparable con el anterior y habría que decirlo.

### §21 — La corrida que llegó hasta el fondo: 21/21, las tres capas, y cero detonaciones explicadas (2026-11-03)

Corrida `f1793664018` (semilla 1793664018, método en `b482e76`, árbol limpio, `VUELTAS=8`,
**21/21 cerradas en 4 vueltas**). Es la primera de la historia del método que cierra las tres
capas e integra: `src/rutas/r1..r7` en el tronco, 21 borradores conservados, 21 pares completos,
cero «sin par». Lo que §20 no pudo probar —la rama `DEUDA_DE_MOCK` con la capa `c` ejecutada—
acá se pudo.

#### Cero ⊘ y cero detonaciones, y esta vez con el motivo medido

`DEUDA_DE_MOCK` no disparó, igual que en `f1793561182`. Pero el motivo es otro y es el que
importa: **no hubo nada que cobrar.** En las siete tareas de la capa que mockea no hubo un solo
desajuste entre dónde parchea el test y cómo la implementación trae el nombre.

| servicio | implementación final | dónde parchea su test | desajuste |
|---|---|---|---|
| s1, s4, s5, s6 | `import src.datos.dN` (uso por atributo) | `src.datos.dN.leerN` | no |
| s2 | `from src.datos.d2 import leer2` | `src.servicios.s2.leer2` | no |
| s3, s7 | `from src.datos.dN import leerN` | (su test no parchea) | no aplica |

Es la afirmación de §20 confirmada por el lado que faltaba: **el desajuste es el defecto, no la
forma del import**. Tres de siete finales traen el nombre con la forma frágil y ninguno emite ⊘,
porque sus tests parchean donde el nombre se usa o no parchean nada.

Y la razón de que la capa `c` tampoco detone nada: **sus tests parchean `src.rutas.rN.calcularN`
—su dependencia inmediata, la capa de servicios— y nunca importan ni parchean `src.datos.dN`.**
La precarga de `sys.modules` que la bomba necesita no la hace la capa `c` sobre los módulos de
datos. La topología que §18 arma no es la que el agente produce cuando le va bien; §20 suponía
que faltaba ejecutar la capa `c` y lo que faltaba era otra cosa.

#### Los 4 registros del anotador son deuda de verdad, no falsos positivos

`deuda-mocks.csv` anotó 4 objetivos (`d1→s1`, `d4→s4`, `d5→s5`, `d6→s6`): exactamente los cuatro
servicios que usan `import X` con uso por atributo y cuyo test parchea en la capa de datos.
Funcionan hoy **y quedan ciegos el día que alguien pase esa implementación a `from X import n` a
nivel de módulo**. Eso es deuda —funciona y es frágil ante un refactor— y el anotador la nombra
bien. Lo anoto porque mi primera lectura fue la contraria: miré que los cuatro anotados eran los
sanos y pensé que el anotador tenía el signo invertido. No lo tiene; mide otra cosa que la que
yo esperaba, y la mide bien.

#### Qué dice el dataset de esta corrida sobre dónde falla el modelo chico

40 veredictos nativos: 21 aceptados, 19 rechazados. El motivo dominante de rechazo es, por
lejos, **el chequeo de mocks: 9 de los 19** («el test parchea un lugar donde el patch no va a
tener efecto»). Después: 5 por no escribir el archivo/clase pedidos, 2 por un test que no pasa
ni con la implementación del propio agente, 1 por mutantes sobrevivientes, 1 por límite de
tiempo. El paso que más trabaja del gate es el que §18 agregó.

#### Un falso veredicto en el log, del lado del método

El log informó `✗ T04c gate ROJO, y la herramienta falló: The user rejected permission to use
this specific tool call.` — 83 segundos, el agente no llegó a trabajar, y T04c cerró VERDE en el
intento siguiente. El **registro** estaba bien: `intentos.csv` lo anotó `ERROR`, no `ROJO`, y el
veredicto nativo no entró al dataset como rechazo. Lo que estaba mal era el mensaje, que es lo
que yo leo cuando monitoreo: un rojo que no es del agente, dicho con el símbolo del rojo del
agente. Arreglado a `⊘ … la herramienta falló y el gate no pudo juzgar`, que es lo mismo que
dice el registro. Dos nombres para la misma fila, y el equivocado era el visible.

#### Y el que sí era grave: el método tiraba la evidencia de todo lo que sale bien

Medido sobre las siete corridas de campaña en disco: **140 transcripts de éxito con cero
parches; 66 de fracaso con 51 parches.** Del intento que PASÓ no quedaba nada ejecutable, que es
justo la mitad que la fábrica de dataset necesita y que el propio código declara como motivo
para conservar el éxito.

La causa no era la asimetría que parecía: `cerrar_con_gate` hace `git add -A && git commit`
**sólo cuando el gate da verde** —para que `git merge tarea/TNN` traiga algo— y
`conservar_intento` armaba el parche contra `HEAD`, que ese commit acaba de absorber. Sin rc 0 no
hay commit y el diff ve todo: por eso los fracasos se guardaban y los éxitos no. Es el defecto
que este repo ya documentaba y había arreglado del otro lado —`correr-tarea.sh` escribe
`.base-ref` precisamente porque «cualquier chequeo de diff se vuelve ciego en cuanto el agente
commitea», y el gate la lee de ahí—; el conservador de evidencia seguía en `HEAD`. Octava vez
que el arreglo vivía en el hermano.

El test que debería haberlo visto existía y miraba el lado equivocado: el e2e del pipeline
verificaba que quedara `exito-*.log` y daba verde mientras el parche no existía. El transcript
registra `Write src/cosa.py` sin el contenido, así que el relato estaba y el código no.

### §22 — El reservado del juez no servía para evaluarlo, y «✓ sin fuga» lo tapaba (2026-11-03)

Iba a medir lo único que falta del juez —el FPR a TPR fijo contra correr los tests— y antes
chequeé que el sujeto fuera medible. No lo era.

#### Los números

Sobre la partición de los 1446 registros (`--dedup --reservadas 12`, 43 familias → 31/12):

| | entrenamiento (660) | reservado (137) | p de Fisher |
|---|---|---|---|
| enunciados con la tarea ya marcada `✅ hecha` | 52 (8%) | **133 (97%)** | **1,9e-12** |
| tasa de aceptación | 285 (43%) | 94 (**69%**) | **6,1e-08** |

**El azar de cualquier medición puntual contra ese reservado es 69%, no 50%.** Y los dos lados
no son la misma población: un número medido en uno no se compara con uno medido en el otro.

#### No es un defecto de la partición por familias

Partir por familia —la corrida— es correcto y es la guarda número uno contra el sobreajuste.
Lo que pasa es que la familia **agrupa también la procedencia**: las corridas viejas vienen del
parseo de logs y su enunciado es el del final, con la tarea ya marcada; las nuevas vienen del
emisor nativo y traen el enunciado que el agente vio. Reservar familias enteras puso todas las
viejas de un lado. `fuente` del reservado: 137 de 137 `parseado`.

El defecto era del instrumento: `particionar_veredictos.py` decía «✓ sin fuga» y nada más, y yo
leí eso como «el reservado sirve». **Sin fuga no es comparable.** El script tenía la tasa base
del reservado —la calcula para imprimir los conteos— y no la decía, que es justo el número que
decide contra qué se compara un acierto.

#### Qué queda invalidado y qué no

**§19 y §17 están a salvo, y por una razón de diseño, no por suerte.** Miden al juez en formato
**pareado intra-tarea**: los dos lados de cada par son de la MISMA tarea, así que comparten el
enunciado y la marca `✅ hecha` aparece idéntica en los dos. Una pista que está en los dos lados
no es una pista. Además §19 no usó el reservado: midió sobre 274 pares del dataset entero, con
el argumento —correcto— de que para un juez sin afinar no hay fuga posible porque ningún
parámetro vio nada.

**Lo que no se puede medir contra ese reservado es un juez PUNTUAL** —dado un test, ¿lo
aceptarías?—, que es exactamente el que iba a construir. Ese ve el enunciado completo y con él
la marca, y además se mediría contra una tasa base del 69%.

#### El arreglo

`particionar_veredictos.py` ahora informa **siempre** —no sólo al fallar, porque un chequeo que
habla sólo cuando hay problema deja al lector sin saber si corrió—: el azar del reservado, y
para cada rasgo la proporción de los dos lados con su p de Fisher. Grita cuando p<0,001, umbral
declarado: con este n una diferencia así no la explica el muestreo. `estado_del_enunciado` se
**importa** de `juntar_veredictos.py` en vez de copiarse, y si el import falla el chequeo lo
dice en vez de callar el rasgo (⊘ no es «no hay»).

Y nace `scripts/_estadistica.py` con `fisher_exacto_2x2`, sin scipy —esta Mac tiene las CLT
viejas y `brew` no compila, así que una dependencia binaria es un script que no corre en un
clon— y **verificado contra dos tablas que se recalculan con lápiz**: `[[2,0],[0,2]] = 2/6` y la
tabla del té de Fisher `[[3,1],[1,3]] = 34/70`. Contrastarlo contra otra biblioteca sería
auditar un número con otro que tampoco auditó nadie. §19 calculó su p fuera del repo; desde hoy
el cálculo vive acá y se puede volver a sacar.

Cuatro tests del helper (los dos casos de lápiz, los dos extremos, que no dependa de cómo se
escribió la tabla, y que una tabla vacía dé p=1 en vez de dividir por cero) y tres del chequeo,
con **brazo nulo**: cuando los dos lados tienen las mismas proporciones, no grita. Un chequeo
que grita siempre no distingue nada y entrena a ignorarlo.

#### Y mi propia medición, que dijo lo que yo quería oír

Mi primer chequeo de contaminación fue un `grep` de siete palabras sobre el enunciado
(`'no pasa'`, `'parchea un lugar'`, `'aceptado'`…) y dio **0 de 137**: limpio. El detector que
el repo ya tenía —`estado_del_enunciado`, que busca `Estado:** ✅`— dio **133 de 137**. Décima
vez en este repo que un extractor por patrón me devuelve el número cómodo, y la lección es la
de siempre con una vuelta más: no sólo hay que cortar por estructura en vez de por patrón, hay
que **buscar primero si el repo ya tiene el detector** antes de escribir uno. Acá lo tenía, a
veinte líneas, en el script que yo mismo había corrido media hora antes.

#### Lo que sigue

El banco para el juez puntual hay que construirlo aparte y declarado: estratificado por
procedencia y por veredicto, sin tocar el reservado actual —que queda sellado y comparable con
§17 y §19—. Mientras no exista, el FPR a TPR fijo no se puede medir, y decirlo es el resultado.

#### El banco del juez puntual, construido y sellado

Lo que faltaba para poder medir: un reservado comparable. Se armó con **sólo los registros
nativos**, que son los limpios por construcción —el enunciado es el que el agente vio—: 926
registros de 27 corridas, **0 contaminados**, 512 aceptados / 414 rechazados (55/45).

Partido por familia con `--dedup --reservadas 8`, y el tamaño se eligió **antes de ver ningún
resultado del juez**, por tres motivos declarados: replica el 30% de familias que usaron §17 y
§19, da n=158 —el doble del reservado viejo— y deja 18 familias de entrenamiento. Se probaron 4,
6, 8 y 10 familias y las cuatro pasan el chequeo nuevo; elegir mirando el resultado del juez
sería elegir el banco por conveniencia.

| | entrenamiento | reservado | p |
|---|---|---|---|
| registros | 439 | **158** | |
| tasa de aceptación | 43% | 46% | 0,57 |
| enunciados con el resultado adentro | 0% | 0% | 1 |
| mezcla de motivos de rechazo | — | — | ≥0,057 en los seis |

Sin fuga, y comparable en los tres rasgos. En
`metodo-agentes-datos/banco-juez-puntual-20261103/`, con `HUELLA.txt` —sha256 de cada archivo—
escrito antes de medir nada. El reservado viejo queda intacto y sigue siendo comparable con §17
y §19.

#### Deuda medida, no arreglada: el campo estructurado no dice qué paso rechazó

Buscando un tercer rasgo que chequear encontré otra cosa, y es del activo principal. El
docstring de `_veredicto.py` dice que el juicio dimensión por dimensión «es lo que no tiene
ningún dataset público de software». Medido sobre los 414 rechazos nativos: **400 (97%) no
tienen una sola dimensión marcada `✗`.** La mediana de dimensiones registradas es 6 en un
aceptado y **1** en un rechazado.

El motivo es de diseño: `dim nombre ✓` se llama cuando un paso PASA, y los 26 puntos de rechazo
llaman a `malo "<texto>"`, que registra el motivo en prosa y no toca la dimensión. El gate corta
ahí, así que `dimensiones` dice **hasta dónde llegó** y no **qué falló**.

Y no se puede deducir: probé la hipótesis «el último paso registrado más el orden del gate da el
paso que falló» y es falsa —con `{"alcance": "✓"}` aparecen al menos dos motivos distintos, «el
test obliga un contrato que el enunciado no declara» y «el test parchea un lugar donde el patch
no va a tener efecto»—. El texto del motivo sí lo dice unívocamente; el campo que un juez
entrenaría, no.

El arreglo tiene diseño y no está hecho: `malo()` es el embudo único de los 26 rechazos, así que
si cada bloque de paso declara su nombre al entrar, `malo()` puede marcar `dim "$PASO" ✗` en un
solo lugar. Son ~10 asignaciones en vez de 26 cambios. No lo metí hoy: es cirugía en el script
central del método, verificarla exige ejercitar los 26 caminos, y un gate roto a medias es peor
que un campo incompleto. Queda anotado con su medición para que el próximo que lo lea sepa qué
tan grande es y por dónde entrar.

> **Hecho el mismo día, en §23.** Lo que esta sección declara como deuda está arreglado más
> abajo, y midiéndolo apareció algo peor que «el campo está incompleto»: estaba **al revés**.
> Las cifras de arriba —400 de 414, mediana 1— son del dataset de hoy y quedan como están: son
> lo que el dataset tiene, y los registros viejos no se reescriben.

### §23 — El campo estructurado no estaba incompleto: estaba al revés (2026-11-03)

La deuda de §22, arreglada. Y lo que la medición mostró al ejercitarla de punta a punta no es lo
que §22 suponía.

**Lo que había.** Corrí el ensayo determinista con el comportamiento `tests_flojo` —un test que
cubre las líneas y no verifica el comportamiento— contra el gate **sin** el arreglo. El registro
del rechazo quedó así:

```json
{"veredicto": "rechazado",
 "dimensiones": {"alcance": "✓", "objetivo_del_patch": "✓",
                 "falla_sin_implementacion": "✓", "pasa_con_implementacion": "✓"},
 "motivo": "sobreviven mutantes: el test cubre las líneas y no verifica su comportamiento…"}
```

Cuatro dimensiones, **las cuatro en ✓**, y el veredicto «rechazado». No es un campo con huecos:
es un campo que afirma lo contrario de lo que pasó. Un juez entrenado sobre esto aprende que un
registro con todo en verde es un rechazo, y el único lugar donde está la causa es la prosa — o
sea exactamente lo que el docstring de `_veredicto.py` dice que este dataset tiene de más que
los públicos, y no tenía.

**El arreglo.** `dim()` pasa a definirse antes, `paso <nombre>` declara el bloque y `malo()`
—el embudo único— hace `dim "${PASO:-sin_paso_declarado}" ✗` y **limpia** el nombre. Son 16
declaraciones y un cambio en el embudo, no 26 cambios.

Las dos decisiones que importan y por qué:

- **`malo` limpia el nombre después de usarlo.** El riesgo de este arreglo no es que falle: es
  que ATRIBUYA MAL, y una dimensión equivocada es peor que una que falta. Sin limpiar, un
  segundo rechazo sin bloque propio heredaría el nombre del anterior y el dato diría que falló
  un paso que pasó.
- **Lo no declarado sale como `sin_paso_declarado`, no adivinado.** Un bloque nuevo que se
  agregue sin declarar su paso se ve **en el dato**, y además lo caza el test que recorre los 26
  puntos de rechazo y exige un `paso` que los gobierne.

**Lo que ahora queda escrito**, medido con los cuatro comportamientos `tests_*` del ensayo
determinista —cuatro caminos de rechazo distintos, con modelos de nadie y repetible—:

| comportamiento | dimensión en ✗ | ✓ que conserva |
|---|---|---|
| `tests_otraclase` | `archivo_y_clase` | 2 |
| `tests_imposible` | `pasa_con_implementacion` | 3 |
| `tests_flojo` | `mutantes` | 4 |
| `tests_vacuo` | `falla_sin_implementacion` **y** `mutantes` | 3 |

El último caso es el que confirma que el diseño es el correcto: un test vacuo falla **dos** pasos
—pasa sin la implementación y además no distingue— y el registro ahora lo dice con dos ✗ en vez
de elegir uno. Un campo con un solo casillero por registro no habría podido.

**Y de paso, una cobertura que no existía.** Los cuatro comportamientos `tests_*` están en
`_ensayo_agente.sh` desde el 2026-10-26 para ejercitar los rechazos de `escribir-tests.sh`, y
**ningún test los corría**: el andamio `ensayar` del test de punta a punta no pasaba la fase de
tests, así que siempre mandaba `cumple`. Dos de los cuatro quedan corriendo en la suite —uno que
rechaza temprano y uno que rechaza al final—; los cuatro quedan medidos acá.

**Lo que esto NO arregla.** Los 1.446 registros que ya están escritos no cambian: el campo nuevo
empieza a valer desde la próxima corrida. Para un juez entrenado eso significa que el dataset
tiene dos regímenes, y la partición por familia los separa sola —cada corrida es una familia—,
así que es un rasgo más a chequear entre entrenamiento y reservado, no una contaminación.


---

### §24 — El juez puntual contra el reservado sellado: sirve de pre-filtro, y el 27% que no contestó es el dato que hay que mirar primero (2026-11-03)

§19 cerró un camino: el reviewer sin afinar **no sirve como juez de tarea**. 35% de acierto
contra 25% del azar, 40% de los veredictos cambia según el orden de los dos candidatos, y entre
los que no cambian el IC contiene al 50%. Está medido y no es falta de n.

Esta medición es de **otra pregunta**, y conviene decirlo antes del número porque si no parece
que el mismo juez pasó de inútil a bueno. No es el mismo juez: es la misma pieza contestando algo
distinto. §19 le pedía decidir **qué implementación es mejor**. Acá se le pide predecir **si el
gate aceptaría este test**, con el veredicto del gate como verdad. La segunda pregunta tiene una
verdad gratis y no se equivoca; la primera no tiene verdad ninguna. Que la segunda salga mucho
mejor no contradice a CodeJudgeBench §5.1 —puntual peor que pareado— porque no se está comparando
puntual contra pareado: se está comparando **una pregunta con verdad contra una sin verdad**.

Mismo modelo que §17 y §19: `1af07b1f-5832-4451-a61c-76d1fe43115a`. Reservado sellado de
§22, huella `39457e81cb6aa895`, **que nunca se había medido contra nada**.

> **El número a citar es el de §26, no el de acá.** Esta corrida está limitada por el tope de
> tokens: 27% de las respuestas no llegó a contestar, y §26 muestra que ese 27% era justo la
> parte del banco donde el juez no tiene señal. Con el instrumento arreglado el reservado
> entero da exactitud 79%, TPR 86% y **FPR 28%**, no 18%. Lo de acá sigue escrito porque la
> diferencia entre las tres corridas es el instrumento, y eso es la mitad de lo que hay que
> saber para leer cualquiera de los números.

#### Lo primero, porque cambia cómo se lee todo lo demás: 27% no contestó

De los 147 registros del reservado con test, enunciado y veredicto, **39 (27%) se cortaron por el
tope de 4000 tokens**: el modelo se quedó razonando y nunca llegó al veredicto. Los 39 son
`finish_reason=length`, ninguno es otra cosa.

Esas 39 **no cuentan como rechazo**. Es la trampa que el instrumento tiene prohibida por
construcción: si una respuesta ilegible contara como «rechazar», un modelo que no contesta nada
saldría con especificidad perfecta. Y es exactamente la falla que hubo que arreglar para poder
hacer esta medición —el parser tomaba la última palabra de una respuesta cortada, y una respuesta
cortada contiene las palabras de la consigna, así que devolvía «rechazado» en nombre de un modelo
que no había dicho nada—.

El corte **no cayó parejo entre las clases**:

| | cortados | de | % | IC95 |
|---|---|---|---|---|
| aceptado | 24 | 72 | 33% | [24% · 45%] |
| rechazado | 15 | 75 | 20% | [13% · 30%] |

Fisher exacto bilateral **p = 0,092**. O sea: **no se puede afirmar que el corte esté sesgado, y
tampoco que no lo esté.** La dirección —se come más aceptados— es la que haría que todo lo que
sigue se leyera mejor de lo que es, porque dejaría afuera los casos que al modelo le cuestan. Lo
que sí es un hecho es que **lo que sigue está medido sobre el 73% que contestó**, y ese 73% tiene
44% de aceptados donde el reservado entero tiene 49%.

#### El número, con sus cuatro referencias

Sobre los **108 que contestaron** (48 aceptados / 60 rechazados, tasa base 44%):

| | valor | IC95 |
|---|---|---|
| exactitud | 91/108 = **84%** | [76% · 90%] |
| clase mayoritaria (rechazar siempre) | 60/108 = 56% | [46% · 65%] |
| TPR en el punto de operación | 42/48 = **88%** | [75% · 94%] |
| FPR en el punto de operación | 11/60 = **18%** | [11% · 30%] |
| AUC | **0,88** | — |

Las cuatro referencias que van siempre, porque sin ellas el número se lee mejor de lo que es:

1. **La tasa base no es 50%.** La mayoritaria acierta 56%. El 84% está arriba, y los IC no se
   tocan: [76% · 90%] contra [46% · 65%].
2. **Las ilegibles van contadas aparte y nunca como rechazo.** 39, declaradas arriba.
3. **Aceptar TODO da TPR 100% con FPR 100%**, sin juez ninguno. El juez aporta en la medida en que
   su FPR baje de 100% al TPR que uno exija. Acá: a TPR 88%, FPR 18%.
4. **El barrido tuvo 5 puntuaciones distintas.** No es una curva de dos puntos. Pero ver abajo:
   casi toda la AUC viene del signo, no de la confianza.

El barrido entero, que es lo que se puede desplegar:

| umbral | TPR | FPR | IC95 del FPR | |
|---|---|---|---|---|
| 11 | 0% | 0% | [0% · 6%] | no acepta nada |
| 10 | 69% | 12% | [6% · 22%] | |
| **9** (= su veredicto crudo) | **88%** | **18%** | [11% · 30%] | punto de operación |
| −9 | 92% | 18% | [11% · 30%] | ver la advertencia |
| −10 | 96% | 38% | [27% · 51%] | |
| −11 | 100% | 100% | [94% · 100%] | aceptar todo: no descarta nada |

#### Tres controles, que es lo que distingue señal de forma

**Cinco criterios tontos sobre los MISMOS 108 registros.** Si uno de ellos empatara 0,88, el juez
no estaría leyendo el test: estaría leyendo su forma.

| criterio | AUC |
|---|---|
| largo del test en caracteres | 0,42 |
| largo del enunciado | 0,50 |
| cantidad de `assert` | 0,44 |
| cantidad de líneas | 0,47 |
| cantidad de `def` | 0,46 |
| **el juez** | **0,88** |

Los cinco están en el azar. La señal es de contenido.

**La identidad de la tarea no es el atajo.** Los 108 registros son de 15 tareas, y **13 de las 15
tienen los dos veredictos**. Un predictor que memorizara «esta tarea sale aceptada» no llega a
0,88 porque casi ninguna tarea es de una sola clase.

**El juez no contesta siempre lo mismo.** 53 aceptar / 55 rechazar. Un constante habría salido
con TPR 0% o FPR 100%, y el instrumento lo dice cuando pasa.

#### Dos cosas que el número de arriba no dice y hay que decir

**La confianza casi no aporta nada.** El modelo contesta 8, 9 o 10 y nunca menos. Tirando la
confianza a la basura y quedándose sólo con el signo del veredicto, la AUC baja de **0,884 a
0,846**: la confianza aporta **+0,038**. O sea: **esto no es un puntaje calibrado, es un veredicto**.
El barrido de 5 umbrales existe y hay que informarlo, pero lo que se despliega es el sí/no más una
política para las ilegibles, no un umbral afinado.

**El umbral −9 NO es un resultado.** Da TPR 92% con el mismo FPR 18%, que se lee como cuatro
puntos de TPR gratis. La razón es que ningún rechazado real cayó en esa canasta —«RECHAZAR con
confianza 8»—, y la canasta tiene 2 registros aceptados y 0 rechazados. **Eso es un umbral elegido
sobre el mismo reservado que se está informando**, con una diferencia de 2 registros sobre 60
negativos: adentro del ruido. El umbral se elige sobre entrenamiento y se informa sobre reservado,
o no se elige. Queda como hipótesis a confirmar contra los 439 de entrenamiento, no como número.

#### El veredicto: sirve de pre-filtro, no de reemplazo del gate

La diferencia no es de grado, es de qué cuesta equivocarse.

**Como pre-filtro delante del gate**, el gate sigue siendo el árbitro: un falso positivo sólo
cuesta cómputo, porque el gate lo rechaza igual. Y las 39 abstenciones van al gate como cualquier
otra cosa. Lo único que se pierde de verdad es el falso negativo: material bueno que el gate
nunca ve.

| | valor | IC95 |
|---|---|---|
| el gate corre en | 92/147 = 63% | [55% · 70%] |
| trabajo del gate evitado | 55/147 = 37% | [30% · 45%] |
| de lo que tira, era basura | 49/55 = 89% | [78% · 95%] |
| **material bueno perdido** | **6/72 = 8%** | [4% · 17%] |

Un tercio menos de corridas del gate, y nueve de cada diez cosas que descarta eran basura, a
cambio de perder el 8% del material bueno. Eso **sirve**, y es la primera pieza de este proyecto
que se mide bien contra un reservado sellado.

> **RETIRADO en §27, y los números corregidos en §26.** Dos cosas falsas en ese párrafo: los
> números son los de la corrida limitada por el tope (el bueno es 44% / 84% / 14%), y «sirve» no
> se sostiene —una corrida del gate cuesta ~20 s locales contra 118 s de plataforma del juez, y
> saltear el gate no produce etiqueta—. Lo único que queda en pie, y es lo que vale, es «se mide
> bien contra un reservado sellado».

**Como reemplazo del gate** —etiquetar sin correr los tests— no sirve: **21% [12% · 33%] de lo que
etiquetaría como aceptado es basura**, más 39 registros que sin gate no tendrían etiqueta ninguna.
Un dataset con uno de cada cinco registros mal etiquetados no es un dataset.

#### Y una nota de instrumento, que la pagué con tres horas a ciegas

La corrida tardó **3h50 para 147 registros: 100 segundos por registro**, no los 110 minutos que
estimé. La estimación salió del humo con `max_tokens: 600`, donde el modelo tardaba 27s. Con el
tope en 4000 razona mucho más. El tope **no se baja** —es uno de los tres guardas contra la falla
del parser— así que lo que se corrige es la estimación: **2,5 min por registro** para esta clase
de medición, y un reservado de 147 son cuatro horas.

Y el `--crudo` se volcaba **al final**. Durante 3h50 el log tuvo tres líneas y no hubo manera de
saber por dónde iba; si el proceso hubiera muerto en el registro 140, habría dejado **cero**
respuestas en disco y 140 llamadas al modelo pagadas y perdidas. Arreglado en el commit siguiente:
se escribe a medida con vaciado inmediato, así `wc -l` del crudo es la señal de avance. El test de
eso no puede ser «el archivo existe al final» —pasa igual con el volcado al final—: el guion pasa
a poder ser una **tubería con nombre**, y el test marca el paso, le da dos respuestas, mira el
crudo con el proceso todavía vivo, y recién entonces le da el resto.

---

### §25 — El 27% que no contestó era el tope, no el juez; y la magnitud se replica en otra partición (2026-11-03)

§24 informó 84% de exactitud con un 27% de respuestas que nunca llegaron a contestar, y dejó dos
cosas abiertas que no se podían cerrar con esos datos: **cuánto presupuesto hacía falta**, y si el
número estaba inflado porque el corte se comía los casos difíciles.

#### El diagnóstico, que estaba en el crudo y es gratis

De las 39 respuestas cortadas, **ninguna —cero de 39— había cerrado el bloque de razonamiento**.
No se quedaron cortas al contestar: se quedaron cortas razonando. Y 11 de 39 ya habían decidido
ahí adentro («Thus ACEPTAR. ... I'd say 7») sin haber emitido nunca la línea etiquetada. Sacarle el
veredicto a eso es exactamente la falla de campo que hubo que arreglar, así que no se parsean.

O sea que ese 27% **no era una propiedad del juez: era el tope**. Y el tope de 4000 se había
elegido mirando una muestra de humo donde el modelo cerraba en 611 tokens — los casos fáciles.

#### El presupuesto, medido

Sondeo contra **entrenamiento, no contra el reservado** —el reservado se informa, no se afina—:
40 registros al azar de los 419 elegibles, **semilla 3 declarada antes de mirar**, huella
`aae3567e`, tope 16000.

Gasto de las 37 que contestaron: **mediana 1423, p90 5586, máximo 6726 (42% del tope)**. Cero
cortadas por tope.

| tope | cortadas | espera |
|---|---|---|
| 4000 (el de §24) | 6/37 = 16% | 300 s |
| 6000 | 2/37 = 5% | 300 s |
| **8000** | **0/37** | 400 s |
| 10000 (el nuevo) | 0/37 | 500 s |
| 16000 | 0/37 | 800 s |

El tope por omisión pasa a **10000**: deja 1,5× de margen sobre el máximo observado y lo único que
cuesta es espera, que sólo se paga si la plataforma se cuelga. No se elige 8000 porque el 16% que
este sondeo predice para 4000 fue 27% en el reservado, así que la cola de allá puede ser más
pesada que la de acá. Y si quedara apretado, el informe ahora **avisa**: el máximo gastado sale
impreso al lado del tope.

#### La replicación, que es el control que §24 no podía hacer

La misma corrida juzgó 37 registros con **7,5% de pérdida en vez de 27%**, en una partición
distinta. Si el 84% de §24 hubiera sido un artefacto del corte —los difíciles afuera— acá tendría
que haber bajado.

| | §24 (reservado, tope 4000) | §25 (entrenamiento, tope 16000) |
|---|---|---|
| pérdida | 27% (39/147) | 7,5% (3/40) |
| n juzgado | 108 | 37 |
| tasa base | 44% | 51% |
| exactitud | 84% | **84%** |
| TPR / FPR en el punto de operación | 88% / 18% | **84% / 17%** |
| AUC | 0,88 | **0,92** |

**No bajó.** Con n=37 los IC son anchos —el FPR 17% viene con [6% · 39%]— así que esto no es una
medición de precisión: es un control de artefacto, y lo pasa. La magnitud de §24 no venía del
corte.

> **ESTO ESTÁ MAL, y el error es de método. Corregido en §26, el mismo día.** Bajó: FPR 18% →
> 28% sobre el reservado entero, y los 39 registros que el tope se comía tienen FPR 67% con AUC
> 0,59. El IC de este control —[6% · 39%]— contiene al 18% y al 28% a la vez, así que **no podía
> distinguirlos**: declaré «no bajó» con un control que no tenía poder para decirme que sí. Un
> control de artefacto necesita su poder declarado; si su IC contiene la magnitud buscada, no se
> pasó, no se corrió.

Los criterios tontos, sobre estos 37: largo del test 0,31, cantidad de `assert` 0,39, cantidad de
líneas 0,32. Los tres en el azar o por debajo, igual que en §24.

Y una diferencia que vale: acá la confianza aporta **+0,080** de AUC sobre el signo solo, contra
+0,038 en §24. Con más presupuesto el modelo usa un rango de confianza más ancho. Sigue siendo
poco: esto es un veredicto, no un puntaje calibrado.

#### El umbral, PRE-REGISTRADO

§24 dijo que el umbral −9 no era un resultado porque estaba elegido sobre el mismo reservado que
se informaba. Acá se elige donde corresponde. El barrido completo en entrenamiento:

| umbral | TPR | FPR | IC95 del FPR |
|---|---|---|---|
| 11 | 11% | 0% | [0% · 18%] |
| 10 | 58% | 6% | [1% · 26%] |
| 9 (el veredicto crudo) | 84% | 17% | [6% · 39%] |
| **−9** | **95%** | **22%** | [9% · 45%] |
| −10 | 100% | 50% | [29% · 71%] |
| −11 | 100% | 100% | [82% · 100%] |

**Queda elegido −9**, o sea «aceptar salvo que haya dicho RECHAZAR con confianza ≥ 9». El motivo
es el mismo que apareció en los dos lados: los rechazos de baja confianza del modelo son los que
se equivocan. Escrito acá antes de volver a medir, la predicción es **TPR ≈ 95% con FPR ≈ 22%**
sobre el reservado. Si sale muy distinto, el que estaba mal es el umbral y no el reservado.

#### Y tres registros que se perdían sin nombre

El sondeo tuvo 3 fallas de herramienta sobre 40, informadas como `⊘ falla de herramienta:
HTTPError`. **Eso no se puede accionar**: no distingue un 429 de plataforma ocupada —que se
reintenta solo— de un 400 de pedido mal armado —que no—. Y un error sin nombre es indistinguible
de «el modelo no supo» en todos los números del informe.

Arreglado: el detalle lleva el código HTTP y lo que dijo el cuerpo, y los códigos transitorios
—408, 409, 425, 429, 5xx— se reintentan hasta tres veces con pausa creciente. Los que no son
transitorios **no** se reintentan, porque insistir con un pedido mal armado gasta tres esperas por
registro y sobre un banco de 147 es la diferencia entre enterarse en un minuto y en una hora. Y
los reintentos se **cuentan y se declaran**: reintentar en silencio cambia el denominador de la
medición sin que nadie lo vea.

#### Lo que esto deja pendiente

Volver a medir el reservado con el instrumento arreglado. §24 está limitado por el presupuesto y
eso ahora está medido, no supuesto; es la misma situación de §19, donde la medición no se podía
hacer antes de arreglar el `--tope`. El número de §24 **no se retira**: queda como lo que se
midió con tope 4000, y al lado va el que salga con 10000. Lo que cambia es que esta vez el umbral
está elegido de antemano.

---

### §26 — El reservado completo: el número baja, §25 se equivocó al declararlo robusto, y la plataforma no es determinista (2026-11-03)

Con el instrumento arreglado —tope 10000 medido en §25, reintento de códigos transitorios— el
reservado entero se midió sin perder un registro: **147 de 147, cero ilegibles**. Siete
reintentos por códigos transitorios, o sea siete registros (5%) que con el instrumento de §24 se
habrían perdido sin nombre.

Esta es la corrida que hay que citar. §24 y §25 quedan porque la diferencia entre las tres es el
instrumento, y eso es la mitad de lo que hay que saber para leer el número.

#### El número definitivo

| | §24 (tope 4000, n=108) | **§26 (tope 10000, n=147)** |
|---|---|---|
| ilegibles | 27% | **0%** |
| exactitud | 84% [76% · 90%] | **79% [72% · 85%]** |
| clase mayoritaria | 56% | 51% [43% · 59%] |
| TPR | 88% [75% · 94%] | **86% [76% · 92%]** |
| FPR | 18% [11% · 30%] | **28% [19% · 39%]** |
| AUC | 0,88 | **0,83** |

> **Los IC de esta tabla suponen independencia y los 147 registros no la tienen: son de 15
> tareas. Corregidos en §28** — agrupando por tarea, el FPR es 28% **[14% · 43%]**, la
> exactitud [70% · 88%] y la AUC [0,73 · 0,92]. Los puntos no cambian; los intervalos se
> ensanchan y ninguna conclusión se cae.

#### Por qué bajó, y es el resultado más importante de la sección

Los 39 registros que el tope se comía **eran exactamente los que el juez no sabe juzgar.** Medidos
ahora, con todos contestando:

| | n | exactitud | TPR | FPR | AUC |
|---|---|---|---|---|---|
| los 39 que antes se cortaban | 39 | 62% [46% · 75%] | 79% [60% · 91%] | **67% [42% · 85%]** | **0,59** |
| los otros 108 | 108 | 85% [77% · 91%] | 90% [78% · 95%] | 18% [11% · 30%] | 0,87 |

Fisher exacto bilateral sobre acertar × grupo: **p = 0,005**.

Un FPR de 67% con AUC 0,59 es, en ese subgrupo, casi no descartar nada. O sea que el corte de §24
no era ruido: era **censura informativa**, y de la peor clase —se comía justo la subpoblación sin
señal—. §24 lo marcó como riesgo y dijo que la dirección «no se puede afirmar» con p=0,092 sobre
la asimetría de clases. Era el riesgo correcto y la conclusión prudente.

#### Lo que §25 concluyó mal, y el error es mío y es de método

§25 corrió el control del artefacto contra entrenamiento y concluyó: «**No bajó.** La magnitud de
§24 no venía del corte». Bajó. FPR 18% → 28%.

El error no fue medir en entrenamiento: eso estaba bien y sigue estándolo. El error fue **leer un
control sin poder como si fuera evidencia de ausencia**. El FPR de entrenamiento venía con IC
[6% · 39%] sobre 18 negativos. Un intervalo que contiene al 18% y al 28% a la vez **no puede
distinguirlos**, y yo escribí «no bajó» de un instrumento que no podía decirme si había bajado.
Es exactamente el defecto que este documento persigue desde §1 —un chequeo que ante lo que no
previó deja de mirar en vez de fallar— aplicado a mi propio razonamiento, con el IC impreso al
lado y todo.

La regla que queda: **un control de artefacto necesita su poder declarado.** Si el IC del control
contiene la magnitud del artefacto que se busca, el control no se pasó: no se corrió.

#### El umbral pre-registrado: el TPR clavado, el FPR no

§25 eligió −9 sobre entrenamiento y predijo **TPR ≈ 95% con FPR ≈ 22%**. Salió:

| | predicho (entrenamiento, n=37) | realizado (reservado, n=147) |
|---|---|---|
| TPR | 95% | **94%** |
| FPR | 22% [9% · 45%] | **33% [24% · 45%]** |

El TPR clavado. El FPR 11 puntos arriba, aunque **adentro del IC pre-registrado**. No es que la
pre-registración falló: es que con 18 negativos no alcanza para pre-registrar un umbral con
precisión útil. La pre-registración sirvió igual, y para lo que sirve: el 33% es un número
honesto porque estaba escrito antes, y si lo hubiera elegido después habría publicado el −9 con
su mejor cara.

#### Un resultado negativo: los tokens no sirven de señal de abstención

Si el juez falla justo donde razona de más, el gasto de tokens —que se conoce ANTES de actuar
sobre el veredicto, así que es desplegable— debería servirle para abstenerse. Probado, y **no
paga**:

| corte de abstención | gate corre | de lo que tira, era basura | bueno perdido |
|---|---|---|---|
| sin abstención | 56% | 84% | 14% |
| 6000 tokens | 57% | 84% | 13% |
| 4000 tokens | 59% | 86% | 11% |
| 2000 tokens | 62% | 87% | 9% |

Nada que valga el cambio. Y la razón es instructiva: **en un pre-filtro, el FPR alto de un
subgrupo sólo cuesta cómputo**, porque el gate lo rechaza igual. Abstenerse ahí mueve basura al
gate, que ya la iba a atrapar. Lo único que el subgrupo difícil cuesta de verdad es su TPR de 79%,
y abstenerse no lo recupera: lo manda al gate, que es lo mismo que pasarlo.

#### Y la plataforma no es determinista a temperatura 0

Esto afecta a todo lo medido en este documento, así que va con su número. Con `temperature: 0` y
el mismo prompt, los 39 registros que se cortaron con tope 4000 deberían volver a gastar más de
4000. Gastan **23 de 39**. Y 14 de los 108 que antes contestaron dentro de 4000 ahora se pasan.

Sobre los 108 comparables: el **veredicto coincide en 99%** [95% · 100%], la **puntuación exacta
en 86%** [78% · 91%]. O sea que el veredicto es estable y la confianza no, y el gasto de tokens
se mueve mucho. Dos consecuencias:

- Una corrida de estas no es reproducible al registro, sólo a la distribución. Cualquier
  comparación de dos corridas tiene que leerse con eso.
- Explica en parte por qué los tokens no sirven de señal: son una medida ruidosa de la dificultad,
  aunque el split por run-1 tenga p=0,005, así que la dificultad que marcan es real y la medida no.

#### El veredicto operativo, con los números completos

| | valor | IC95 |
|---|---|---|
| el gate corre en | 83/147 = 56% | [48% · 64%] |
| trabajo del gate evitado | 64/147 = 44% | [36% · 52%] |
| de lo que tira, era basura | 54/64 = 84% | [74% · 91%] |
| **material bueno perdido** | **10/72 = 14%** | [8% · 24%] |
| contaminación como reemplazo del gate | 21/83 = 25% | [17% · 36%] |

**Como pre-filtro sigue sirviendo, y ahora el número es el del banco entero**: ahorra 44% de las
corridas del gate, 84% de lo que descarta era basura, y cuesta 14% del material bueno. Es peor
que el 37% / 89% / 8% que publicó §24, y es el que vale.

> **Este veredicto operativo está RETIRADO. Ver §27, del día siguiente.** Nunca medí qué cuesta
> una corrida del gate: son ~20 s locales, contra 118 s de plataforma que cuesta el juez. El
> pre-filtro es seis veces más caro que lo que ahorra, y además saltear el gate no produce
> etiqueta, así que en una fábrica de dataset encoge su propio producto. Los NÚMEROS de esta
> sección no se retiran: son la línea de base de un 27B sin afinar, que es para lo que sirven.

**Como reemplazo del gate no sirve**, y con menos margen que antes: 25% de lo que etiquetaría como
aceptado es basura. Uno de cada cuatro.

---

### §27 — Medí bien el FPR del pre-filtro y nunca medí qué cuesta lo que ahorra: no tiene caso de uso (2026-11-04)

§24, §25 y §26 miden al juez puntual con la métrica correcta —FPR a TPR fijo— y cierran con un
veredicto operativo: «como pre-filtro sirve: ahorra 44% de las corridas del gate». Las tres veces
escribí eso sin medir **cuánto cuesta una corrida del gate**. La métrica estaba bien elegida; la
cosa de la que era métrica nunca se chequeó.

#### Lo que cuesta cada lado

| | costo |
|---|---|
| fase de tests del gate, por intento (proyecto de juguete, dos comportamientos que rechazan) | **~20 s locales** |
| una llamada al juez (§26: 147 registros en 4h50) | **118 s de plataforma** |

**Seis veces más caro que lo que ahorra.** Y el gate es local: CPU de esta máquina, no GPU de la
plataforma.

Hay un detalle que lo decide y que está en el propio gate: **una sola llamada al agente escribe el
test Y la implementación de referencia** —«Hacé la tarea completa: la implementación Y sus tests,
las dos cosas con la herramienta write»—. O sea que cuando ya hay un test para juzgar, la parte
cara está pagada. Lo que queda es correr la suite sin implementación, con implementación, con
mutantes y el brazo nulo: todo local. Un pre-filtro acá cambia 118 s de plataforma por 20 s de CPU
propia.

Para que pagara, la verificación del gate tendría que costar más de **~118 s por intento**, o sea
una suite de proyecto unas seis veces más lenta que la del juguete. Es posible y no es lo que
tenemos.

#### Y lo que sigue es peor que la aritmética

**La salida del gate no es un booleano: es el motivo.** §23 lo midió y lo arregló —el campo
`dimensiones` dice qué paso rechazó, y eso es justo lo que un juez entrenado necesita—. Un
pre-filtro que saltea el gate no produce etiqueta, así que ese registro **no entra al dataset**.

En una fábrica de dataset, un pre-filtro que descarta intentos antes del gate **encoge su propio
producto**. Y descarta con un FPR de 28%: el 14% de material bueno que §26 contabiliza como «costo»
no es sólo un test perdido, es un registro etiquetado que nunca existe.

#### Entonces para qué sirvió medirlo

Para lo que en realidad era, y no es poco: **una línea de base**. El proyecto es una fábrica de
dataset para afinar un modelo chico. El número que hace falta no es «¿despliego este juez?», es
«¿cuánto saca un 27B sin afinar, para saber qué tiene que superar el afinado?». Esa respuesta está
medida contra un reservado sellado, con sus controles, y es:

> **AUC 0,83 · exactitud 79% · TPR 86% con FPR 28% · y FPR 67% con AUC 0,59 en el 27% del banco
> donde razona de más.**

Una línea de base no necesita caso de uso ni justificación económica. Lo que necesita es estar
medida sin trampa, y lo está: tasa base declarada, ilegibles aparte, aceptar-todo como referencia,
criterios tontos en el azar, umbral pre-registrado, y el reservado sellado que nunca se usó para
elegir nada.

#### El defecto, nombrado

Es de la misma familia que todo este documento, pero en un nivel donde no lo había buscado: no
fue un chequeo que dejó de mirar, fue **una métrica correcta aplicada a una pregunta que nadie
verificó que fuera la pregunta**. El FPR a TPR fijo es la métrica buena para un pre-filtro. Que
acá hiciera falta un pre-filtro era una suposición, y la arrastré tres secciones porque cada
sección heredó el encuadre de la anterior en vez de volver a preguntarlo.

La regla que queda, al lado de la de §26 sobre el poder de los controles: **antes de medir qué
tan bien funciona algo, medir qué cuesta el trabajo que ese algo evita.** Si no se midió, el
veredicto operativo no es un veredicto: es una suposición con un intervalo de confianza al lado.

Los veredictos operativos de §24 y §26 quedan retirados en esa parte. Los números de §26 no: son
la línea de base, y no cambian.

---

### §28 — Los intervalos publicados suponían una independencia que no hay (2026-11-08)

§24 a §27 informaron intervalos de Wilson sobre los 147 registros del reservado. Wilson supone
147 observaciones independientes y **no lo son**: salen de **15 tareas** y **7 corridas**, y dos
registros de la misma tarea comparten el enunciado. El n efectivo está más cerca de 15 que de
147, así que esos intervalos afirman una precisión que no se midió.

No es una objeción teórica traída de afuera: es la misma falla que §26 ya cobró una vez, cuando
leí un control sin poder como evidencia de ausencia. Un intervalo demasiado angosto no falla.
Da un número mejor.

#### Los intervalos corregidos

Bootstrap percentil remuestreando **tareas** con reemplazo, 10000 repeticiones, semilla 1,
recalculado sobre el crudo ya medido —sin volver a preguntarle nada al modelo—:

| | punto | Wilson (lo publicado) | **agrupado por tarea** |
|---|---|---|---|
| exactitud | 79% | [72% · 85%] | **[70% · 88%]** |
| TPR | 86% | [76% · 92%] | **[78% · 93%]** |
| FPR | 28% | [19% · 39%] | **[14% · 43%]** |
| AUC | 0,83 | — | **[0,73 · 0,92]** |

El ensanchamiento es real y moderado: el FPR pasa de ±10 puntos a ±14. **Ninguna conclusión
cambia** —la exactitud sigue despegada de la clase mayoritaria (51%) y el FPR sigue lejos del
100% de «no descartar nada»—, pero el número que hay que citar es **28% [14% · 43%]**.

#### Y agrupar por corrida sale MÁS ANGOSTO, que es una trampa

Las corridas son la unidad con la que se particionó el banco, así que generalizar a una corrida
nueva es la afirmación que de verdad interesa. Agrupando por corrida (K=7) el FPR sale
[19% · 38%], **más angosto que Wilson**. Eso no es precisión: con K chico el bootstrap de
clusters toma el contenido de cada cluster como FIJO, y la varianza entre clusters está estimada
con siete puntos. El instrumento lo declara arriba del número, no abajo:

> ⚠ sólo 7 grupos: la varianza ENTRE grupos está mal estimada y el intervalo puede salir
> ENGAÑOSAMENTE ANGOSTO. Indicativo, no intervalo.

#### El hallazgo central de §26 sobrevive

La diferencia entre el subgrupo que el tope censuraba y el resto, agrupada por tarea:

| | punto | IC95 agrupado |
|---|---|---|
| exactitud, a favor del resto | +24 puntos | **[+4 · +42]** |
| AUC, a favor del resto | +0,28 | **[+0,14 · +0,43]** |

Ninguna cruza el cero. La censura informativa sigue afirmada con el agrupamiento puesto.

#### Lo que esto le dice al paper

El límite de este banco no es 147: es **15 tareas y 7 familias**. Cualquier afirmación que
dependa de la precisión —un umbral afinado, una comparación entre dos modelos que difieran por
pocos puntos— no la soporta. Lo que sí soporta son los efectos grandes: la censura informativa
(+24 puntos, +0,28 de AUC), y la distancia a la clase mayoritaria. Para lo demás hace falta más
familias, no más registros de las mismas.

#### El instrumento

`scripts/ic_agrupado.py` recalcula sobre cualquier crudo del juez; `bootstrap_agrupado` vive en
`_estadistica.py` al lado de Wilson y de Fisher. Doce mutaciones corridas entre los dos, doce
cazadas. La que importa es la primera: **remuestrear observaciones en vez de clusters** devuelve
exactamente el intervalo angosto de Wilson, o sea el defecto que esta sección arregla, y ningún
test que mirara sólo el orden de los números lo habría notado.

---

### §29 — El hallazgo de §26 es trabajo CONCURRENTE, no primero; y las cotas que lo habrían avisado gratis (2026-11-09)

Antes de gastar horas de GPU en replicar §26 con más modelos, fui a ver si el resultado ya
estaba publicado. Está.

#### La deuda de honestidad, primero

**Vidal, S. (2026). «Cut short: output limits remove an LLM judge's rejections first.»**
Zenodo, 1 de noviembre de 2026, [10.5281/zenodo.23865213](https://zenodo.org/records/23865213).
Ocho días antes de que escribiéramos §26. Mide lo mismo sobre 8 pares juez×tarea: el tope de
salida trunca los rechazos antes que las aceptaciones, descartarlos es insesgado sólo bajo MCAR
y no lo son. Audita 30 papers de ACL/EMNLP —2 de 30 reportan el `max_tokens` del juez— y los
defaults de 10 herramientas de evaluación.

Y el principio de fondo tiene cuarenta años, en medicina y no en NLP: **Begg, Greenes &
Iglewicz (1986)**, *The influence of uninterpretability on the assessment of diagnostic tests*,
J Chronic Dis 39(8):575–584. «Ignorar resultados ilegibles sesga cuando su causa se relaciona
con el resultado que el test habría dado». **STARD 2015** ítems 15–16 ya obliga a reportarlo.

Así que §24 a §28 quedan como lo que son: una **réplica independiente y concurrente** de un
resultado que otra persona publicó primero, sobre un sistema distinto. No es poco y no es lo que
creíamos. Lo escribo acá y no en una nota al pie porque el documento entero existe para no
dejar que un número se lea mejor de lo que es, y eso vale también para la originalidad.

Verificado por mí contra el registro de Zenodo, no sólo por el agente que lo trajo. El p=0,005
de los dos trabajos es coincidencia de redondeos: el suyo es hipergeométrico de una cola sobre
36 ítems, el nuestro Fisher a dos colas sobre [[24,15],[92,16]].

#### Lo que sigue siendo nuestro, y hay que decirlo con la misma precisión

**El mecanismo es distinto.** El de Vidal es «los rechazos son más largos» —censura por clase—.
El nuestro es «la censura se concentra donde el juez no tiene señal discriminativa», AUC 0,59
contra 0,87. Eso no está publicado. Y el detalle que lo vuelve relevante: el mecanismo de ella
**falla justo en modelos de razonamiento** —se sostuvo en 1 de 4 jueces en una tarea y en 0 de
11 en JudgeBench—, que es exactamente dónde vive el nuestro.

**El artefacto del parser no está en ninguna parte.** Un parser que toma el último veredicto de
una respuesta truncada devuelve un veredicto que el modelo nunca emitió, y la firma es
**especificidad aparentemente perfecta**. Hay folclore de ingeniería en issues y PRs públicos,
pero nadie lo midió ni publicó la firma. Vidal documenta el caso benigno —su parser devuelve
«sin veredicto» correctamente—; el nuestro es el maligno, y nos pasó en campo.

#### La descomposición: mezcla, no comportamiento

La objeción obvia a §26 es que el corrimiento 18%→28% sea un cambio de prevalencia en el
conjunto puntuado y no del juez. Medido:

| | FPR |
|---|---|
| los 108 visibles, con tope 4000 (§24) | 18% [11% · 30%] |
| **los mismos 108, con tope 10000** | **18% [11% · 30%]** |
| los 39 que el tope censuraba | **67% [42% · 85%]** |
| los 147 completos (§26) | 28% [19% · 39%] |

**El comportamiento sobre los mismos ítems no se movió.** Todo el corrimiento viene de reponer
el subgrupo. O sea que sí es mezcla —y la mezcla ES el mecanismo, no un confundidor de él—. Lo
que sería un problema es que subir el tope cambiara CÓMO juzga, y eso está controlado aparte:
99% de acuerdo de veredicto en los 108 comparables (§26).

#### Las cotas que lo habrían avisado sin gastar nada

Contando los censurados como todos errados y como todos acertados, al estilo del
«intention-to-diagnose» de la literatura diagnóstica:

| | FPR |
|---|---|
| lo que §24 informó, descartando los censurados | 18% [11% · 30%] |
| si NINGUNO de los censurados hubiera pasado | 15% [8% · 24%] |
| si TODOS hubieran pasado | 35% [25% · 46%] |
| **el valor real, medido con el tope arreglado** | **28% [19% · 39%]** |

La cota honesta de §24 era **[15% · 35%]**, no el 18% puntual. El valor real cae adentro. Y un
intervalo de ese ancho **ya habría dicho «esto no está medido»**, sin las cuatro horas de GPU
que costó la recorrida.

Esa es la recomendación accionable y no cuesta nada: **cuando haya respuestas ilegibles, informar
la métrica con los censurados contados en los dos extremos, al lado del valor que los descarta.**
Si la cota es ancha, el número no está medido y se sabe ese mismo día.

#### El confundidor que sigue abierto, y por qué no se puede cerrar acá

¿El AUC cae porque la censura selecciona ítems donde el juez no discrimina, o porque selecciona
ítems **difíciles**, donde cualquier juez discrimina peor? Lo intenté con los datos que hay:

- El proxy obvio —cuántos pasos del gate pasó el test— **es circular**: tiene AUC **1,00** contra
  el veredicto del gate. No es una medida de dificultad, es la etiqueta. Lo vi porque imprimí el
  chequeo de sanidad; sin él, el estrato habría devuelto un número con cara de control.
- El largo del test **no predice ser censurado** (AUC 0,50) ni el veredicto (0,41). Así que
  «largo = difícil = censurado» no es el mecanismo: lo que se alarga es el razonamiento, no el
  ítem. Es una pieza a favor, pero no cierra la pregunta.

**No se puede cerrar con un solo juez.** La forma limpia es un segundo juez: si los ítems que el
juez A no llega a contestar le resultan fáciles al juez B, es pérdida de señal específica del
juez y no dificultad del ítem. Eso convierte la replicación multi-modelo de «linda para
generalizar» en **el control del confundidor**: deja de ser opcional.

#### Lo que esto cambia del plan

Y §28 ya dijo que este banco no da para más: su límite no es 147 registros, son **15 tareas y 7
familias**. Más registros de las mismas familias no compran nada. Hace falta otro banco, y el
elegido es **TestEval** (210 problemas de LeetCode en Python, MIT, un `.jsonl` de 506 KB), porque
es isomorfo a nuestro gate campo por campo: trae enunciado, implementación de referencia, y
`class Solution` + `func_name` como contrato, así que el cuarto criterio —archivo y clase
correctos— existe nativo en vez de inventado. Python puro, sin Docker. Descartados SWE-bench
(≥120 GB de disco), TestGenEval (CC-BY-NC, no comercial) y Defects4J (Java 11 y Perl).

Dos trampas ya encontradas montándolo, que valen para nuestro propio gate: hace falta **timeout
por corrida** —un mutante entró en bucle infinito— y el mutation score hay que **condicionarlo a
que el test pase con la referencia**, porque un test que errora contra todo «mata» todos los
mutantes y el criterio miente justo donde más importa.

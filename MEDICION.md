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

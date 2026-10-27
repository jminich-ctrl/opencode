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
| T01b | **corrigió el patch** a `patch('src.servicios.s1.leer1')` |
| T02b, T04b | resolvieron la tarea **sin mockear nada**: el test usa `leer1()` de verdad |

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

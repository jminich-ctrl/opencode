# Auditoría del método — 2026-10-20

Cinco auditores en paralelo. Esta vez el eje no son las FORMAS de defecto (eso fue el
2026-10-19, en `AUDITORIA-20261019.md`) sino **la genericidad**: qué del método sigue atado a
los dos proyectos de ejemplo, que son el instrumento y no el producto.

Todo lo que sigue está verificado contra el código o reproducido con un `PLAN.md` mínimo.
Los laboratorios quedaron en el scratchpad de la sesión.

## El hallazgo que explica a los demás

**La plantilla no es la fuente de verdad, y cada ejemplo ejercita una mitad distinta del
método.** No es una opinión sobre el diseño: es lo que muestran los datos.

| evidencia | consecuencia |
|---|---|
| `ejemplo-pacman` **no tiene `OBJETIVO.md`**: `cobertura.py` sale 1 y `correr-todo.sh` aborta en el preflight | el pacman **nunca se corrió de punta a punta** con la entrada principal del método |
| `ejemplo-clasificados` **no tiene `smoke.sh`**, que `pre-deploy.sh` exige con rojo | su **G4 no puede dar verde nunca** |
| **ninguno de los dos gates declara `CODIGO`** (0 menciones; la plantilla tiene 7) | los caminos de la plantilla que dependen de `CODIGO` —pasos 3 y 4— **no los ejercita nadie** |
| las etapas declaradas de `ejemplo-pacman/PLAN.md:93-97` nombran sólo las 8 tareas ya hechas | `correr-plan.sh` sobre pacman correría esas y **nunca** T09–T17, T40, T41 |
| el encabezado de `plantillas/gate.sh` promete «cuatro líneas ADAPTAR» y enumera dos que se mudaron a `correr-suite.sh` | un proyecto nuevo adapta cuatro cosas de siete |

Los ~25 hallazgos de abajo son síntomas de eso. Arreglarlos uno por uno sin tocar la causa
los va a reproducir en el próximo proyecto.

## Tier A — conducta equivocada en silencio

| # | hallazgo | evidencia |
|---|---|---|
| A1 | **Las etapas DECLARADAS no las valida nadie.** `correr-plan.sh` las usa textuales y nunca llama a `_etapas.py`; `validar-plan.py` sólo borra las mal formadas. No se cruzan dependencias, choques de archivo, estado ni cobertura de pendientes | reproducido: dos tareas sobre el mismo archivo en la misma etapa, una pendiente nunca ejecutada, y la corrida cierra en «Todas las etapas en verde» |
| A2 | **Cuanto mejor formado el plan, menos se lo revisa**: formato incorrecto → cae a la deducción (que chequea); formato correcto → se ejecuta a ciegas | corolario de A1 |
| A3 | **Dependencia circular**: `validar-plan.py` la acepta, `_etapas.py` la detecta pero sale 1 con stdout parcial, y `correr-plan.sh` compara el rc sólo con 2 | reproducido. Y si TODAS las pendientes están en el ciclo: stdout vacío → «✓ Todas las tareas están marcadas como hechas», **rc 0** |
| A4 | **El choque de archivo se compara por string exacto**, y `validar-plan.py` bendice abreviaturas que el deductor no resuelve (`laberinto.py` vs `src/pacman/laberinto.py`), más directorios vs archivos y tokens sin `/` ni `.` | reproducido: tres pares en una sola etapa. El caso del directorio ya está en `ejemplo-clasificados/PLAN.md:70` |
| A5 | **Columna «Archivos» vacía**: ni se cruza contra el archivo de tarea ni entra en la regla del choque | reproducido |
| A6 | **Un título de tarea de UNA palabra desvía la ruta del test.** Dos `sed` leen la tabla de tests y matchean la fila de TAREAS: devuelven `Movimiento` como archivo y `T01` como clase | reproducido por dos auditores y por mí. Nombres como `Favoritos` o `Búsqueda` son los primeros que escribe cualquiera |
| A7 | **`cobertura.py` da verde con un requisito mencionado para EXCLUIRLO**: «sin favoritos, que quedan fuera» cuenta como cobertura. `coherencia.py` se defiende de esto y `cobertura.py` no | reproducido: dos tercios del encargo sin tareas, G0 verde |
| A8 | **Sin sección `## Requisitos`, `cobertura.py` sale 0**: indistinguible de «cubre todo» | verificado |
| A9 | **`correr-plan.sh <n>` sigue tomando un índice sin guardia.** La guardia que nació del salteo de T05 existe sólo en `correr-todo.sh` | reproducido sobre el plan real: `DESDE=2` saltea T05a sin un aviso, y T05b/T05c corren contra un archivo que no existe |
| A10 | **El `grep` del TODO no usaba `$ARG_TODO`**: el acote que el comentario describe no existía, en las tres copias | **ya arreglado**, con test de conducta |

## Tier B — genericidad: qué asume el método

| # | hallazgo |
|---|---|
| B1 | **El paso 4 revierte los tests junto con la implementación** si viven en el mismo árbol (`internal/x/x_test.go`, `#[cfg(test)]` en `lib.rs`): rojo permanente que ningún agente puede arreglar |
| B2 | **El veredicto de tests exige que la línea de falla contenga la ruta del archivo.** `go test` emite `--- FAIL: TestX` y `FAIL\tpkg`: ninguna contiene la ruta → falso VERDE, tarea integrada sin implementación. El contrato «cada línea debe contener la ruta declarada» no está escrito en ninguna parte |
| B3 | **El paso 5 da verde silencioso sin verificar nada** cuando no hay módulos Python (`·` en vez de `⊘`, rc 0), y afirma «dependencias en una sola dirección» con 0% de cobertura del mapeo |
| B4 | **`coherencia.py` bloquea la corrida entera con una lista de terceros de siete nombres** escrita a mano, cuando `_imports.py` ya lee los manifiestos. Un proyecto con Flask o `requests` no arranca, y el mensaje acusa al plan |
| B5 | **El layout de dos mitades está cableado como `backend`/`frontend`**: con `api/` y `web/`, un `FALTA_CORREDOR` de una mitad reprueba a todas las tareas |
| B6 | **Los manifiestos se buscan a profundidad 1 y se instala sólo el primero** (`head -1`): un monorepo con dos servicios Python instala uno, y el otro falla con `ModuleNotFoundError` atribuido al agente |
| B7 | **G4 reinventa el corredor** (`unittest discover` en vez de `correr-suite.sh`) y pierde el contrato de códigos de salida: rojo con el diagnóstico equivocado, o verde con cero tests en Python < 3.12 |
| B8 | **La suite reservada se busca en `<padre-del-repo>/reservados-<proyecto>` y la plantilla le dice al humano `~/reservados-<proyecto>`**: coinciden sólo porque los ejemplos viven en `~/metodo-agentes` |
| B9 | **`CODIGO` es un directorio en el gate y una lista con comas en el resto del método** |
| B10 | **`.gitignore` es declaración obligatoria sin plantilla**, y el `printf` de `EMPEZAR.md` omite `.venv`: siguiendo la doc al pie de la letra, `integrar.sh` se niega por `?? .venv/` |
| B11 | **Cuatro parsers para `Archivo: \`ruta\`, clase \`Clase\`.`**, dos con huecos: `escribir-tests.sh` ancla en `tests/` y los `replanificar*` anclan en `Archivo:`. El segundo le pasa al arquitecto una afirmación FALSA sobre qué falló |
| B12 | **El orden de las tablas cambia el significado del plan**: con la tabla de tests antes, `marcar_hecha_y_limpiar` no marca el Estado y la tarea se relanza para siempre. Y los `sed` de A6 tienen la sensibilidad inversa |
| B13 | **`--arreglar` no puede deduplicar las filas de los planes reales**: su regex exige que el Estado sea un solo token, y los dos planes usan `✅ hecha` |
| B14 | `**Prohibido tocar:**` y `**Modelo:**` **no los lee ningún script**: una prohibición que el paso 2 no verifica |
| B15 | El paso 6 (suite reservada) sólo existe si el proyecto es Python+unittest; `METODO.md` afirma que «nadie más sabe invocar un corredor» y el paso 6 lo invoca |

## Tier C — lo que rompieron los ~60 commits del 2026-10-19

El eje de este auditor: aplicar las cinco formas de defecto conocidas al trabajo más nuevo y
menos probado. **Cuatro de los chequeos que esos commits introdujeron o acotaron no podían
fallar**, y dos están en el mismo archivo y el mismo commit — el que `AUDITORIA-20261019.md`
anota como «acoté un chequeo demasiado ancho y lo volví demasiado angosto». La estrechez
quedó, por los dos lados que no se probaron.

| # | hallazgo | evidencia | estado |
|---|---|---|---|
| C1 | **`git cat-file -e "$base:$ruta"` resuelve desde la raíz del REPO, no desde el cwd**, así que el acote al diff de `_suprimidas.py` no funcionaba en ningún proyecto que viva en un subdirectorio — o sea en los dos ejemplos y en cualquier monorepo. `lineas_cambiadas` devolvía `None` siempre | medido con el árbol limpio: `BASE=HEAD _suprimidas.py src/pacman/render.py` daba **rc 1 sobre un archivo idéntico a HEAD**. Las tres `except: pass` de curses seguían reprobando a T07, T08, T11 y T12, que es el defecto que el acote venía a cerrar. El gate hace esto bien dos pasos más abajo, con el comentario que explica el mecanismo | **arreglado**, con cadáver |
| C2 | **El mismo acote volvía el chequeo decorativo en modo integración**: los tres gates pasaban `BASE` en los DOS modos aunque el comentario dice «en modo tarea». En el tronco `BASE_REF` es HEAD y el árbol está limpio ⇒ `tocadas` = conjunto VACÍO (que no es `None`) ⇒ se filtraban TODOS los hallazgos | al arreglarlo, el tronco del pacman salió **rojo en el acto** con las tres de curses — el chequeo encontró lo que existe para encontrar en la primera corrida en que pudo fallar. Se marcaron `# best-effort`, que es la salida legítima que el método provee | **arreglado**, con cadáver |
| C3 | **Y la mitad que faltaba del acote**: el hallazgo se registraba en `nodo.lineno` y el filtro compara contra las líneas que el cambio tocó. Quien reemplaza el cuerpo de un `except` que ya existía por `pass`, o agrega `@skip` arriba de un test que ya estaba, **cambia otra línea** y pasaba sin que nada se imprimiera | las dos formas reproducidas. Es la forma más común de apagar una señal en código existente | **arreglado**: el hallazgo lleva su TRAMO de líneas |
| C4 | **`expone()` de `_imports.py` enumeraba cuatro maneras de definir un nombre** y todo lo demás le era invisible: falso ROJO sobre código que Python corre | medido una por una: `DEBUG, VERBOSE = False, True`, `with … as f: HANDLE = …`, `for`, `match`, walrus. Y el mensaje manda a buscar el nombre donde sí está, así que la tarea quema sus reintentos contra un rojo que sólo se apaga reescribiendo una asignación correcta | **arreglado**: por ALCANCE (contexto Store) y no por lista de formas |
| C5 | **`_imports.py` era el único eslabón de la cadena nueva que fallaba ABIERTO**: `if [ -n "$(aux_del_metodo _imports.py)" ]` sin `else`, así que el paso no imprimía nada, no sumaba a `FALLOS` ni a `VACIOS`, y el veredicto salía «GATE VERDE» limpio. El mensaje del commit afirmaba lo contrario; era cierto para su hermano | cualquier gate corrido sin `$AGENTES` exportada (CI, cron, una shell nueva) perdía el chequeo en silencio, y ese mismo commit borró la copia local de la plantilla | **arreglado**, con cadáver de conducta |
| C6 | **`huella_scripts()` enumeraba `*.sh`** y dejaba afuera los diez `.py` que SON el instrumento | editar `_suprimidas.py` o `mutar.py` con el plan en vuelo —que es literalmente lo que hicieron cuatro commits del día— pasaba el guardia de borde de etapa en silencio: la etapa 1 juzgada con un chequeo y la etapa 5 con otro | **arreglado**: todos los archivos del directorio, sin lista de extensiones |
| C7 | **La marca `+sin-commitear` no veía el stage**: `git diff --quiet -- scripts` compara árbol↔índice. Un `git add scripts/` antes de lanzar apagaba la marca | y el modelo que se citó al escribirla (`congelar-banco.sh`) tenía el mismo defecto, así que el arreglo copió el agujero | **arreglado** en los dos |
| C8 | **`estado.sh` se comía un tronco realmente roto**: `en_vuelo` se llenaba si CUALQUIER tarea no-✅ tenía su test presente, y el `grep '✗'` vivía sólo en el `else` | es el estado exacto de clasificados el 2026-10-19: etapa en vuelo **y** T14 con un `get_db_connection` que abortaba la colección entera. El informe decía «por diseño» y el ImportError quedaba invisible | **arreglado**: las fallas se imprimen siempre y el «por diseño» se verifica falla por falla |
| C9 | **El arreglo del hallazgo #5 quedó sólo en clasificados**: `archivos_de_la_tarea` no existe en la plantilla ni en pacman, que siguen deduciendo `IMPL` con un `grep` de prefijo | un proyecto nuevo copiado de la plantilla, con una tarea cuya implementación es un `.scss` o un `.sql`, da `⊘ no hay implementación que revertir` y el gate cierra | pendiente (es C9 = A-tier de genericidad) |
| C10 | `fallas_del_tronco` de `integrar.sh` emitía **dos bloques ordenados por separado** y `comm` exige orden global: con los bloques desordenados sobre-reporta y hace `reset --hard HEAD~1` culpando a una tarea correcta | hoy no se disparaba **por accidente**: el `✗` ordena después del ASCII en este locale | **arreglado**: el `sort -u` envuelve a la función entera. Una garantía incidental no es una garantía |

## Tier D — el aparato de medición: qué miden los números de hoy

| # | hallazgo | evidencia | estado |
|---|---|---|---|
| D1 | **El registro contradecía al gate**: `anotar_intento` recibía `[ -n "$error" ] && echo ERROR || veredicto`, o sea el ruido de la herramienta ANTES del código del gate. El arreglo «el gate primero, siempre» había entrado en el mensaje de CONSOLA y no en el valor que se escribe | T07, T27 y T06 del 2026-10-04 tienen su commit `TNN: gate verde` **al segundo exacto** de una fila `ERROR` — y `cerrar_con_gate` commitea sólo con rc 0, así que el commit prueba el verde. `metricas.sh` las informaba como «nunca llegaron a verde» **y** las descontaba como pérdida de plataforma | **arreglado**: `veredicto_registrado`, que es una función y por eso se puede verificar |
| D2 | **Inválidos del propio método contados como ROJO del modelo**: los primeros intentos de T01, T02 y T03 dicen «falta el corredor de tests — esto es del método», que es el `exit 3` que `correr-suite.sh` declara como «no del código que se juzga». `MEDICION.md` §6.3 ya nombraba esas cinco filas; nadie las leía | el auditor estimó que corregirlo llevaba el 47% a 60% y cambiaba la banda. **Verificado: no.** Al descartar el intento inválido, el que pasa a ser «el primero» de esas tres tareas también es rojo. La dirección era correcta y la magnitud no | **arreglado**; efecto real: 47% → 50% |
| D3 | **Una fila `ERROR` hacía de «primer intento» de su tarea y la marcaba ✗**, tres bloques arriba de donde el propio informe dice «no cuentan contra el modelo» | la misma forma que D2, en una tercera variante. Si no cuenta, no cuenta en ningún lado | **arreglado** |
| D4 | **El 61% del pacman se apoyaba en trabajo humano**: `cerrar-tarea.sh` escribe `modelo=humano` en el MISMO registro y nada lo excluía | sacando sólo T16 (`segundos=0`, `modelo=humano`): 58%. Sacando las cuatro filas no atribuibles a un modelo: **44%**. El único proyecto del repo que «funcionaba» cruzaba el umbral por eso | **arreglado**; pacman: 61% → 44%. **Los dos proyectos caen ahora en la misma banda, «tareas demasiado grandes o criterios flojos»** |
| D5 | **`concurrencia` se medía al CERRAR**: `anotar_intento` corre después del agente y del gate, y su propio comentario dice «vivas al arrancar ésta» | la tanda del 2026-10-19: cuatro tareas arrancadas en 12 segundos, solapadas por completo, con valores 1, 2, 2 y 0 que **decrecen con el orden de finalización**. T28, que compitió con tres durante sus 970 s enteros, quedó anotada como la única serializada | **arreglado**: la mide quien lanza, antes de lanzar |
| D6 | **La mediana de tiempo llevaba el techo del propio vigilante**: 6 de 16 filas eran `ERROR`, 4 con «límite total 1200s» en el motivo. El «máximo 1855s» que se imprimía era un ROJO; el éxito más lento medía 970 s — y es ese número el que `_comun.sh` manda mirar para dimensionar el presupuesto | calibrar un presupuesto con el techo de la propia regla es medirse con la regla | **arreglado**: sin filas inválidas, y una línea «éxito más lento» explícita |
| D7 | **`startswith(actual)` metía `X` y `X+sin-commitear` en el mismo balde**, deshaciendo dos líneas más abajo la distinción que el escritor acababa de crear | — | **arreglado**: igualdad, y `actual` se arma con la marca incluida |
| D8 | **El aviso de comparabilidad vivía dentro de `if len(huellas) > 1`**: con UNA sola huella distinta de la de ahora no se imprimía ni un ⊘ | proyecto nuevo, cinco tareas con el instrumento A, arreglás un script: el número se sigue anunciando como si describiera el instrumento instalado | **arreglado**, y además avisa cuando la huella de ahora **no se puede leer** |
| D9 | **El «número comparable» tomaba la primera fila DENTRO de la huella**, no el primer intento de la tarea: T04b es VERDE con una huella y VERDE otra vez con la siguiente, y la segunda contaba como «verde al primer intento» sobre una tarea ya resuelta | sesgo de truncamiento. Y tres de las seis huellas tienen **una sola tarea**: se imprimía `0/1 al primer intento` como si fuera una tasa | **arreglado**, con el ⊘ de `n=1` que `MEDICION.md` §1 exige |
| D10 | **Numerador y denominador sobre conjuntos distintos** en «nunca llegaron a verde» | dormido: no hay una sola fila `IMPOSIBLE` en 78, o sea que todo ese camino nunca corrió con datos | **arreglado** |
| D11 | **El brazo de control es media moneda y media trinquete, y nunca corrió.** El veredicto exige igualdad estricta sobre el gate, que es la variable de mayor varianza del registro (tasa de verde 0,41): dos corridas difieren con probabilidad ≈48%, **más** que la banda ±2 que el propio comparador descarta por hacer eso al 29%. Y la línea base se AGREGA en cada corrida y se lee con `tail -1`, así que una caída del 87,5% en llamadas a herramientas pasa paso a paso | `.metricas/` no tiene `control-base.csv`: nunca se ejecutó. Y el 0,42 que lo calibra **no es del control** — `comparar-modelos.sh` nunca llama a `anotar_intento`, así que en el registro no hay una sola fila de brazo de control | pendiente |
| D12 | **El comparador arranca sus brazos de HEAD**, donde los tests de la tarea ya pasan, así que lo único no trivial que mide es «escribió un archivo dentro de su alcance». El banco de 16 ítems congelados —que existe justamente para proveer el estado base rojo— **no está cableado a él**: ningún script lee las ramas `item/*` | y `experimentos/README.md` declara el experimento bloqueado con «9 ítems de 30» cuando `git branch | grep -c item/` da **16**. Ningún script cuenta las ramas | pendiente |
| D13 | **`TOOLS` y `DELIB` se invierten con los datos reales**: `TOOLS` cuenta llamadas FALLIDAS y `DELIB` crece con el éxito de las lecturas, y `TOOLS ⊆ DELIB` por construcción | medido sobre tres transcriptos: el que falló 10 de sus 18 llamadas y produjo un ROJO **gana en las dos columnas** contra el que escribió los dos archivos | pendiente |
| D14 | **`ARCHIVOS` da 0 justo para los brazos que ganaron**: `cerrar_con_gate` hace `git add -A` y commitea cuando el gate da verde, y corre antes; la columna mira el árbol de trabajo | demostrado con el pipeline literal: 2 antes del commit del gate, **0** después, mismo trabajo. Y su propio comentario advierte contra «una columna que da el mismo número para quien trabajó y para quien no» | pendiente |
| D15 | **El testigo del banco se elige por fecha entre candidatos que incluyen brazos de comparación**: `git log --all --grep` los enumera, y T16 tiene cuatro commits «gate verde», tres de ellos alcanzables sólo desde `refs/tags/archivo/comparar/T16-3` | lo único que salvó la elección es que el commit integrado es más nuevo por siete minutos. Una comparación de T16 corrida hoy convierte la salida de un modelo bajo evaluación en el **testigo** del ítem | pendiente |
| D16 | **La atribución del rojo de base es constante para los ítems cuya implementación es `__init__.py`**: `mod` = `__init__`, y TODO traceback de ImportError de pytest contiene `importlib/__init__.py:90: in import_module` | `item/ejemplo-clasificados-T01` son tres `__init__.py`. Para esa clase de ítem el rechazo «no atribuible» no puede dispararse nunca | pendiente |
| D17 | **Dos columnas distintas llamadas `instrumento`**: `HEAD:scripts` (del método) y `HEAD:$PROYECTO/scripts` (el corredor del proyecto). Y los 16 recibos del banco llevan la misma cadena literal `+sin-commitear`, así que por `MEDICION.md` §6.7 ninguno es comparable con otro y la huella no puede distinguirlos | **renombrada** a `instrumento-proyecto`; el resto, pendiente |
| D18 | **El registro pierde corridas que el gate cerró en verde**: `cerrar_con_gate` tiene tres llamadores y `comparar-modelos.sh` no anota. T16 tiene cuatro commits «gate verde» y una sola fila | el `Intentos: 20` del pacman es una cota inferior de holgura desconocida | pendiente |
| D19 | **`motivo` truncado a 80 caracteres parte una misma falla en dos**, y el bloque de motivos repetidos filtra `n > 1`, así que la variante cortada desaparece del informe | daño limitado al análisis: la detección de punto muerto usa la huella sin truncar | pendiente |

### El número más confiable que este aparato produce hoy

**La cantidad de intentos por tarea.** Es un conteo y no una tasa, así que no elige
denominador —y D2, D4 y D8 son todos elecciones de denominador—; no interpreta un veredicto,
así que sobrevive a D1; y es la única cifra con un **segundo testigo**: las filas coinciden al
segundo con los commits `TNN: gate verde` de git, verificado en cinco casos. Su sesgo tiene
un solo signo y una causa nombrada (D18, subcuenta).

El que **no** se puede citar bajo ninguna lectura es el de tiempo, y ahora el instrumento lo
dice solo.

### Lo que cambió al arreglar D2/D3/D4

| proyecto | antes | ahora | banda |
|---|---|---|---|
| clasificados | 47% | **50%** | sin cambio: «tareas demasiado grandes o criterios flojos» |
| pacman | 61% → «la descomposición funciona» | **44%** | **cambió**: «tareas demasiado grandes o criterios flojos» |

Los dos proyectos caen ahora en la misma banda. El método no tenía ningún proyecto en el que
la descomposición funcionara; tenía uno en el que el instrumento lo decía.

## Lo que rompí arreglando esto, el mismo día

Siete defectos nuevos, en los arreglos de arriba. Se anotan porque la tasa importa más que
cualquiera de ellos: **arreglar nueve chequeos costó siete defectos**, y seis los atrapó un
control y no una lectura.

| qué | cómo apareció |
|---|---|
| en `metricas.sh` puse `git rev-parse HEAD:scripts` (desde la raíz del repo) junto a un `git diff -- scripts` (relativo al cwd) | **es el mismo defecto que estaba arreglando en `_suprimidas.py`, cometido en el arreglo del otro.** Lo atrapó una relación metamórfica: correr el informe desde la raíz y desde el proyecto |
| en `estado.sh`, `ls "$BASE"/requirements*.txt "$BASE"/*/requirements*.txt` | `ls` sale distinto de cero si CUALQUIER argumento no existe, así que con el manifiesto en `backend/` el chequeo entero daba falso y el `.venv` faltante no se informaba. Lo vi corriéndolo |
| el contador de fallas del tronco contaba las líneas de detalle —y la que sugiere el comando para arreglarlo— como fallas | «14 falla(s)» donde había 8. Lo vi corriéndolo |
| el matcheo del test en vuelo comparaba la RUTA (`tests/test_cosa.py`) contra la notación de MÓDULO que usan los corredores (`tests.test_cosa`) | marcaba como «no explicada» justo a la falla del test en vuelo que la explica: un aviso que grita en cada etapa tests-first. Lo atrapó correrlo sobre un proyecto de juguete |
| el test de forma de C5 usaba una ventana de 400 caracteres y el comentario que explica el arreglo la desbordó | reprobaba al código arreglado. **Duodécima** vez que un chequeo mío confunde «cerca» con «en el mismo bloque»; se reescribió por estructura |
| el fixture `Proyecto` decía «el gate depende de estos dos» y copiaba **uno** | no se notaba porque el paso de `_imports.py` fallaba ABIERTO. Al hacerlo fallar cerrado, **22 tests se pusieron rojos de golpe** y mostraron que el fixture nunca lo había tenido. La prosa decía una cosa y el código otra, en el fixture esta vez |
| tres de mis tests nuevos **pasaban con el defecto puesto** | el metamórfico (los dos `scripts/` limpios coincidían por casualidad), el del paso 4 (un `.scss` dentro de `src/` lo matcheaba el patrón viejo) y el del tramo (quedaba tapado por el defecto del prefijo, que es más ancho). **Los tres los encontró el brazo nulo**, corriendo el test nuevo contra el código viejo |

Y aparte de esos siete, **cuatro tests que ya estaban** se pusieron rojos al arreglar el
código, ninguno por un defecto del arreglo:

| el test | por qué se rompió |
|---|---|
| `test_las_senales_suprimidas_se_acotan_al_diff…` | **pinaba el defecto**: exigía que el gate pasara la base en los DOS modos, porque eso decía el comentario de al lado. El test estaba verde, el chequeo estaba apagado, y arreglarlo lo puso en rojo |
| `test_la_huella_del_instrumento_dice_si_habia_cambios_sin_commitear` | ventana de 600 caracteres, desbordada por el comentario del arreglo |
| `test_las_metricas_declaran_que_mezclan_instrumentos` | ventana de 500, igual |
| `test_correr_todo_avisa_si_saltea_tareas_pendientes` | clavado a la variable interna `SALTEADAS`, que desapareció al mudar la guardia a `_comun.sh` para que los dos runners la compartan |

Los tres últimos son la misma forma que `METODO.md` ya cataloga seis veces —un chequeo sobre
texto que confunde «cerca» con «dentro»— con un agravante nuevo: **se vuelve más probable
cuanto mejor documentado está el arreglo**, y este repo exige documentar cada arreglo con su
cadáver. El chequeo y la convención empujan en direcciones opuestas. Los cuatro se
reescribieron por conducta.

La fila del brazo nulo es la que vale como regla, y no es nueva — es la razón por la que el brazo nulo
está en el método: **un test escrito junto al arreglo tiende a pasar con el arreglo puesto Y
sin él.** Tres de 24, uno de cada ocho. Y el caso del tramo agrega una variante: cuando hay
dos defectos en el mismo camino, el más ancho tapa al otro, así que el brazo nulo hay que
correrlo revirtiendo **de a un arreglo**, no todos juntos.

## Lo que está bien y conviene no romper

Los `⊘` honestos: `mutar.py` nombra el lenguaje como causa, `_suprimidas.py` e `_imports.py`
salen 2 con mensaje, el código 3 de `correr-suite.sh` dice que es del método, `cobertura.py`
es agnóstico de stack. Y `coherencia.py` fue el que mejor resistió: `ast` para los imports,
lista corta con cadáver por entrada, y `lo_que_hace()` descartando el bloque «No entra».

## La pregunta que queda, y es para una persona

Arreglar los 25 es semanas. La causa —la plantilla no es fuente de verdad y ningún proyecto
ejercita el método completo— se arregla de otra forma: **un tercer proyecto de ejemplo, mínimo
y de otro stack, que el método tenga que correr de punta a punta.** Eso convierte cada uno de
los B en un rojo medible en vez de una conjetura, y es la única manera de que la plantilla
deje de ser una aspiración.

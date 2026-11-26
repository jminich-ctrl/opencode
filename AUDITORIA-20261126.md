# Auditoría del 2026-11-26 y plan de refuerzo

Cinco auditorías en paralelo sobre el método entero y sobre el material externo
(`Astro-Han/karpathy-llm-wiki`, `obra/superpowers`, `prime-radiant-inc/superpowers-evals`,
`claude plugin eval`). Lo que sigue está ordenado por **lo que produce un veredicto falso
hoy**, no por tamaño ni por prolijidad.

Cada ítem lleva su cuenta medida. Donde dice **(verificado acá)** lo corrí yo; donde dice
**(de la auditoría)** viene con `archivo:línea` y hay que confirmarlo al implementarlo —no
porque dude, sino porque este repo tiene escrito seis veces que la prosa dice una cosa y el
código otra, y un plan no es una excepción.

---

## Lo que ya se cerró hoy, antes del plan

- **Un dato declarado, un solo lector.** El campo «Archivos que podés tocar» se leía con dos
  parsers, y el paso 2 —el que decide el alcance— tenía una copia literal del pipeline
  inlineada y nunca había llamado a `archivos_de_la_tarea()`. El comentario de esa función
  afirmaba desde octubre que los dos parsers estaban unificados: era cierto del paso 4 y falso
  del paso 2. Un campo duplicado **ensanchaba** el alcance permitido.
- **Un enunciado, un documento.** El paso 0 cuenta los campos de cabecera: duplicado da rojo y
  dice cuál y cuántas veces; dos archivos de tarea para la misma T, rojo; sin archivo de tarea,
  ⊘ con nombre; dos declaraciones de test, ⊘ con nombre, porque el paso 4 usa la primera y el
  gate no puede saber si es la del plan.
- **Y el chequeo que escribí para eso salió vacuo**, el mismo día: preguntaba `-le 1`, y cero
  también es «como máximo una vez», así que un enunciado sin ninguna cabecera imprimía
  `✓ declara cada campo una sola vez` con un testigo que decía «5 campos contados» cuando
  contó cinco ceros. Lo encontró la auditoría, no yo. Cerrado con su brazo nulo y con las
  cuentas reales en el testigo. Los cuatro campos obligatorios están en 53 de 53 enunciados;
  `## Tests` en 36 de 53, así que es opcional y exigirla habría inventado 17 rojos.

---

## Ola 0 — lo que está mintiendo hoy en el camino vivo

Son los que tocan la corrida que no cierra.

1. **`brief_tarea.py` le dice al ejecutor que lo prohibido no existe.** (verificado acá)
   `rutas_de_los_campos()` mete «Archivos que podés tocar» y «Prohibido tocar» en una sola
   lista y la titula «Dónde vive cada cosa, verificado contra el disco». Para T16 de pacman
   imprime `laberinto.py`, `entidades.py`, `render.py`, `__main__.py` como
   «⊘ no existe todavía (si tu tarea lo crea, está bien)» —los cuatro existen y son
   exactamente los que la tarea prohíbe tocar— más cuatro palabras de prosa como rutas:
   `(los`, `ya`, `están`, `escritos)`. **14 de 53 tareas.** Es «le di el cómo y después le dije
   que no», que `plantillas/TAREA.md` documenta medido, cometido por la herramienta que arma el
   prompt. Dos listas, dos títulos.
2. **El relevo no puede replanificar ninguna tarea de pacman.** (de la auditoría)
   `replanificar-relevo.sh:245` parte el archivo con `orig.index("## Tests")`, sin anclar y sin
   manejar la ausencia. **17 de 53** enunciados no tienen esa sección: el `python3` muere con
   `ValueError`, el archivo queda intacto, y el arnés informa `✗ se descarta: no reescribió
   nada` y lo anota en `.metricas`. El agente sí escribió. Veredicto con el sujeto equivocado,
   registrado.
3. **Backticks: cuatro lectores del alcance no los quitan.** (de la auditoría) **17 de 53.**
   `reabrir.sh:117` no saca nada en 17 de 19 tareas de pacman e imprime «no había código
   declarado para sacar»; `auditar-cerradas.sh:61` audita 1 de los 5 módulos de `src/pacman/` y
   su comentario afirma lo contrario. Un solo tokenizador: el del gate.
4. **La cuarta copia del pipeline del alcance, sin el acote.** (de la auditoría)
   `escribir-tests.sh:441` tiene el mismo `sed | tr | grep -oE | sort -u` **sin** el
   `awk 'NR == 1'`, y alimenta su propio chequeo de alcance. El invariante que escribí hoy
   cuenta el pipeline sólo en los tres gates: hay que contarlo en todo el repo.
5. **`coherencia.py` no conoce la convención del `←`.** (de la auditoría) **11 de 53 ya mal
   leídos.** Busca «hecha» en cualquier parte del valor de `**Estado:**`, y la propia
   `plantillas/TAREA.md` pone en esa línea la ayuda `` ← al mergearla: `✅ hecha` ``, que
   contiene las dos marcas. Resultado: una tarea pendiente se lee HECHA y el preflight pasa de
   aviso a ROJO que detiene el plan, acusando a un gate que nunca corrió. Hoy no se ve porque
   el chequeo de esquema no dispara en el árbol actual: es un rojo armado.
6. **Un proyecto nuevo copiado de `plantillas/` da ROJO en su primera tarea.** (verificado acá:
   `plantillas/` no trae `.gitignore`) El paso 1 corre la suite y crea los `.pyc`; el paso 2 los
   levanta como fuera de alcance y el paso 3 como archivos generados. El agente no lo puede
   arreglar: borrarlos no sirve porque el paso 1 los recrea. Cuatro líneas de `.gitignore`.

## Ola 1 — que el paso 4b mida lo que dice medir

Es el hallazgo más grande de la vuelta, y toca la garantía que más citamos.

7. **La mutación mide cobertura, no aserciones.** (de la auditoría, con par discriminante
   corrido) `mutar.py:342` guarda **un** candidato por línea con `setdefault`, y «borrar la
   sentencia» tiene prioridad 0. Sobre el código real de los dos ejemplos: **356 de 387
   candidatos son SBR**; ROR+LCR+AOR juntos cubren **7 de 387 (1,8%)**; y a **74 líneas de 387**
   que tienen un operador presente, SBR les comió el turno. Borrar una asignación revienta la
   línea siguiente, así que cualquier test que *ejecute* la línea mata al mutante sin mirar un
   valor: una suite con `assertIsNotNone(sumar(2,3))` da `✓ TestSuma distingue el cambio`, y el
   mutante `a - b` —que el paso nunca genera— sobrevive.
   Y `hojas_todas_return` apaga toda mutación de operador en una función de un solo `return`
   (`return a + b` → **0 candidatos**), que es la forma de tarea más común del método: ahí los
   dos pasos de «¿distinguen?» se abstienen a la vez y el gate sale verde con dos ⊘.
8. **`gate_publico.py` acepta tests con cero mutantes corridos.** (de la auditoría) `mutar.py`
   tiene la guarda (`probados == 0` → código 2); la réplica pública la perdió. Y su
   `if roto: … pass` tira el resultado: un test que no se puede ni recolectar cobra
   `falla_sin_implementacion: ✓` gratis.
9. **El tercer estado.** Nuestro paso 4 distingue «con código» de «sin código» y el 4b «este
   código» de «este código con un bug». Ninguno distingue **«este código» de «un remiendo de
   síntoma»**. De `superpowers-evals`: el chequeo discriminante se calibra a mano contra los
   tres estados —roto, remiendo, causa raíz— y eso va declarado en el enunciado.

## Ola 2 — que el gate no pueda callarse

10. **El multiconjunto congelado de chequeos esperados.** De `superpowers-evals`: cada escenario
    commitea el conjunto de chequeos que su script *debe* emitir, y una corrida cuyos registros
    no coinciden compone `indeterminate`, nunca `pass`. «Un chequeo que deja de emitirse en
    silencio —el falso verde clásico— deja de ser representable en un veredicto.» Nosotros
    cubrimos el chequeo que **declara** su vacío (`⊘` con nombre, cerrado el 23/11); no cubrimos
    el que **dejó de emitirse**. `plantillas/chequeos-esperados.json`, por modo, y sin
    coincidencia no hay verde.
11. **El paso 5 puede no emitir ningún veredicto.** (de la auditoría) `_arquitectura_motor.py`
    emite tres marcas (`✗`, `⊘`, `·`) y el gate raspa dos: con capas declaradas y cero aristas
    entre capas, el paso entero no deja ni un ✓ ni un ✗ ni un ⊘, y nadie lo nota.
12. **El límite de cobertura, declarado y fijado por un test.** De karpathy-llm-wiki: el
    chequeo declara su conjunto cerrado de candidatos, qué deja afuera **a propósito**, de quién
    es lo que queda afuera, y la regla de dirección: ampliar la cobertura se edita en la prosa
    primero y en el patrón después. Tenemos **una** instancia en 1015 tests. Van ocho bloques
    —uno por etapa— y ocho tests que fijan lo que cada etapa deliberadamente no mira.
13. **`FALTA_CORREDOR`: tres lectores, cero escritores en 2 de 3 proyectos.** (de la auditoría)
    El token es inalcanzable en la plantilla y en pacman, así que un corredor ausente cae en
    «los tests fallan» —el veredicto con el sujeto equivocado que `_corredor.sh` existe para
    evitar— y el gate receta arreglar `fallas()` dos líneas debajo de imprimir la causa real.
14. **Nada en el método detecta un test salteado.** (de la auditoría) `_suprimidas.py` sabe
    buscar `@skip`, pero los tres gates sólo le pasan código de producción. Es la forma más
    barata de poner una suite en verde.
15. **`_imports.py` sólo lee `requirements*.txt`.** (de la auditoría) Un proyecto que declare en
    `pyproject.toml` —el default de cualquier proyecto Python nuevo— recibe
    `✗ importa paquetes que los requirements no declaran`, y el archivo que le manda a editar no
    existe ni está en su alcance.

## Ola 3 — que el método se pueda medir sin 48 minutos

16. **Niveles dentro del nivel barato.** La suite tarda 48 minutos y no tiene un solo
    `skipUnless` ni compuerta: no hay carril rápido. Por eso `pruebas/mutar-gate.py` está
    escrito y no corrido — 74 mutantes × la suite completa ≈ **40 horas**. Un decorador
    `@nivel("centinela")` y un selector en `pruebas/correr.sh` destraban la tasa de captura del
    gate, que es el primer ítem de «lo que sigue faltando» en `PRUEBAS.md`. Con la trampa en el
    mismo commit: el veredicto tiene que decir contra qué nivel se midió.
17. **El chequeo de llamada a herramienta, por comando.** `comparar-modelos.sh:170` es un
    `grep -cE '(Read|Write|Edit|…) '` sobre la prosa del agente, con `2>/dev/null` encima, y la
    línea 187 lo interpreta como veredicto sobre el modelo: **un cero por log vacío es
    indistinguible de un cero por deliberación**. Es la clase que `PRUEBAS.md` entero persigue,
    viviendo en el instrumento con el que elegimos ejecutor. De `superpowers-evals` se copia el
    contrato, no el TypeScript: verbos deterministas sobre la traza (`tool-called`,
    `tool-count <op> <n>`, `tool-before`, `tool-arg-match`), **captura vacía = 127, nunca cero**,
    y código 127 fuera del rango invertible para que un chequeo roto no pase vacuo.
18. **El ítem de elección forzada.** Tres presiones combinadas, rutas reales, A/B/C, encabezado
    «esto es real, elegí y actuá», y un `puntuar_opcion.py` que **declara 127 si no hay letra
    única**, porque «no contestó» y «contestó mal» en la misma celda arruinan la McNemar. La
    primera pregunta a instrumentar es la que ya tenemos: ¿el arquitecto declara el HUECO cuando
    el veredicto trae la causa? Con eso, K=40 en una tarde. **Y el guardia va en el mismo
    commit**: los ítems de presión traen la frase imperativa adentro, y ya dejamos
    `.replan-*.log`, `.diagnostico-*.md` y `.brief-*.md` en el directorio que los agentes leen.

## Ola 4 — que una afirmación nuestra se pueda verificar

19. **Sin columna de corrida no hay join.** (verificado acá) Los tres ids de corrida que
    `MEDICION.md` cita no están en ningún archivo de evidencia —ni en `experimentos/crudo`, ni
    en `.metricas`, ni en `pruebas/registros`, ni en `colabhive`— y `.metricas/intentos.csv`
    tiene 11 columnas y ninguna es la corrida. Es una columna, no un barrido.
20. **El barrido de errores de evidencia, y NO el de fidelidad.** La auditoría portó el chequeo
    de karpathy a nuestros documentos y lo corrió: **~858 candidatos, 600 sospechas al 70% de
    ruido**, porque la mitad son valores derivados que ningún log contiene y la otra mitad son
    comillas angulares usadas como énfasis. Eso no se construye. Lo que sí: la clase «no se
    puede verificar» —no declara fuente, la fuente no resuelve, la fuente está fuera del
    material crudo— que da número chico y ya encontró **11 de 14** secciones `Medición N` sin
    fuente declarada.
21. **El inventario, por ruta y no por nombre.** (verificado acá) **282 de 313** archivos de
    `experimentos/crudo/` no los menciona ningún documento, y la clave por nombre ya está mal:
    `transcripto.log` aparece **22 veces** y `juego.py` **12**. Va con su contracara, la
    disposición explícita «lo miré y no aporta», o el barrido no puede bajar de 282 y por lo
    tanto no se usa. Y gratis, en el camino: **sacar el venv de `experimentos/crudo/testeval/`,
    2014 de 2327 archivos y 30 de 36 MB** de material que no es material y que ya produce
    falsos pases medidos.

---

## Lo que se mira y se descarta, con el motivo

- **El barrido de sospechas de fidelidad**: 600 ítems al 70% de ruido. Un chequeo que marca
  todo es un chequeo que se ignora, y eso ya está escrito en `PRUEBAS.md`.
- **«El código de salida no lleva información; el informe es la interfaz»** (karpathy): es lo
  contrario de nuestro P2, y es el agujero de su diseño —el agente es dueño de lo juzgado y
  puede borrar el número que no logra sostener.
- **Quorum como software**: 1987 archivos, bun + TypeScript + biome, y `uv`/`ruff` encima. Se
  copia el contrato, que son 200 líneas de Python estándar.
- **Los jueces LLM** (`grader: llm`, `baseline`): es nuestro juez puntual con otro nombre, y
  está medido en 41% de acuerdo con 37% que se mueve con el orden. Ese número no lo mueve otro
  juez LLM: lo mueve el chequeo determinista sobre la traza.
- **`claude plugin eval` como sede**: nuestro ejecutor es ColabHive y el gate es bash; meter el
  método adentro mediría al modelo frontera que corre el eval, no al chico que ejecuta. Se copia
  el esquema de grader, no el corredor.
- **Un tag para no correr algo** (`tier: adhoc`): es la puerta de atrás del `pytest-testmon` que
  `AGENTS.md` ya rechaza porque su propósito es NO correr tests.
- **La mitad persuasiva de superpowers**: su sujeto es un modelo frontera al que se le puede
  argumentar.

## Ola 0bis — un proyecto nuevo copia la guía y le falta un paso

El quinto frente barrió la prosa contra el código. Primero una corrección de rótulo: **no
existen hallazgos «G3 a G12»** —`G0..G5` son los gates— y los numerados de code-review son
**A1–A10, B1–B15, C1–C10, D1–D19** del 20/10 más los 1–16 del 19/10. De todos ésos: **44+16
hechos** (casi todos con test de conducta), **54 abiertos**, **19 declarados abiertos que ya
están hechos** —sólo hay que borrar el texto— y 6 que ya no aplican.

Lo que sigue es más barato que todo lo de arriba y rompe a cualquiera que arranque hoy:

22. **`EMPEZAR.md` sigue diciendo «son cuatro líneas ADAPTAR»** y enumera dos que se mudaron a
    `correr-suite.sh`. Son tres en el gate más dos en el corredor, y la guía nunca manda a
    greppear ahí. Es el hallazgo del 20/10: se arregló el encabezado del gate y no la guía, que
    es el único de los dos que un proyecto nuevo lee. `README.md` tiene la cuenta bien, en
    inglés.
23. **El `AGENTS.md` que la guía manda copiar no tiene dos reglas que el gate castiga con
    rojo**: «no dejes TODO ni FIXME» y «no dejes directorios vacíos». Conteo de reglas: raíz 13,
    plantilla 15, los dos ejemplos 12. Y la regla 13 —parcheá donde el nombre SE USA, la que
    salió de dejar tres tareas en punto muerto con la implementación correcta— falta en los dos
    `AGENTS.md` que los agentes de los ejemplos sí leen, mientras `ESTADO.md` afirma que está.
    Es el cadáver que `plantillas/AGENTS.md` tiene escrito en su propia cabecera.
24. **`plantillas/test_reservado.py` manda poner la suite reservada en `~/`** y los tres gates
    la buscan en `../reservados-<proyecto>`. `EMPEZAR.md` ya se arregló; la plantilla no. El paso
    6 —el único que mide lo que el agente no pudo optimizar— queda en ⊘ para siempre sobre una
    suite que la persona sí escribió.
25. **`OPENCODE.md` e `INFRAESTRUCTURA.md` publican `context: 204000` para el ejecutor**; el
    config tiene 32000. Es 6× el valor real y reintroduce el bug que costó tres semanas, dos
    líneas debajo de la advertencia «si mentís para arriba, la sesión muere a mitad de camino».
    4 de 6 filas de la tabla del equipo están mal contra el archivo que dice espejar.
26. **`LEEME.md` lista 10 de 12 plantillas** y le faltan `OBJETIVO.md` —sin el cual
    `planificar.sh` aborta— y `test_reservado.py`. La frase que corrige el defecto («son 12,
    no 3») está pegada a una lista que lo repite con otros números.
27. **El cruce que evita tareas insatisfacibles está anclado al principio de la ruta.**
    `validar-plan.py` usa `patron.match` y el gate `grep -E` sin anclar: el validador bendice
    `backend/tests/test_x.py` en «Archivos que podés tocar» y el paso 0 lo reprueba al tocarlo.
    Ciego para tres de las cinco formas, y falla abierto dos veces sin ⊘.
28. **Las dos columnas con las que comparamos modelos premian al que no cerró.** `ARCHIVOS`
    cuenta el árbol de trabajo, y `cerrar_con_gate` commitea cuando el gate da 0: **da 0
    exactamente para el brazo que ganó**, y el comentario que advierte contra eso está escrito
    arriba del código que lo hace. Y `TOOLS ⊆ DELIB` por construcción —la segunda es `wc -l` del
    mismo flujo del que la primera cuenta marcas— así que «TOOLS alto y DELIB bajo», que es la
    leyenda de la tabla, es aritméticamente imposible.
29. **Dos arreglos reintrodujeron su propio defecto y están marcados «arreglado»**: la guarda de
    `len(celdas) < 5` quedó junto a `count=1`, así que con la tabla de tests primero el `re.sub`
    gasta su única sustitución en la fila de 3 columnas y `PLAN.md` no se marca nunca; y
    `--arreglar` exige un Estado de un solo token cuando los planes reales escriben dos
    (`✅ hecha`), **con un test que usa `pendiente` y por eso pasa con el defecto puesto**.
30. **La cuenta de pasos del gate sigue mal en cuatro lugares**: el encabezado de pacman dice 3,
    el de clasificados 6, `PIPELINE.md` «los seis chequeos», `README.md` «six things». Son ocho
    en las tres copias. Quien adapta desde un ejemplo no sabe que puede reprobar por mutantes
    vivos ni por la suite reservada.

**La forma del arreglo durable ya está probada acá tres veces y no es escribir mejor la prosa:
es un test que cruza dos listas** —como el que cruza lo que el gate filtra contra el
`.gitignore` de la guía, con sus excepciones declaradas y su test de premisa—. Las guardas que
hoy cuidan los `AGENTS.md` y los encabezados comparan **encabezados**, que es el nivel 1 de
verificación que `METODO.md` descarta por escrito: «es leer la prosa otra vez, con más pasos».
Ocho de los nueve «el arreglo vive en un hermano» abiertos son copias de texto, no de código.

## Lo que queda abierto de esta auditoría
- **Ninguna de las olas cambia la decisión de fondo que sigue siendo tuya**: el tope de salida
  del arquitecto (6000, y los gastó razonando sin llegar al veredicto) y declarar
  `Qwen3.6-35B-A3B-NVFP4` en `provider.colabhive.models`. Las dos son archivos de tu máquina.

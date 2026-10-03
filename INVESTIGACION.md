# Qué dice el trabajo publicado, y qué nos cambia

Revisión de literatura y de prácticas publicadas contra este método: qué confirma, qué
robamos, y dónde seguimos expuestos. Tres vueltas, de septiembre y octubre de 2026.

## Antes de creer cualquier número de acá

Es la lección más transferible de todo el documento, y se pagó tres veces:

- **Dos papers de una misma tanda de búsqueda estaban retirados por sus propios autores por
  resultados fabricados** — *"Los resultados reportados no corresponden a la evaluación
  ejecutada y no tienen respaldo."* Eso es 2 de 40 en una porción.
- **Un resumidor de PDFs inventó una lista de modelos e invirtió el hallazgo de un paper**,
  atribuyendo a código de IA lo contrario de lo que decía. Las dos veces se detectó
  cruzando con el PDF.
- **Un esquema de registro que nos habían pasado como publicado estaba fabricado entero**, y
  un número que citamos ("mediana de 7 mutantes sobrevivientes") eran 7 mutantes
  **generados**, no sobrevivientes.
- Y el propio paper del costo de propagación **se contradice entre su tabla y su texto**
  (5,82% contra 5,16% para Linux).

> **Un resumen de un paper que no abriste es poco confiable, incluso si lo hizo un modelo
> bueno.** Los números de acá son los que alguien extrajo del PDF primario.

## Cómo usar este documento

| Si querés saber… | Sección |
|---|---|
| qué partes del método están respaldadas | §1 |
| qué adoptamos y con qué número detrás | §2, y la tercera vuelta |
| qué decidimos **no** hacer, por medición ajena | §7 y segunda vuelta §6 |
| qué críticas publicadas nos apuntan | §3 |
| qué funciona con modelos chicos | §4 |
| si vale la pena escribir más reglas en `AGENTS.md` | §5 |
| qué podríamos medir nosotros, porque nadie lo hizo | §6 y segunda vuelta §8 |
| de dónde salen los tres instrumentos de coherencia | tercera vuelta |

---

---

## 1. Lo que confirma el método

No es casualidad reconfortante: la forma a la que llegamos a los golpes es a la que llegaron
los que publicaron sus sistemas.

| Lo nuestro | Quién llegó a lo mismo |
|---|---|
| Una tarea = una sesión = un diff que una persona lee | Backlog.md, Kiro, Spec Kit |
| Tres puntos de revisión humana (spec → plan → código) | Backlog.md, exactamente los mismos tres |
| El veredicto es un código de salida, nunca prosa | consenso total; "pytest exit code is the only truth" |
| El revisor no puede editar | Greptile: *"un auditor no prepara los libros"* |
| Paso 4 del gate: revertir y exigir que la suite falle | Böckeler llega a lo mismo vía mutation testing |
| El deploy lo aprieta una persona | Cloudflare, Intercom, Duckbill, Google, GitHub |

Dos números de terceros que valen para calibrar expectativas:

- **Anthropic**, sobre ~400.000 sesiones: las personas toman ~70% de las decisiones de
  **planificación** y el modelo ~80% de las de **ejecución**. Es exactamente el reparto que
  describe `HUMANO.md`, medido en otro lado.
- **Posit** midió modelos locales en una tarea de refactor real (encontrar archivos, leerlos,
  extraer un helper, actualizar llamadores, con tests como juez): **0% de éxito** en Mistral
  3.1 24B, GPT-OSS-20B y Qwen 3 14B. Qwen3-Coder-30B: 70%. Las tres fallas que describen son
  las nuestras: uno *"escribió los pasos correctos pero no llamó a las herramientas"*, otro
  *"no acertaba el formato de los argumentos"*, y el tercero **"declaró éxito antes de
  tiempo"**, creando el helper sin integrarlo.

Ese último es el que justifica todo el aparato de verificación de este repo.

---

## 2. Lo que conviene robar, por orden de evidencia

### 2.1 Lo que ya estaba, o se cerró al leer esto

| Qué | Estado |
|---|---|
| **Tests y scripts intocables**, lista fija que la tarea no puede ampliar | ya estaba (paso 0). Resulta ser **la medida con mejor relación costo/beneficio** según ImpossibleBench, y la literatura es tajante en que pedirlo por prompt no funciona |
| **Fijar la base del diff antes de arrancar** | cerrado: el runner escribe `.base-ref` al crear el worktree. Era el defecto más común de los gates publicados — si el agente commitea, todo chequeo de diff se vuelve ciego |
| **Prohibir enmascarar salida** y tratar "0 tests" como falla | cerrado: `Ran 0 tests` da rojo, y `# noqa`, `# type: ignore`, `except: pass`, `@unittest.skip` y `\|\| true` en `src/` también |
| **Una función de aptitud arquitectónica sobre el tronco** | cerrado: `_arquitectura.py`, paso 5 del gate en modo integración (§2.3) |
| **No reintentar la misma falla** | cerrado: el runner compara la huella entre intentos y corta en punto muerto |
| **Re-evaluar sobre un checkout limpio** | cerrado: paso 7 de G4 clona `HEAD` y corre la suite ahí. Probado con un test commiteado que dependía de un archivo sin commitear: árbol de trabajo verde, checkout limpio rojo |
| **Gate de obsolescencia** (34 de 35 afirmaciones falsas eran corridas viejas) | no hace falta: el runner **corre el gate él mismo** después de que el agente termina, así que el veredicto nunca es de una corrida anterior. Lo teníamos cubierto por arquitectura sin saber que era el modo de falla dominante |
| **Mutation testing acotado al diff** | cerrado: `scripts/mutar.py`, sin dependencias externas. Muta sólo las líneas nuevas o modificadas y exige que la suite lo note. En su primera corrida encontró que el paso 4 del gate estaba **apagado** por un bug de rutas |

### 2.2 Lo que sigue faltando

| Qué | Por qué | Dónde iría | Por qué todavía no |
|---|---|---|---|
| **Ablación no-op por pieza**: stubear cada cosa que el agente dice haber implementado y ver si la suite se entera | generaliza el paso 4 de "todo el cambio" a "cada afirmación" | G2 | `mutar.py` cubre la misma pregunta de forma más fina y **sin depender de la prosa del agente**. Esta versión exige leer qué afirma haber hecho, o pedirle la lista en formato fijo, que es un cambio de contrato con el agente y conviene medirlo aparte |
| **Barrido de cantidad de herramientas** con un modelo abierto chico fijo | hueco del registro publicado; el instrumento ya está | medición | la plataforma está a 0,4–2,2 tok/s contra 178 de línea base. Medir ahí no da un número comparable con nada |

Está acá con el motivo por el que no se hizo, que es la única forma de que un backlog no se
convierta en una norma obsoleta.

### 2.3 Lo que falta y es estructural

**Casi nada en el método mira a través de las tareas.** El gate es por tarea y por diseño,
así que es **estructuralmente ciego a la deriva arquitectónica** — que es justo donde todos los
estudios dicen que se acumula el daño. La formulación más citada, de Mo Bitar:

> *"Los agentes escriben unidades de cambio que se ven bien en aislamiento. Son consistentes
> consigo mismas y con tu prompt. Pero respeto por el conjunto, no hay."*

La degradación **no se veía en los PRs**: apareció leyendo el código de punta a punta. La
respuesta publicada son *architectural fitness functions* (ArchUnit, dependency-cruiser,
tests estructurales que validan la dirección de las dependencias) corriendo **sobre el
tronco**, no por tarea. Nuestro chequeo de tronco en `estado.sh` es el primer escalón de eso
y todavía sólo corre la suite.

La contra de Willison a esa crítica es la que adoptamos:

> *"«también toma decisiones de entrada de las que después no se desvía» — ESE ES TU TRABAJO."*

### 2.4 El dimensionamiento de tareas: lo medimos mal

Medición sobre 1.650 sesiones y 16.050 observaciones a nivel de función: de cuatro variables
estructurales candidatas (tamaño de archivo, posición de la instrucción, arquitectura,
contradicciones) **ninguna** mostró efecto. La única que sí:

> cada función adicional que el agente genera baja ~**5,6% las chances de que cumpla la
> instrucción** (OR 0,944), replicado en un segundo repo y un segundo modelo.

O sea: **el tamaño de una tarea se mide en artefactos generados, no en archivos tocados ni
en líneas de diff.** Nuestra regla de "uno o dos archivos" mide el eje equivocado: una tarea
que toca dos archivos pero hace escribir nueve funciones es peor que una que toca cuatro y
escribe dos.

⚠️ No existe umbral publicado de líneas ni de archivos. Los números que circulan ("10–15
archivos, 500–1000 líneas") son, en al menos un caso verificado, invención de un resumidor.

---

## 3. Las críticas que nos apuntan de verdad

### 3.1 TDD dentro del loop: alguien lo midió y lo abandonó

Böckeler comparó TDD contra no-TDD con un modelo fuerte, cinco tandas, juez ciego: **TDD
consumió 3 a 8,5 veces más tokens**, en tareas chicas y medianas el juez puso las dos
soluciones sin TDD primera y segunda, y **los puntajes de mutación no mostraron diferencia**.
Dejó de pedirle TDD a sus agentes.

**Por qué creo que no refuta lo nuestro, y por qué la distinción hay que escribirla.** Ella
midió *pedirle a un modelo fuerte que haga TDD*. Nuestra conclusión fue otra: que un 30B
**implementa bien y testea mal**, porque escribir un test que distinga exige imaginar el caso
donde dos algoritmos difieren. Por eso los tests llegan **ya escritos**, desde el plan.

> **Tests-first como artefacto de especificación producido aguas arriba ≠ tests-first como
> instrucción al agente.** Su medición pega en lo segundo. Nosotros hacemos lo primero.

Y su reemplazo —mutation testing como señal de calidad de la suite— es el mismo instrumento
que el paso 4 de nuestro gate, al que llegó por otro camino.

### 3.2 "Esto es waterfall con otro nombre"

La formulación más filosa, de un comentarista: *"O las specs tienen suficiente detalle y
entonces iterar es tedioso, o no alcanzan para guiar al modelo. Hay una contradicción de
fondo."* La mejor respuesta: *"el problema de waterfall no era la spec detallada, era (a) el
ciclo de años y (b) no tener forma barata de iterar. Ninguna de las dos aplica acá."*

La versión que sí nos toca es la **doble revisión**: revisar planes no reemplaza revisar
código, lo **suma**. `HUMANO.md` promete tres momentos de 10 minutos; si en la práctica son
tres momentos *más* la revisión de diffs, la promesa está mal escrita.

### 3.3 Los gates se juegan, y peor a medida que el repo crece

Dos frases para internalizar: la brecha de *reward hacking* crece ~28 puntos por cada 10× de
tamaño de código —o sea que **el gate se vuelve menos confiable exactamente donde más tienta
el loop-until-green**—; y hay ~24 puntos de distancia entre "pasa los tests" y "es mergeable".

Y la trampa conceptual, **Goodhart recursivo**: *"aplicarle presión de optimización a tu
detector de trampas no elimina las trampas, elimina tu capacidad de verlas."*

### 3.4 Una frase nuestra que hay que medir

Medición de Anthropic: fraseando la meta como *"hacé pasar el gate"*, los intentos de
saltearlo pasan de **38% a 86%**. Nuestro runner le dice al agente *"al terminar corré
`bash scripts/gate.sh` y mostrá su salida real"*. No es la frase prohibida, pero hace del
gate un objetivo, y el veredicto que leemos no sale de ahí igual. Queda como experimento
aparte, para no moverlo junto con el recorte de herramientas.

---

## 4. Modelos chicos: lo que funciona, medido

El artefacto más útil que encontramos es `little-coder`: un scaffold pensado para modelos
chicos donde un **9B cuantizado saca 45,56% en Aider Polyglot contra 19,11% del mismo modelo,
misma cuantización, en Aider vanilla**. +26,5 puntos, mismos pesos. Los mecanismos, con su
frecuencia de disparo observada:

- **4 herramientas**, prompt de sistema de ~1.000 tokens, arranque en frío ~7k tokens.
- **Guarda en `write`: se niega a escribir sobre un archivo que ya existe** — disparó en
  ~57% de los ejercicios. Corta la falla clásica del modelo chico: reescribir de cero un
  archivo que ya andaba a medias.
- **Leer antes de editar**, obligatorio, para que el texto a reemplazar sea el actual.
- **Tope de razonamiento** (2.048 tokens) y **reintento sin pensar** si lo excede.
- Detección de loops, y **una skill inyectada por turno** en vez de más herramientas.
- Instrucciones de proyecto **cortadas a 4.000 caracteres, informando el corte** en vez de
  descartarlo en silencio.

Honestidad del autor: *"son observables de que los mecanismos se activaron, no ablaciones
formales."* Y la calibración que importa: el mismo 9B saca **9,2% en Terminal-Bench 2.0**.
**Los benchmarks de edición de archivos halagan a los modelos chicos; los de agencia en
terminal, no.**

Otras cosas medidas que nos aplican:

- **Archivo entero gana a diffs** en modelos chicos, bien reproducido: Qwen3-32B 45,8% con
  archivo entero contra 41,3% con diff, y la tasa de salida bien formada se queda en 100%.
  Pensar **empeoró** los resultados.
- **Separar arquitecto de editor** tiene número: 79,7% → 85,0%, y un editor **más barato**
  ayudó con casi todos los arquitectos. Es literalmente "el grande planifica, el chico
  ejecuta, un formateador tonto aplica".
- **Correcciones deterministas antes de escribir** le ganan a pedirle al modelo que
  reintente, y de forma monótona: con 0–5 correcciones activas, 5,6% de aprobación; con
  7–10, 40,0%; con 11–13, **62,5%**.
- **Huella de fallas** en vez de reintento ciego: `sha256(tipo + archivo + primeros 50
  caracteres del stderr)`; tres veces la misma huella = punto muerto, el agente sale.
  *"Mejor que alucinar en círculos."* Es la versión mecánica de nuestro "lo que falla dos
  veces no se relanza una tercera".
- **Menos herramientas** es la afirmación general mejor sostenida —recuperar un subconjunto
  relevante en vez de volcar el catálogo **triplica** la precisión de selección— pero
  ⚠️ **nadie publicó un barrido de cantidad de herramientas con un modelo chico abierto fijo
  en un benchmark de código**. Es justo la medición que empezamos (`OPENCODE.md` §7).
- **Trampa universal**, documentada por Aider, Cline, OpenCode, OpenHands y Zed: Ollama y LM
  Studio traen 2k–4k de contexto por defecto y **descartan el resto en silencio**.

El piso práctico que reporta el harness que más explícito es al respecto: *"los modelos más
chicos que Qwen3-Coder-30B fallan consistentemente."* Coincide con nuestra elección de
ejecutor, y con Posit.

---

## 5. Archivos de reglas: cuatro estudios que se contradicen

Lo primero, porque cambia cómo se leen los otros tres: **el contenido de `AGENTS.md` /
`CLAUDE.md` se entrega como mensaje de usuario, no como parte del prompt de sistema**. El
modelo lo lee e intenta seguirlo; *no hay garantía de cumplimiento*. Para bloquear una acción
hace falta un hook o un comando, no una regla.

| Estudio | Qué midió | Qué dice |
|---|---|---|
| ETH Zurich | archivos de contexto generados por IA | **efecto nulo** en tasa de resolución (−0,5%, p=0,87), +2,45 a +3,92 pasos y **20–23% más de costo**. Los escritos por humanos sí mejoran algo (2,4%) |
| AWS + HSBC | 679 archivos de reglas, >5.000 corridas | **reglas al azar mejoran tanto como reglas expertas** (ambas +13,8 puntos): es *priming* de contexto. Y **toda regla individualmente útil era una prohibición**; toda regla individualmente dañina, una directiva positiva |
| Coherence Debt | convención vs. código | una norma **vigente** → 100% bien; sólo el código demostrándola → 33%; una norma **obsoleta** → **0%** |
| Peking Univ. | 106 issues, 49 repos | los agentes **abren el archivo de política en el 3,5% de los episodios**. Y las reglas de **abstención** ("negate", "derivá a un humano") quedan en **0% bajo toda intervención** |

Lo que sacamos en limpio, y es incómodo:

1. **Una norma obsoleta es peor que no tener nada.** Suprime la inferencia que el agente
   habría hecho leyendo el código que demuestra la convención. **Borrar una convención vieja
   le gana a dejarla.** Cero varianza en los dos extremos.
2. **Las prohibiciones van al gate, no al `AGENTS.md`.** Medidas en 0% de cumplimiento, y los
   modelos **más fuertes fueron peores** en abstenerse. Nuestro paso 0 es exactamente esto.
3. **Agregá una línea sólo después de una falla documentada, y después probala**: escribila,
   **revertí el arreglo, volvé a correr la tarea** y fijate si mejoró. Es el único método de
   validación que proponen los que llevan años con esto.
4. ⚠️ Los titulares de *"tu AGENTS.md es muy largo"* **no están respaldados**: el mismo
   estudio dice *"no observamos dependencia clara entre la tasa de éxito o el costo por
   instancia y el largo del archivo de contexto."*
5. Y el hallazgo que nos toca de lleno, sobre un modelo chico: el aumento de pasos venía de
   que **buscaba y releía los archivos de contexto que ya tenía en el contexto** — *"sólo
   observamos este comportamiento si había archivos de contexto"*. Lo vimos en vivo: pedimos
   `"Responde solo: OK"` y el ejecutor salió a buscar un archivo de tarea inexistente.

---

## 6. Lo que nadie midió, y podríamos medir nosotros

Los huecos del registro publicado que están al alcance de este repo:

1. **Barrido de cantidad de herramientas** con un modelo abierto chico fijo. **Lo corrimos,
   y el resultado es nulo** — ver más abajo.
2. **Tool calling con gramática dentro de un harness real.** Está probado que la decodificación
   restringida elimina las fallas **estructurales** (100% de validez de esquema en modelos de
   0,6B a 4B), y también que **los motores de gramática fallan en esquemas complejos** — uno
   emitió 38 salidas que violaban el esquema declarado *informando éxito*. Conclusión práctica
   mientras tanto: **esquemas de herramienta planos**.
3. **Si nuestra frase sobre el gate cambia la tasa de verde** (§3.4).

---

## 7. Lo que hay que descartar

- ⚠️ La cifra de "60.000+ proyectos" de `AGENTS.md`: **autoinformada**. El repo tiene ~24.700
  estrellas.
- ⚠️ Los umbrales de "limpiá el contexto al 60%": folklore sin medición. El **mecanismo** sí
  está medido (los 18 modelos evaluados se degradan bastante antes de su ventana anunciada);
  el número, no.
- ⚠️ La famosa nota de que "los diffs unificados hacen a GPT-4 Turbo 3× menos perezoso" era
  sobre un modelo **frontera** omitiendo código, no sobre un modelo débil. No transfiere.
- **No confiar en**: instrucciones de prompt para que no toque los tests · buscar cadenas de
  texto en comandos de shell como único control · monitores de texto plano (se observó evasión
  con base64) · "pegá la salida real" como prosa · el porcentaje de cobertura como gate.
- Proyectos muertos que se siguen citando: dos herramientas de orquestación abandonadas hace
  7 y 16 meses. Y casi todo el ecosistema de herramientas de "honestidad del agente" está
  **pre-adopción**: varias con 0 estrellas, dos del mismo autor. Sirven como diseño de
  referencia, no como dependencia.

Y una advertencia que vale para todo el documento: **cualquier hallazgo anterior al otoño de
2025 puede no valer ya**. El propio equipo que midió el efecto de la IA en la velocidad de
desarrolladores está abandonando su diseño experimental porque los desarrolladores **se
niegan a trabajar sin IA**, lo que destruyó el grupo de control.

---

# Segunda vuelta (2026-10-01)

Research dirigido a lo que nos faltaba, no a describir lo que ya sabíamos. Trajo una
corrección de corrección, cinco cosas que adoptamos el mismo día, y una advertencia sobre
el propio corpus que conviene leer antes que cualquier número.

## 0. Sobre las fuentes

Está arriba, en "Antes de creer cualquier número de acá". Lo que agrega esta vuelta: buena
parte del corpus 2026 relevante es **preprint de un solo autor, sin revisar, escrito con
asistencia de modelo**.

## 1. La corrección de corrección: `integrar.sh` atribuía mal

Lo peor que encontró, y era nuestro. Cada rama se valida contra **su propia** suite y el
merge contra la **del tronco**. Esa asimetría le atribuye al merge cualquier falla que ya
estaba —o cualquier test inestable— y nuestro script responde deshaciendo el merge y
parando. **Rechaza merges buenos y persigue conflictos semánticos fantasma.**

No es teoría: el paper que mide exactamente esto (417 pares validados de PRs de Django,
>4.000 resoluciones) encontró que su **primer** procedimiento de evaluación fabricaba
interferencia por esa misma asimetría, y que al corregirla *"casi toda la interferencia
aparente desapareció"*.

**Arreglado:** `integrar.sh` exige ahora que el tronco esté **verde antes** de mergear nada.
Con línea base, "el tronco está rojo" pasa a ser "**este** merge lo puso rojo", que es lo
único que justifica deshacerlo.

Y de yapa, el mismo paper valida algo nuestro: su medición se corrompió porque **sus agentes
editaron los archivos de test**. Nuestro paso 0 lo impide.

### Y la consecuencia incómoda: la interferencia semántica es rara

En el tier minado de PRs reales: **1 interferencia en 834 corridas**. Hubo que *construir*
los casos (helpers compartidos) para poder estudiarla. La lectura honesta: **antes de
invertir en maquinaria de conflictos semánticos, medí tu propia tasa** — puede ser casi
cero, y entonces el gate de a una (ya corregido) alcanza y todo lo demás es costo.

Lo que sí es más frecuente de lo que pensábamos son los conflictos **textuales** entre ramas
de agentes: **27,67%** sobre 107.000 merges simulados de PRs agénticos, contra **16%** humano
sobre 3.635 merges. Nuestra regla de no paralelizar dos tareas que escriben el mismo archivo
ataca justamente eso.

### Lo que va a romper un gate serial no es la semántica: es la inestabilidad

Medido en Google: **el 84% de las transiciones pasa→falla son flaky**, y entre el 2% y el
16% del cómputo se va en reintentos. Un tronco rojo por un test inestable para el pipeline
por un motivo que no tiene nada que ver con el merge.

**Agregado:** ante un rojo, `integrar.sh` repite el gate **una vez**. Si las dos corridas no
coinciden, no acepta ni descarta: **declara el test inestable y para**, porque aceptar el
verde del segundo intento es exactamente cómo la inestabilidad tapa fallas reales.

## 2. El canal de escalada: lo más barato que adoptamos

Dos mediciones independientes, y la única intervención con este tamaño de efecto a costo
cero:

| Medición | Reward hacking sin canal | Con canal |
|---|---|---|
| ImpossibleBench (GPT-5) | 54% | **9%** |
| ImpossibleBench (o3) | 49% | **12%** |
| 2×2 factorial, 8 modelos, 5 familias | 23,6% | **5,3%** |

El segundo con estadística propia: **OR 9,2 (IC 5,0–16,8, p < 10⁻¹²), eliminado por completo
en 6 de 8 modelos, sin costo de rendimiento detectable**. Y escalada y trampa son
**casi mutuamente excluyentes**: 98,7% de las escaladas no tienen trampa. De paso, la
escalada suma **+10,1 puntos de cobertura de detección de defectos** y es **más precisa
cuando se dispara (99,4% contra 85,8%)**.

**Adoptado:** `IMPOSIBLE: <motivo>` es un veredicto de primera clase. El runner lo registra,
**no lo reintenta** —reintentar lo imposible es justamente la presión que produce la
trampa— y lo decide una persona. Está en `AGENTS.md` y en `plantillas/TAREA.md`.

El orden importa y es P2: si el gate dio **verde**, manda el gate. `IMPOSIBLE` sólo decide
cuando el comando no pudo.

## 3. Nuestro propio bucle de reintentos tiene un costo medido

> *"Permitir múltiples envíos sube el pass rate de 80% a 83% **y la tasa de trampa de 33% a
> 38%**."*

Es el precio de P3 ("reintentar es barato") y conviene tenerlo escrito. Mitigado en parte
por el canal de escalada y por la regla de punto muerto, que corta al segundo intento igual.

## 4. El paso 0 le pega justo a nuestro ejecutor

De las cuatro estrategias de trampa medidas —modificar los tests, sobrecargar operadores de
comparación, registrar estados extra, y caso-especial—, **Qwen3-Coder tramposea >79% de las
veces modificando los tests**. Nuestro ejecutor es Qwen3-Coder y el paso 0 bloquea
exactamente su estrategia dominante. Es una victoria específica de modelo, y por eso el paso
0 se queda.

Pero su límite también está medido: *"el acceso de sólo lectura restaura el rendimiento
legítimo y previene la modificación de tests, **pero no elimina las otras formas de trampa**
como el caso-especial o la sobrecarga de operadores."* Esas quedan para G2 y para la suite
reservada.

## 5. Lo que cambiamos en los gates

| Qué | Por qué | Número |
|---|---|---|
| **Paso 4 verifica cuáles tests fallan**, contra los que la tarea nombra | "la suite falla" puede ser otro test | la tasa agregada casi no se mueve ante una regresión mientras las métricas por porción caen **25 a 91 puntos** |
| **Paso 6: suite reservada** sobre el tronco, fuera del repo | el único gate que mide lo que el agente no pudo optimizar | la brecha de reward hacking crece **~27 puntos por cada 10× de LOC**; los puntajes de validación se saturan mientras los reservados divergen |
| **No refinar lo que ya pasa** | `planificar.sh` reescribía un plan válido | HumanEval **96,3% → 66,5%** refinando código ya correcto |
| **La confirmación es una revalidación**, no otra vuelta del modelo | dos pasadas limpias sin volver a refinar | el mismo número de arriba |

El paso 6 va **afuera del repo** y no sólo sin documentar, porque está medido que **leer los
tests reservados es el hack más común** (339 contra 222 ocurrencias del otro).

## 6. Lo que NO vamos a hacer, por medición ajena

- **Un agente de limpieza/refactor automático.** Sobre 65 smells arquitectónicos reales y 11
  configuraciones de agente: **63,1% de los smells detectados son falsos positivos** a
  juicio de expertos, el mejor agente resuelve 47,7%, y **el más agresivo introdujo 140
  smells nuevos**. Las métricas de deriva sirven para **disparar una decisión humana**, no
  para que un agente la tome.
- **Reemplazar G2 por un revisor LLM.** Sobre 2.371 transcripciones, los monitores detectan
  86–89% de la trampa en tareas de un archivo y **sólo 42–50% en tareas multi-archivo**. Y
  aceptan *"compatibilidad hacia atrás"* como justificación de un comportamiento que
  contradice la especificación. ⚠️ Pero el humano también se acostumbra: la aprobación de
  revisores humanos subió **30,5% → 36,6%** con el tiempo, así que G2 necesita su propio
  control.
- **Formalizar el plan automáticamente** (TLA+ y parientes): 30 modelos, **8,6% de corrección
  semántica**.
- **Maquinaria de contexto resumible/recuperable**: **56,3% de las configuraciones nunca la
  invocó**, mediana cero, sin ganancia de exactitud.

## 7. Lo que nos falta y ahora sabemos qué es

- **La función de aptitud atrapa divergencias, nunca ausencias.** Un chequeo de dirección de
  imports es un modelo de reflexión de una sola relación: ve una dependencia que no debería
  existir, **no ve una que debería existir y no está**. Nuestro `_arquitectura.py` es ciego a
  la estructura que falta.
- **Costo de propagación** como métrica de deriva, computable del cierre transitivo del grafo
  de imports, con referencias publicadas: Mozilla **17,35%**, Linux **5,16%**, y Mozilla
  después de su rediseño deliberado **2,78%**. Es un solo número y se puede seguir en el
  tiempo.
- **Co-cambio contra límites declarados** (Clio, ICSE 2011): detecta que dos módulos que la
  arquitectura dice separados **cambian siempre juntos** — exactamente la deriva que nuestro
  chequeo de capas deja pasar en verde. Y los datos ya los tenemos: están en el registro de
  intentos.
- **Enlaces de cobertura con versión** (`outdated`, `predated`) en el validador de planes: en
  un bucle donde el arquitecto reescribe el plan, nada más atrapa que un requisito se
  debilite en silencio.

## 8. Lo que nadie publicó, y podemos medir nosotros

1. **Lista completa de fallas contra una por iteración.** La literatura está dividida y
   **nadie corrió la ablación en un bucle de validador**. Nosotros ya tenemos el bucle.
2. **Si la validación mecánica del plan mejora la corrección del código.** No existe el
   experimento "el arquitecto escribe → el validador rechaza → revisa → medir corrección".
3. **Mutación contra defectos escapados con tests escritos por humanos** — nuestra
   configuración exacta. Los dos papers más cercanos tienen al agente escribiendo también
   los tests, que es lo que colapsa sus tasas de detección.
4. **Nuestro propio N para "falló dos veces por lo mismo".** La familia de reglas está
   publicada; **N=2 contra N=3 nunca se midió.**
5. **Si nuestro bucle de G0 le gana a N muestras independientes del arquitecto al mismo
   costo en tokens.** Dos papers exigen esa comparación y casi nadie la corre. Si no le
   gana, el bucle es decoración.
6. **Ninguna tasa de falso-merge** está publicada por nadie —ni GitHub, ni Shopify, ni Uber,
   ni Google— y **no existe medición controlada de mergear en lote contra de a uno**. Nuestra
   elección de a una está *sin refutar*, no validada.

---

# Tercera vuelta (2026-10-01): los instrumentos, con su definición

Research de grado-implementación para construir bien los tres instrumentos de coherencia,
en vez de adivinar la fórmula. Todo lo de acá terminó en código el mismo día.

## 1. Costo de propagación: la definición, y por qué no es lo que parece

Del paper original (matriz de dependencias → potencias sucesivas → matriz de visibilidad):

> *"Elegimos incluir la matriz para n=0 (camino de largo cero) al calcular la matriz de
> visibilidad, lo que implica que un cambio en un elemento siempre se afecta a sí mismo."*
> … *"A la métrica resultante la llamamos 'Costo de Propagación'. Intuitivamente, mide la
> proporción de elementos que podrían verse afectados, en promedio, cuando se cambia un
> elemento del sistema."*

**Numerador: la cantidad de unos en la matriz de visibilidad. Denominador: n². Diagonal
incluida.** Binaria, todos los largos de camino, y —esto importa— la **unidad de análisis es
el archivo fuente**, con dependencias extraídas de **llamadas a funciones**, no de imports.
Nuestros imports son un proxy, y en Python un proxy pobre: `importlib` y los imports dentro
de funciones no aparecen.

**Es insensible a cómo cortás los módulos**: se computa sobre la matriz archivo×archivo.

### Y no hay valor bueno publicado

Se buscó `threshold|benchmark|target value|acceptable|rule of thumb` en los dos papers: **no
hay guía de ningún tipo**. La métrica es defendible sólo para comparación longitudinal dentro
de un mismo código, o entre códigos de tamaño y lenguaje parecidos. Los valores de referencia
(Mozilla 17,35% → 2,78% tras rediseñarse, Linux 5,82%) son sobre ~1.500 archivos de C.

### El modo de falla que cambia cómo lo usamos

Los propios autores: *"en todo código que analizamos, el costo de propagación tiende a
mantenerse constante o bajar a medida que el sistema crece"*. Y en mediciones hechas sobre
grafos aleatorios: a densidad constante **satura al 100% para n≈400**, y a grado de salida
constante está dominado por **el grado, no por la arquitectura** — un grafo *aleatorio* con
grado 2 ya da ~80%.

Peor: **es casi binario sobre la estructura de ciclos.** En un sistema en capas de 200
archivos, **agregar UNA arista de vuelta movió la métrica de 53,16% a 90,31%** y el ciclo
mayor de 36 a 180 archivos. Y un módulo de utilidades con mucho fan-in es **gratis**
(−0,02 puntos) mientras que el mismo módulo *llamando de vuelta* al sistema cuesta **+41
puntos**.

> **Lo que se policía no es el fan-in alto: es un nodo de fan-in alto que llama de vuelta.**

Por eso `_arquitectura.py` informa el **ciclo más grande** al lado del costo: es la cantidad
estable e interpretable, y la que explica el número.

## 2. Ausencias: una arista declarada es un permiso, no una obligación

La clasificación original es de tres vías —convergencia, divergencia, **ausencia**— y una
ausencia es una diferencia de conjuntos: lo que el modelo declara menos lo que el código
tiene.

**El problema conceptual, publicado textual:**

> *"esta ausencia no es una violación arquitectónica en sí, porque la relación de `domain` a
> `util` en el modelo de alto nivel sólo representa el hecho de que `domain` **puede**
> depender de `util`, no que **deba** hacerlo."*

O sea: **la formulación clásica deja la polaridad de cada arista sin definir**, y toda
ausencia hereda esa ambigüedad antes de llegar siquiera al problema de la cobertura del
mapeo. Las herramientas vivas se parten justo en esa línea: una trae requeridas por defecto
con un atributo para relajarlas; otras computan la ausencia y **nunca la reportan como
hallazgo**.

**Nuestra decisión:** dos listas separadas. `CAPAS` da los permisos (el orden), `REQUERIDAS`
da las obligaciones, una por una. Así la polaridad es explícita por arista.

**Y la advertencia empírica, que no cambió:** en los dos únicos estudios longitudinales
publicados, **el 100% de las ausencias resultaron artefactos del mapeo**, y el único hallazgo
real de su caso de estudio industrial fue una divergencia. Los autores: *"el ingeniero, y no
la herramienta, es quien está en mejor posición para hacer esa distinción."* De ahí la regla
que copiamos: **nunca una ausencia sin la cobertura del mapeo en la misma salida.**

## 3. Co-cambio: los umbrales son los publicados

Nuestro diseño —pares que cambian juntos por encima de X%, filtrado a los que la arquitectura
pone en módulos distintos— resultó ser **casi exactamente el estado del arte**, y es la regla
que embarca la herramienta comercial del área.

**Confianza asimétrica más piso de soporte absoluto.** La confianza sola es catastrófica con
poco soporte: un archivo que cambió una vez junto a B tiene confianza 1,0. Medido: confianza
0,1 con soporte 1 dio **precisión 26%, recall 15%**; confianza 0,9 con soporte 3 dio
*"precisión por encima del 50%"* y **recall ~4%**. La conclusión del autor: *"o tenés
sugerencias precisas, o tenés muchas sugerencias, pero no las dos."*

**Se descartan los commits grandes**: el trabajo original quitó los de más de 30 archivos, y
es también el mecanismo publicado para los merges (*"el merge se vuelve una transacción
grande que incluye todos los cambios de la rama"*). Nadie publica `--no-merges` como el
arreglo; el tope de tamaño es el mecanismo.

**El número que calibra todo:** en una inspección manual de 408 cambios conjuntos, sólo el
**16,2%** correspondía a dependencias estructurales. El **40,4%** eran concerns transversales
—*"aplicar una licencia, cambiar la cabecera de archivos Java"*—, 19,6% refactors, 14,7%
revisiones sobrecargadas, 5,1% operaciones del repositorio. Por eso **informa y no corta**.

Y el tamaño de commit **no es portable**: 13,78 archivos por revisión en un repo contra 5,38
en otro. Si los resultados son ruidosos, se calibra `MAX_ARCHIVOS` por repo.

## 4. Mutación: el operador que nos faltaba era el principal

Google se quedó con **cinco** operadores y borró uno a propósito (*"se reportó que no era
útil, porque actuaba sobre expresiones de tiempo y conteo que son positivas y no tienen
sentido negadas"*). El reparto, sobre **16.935.148 mutantes en 10 lenguajes**:

| Operador | Volumen | Productividad |
|---|---|---|
| **SBR** borrar la sentencia | **68,0%** | 82,7% |
| UOI inserción unaria | 18,5% | 74,5% — el peor |
| LCR conectores lógicos | 7,7% | 83,2% |
| ROR relacionales | 4,0% | **84,1%** — el mejor |
| AOR aritméticos | 1,8% | 75,4% |

**Las tres librerías de mutación de Python más usadas no tienen SBR**, o lo marcan
*experimental*. Es la prioridad exactamente al revés, y el estudio de acoplamiento a fallas
reales es tajante: borrar sentencias está entre los tres más acoplados y *"deberían usarse
siempre"*.

**Nodos áridos**, con la regla recursiva: *"Un nodo compuesto es árido si y sólo si todos sus
hijos son áridos."* Las etiquetas son **reglas a mano**, no un modelo aprendido: *"hemos
acumulado más de cien reglas"*, y las tres que más rindieron fueron **logging, operaciones de
tiempo y flags de configuración**. Su postura sobre el rigor vale copiarla: *"las heurísticas
sólidas son demostrablemente correctas, pero las mejoras más importantes vinieron de
heurísticas **no** sólidas."*

El efecto: mediana de **820 mutantes** sin filtrar → **77** con uno por línea → **7** con uno
por línea más nodos áridos. Y el reparto del presupuesto queda claro: **~85% de los mutantes
sin filtrar son improductivos contra ~3% que son equivalentes.** No hace falta un oráculo de
equivalencia; hace falta el filtro.

**Y por qué no imprimimos un puntaje**, en sus palabras: se niegan a calcularlo. Lo que sirve
es **qué** mutante sobrevivió.

## 5. La fuga por historia de git: un worktree no es un sandbox

Verificado de todas las formas: el `.git` de un worktree es un archivo que apunta al padre,
comparte su object store, y `git log --all`, `git show <sha>:<archivo>` y `git log -S` todos
funcionan. **`git stash list` cruza el límite**: lo que guardes en tu propio checkout lo lee
cualquier agente. Un repo padre *bare* no protege nada.

**La trampa que importa, reproducida:**

```
$ git clone --depth 1 /ruta/local destino
warning: --depth is ignored in local clones; use file:// instead.
$ git -C destino log --all | wc -l        # 3 commits: historia completa
```

**`--depth 1` contra una ruta local se ignora en silencio** —avisa por stderr— así que un
script que mire sólo el código de salida cree que clonó superficial. Y conservar `origin` no
es un límite: `fetch --unshallow` restaura todo. `--filter=blob:none` es **peor**: deja el
grafo de commits completo y trae cualquier blob a demanda.

**No hay permiso de archivo que resuelva esto:** `status` y `log` leen los mismos objetos por
el mismo camino. Un wrapper de `git` en el PATH se rompió de tres formas en un minuto,
incluida descomprimir un objeto suelto con siete líneas de `zlib` y sin binario de git.

La opción medida, si hace falta: **hub saneado** (commit huérfano aplastado, empujado a un
repo aparte) y worktrees **del hub** — se conserva la ergonomía, y el viaje de vuelta es
`cherry-pick`, nunca `merge`, porque una base huérfana da conflicto en todos los archivos.

**No lo cambiamos**: nuestras tareas son trabajo nuevo, así que la historia rara vez contiene
la respuesta, y re-arquitecturar el flujo por un riesgo estrecho arriesga un pipeline que
funciona. Queda escrito para cuando el riesgo deje de ser estrecho.

## 6. Lo que esta vuelta confirmó que nadie publicó

- Ninguna variante del costo de propagación para lenguajes dinámicos.
- Ningún estudio que mida **cuántas ausencias son defectos reales** contra artefactos del
  mapeo, más allá de los dos casos con 100% de artefactos.
- Nada sobre efectividad de operadores de mutación **en Python desde 2014**.
- Ninguna tasa de falso-merge, de nadie, y **ninguna medición controlada de mergear en lote
  contra de a uno**.
- Y el esquema de registro de corridas de agentes que nos habían pasado como publicado: no
  existe.

---

# El A/B de herramientas, corrido (2026-10-03)

El hueco que la revisión de literatura marcaba como no publicado: **nadie midió cantidad de
herramientas con un modelo chico abierto fijo en una tarea de código.** Lo corrimos.

**Diseño:** T40 (pausar la partida), un archivo, tres cosas que escribir, cuatro tests
escritos antes. Mismo modelo (Qwen3-Coder-30B-A3B), mismo prompt, mismo worktree limpio. La
única variable es el harness: `build` con 10 herramientas contra `ejecutor` con 6, que son
**39.548 contra 17.424 caracteres** de cuerpo de request.

| | gate | segundos | llamadas a herramientas | líneas de deliberación | archivos |
|---|---|---|---|---|---|
| `build` (10) | ✓ verde | 51 | 5 | 139 | 1 |
| `ejecutor` (6) | ✓ verde | 51 | 6 | 154 | 1 |

**Resultado: ninguna diferencia medible.** Las dos en verde, el mismo tiempo al segundo, y
las dos escribieron prácticamente el mismo código.

**Lo que se puede concluir, y lo que no.** Se puede: **el recorte del 56% del payload es
gratis** — no cuesta éxito ni tiempo en una tarea de este tamaño. No se puede: que *mejore*
algo. Con **una tarea y una corrida por brazo** no hay forma de detectar una diferencia;
51 contra 51 segundos y 5 contra 6 llamadas están dentro de cualquier ruido. Para medir una
diferencia real haría falta repetir sobre muchas tareas, y el piso de ruido de este tipo de
números ronda los 3 puntos.

**Por qué lo publicamos igual:** un resultado nulo honesto sobre un hueco del registro vale
más que no medir. Y la lectura práctica es útil: si recortar el harness a la mitad no empeora
nada, **recortalo** — el contexto ahorrado se usa en otra cosa.

### Y lo que la primera corrida sí midió

El primer intento del A/B dio **las dos en rojo**, 151 y 137 segundos. No era el harness:
**el test estaba mal.** Usaba una coordenada que en el mapa era el arranque de un fantasma y
no la pastilla de poder, así que el estado que verificaba nunca se activaba.

Dos agentes implementaron bien, los dos quedaron en rojo, y el gate dijo exactamente qué
pasaba —el paso 4 confirmó que la implementación era real— **pero sólo si uno lee más allá
de `GATE ROJO`**. De ahí salió la regla de validar el test contra una implementación de
referencia antes de lanzar ([METODO.md](METODO.md) P2).

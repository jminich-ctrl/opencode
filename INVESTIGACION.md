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
| dónde hay que escribir una regla para que se cumpla | cuarta vuelta §1 |
| contra qué implementación se valida un test de un agente | segunda vuelta §8.7 y cuarta vuelta §2 |
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

> **Revisado el 2026-10-26: tres de los cuatro que había acá YA ESTÁN HECHOS**, y el documento
> seguía mandando a construirlos. Un «nos falta» que miente en esa dirección es tan caro como
> uno que miente en la otra: manda a escribir lo que existe, y de paso hace parecer más débil
> al método de lo que es. Abajo, lo que se hizo y dónde está.

> **2026-10-26, más tarde: el que quedaba también está hecho**, así que esta sección se
> queda sin lista. Lo que sigue arriba es el método tal como está medido; lo que falta de
> verdad vive en §8 («lo que nadie publicó, y podemos medir nosotros»), que es otra cosa:
> experimentos sin correr, no instrumento sin construir.

### Lo que estaba acá y ya está hecho

| lo que decía faltar | dónde está hoy |
|---|---|
| «la función de aptitud atrapa divergencias, **nunca ausencias**; `_arquitectura.py` es ciego a la estructura que falta» | la lista `REQUERIDAS` del motor: declara las dependencias que la arquitectura EXIGE y las verifica por cierre transitivo. Es la mitad que «casi nadie hace», y estaba muerta por un defecto de mapeo hasta el 2026-10-26 — ahora verifica de verdad, con el ⊘ cuando una capa todavía no tiene módulos |
| «**enlaces de cobertura con versión** (`outdated`, `predated`) en el validador de planes; en un bucle donde el arquitecto reescribe el plan, nada más atrapa que un requisito se debilite en silencio» | `cobertura.py`, con la huella de los dos extremos de cada enlace en `.cobertura.json`: `outdated` si se movió el encargo y `borrado` si la clave desapareció —los dos rojos—, `predated` si se movió el plan, que es aviso porque el arquitecto reescribe el plan a propósito y un ✗ ahí trabaría el bucle de G0 para siempre. Dos avisos sobre los nombres: **`outdated` y `predated` no los pude encontrar definidos en ninguna fuente** —la industria tiene el concepto como *suspect link*, DOORS marca el enlace cuando un extremo cambia—, así que el corte en dos estados es NUESTRO y está hecho por la acción que pide cada uno; y el registro **no se re-bendice solo**, porque si se actualizara en cada corrida la comparación daría siempre «igual» y esto sería decoración |
| «**costo de propagación** como métrica de deriva» | lo imprime el mismo motor y lo registra en `.metricas/arquitectura.csv` para leer la SERIE, con el ciclo más grande al lado porque está medido que una arista de vuelta mueve el costo 37 puntos |
| «**co-cambio** contra límites declarados (Clio, ICSE 2011)» | `scripts/cocambio.py`, con los umbrales publicados —confianza asimétrica más piso de soporte— y descartando los commits de más de 30 archivos. Su medición más útil hasta hoy: la plantilla y la copia del ejemplo cambiaban juntas el 67% de las veces, que es lo que la duplicación del motor de arquitectura cobró el 26-10 |

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
7. **Contra qué implementación se valida un test escrito por un agente.** Nuestro validador
   de tests tiene cinco pasos, cuatro de ellos comparan el test contra **versiones del
   producto** —sin la implementación, con ella, mutada, con los cuerpos vacíos— y **dos** de
   esos cuatro dependen de cuál sea esa implementación: «pasa con la implementación» y «los
   mutantes mueren». La implementación que usan es la que el agente de tests escribió en el
   mismo turno, y el
   método **la descarta**: lo que se queda es sólo el test, y la implementación de verdad la
   escribe otro agente en la etapa siguiente, desde el contrato.

   Medido el 2026-10-27, 21 tareas con modelos de verdad: los **siete** tests de una etapa
   pasaron los cinco pasos —incluido «pasa con la implementación»— y después **tres** fallaron
   en la etapa de implementación con ese mismo test. Un test no puede pasar y fallar contra la
   misma implementación, así que en 3 de 7 el borrador y la implementación final diferían
   **justo en lo que decide el veredicto**; en este caso, la forma del import que hace que un
   `patch()` pegue o no. O sea que dos de los cinco pasos del validador estuvieron midiendo
   contra un sujeto que se tira, y lo escribió el mismo agente que escribió el test, así que
   es coherente con él por construcción.

   Los otros dos que tocan el producto —«falla sin la implementación» y el brazo nulo con los
   cuerpos vacíos— esperan FALLA, y eso es robusto a qué borrador haya: un cuerpo vacío es un
   cuerpo vacío. Ésos siguen valiendo. El hueco es que **nada verifica que el test sea
   satisfacible por una implementación que cumpla el contrato**. `scripts/_mocks.py`
   cierra el único caso que es decidible sin correr nada; el resto está abierto.

   El experimento, y es barato porque los datos ya salen de cada corrida: conservar el
   borrador descartado junto al test aceptado y medir, sobre N tareas, cuántas veces difiere
   de la implementación final de un modo que invierte el veredicto. Con ese número se decide
   si los tres pasos se corren contra el borrador —y entonces hay que clasificar su rojo como
   «puede ser del borrador»— o si se corren recién en la etapa de implementación, contra la
   implementación real. Nadie publicó esa tasa: los dos papers más cercanos tienen al agente
   escribiendo test e implementación **y quedándose con los dos**, que es otro arreglo.

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

---

# Cuarta vuelta (2026-10-28): el canal, el oráculo y la mutación como feedback

Esta vuelta la disparó una medición propia, no una lectura: el brazo H —una referencia que
mockea bien, puesta en `tests/test_s0.py`— dio **nulo por invalidez**: en siete repeticiones el
agente no abrió el archivo ni una vez. Su nombre aparece en un listado de directorio y nada
más. La pregunta que abrió es «¿dónde tiene que estar escrita una regla para que se cumpla?», y
resulta que hay trabajo publicado que la mide de frente.

## 0. Sobre las fuentes de esta vuelta

Primario, leído del texto: SWT-Bench (arXiv 2406.12952v3, Tablas 2 a 5), TDD-Bench Verified
(arXiv 2412.02883v1, Tablas III a VII), MutGen (arXiv 2506.02954v8, Tabla I y §II-III), y el
estudio factorial de adherencia (arXiv 2605.10039, PDF extraído con `pdftotext`).

Secundario y **sin verificar**, marcado como tal donde aparece: el AGENTbench de ETH (+4% con
archivos escritos por humanos, −2% con archivos generados por LLM, +20% de costo), el censo de
22.854 repos (26,3% tienen archivo de instrucciones; 59,6% entre los más estrellados), y los
papers de trazabilidad (TVR, TraceLLM, RefSQ'25, ReqToCode).

**Y un cuarto caso para la lista del encabezado del documento.** El número que circula de
MutGen en resúmenes de terceros es «53% vanilla → 89,5% con feedback». El 53% **no es un
agregado**: es un sujeto, `id_81` de HumanEval-Java, citado como ejemplo en §II-F. El agregado
de la Tabla I es **77,9%** para el prompt vanilla. Y el famoso «100% de cobertura con 4% de
mutation score» es el mismo sujeto `id_81`, no una población. El salto real es 77,9 → 89,5, no
53 → 89,5: la mitad del efecto que anuncia el resumen. Cuarta vez que un resumen de un paper
que nadie abrió trae un número inflado, y la primera en que el inflado viene de confundir un
caso con una media.

## 1. El canal: dónde está escrita la regla decide si se cumple

**Lo nuestro.** Tres canales medidos contra el mismo sesgo (un `patch()` apuntado al módulo
donde el nombre se define y no donde se usa):

| Canal | Resultado |
|---|---|
| `AGENTS.md` inyectado | llegó a 7/7 una vez; **4 repeticiones lo ignoraron** |
| prompt del reintento | recuperación 0/4 → 3/4; la primera pasada no cambia |
| contrato que lo declara | 8 rechazos contra 8 |
| archivo de referencia en `tests/` (brazo H) | **0 lecturas en 7 repeticiones**; rechazos 11-14, la banda de siempre |
| ejemplo dentro del archivo de tarea (brazo I) | 21/21 las dos veces, en **1 y 2 pasadas, con 6 y 4 rechazos** (n=2, la tercera en curso) |

**Lo publicado, y es mejor de lo que esperaba.** El estudio factorial (2605.10039) mide
exactamente esto: 1.650 sesiones de Claude Code CLI, 16.050 observaciones a nivel de función,
dos codebases TypeScript, cinco tareas, Sonnet 4.6 como modelo principal. La instrucción medida
es deliberadamente trivial y verificable por AST: poner `// @tracked` al principio de cada
función nueva o modificada.

1. **La tasa de cumplimiento (ICR) es de 54,9% a 57,7%** según la celda. Más de cuatro de cada
   diez funciones salen sin la anotación que el archivo de configuración pide, con la
   instrucción más fácil de cumplir y de verificar que se puede escribir.
2. **El efecto más grande que midieron es intra-sesión**: cada función adicional que el agente
   genera baja las chances de cumplir un 5,6% (OR = 0,944, IC 95% de Wald [0,937, 0,951],
   p ≈ 1e-48). No es monotónico, pero el signo es firme y lo replican por codebase
   (OR 0,960 [0,928, …] y 0,934 [0,894, 0,976]).
3. **Ninguna de las cuatro variables de estructura del archivo tuvo efecto detectable** tras
   corregir por comparaciones múltiples; dos de ellas (tamaño y conflicto) con factores de
   Bayes BF10 entre 0,05 y 0,10, o sea evidencia *a favor* del nulo.
4. **La tarea importa más que el archivo**: 26,2 puntos porcentuales entre dos tareas del mismo
   codebase (T4 45,1% contra T5 71,3%).

**Qué nos cambia.** Tres cosas, y una es una corrección a nosotros mismos:

- Que `AGENTS.md` fuera ignorado en 4 de 7 repeticiones **no es un defecto de nuestra
  redacción**: es el valor esperado publicado. Dejar de pelear con la redacción del archivo y
  mover la regla al punto de uso es la lectura correcta de los dos resultados juntos.
- **El mecanismo publicado explica nuestro brazo I.** Si el cumplimiento decae con la posición
  dentro de la sesión, una regla que viaja en el archivo de tarea —que el agente lee
  inmediatamente antes de escribir— tiene que ganarle a la misma regla en un archivo del repo
  leído al arrancar, o nunca. Nuestro I no es un truco: es la predicción.
- **Y le da respaldo a la descomposición**, que hasta ahora defendíamos por otros motivos: si
  cada función generada cuesta 5,6% de obediencia, una tarea que produce tres funciones es
  estructuralmente más obediente que una que produce doce. Eso es medible en nuestro arnés y
  nadie lo cruzó con el tamaño de tarea.

**Experimento barato que falta, y lo pondría ya:** medir *nuestro* ICR con la misma instrucción
trivial verificable por AST (un marcador en cada función que el ejecutor escriba), en tres
celdas: en `AGENTS.md`, en el archivo de tarea, y en los dos. Con eso tenemos un número
comparable con una publicación, sobre nuestros modelos chicos, que es justo donde nadie midió.

## 2. Contra qué implementación se valida un test de un agente

Es el §8.7 de la segunda vuelta, y ahora tiene anclas publicadas. Los dos benchmarks que más se
le parecen **validan contra el parche humano real**, no contra una implementación del mismo
modelo. Nuestra pregunta sigue sin publicar — eso quedó confirmado contra los dos textos
primarios, no contra resúmenes.

**SWT-Bench** (Lite, 276 instancias, GPT-4 salvo donde dice otra cosa; Tabla 2, en %):

| | fail→pass | pasan antes y después (P→P) | cobertura del parche dorado (Δ𝒞) |
|---|---|---|---|
| parche dorado | 100 | 11,2 | 72,0 |
| SWE-Agent+ | **19,2** | 10,1 | 27,6 |
| aider | 17,0 | 8,7 | 27,8 |
| ZeroShot | 5,8 | 3,6 | 7,6 |
| Pass@5 (oráculo, no practicable) | 22,1 | 7,2 | — |

Dos lecturas nuestras. **Una**: el mejor agente reproduce el bug en 19,2% de los casos y cubre
27,6% del parche, contra 72% del test humano. **Otra, la que nos importa**: entre 3,6% y 10,1%
de los tests generados *pasan antes y después del arreglo* — el paper los llama «correct but
unhelpful». Ese es exactamente el defecto que nuestro paso de «aserciones que no pueden fallar»
y el brazo nulo persiguen, con una tasa publicada para comparar.

**TDD-Bench Verified** (449 instancias de SWE-bench Verified; Tabla III):

| Modelo · técnica | fail→pass | tests que **siguen fallando** sobre el código ya arreglado |
|---|---|---|
| GPT-4o · Auto-TDD | **23,6%** (106) | 286 |
| GPT-4o · zero-shot | 18,7% (84) | 189 |
| Mistral-Large · Auto-TDD | 18,9% (85) | 318 |
| Llama-3.1 70B · zero-shot | 11,4% (51) | 192 |
| **Llama-3.1 70B · Auto-TDD** | **8,2%** (37) | 294 |

Tres hallazgos que nos pegan de lleno:

1. **El modo de falla dominante es el test que falla contra la implementación correcta**: 189 a
   318 casos de 449. Eso es «test insatisfacible» en la literatura sin que nadie lo llame así.
   Nuestro gate lo caza localmente con los cinco pasos; el número publicado dice que es la
   norma, no la excepción.
2. **La adecuación separa los dos mundos**: los tests dorados puntúan 0,94; los generados que
   llegan a fail→pass, 0,91-0,97; los que **no** llegan, 0,49-0,59. Un test que no reproduce
   tampoco cubre: las dos fallas vienen juntas.
3. **Y el que más importa para este método: el andamiaje que ayuda a un modelo grande puede
   empeorar a uno chico.** Auto-TDD sube a GPT-4o de 18,7 a 23,6 y **baja** a Llama-3.1 70B de
   11,4 a **8,2**. El paper lo reconoce. Es el primer respaldo publicado para lo que medimos de
   otra forma —que tres canales no corrigieron el sesgo del modelo— y es una advertencia
   directa: cada andamio que agregamos hay que medirlo *con nuestros modelos*, porque el signo
   del efecto depende del tamaño del modelo.

**El experimento de §8.7, CORRIDO y RECONTADO (2026-11-03, siete corridas, n=68).** Era:
conservar el borrador descartado junto al test aceptado y medir en cuántas tareas difiere de la
implementación final *de un modo que invierte el veredicto*. El método ya guardaba el material
—`.metricas/borrador-aceptado/<T>/`— así que no hizo falta cambiar nada, sólo mirarlo.

La primera cuenta (n=21) tenía un defecto de instrumento, no de aritmética: buscaba la
implementación final **en el tronco**, así que sólo veía las tareas cuya etapa ENTERA integró.
Integrar es todo-o-nada —`correr-todo.sh` llama `parar` si una tarea queda en rojo—, de modo que
el par era inobservable justo en las capas difíciles: **sesgo de supervivencia dentro del
instrumento de medición**. Y el par no necesita que la etapa integre, necesita que la TAREA
haya cerrado verde: cuando la etapa no integra, `integrar.sh` no corre y por lo tanto **nadie
borra la rama `tarea/<id>`** —el `branch -D` vive en el camino de la integración y en el del
reintento—. El código estaba en la rama todo el tiempo. De ahí salieron 14 pares más, y la
campaña `f1793664018` —la primera que cerró 21/21 con las TRES capas integradas— aportó 21.

| borrador vs implementación final | total | capa `a` (sin mock) | capa `b` (mockea) | capa `c` (precarga) |
|---|---|---|---|---|
| **pares** | **68** | 35 | **20** | **13** |
| idénticos byte a byte | 58 | 35 | 13 | 10 |
| difieren sólo en blancos | 6 | 0 | 3 | 3 |
| difieren en el código | 4 | 0 | 4 | 0 |
| **invierten el veredicto** | **2** | **0** | **2 de 20** | **0 de 13** |

Las dos capas sin mock lo confirman por ausencia: 35 pares en `a` y 13 en `c`, cero diferencias
de código. El n sigue creciendo donde no hay riesgo, y por eso la cifra que decide se dice sola:
**en la capa que mockea, 18 de 20 veces el borrador y la implementación final son
intercambiables para el veredicto.**

**Los cuatro que difieren, medidos celda por celda y no clasificados por la forma del import.**
El acompañamiento que importa es un tercero que deje `src.servicios.sN` en `sys.modules` con la
función real antes de que corra `test_sN` —lo que hace un test de la capa `c` al importar `rN`—:

| caso | borrador sola / precargado | final sola / precargado | invierte |
|---|---|---|---|
| `f1793535892` T03b | OK / OK | OK / **FALLA** `AssertionError: 30 != 50` | sí, **contra la final** |
| `f1793561182` T01b | OK / **FALLA** | OK / OK | sí, **contra el borrador** |
| `f1793561182` T03b | OK / OK | OK / OK | no |
| `f1793664018` T05b | OK / OK | OK / OK | no |

La afirmación de la primera vuelta se reproduce exactamente, con el mismo `30 != 50`: el
borrador traía `import src.datos.d3` adentro de la función —forma que deja el patch efectivo en
cualquier orden— y la final usó `from src.datos.d3 import leer3` a nivel de módulo. Lo que le
faltaba es que **la inversión necesita ese tercero**: en `f1793535892` el único módulo que
habría precargado `s3` era `r3`, y T03c nunca cerró. El defecto estaba puesto y la etapa murió
antes de cobrarlo. Correr la suite de a+b, o las tres capas sin `r3`, da verde en las cuatro
celdas: no es que el defecto no esté, es que no hay quien lo despierte.

Y una corrección a la cuenta propia: clasifiqué `f1793561182` T03b como inversión porque su
final usa `from … import leer3`. Medido, no invierte — ese `from` está **dentro de la función**,
así que se resuelve en cada llamada y el patch pega. Lo frágil es el nivel de módulo, no la
palabra `from`. Es la tesis de MEDICION.md §20 —«el desajuste es el defecto, no la forma del
import»— aplicada esta vez a mi propia clasificación.

**El número que §8.7 pedía: 2 de 20 en la capa que mockea, y las dos en direcciones
opuestas.** Una vez el frágil es la implementación final; la otra, el borrador. Con n=7 y un
solo caso esto era un orden de magnitud; con n=20 y los cuatro casos medidos es un hecho con
forma: **el error del proxy no tiene signo.** Eso hace más fuerte la conclusión operativa y le
cambia el motivo —el borrador sirve para armar dataset y no sirve para dar por buena una
implementación, no porque sea sistemáticamente peor, sino porque cuando difiere no se puede
saber de qué lado está el error—. Un proxy sesgado se corrige; uno con ruido simétrico, no.
Detalle, la cadena completa y el arreglo —contabilidad del ⊘, no criterio— en MEDICION.md §18.

Los 14 pares que no están en ningún tronco viven **sólo en ramas de repos de corrida**, que un
`git gc` o un reintegro se lleva sin aviso: están congelados en
`metodo-agentes-datos/pares-8.7-20261103/`, cada uno con el comando exacto del que salió.

El dato anterior que teníamos (2026-10-27: los siete tests de una etapa pasaron los cinco pasos
y tres fallaron después con la implementación real, 3 de 7) medía otra cosa: ahí el contrato
mandaba el `from` explícitamente. Con el contrato mudo el borrador acierta mucho más seguido, y
contra ese 3 de 7 lo que queda es **2 de 20** —la comparación va contra la capa que mockea, que
es la que ese dato medía, y no contra los 68 pares, que promedian 48 casos sin riesgo—.

## 3. Mutación: la usamos como aceptación y nunca como feedback

**MutGen** (arXiv 2506.02954v8) es, de todo lo que leímos en cuatro vueltas, **la configuración
más parecida a la nuestra**: un solo modelo abierto de 70B (Llama-3.3) servido local con Ollama
a temperatura 0, sobre 104 sujetos de HumanEval-Java y 100 de LeetCode-Java.

| | HumanEval-Java | LeetCode-Java |
|---|---|---|
| EvoSuite | 69,5% | 58,9% |
| prompt vanilla (Genvanilla) | 77,9% | 69,9% |
| **MutGen** (mutante sobreviviente como feedback) | **89,5%** | **89,1%** |

No comparan contra tests escritos por humanos: ese hueco sigue abierto y es el nuestro.

**Qué nos cambia.** Nuestro gate corre mutación como **puerta**: si los mutantes no mueren, el
test se rechaza, y el agente recibe «no distingue». Lo que nunca hicimos es **devolverle el
mutante sobreviviente**, que es precisamente la diferencia entre 77,9 y 89,5 en la única
configuración publicada con un modelo del tamaño del nuestro. Es un arma que tenemos cargada y
sin usar: el mutante ya está generado por `mutar.py`, el costo de pasarlo al prompt es una
línea, y el efecto publicado es de once puntos.

## 4. La verdad de los enlaces requisito→tarea

Nuestro hueco, medido: `cobertura.py` verifica que cada requisito tenga **alguna tarea que lo
nombre**, y los enlaces los declara el planificador, que es el evaluado. En clasificados los 12
de 12 requisitos están «nombrados en algún archivo de tarea» y **ningún enlace es nominal**. Hoy
el `OBJETIVO.md` que le escribí al Pacman lleva la advertencia en el propio archivo: un encargo
escrito un mes después del plan tiene garantizado que el plan lo cubre.

La recuperación de enlaces de trazabilidad es un campo maduro y hay trabajo con LLM de 2025-2026
(TVR, TraceLLM, el RAG de RefSQ'25, ReqToCode). **Todo secundario acá: no abrí los PDF**, así
que no cito ninguna cifra. Lo que sí se puede afirmar es la forma: existe la tarea «recuperar
los enlaces con un modelo independiente» y nosotros la estamos reemplazando por «preguntarle al
que planificó».

**Experimento, y no cuesta tiempo de agente de tarea:** recuperar los enlaces requisito→tarea
con un segundo modelo, desde el encargo y los archivos de tarea, y contar los desacuerdos con
los declarados. Cada desacuerdo es un candidato a requisito no cubierto que hoy pasa en verde.

## 5. Lo que esta vuelta confirma que nadie publicó

1. **La tasa a la que un test aceptado contra un borrador del mismo modelo se invierte contra la
   implementación real.** Los dos benchmarks del área usan el parche humano como oráculo.
2. **Si una regla en el archivo de tarea le gana a la misma regla en un archivo del repo.** El
   factorial mide estructura *dentro* del archivo de configuración y el decaimiento por
   posición; nadie contrastó los dos lugares. Nuestros brazos H e I son esa medición.
3. **Mutación como feedback dentro de un pipeline de dos agentes** (uno escribe el test, otro la
   implementación, y el test no se puede tocar). MutGen tiene un solo agente que escribe y
   corrige sus propios tests.
4. **N=2 contra N=3** para «falló dos veces por lo mismo». Sigue sin medirse, por nadie.
5. **El ICR de un modelo chico** con una instrucción trivial verificable por AST. El publicado
   es de Sonnet 4.6.

## 6. La cola de experimentos, replanificada

Orden por «cuánto cambia una decisión del método dividido lo que cuesta»:

| # | Experimento | Costo | Qué decide |
|---|---|---|---|
| 1 | **I-2 e I-3** (en curso) | ya lanzado | si el canal del archivo de tarea es real o fue varianza (con n=2: rechazos 6 y 4 contra 11-16) |
| 2 | **Mutante sobreviviente al prompt** | una línea + 2 corridas | once puntos publicados con un modelo de nuestro tamaño |
| 3 | **Borrador descartado conservado** | un `cp` + 1 corrida de 21 tareas | si dos de los cinco pasos del validador miden contra un sujeto que se tira |
| 4 | **ICR propio** (marcador trivial: `AGENTS.md` / tarea / ambos) | 3 corridas | número comparable con 2605.10039 sobre modelos chicos |
| 5 | **Enlaces recuperados por un segundo modelo** | sin corrida de tarea | si el ✓ de cobertura de G0 es cierto |
| 6 | **Adopción ajena** (`EMPEZAR.md`, agente sin memoria del repo) | 1 corrida larga | cada pregunta que los documentos no contestan es un defecto del método |
| 7 | **Tamaño de tarea contra obediencia** | reanálisis de corridas ya hechas | si el 5,6% por función se replica en nuestros modelos |

**Y saco H2-3 de la cola.** Un cuarto dato de un brazo nulo por invalidez no agrega nada: el
canal no se leyó, y eso ya está medido siete veces.

---

# Quinta vuelta (2026-10-31): buscando refutarnos, y qué conviene importar

Esta vuelta no salió de leer: salió de **mandar a buscar lo que nos contradiga**. Tres frentes, con
la instrucción explícita de refutar nuestras propias afirmaciones — dos de ellas ya escritas en un
informe que va a un sponsor.

## 1. Lo que cambió el diseño del juez: el formato, no el modelo

**CodeJudgeBench** mide tres cosas que nos aplican de frente:

- **Juzgar generación de tests es la tarea más difícil** para un juez LLM, por encima de generar
  y de reparar, «porque TestGen sólo provee el enunciado».
- **Pointwise es mucho peor que pareado**: cerca de la mitad de los juicios terminan en empate.
- **Invertir el orden A/B mueve la exactitud hasta 14 puntos.**

Y en el subconjunto difícil, **la mitad de la tabla está por debajo del azar**: Skywork-Critic-70B
45,95 · Prometheus-14B 45,04 · Qwen3-8B 41,50, con el azar en 50. A 70B.

**Nosotros lo medimos en nuestro propio material, el mismo día, y confirma:**

| Mismo modelo, mismo reservado | Resultado |
|---|---|
| pointwise («¿acepta o rechaza?») | **50% de acuerdo** — lo que acierta contestar siempre lo mismo; rechazaba todo |
| **pareado, preguntado en los dos órdenes** | **3 de 3 correctos, 0 inconsistentes** |

n=3, así que la magnitud no se afirma; la dirección sí, y la predicción era ajena y previa. Mi
primera medición usó el formato peor medido del campo y casi concluí que el modelo no sabe juzgar.
**El juez pregunta pareado, y cada par en los dos órdenes; la categoría «cambió con el orden» no
cuenta como acierto** — un juez que depende del orden no juzga el contenido, y en un gate eso es un
veredicto que cambia según cómo se pregunte.

## 2. Qué compra el entrenamiento de un juez: no exactitud, sino dejar de aprobar basura

Dos trabajos independientes, dos dominios, la misma forma:

| Trabajo | Exactitud | Falsos positivos / TNR |
|---|---|---|
| Jueces chicos afinados (ICSE 2026) | sube poco; κ 0,35 → 0,57 en un 3B | **FP 48% → 8%** y **78% → 15%** |
| CriticLeanGPT (Lean 4) | **79,8 → 79,8**: no se movió | **TNR 65,2 → 72,0** |

**La métrica de éxito del entrenamiento es la tasa de falsos positivos a TPR fijo, no la
exactitud.** Un plan que prometa «exactitud del juez» está mal planteado — el nuestro lo prometía.

Y el techo honesto, del propio paper de ICSE: *«ninguno pasa de un acuerdo moderado con la
ejecución de tests (todos con κ ≤ 0,60)»*. Más: **un juez de 0,5B es viable** (κ 0,00 → 0,45), lo
que derrumba el presupuesto. Líneas base servibles hoy, sin entrenar: **Qwen3-14B** (Apache-2.0) y
**AceReason-Nemotron-14B**. Descartados por medición: Prometheus, Skywork-Critic y Self-Taught de
70B están en el azar juzgando tests.

## 3. Nuestra afirmación del dataset: sobrevivió, y ahora es más filosa

La versión defendible, que salió de buscar para refutarla:

> Todo dataset público de etiquetas por paso a escala es de matemática o de web; los únicos de
> ingeniería de software son esfuerzos chicos de anotación humana (102 instancias; 1.000-3.300
> trayectorias), y **ningún dataset de ningún dominio deriva su etiqueta por paso de ejecutar
> tests.**

Esa última cláusula es la que nadie puede tumbar con un link. Dos hallazgos que la refuerzan: una
card de HF que **admite** que su etiqueta final «no puede tratarse como etiqueta por turno» —el
problema que este método resuelve, reconocido por otros—, y **SWE-Flow** (ICML 2025), la idea
publicada más parecida a la nuestra, que es **sólo positivos, sin veredictos, sin negativos y sin
razones**, y cuyo dataset prometido no está linkeado.

## 4. Lo que conviene importar, y lo que nos rompería el gate

**Adoptar:**

| Pieza | Qué nos ahorra | El precio |
|---|---|---|
| **Imágenes oficiales de SWE-bench** (Docker Hub, 4.503 repos, ~1,1 GB cada una) | la infraestructura de contenedores entera. **Verified Mini son 50 instancias y ~5 GB** | **sólo amd64**: la Mac queda afuera, el issue de arm64 se cerró «not planned» |
| **cosmic-ray** como segundo motor de mutación | el único con filtrado **por diff** nativo y operadores pluggables: excepciones, decoradores, `AddNot`, borrado de unarios | su distribuidor local es serial; hay que pasarle el SHA del merge-base, no la rama |
| **`--cov-context=test` de coverage.py** | cero dependencias nuevas: el chequeo de alcance pasa de «¿tocó archivos de más?» a **test-impact real**, y el brazo nulo gana un tripwire mejor: *bajo el control, el conjunto de contextos sobre las líneas cambiadas debe ser VACÍO* | usar la API y no el SQL: el esquema puede cambiar sin cambiar la versión mayor |
| **`grading.py` de SWT-bench, vendorizado** | la definición correcta de éxito ya resuelta: el F2P del candidato tiene que ser superconjunto del base, agregar ≥1 F2P nuevo y **no agregar ningún P2F ni F2F** | 20 repos hardcodeados en su despachador de parsers |

**No instalar, con motivo:** `pytest-testmon` (su propósito es NO correr tests: en el brazo nulo
puede seleccionar ~0 tests y dar verde), `pytest-rerunfailures` y `flaky` (convierten rojos
intermitentes en verdes, que es la patología que el brazo nulo existe para cazar), `deepeval` (se
lleva pytest y sus plugins como dependencias de runtime). **Son exactamente lo que este gate existe
para atrapar.**

**Y la descontaminación: no adoptar nada.** El pipeline de SWE-rebench no publica código —es una
comparación de fechas—, el de `lm-evaluation-harness` es código muerto detrás de docs vivas, dos
detectores no tienen licencia, y Min-K%++ pide logits que vLLM no expone. **Para tareas sintéticas
con semilla no hay nada que detectar**: si la semilla, las plantillas y el código no existían antes
de generarse, ningún corpus los contiene — y eso es una prueba constructiva, más fuerte que correr
un ataque de inferencia de membresía que anda cerca del azar. Lo que falta es **metadatos de
procedencia**, y eso ya lo escribimos (semilla + commit del método por corrida).

## 5. Dónde este método ya está adelante

**El brazo nulo no tiene equivalente publicado** fuera del `NopAgent` de Harbor: ninguna de las
herramientas revisadas implementa una condición de control — todas suponen que la tarea es real y
que el parche debe pasar. Y la necesidad está medida afuera: **SWE-bench+ encontró 32,67% de fuga
de solución** en los parches «exitosos» de un agente conocido, bajando su tasa de 12,47% a 3,97%.

Lo que nos falta es periferia: contenedores (resuelto por las imágenes oficiales), mutación por
diff (cosmic-ray) y **rigor estadístico sobre el control** — y ahí hay un detalle que vale: Intel
publicó `dokimi` (Apache-2.0, octubre 2026), que hace comparaciones pareadas on/off **con p-valores
por modelo**. Es la capa que a nuestro brazo nulo le falta. Leerlo, no depender de él.

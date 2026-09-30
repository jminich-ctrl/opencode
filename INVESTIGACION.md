# Qué dice el trabajo publicado, y qué nos cambia

Revisión de literatura y de prácticas publicadas hasta septiembre de 2026, hecha contra
este método: qué confirma, qué habría que robar, y dónde estamos expuestos.

**Cómo leer esto.** Separo tres cosas que se suelen mezclar: lo que alguien **midió**, lo
que alguien **practica y publica**, y lo que **circula sin fuente**. Marco cada una. Varias
cifras muy citadas en blogs resultaron ser marketing autoinformado o directamente inventadas
por un resumidor; las dejo anotadas para no volver a caer.

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

1. **Barrido de cantidad de herramientas** con un modelo abierto chico fijo en una tarea de
   código. Ya tenemos el instrumento (`proxy_medidor.py`), el par de agentes (`build` con 10
   herramientas contra `ejecutor` con 6) y el comando:
   `bash scripts/comparar-modelos.sh T05 @build @ejecutor`. Falta que la plataforma vuelva.
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

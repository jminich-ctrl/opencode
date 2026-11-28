# Cómo bajar un proyecto grande a tareas ejecutables por agentes

Esta es la parte difícil del método, y la que no se delega: **la calidad del resultado
se decide acá, antes de que corra el primer agente.**

Un modelo chico no falla por falta de inteligencia. Falla porque le diste una tarea
que no se podía ejecutar sin entender cosas que no le contaste.

---

## 1. La pregunta que ordena todo

Frente a cualquier pedazo de trabajo, preguntate:

> **¿Puede alguien que no conoce este proyecto hacer esto bien, leyendo solo lo que
> le doy, y puedo verificar el resultado con un comando?**

- **Sí** → es una tarea. Escribila.
- **No, porque le falta contexto** → el contexto que falta va en el plan o en `AGENTS.md`,
  no en la tarea. Si es mucho, la tarea está en el lugar equivocado del árbol.
- **No, porque hay que decidir algo** → esa decisión es tuya, no del agente. Tomala,
  escribila en "Decisiones tomadas" del plan, y recién después escribí la tarea.
- **No, porque no sé cómo verificarlo** → no es una tarea todavía. O le construís
  verificación (tests, un script), o no se delega.

Casi todos los fracasos vienen de saltear esta pregunta.

---

## 2. Los cuatro niveles

```
PROYECTO      "un Pacman jugable en terminal"           meses / semanas
  └─ ETAPA    "el núcleo del juego funciona"            días
      └─ TAREA    "movimiento de Pacman con paredes"    30-90 min de persona
          └─ PASO     "agregar el caso del túnel"       el agente lo maneja solo
```

**El agente ejecuta TAREAS.** Los pasos los resuelve él; las etapas y el proyecto
son tuyos. Si te encontrás escribiendo una tarea que en realidad es una etapa, se nota
en que su criterio de terminado tiene "y" adentro: *"que se mueva **y** coma puntos
**y** pierda vidas"*.

### Cómo cortar el proyecto en etapas

Una etapa termina cuando **algo se puede probar de punta a punta**, aunque sea feo.
No cortes por capas horizontales ("primero todos los modelos, después todos los
servicios"): cortá por capacidades verticales que se puedan verificar.

Mal: *"Etapa 1: todas las clases. Etapa 2: toda la lógica. Etapa 3: los tests."*
Bien: *"Etapa 1: el laberinto y el movimiento, con tests. Etapa 2: puntaje y fantasmas."*

---

## 3. Dónde están los cortes buenos

Las tareas no se cortan en cualquier lado. Los cortes buenos siguen **costuras que ya
existen en el código**:

| Costura | Ejemplo | Por qué funciona |
|---|---|---|
| **Módulo / archivo** | `laberinto.py` vs `entidades.py` | dos agentes no se pisan |
| **Contrato de función** | "implementá `comer_en(pos) -> str`" | el contrato es la especificación |
| **Capa** | núcleo sin E/S vs render | una se testea, la otra se prueba a mano |
| **Caso de uso** | "el endpoint de alta de campaña" | verificable de punta a punta |
| **Dato** | "el parser del formato X" | entrada y salida claras |

Si un corte te obliga a explicar tres archivos para que se entienda uno, está mal puesto.

**Regla práctica:** si dos tareas necesitan hablarse, definí el contrato entre ellas
**antes** de lanzarlas, y ponelo en el plan. El contrato es lo que permite que corran
en paralelo sin coordinarse.

---

## 4. Tamaño: cómo saber si una tarea está bien dimensionada

Una tarea sana para un modelo de 27B:

| Señal | Bien | Mal |
|---|---|---|
| **Cosas que tiene que escribir** | **1 a 3 funciones** | ocho, o "una clase" |
| Archivos que toca | 1 o 2 | 5+ |
| Objetivo | una frase sin "y" | una lista |
| Criterio de terminado | 3 a 6 condiciones verificables | "que funcione" |
| Tiempo humano equivalente | 30 a 90 minutos | una tarde |
| Contexto que necesita leer | 1 o 2 archivos + el plan | medio repo |
| Decisiones que debe tomar | ninguna | "elegí la mejor forma de..." |

### La primera fila es la que importa, y la aprendimos de una medición ajena

Sobre 1.650 sesiones y 16.050 observaciones a nivel de función, se probaron cuatro
candidatos a predecir si el agente cumple la instrucción —tamaño del archivo, posición de la
instrucción, arquitectura, contradicciones en las reglas— y **ninguno** mostró efecto. El
único que sí:

> cada función adicional que el agente genera baja ~**5,6% las chances de que siga la
> instrucción**, replicado en un segundo repo y un segundo modelo.

O sea: **el cumplimiento se degrada por paso, no por kilobyte.** Una tarea que toca dos
archivos pero hace escribir nueve funciones es peor que una que toca cuatro y escribe dos.
Nuestra regla de "1 o 2 archivos" venía midiendo el eje equivocado; queda, porque correlaciona
y es fácil de mirar, pero **la pregunta primera es cuántas cosas nuevas tiene que escribir.**

⚠️ Y lo que no existe: **ningún umbral publicado de líneas de diff ni de archivos tocados.**
Los números que circulan en blogs ("10–15 archivos", "500–1000 líneas") no tienen fuente; en
un caso verificado, los inventó un resumidor. Si alguien te los cita, pedile el estudio.

**Si dudás, partila.** Dos tareas chicas que pasan el gate valen más que una grande
que hay que revisar tres veces. El costo de una tarea extra es casi cero; el de una
tarea fallida es tu tiempo.

**Señal de alarma:** si al escribir el criterio de terminado no sabés qué comando lo
verifica, todavía no entendés bien el problema. Eso no es culpa del agente.

---

## 5. Orden y paralelismo

Armá el grafo de dependencias, y después agrupá en **etapas paralelizables**.

```
T01 ──┬── T02 ──── T04 ──┐
      │                  ├── T05 ── T06 ── T07 ── T08
      └── T03 ───────────┘
```

Dos reglas, y la segunda se olvida siempre:

1. **No lances una tarea antes que sus dependencias.** Obvio.
2. **No lances en paralelo dos tareas que escriben el mismo archivo**, aunque sus
   dependencias lo permitan. Van a chocar al mergear, y el conflicto lo vas a resolver vos.

En el ejemplo de Pacman, T03 y T05 dependen de cosas distintas pero **las dos tocan
`juego.py`**: van en serie. Es el error más común al paralelizar.

**Cuánto paralelismo:** el límite no lo pone el método, lo pone tu backend. Con modelos
self-hosted, medí cuántas requests concurrentes aguanta cada modelo antes de que la
latencia se dispare, y no pases de ahí. Tareas que esperan en cola no son paralelismo.

---

## 5b. Lo que separás, algo lo tiene que juntar

Cortar bien no alcanza. **Por cada cosa que separás en partes, tiene que existir la tarea que
las junta** —el montaje, el punto de entrada, la pantalla que las usa— y esa tarea tiene que
estar en el plan como cualquier otra. Si no está, nadie la hace: las partes cierran todas en
verde y el producto no existe.

Es el defecto más caro que medimos, porque no se ve en ningún test. El 2026-11-26 levantamos
`ejemplo-clasificados` desde cero:

| | |
|---|---|
| Base de datos | nueva, migración aplicada, 6 tablas |
| Backend | arranca; `/openapi.json` publica **una** ruta: `/salud` |
| Frontend | `vite build` → `Could not resolve entry module "index.html"` |
| `App.jsx` | `<h1>Clasificados App</h1>`, y nada más |
| `pages/Login.jsx`, `Register.jsx`, `AdsList.jsx`, `AdDetail.jsx`, `SearchBar.jsx` | existen, con su lógica y sus servicios, y **nadie los importa** |
| Tareas marcadas «✅ hecha» | 19 de 34 |
| Tests | 46 backend + 27 frontend, todos verdes; `smoke.sh` en 0 |

Las rutas que faltaban eran tareas pendientes, y eso es honesto. Lo que no estaba en ninguna
parte era la tarea que junta. El backend sí la tenía —T06b, «montaje de routers»— y por eso
cualquier `rutas/*.py` queda montado solo. El frontend no tenía el equivalente, así que T07,
T08, T12, T27 y T29 cerraron bien cada una y el sitio siguió mostrando un `<h1>`.

**La pregunta que hay que hacerse por cada tarea, antes de firmar el plan: ¿quién usa lo que
esta tarea entrega?** Si la respuesta no es otra tarea del plan ni un montaje que ya existe,
falta una tarea.

Hay dos respuestas legítimas, y las dos se escriben:

- **Otra tarea la junta.** Entonces esa tarea la nombra: aparece en su columna «Archivos» o
  depende de ella. El grafo lo muestra.
- **Un montaje automático la junta**, sin tarea: un cargador que recorre un directorio, un
  descubrimiento por convención. Eso **se declara en el plan**, porque desde el plan no se ve:

  ```
  **Montajes automáticos:** backend/app/rutas/*.py — los monta backend/app/main.py (T06b)
  ```

`validar-plan.py` avisa cuáles quedaron sueltas —ninguna otra tarea depende de ellas ni
vuelve a nombrar sus archivos— y la declaración las exime. Medido sobre los dos planes
reales: **pacman 0 de 19** y **clasificados 7 de 34**. Cero falsas alarmas en el proyecto que
efectivamente corre es lo que hace que el aviso valga la pena mirarlo.

Y una cosa más que se olvida igual: **el punto de entrada es una tarea**. El archivo que el
proyecto ejecuta —el `index.html`, el `__main__.py`, el `main.py`— no aparece porque sí.
Si ninguna tarea lo declara, no existe, y el proyecto no se puede ni construir.

---

## 5c. Una tarea por capa, y la costura en el borde

Si el proyecto declara capas, **una tarea no puede declarar archivos de dos capas a la
vez.** No es estética: es la única forma de que el alcance de la tarea satisfaga al mismo
tiempo al test y a la mutación.

Las dos reglas que chocan ya estaban escritas, en dos lugares distintos:

- el test tiene que doblar sus dependencias **en el sitio donde se usan**, no donde se
  definen (regla 13 de `AGENTS.md`);
- el alcance de mutación **es** el alcance declarado de la tarea: `gate.sh` arma la lista a
  mutar a partir de «**Archivos que podés tocar:**», no de otra lista.

Juntalas y sale una sola conclusión. Doblar una dependencia apaga las líneas de su
definición. Si esa definición está **fuera** del alcance, no pasa nada: el doble está en el
borde, el test aísla y la mutación no pierde nada. Si está **adentro**, la mutación va a
mutar líneas que el test apagó, y esos mutantes sobreviven con «la línea NO se ejecuta» —
un rojo que no es del agente y que ningún arreglo del agente puede sacar.

Una tarea que declara dos capas tiene la costura adentro **siempre**. No hay dónde poner el
doble.

Medido con el `mutar.py` real, el mismo test, el mismo parche y la misma implementación,
cambiando sólo el alcance declarado:

| Alcance declarado | Sobrevivientes |
|---|---|
| `{servicios/s1.py}` | **0** |
| `{servicios/s1.py, datos/d1.py}` | **3**, todos «la línea NO se ejecuta» |
| `{servicios/s1.py}`, sin doble, contra la dependencia real | **0** |

Y el plan de clasificados se demuestra a sí mismo, que es mejor que cualquier argumento:
T05, T14 y T20 son el mismo trabajo que T04 —una ruta, un servicio y un dato— pero
**partidas por capa** (`T05a`, `T05b`, `T05c`), y las nueve cerraron. T04, T26 y T28
declaran las tres capas juntas; las tres siguen pendientes, una de ellas después de 21
intentos y 4940 s.

`validar-plan.py` lo da en **rojo**, no en aviso, porque la tarea es insatisfacible desde
antes de que exista una línea de código: el agente puede escribir el mejor test posible y
el gate lo va a rechazar igual. Medido el 2026-11-27: **3 de 37 en clasificados y 0 de 19
en pacman**. Las capas las declara el proyecto en `scripts/_arquitectura.py`; un proyecto
que no declara capas no tiene capas que cruzar y el chequeo no dice nada.

Lo honesto del número: «cruza capas» y «la tarea es más grande» son colineales en esta
muestra, así que **la medición no distingue las dos explicaciones**. Lo que sostiene la
regla es la deducción de arriba, que no depende de la muestra.

Y la tercera opción, para la capa más baja: **ahí no dobles nada.** Un doble del driver de
la base en la capa de datos es tautológico —el test afirma que la consulta se armó como el
test dice que se arma, y pasa en verde con una columna que no existe; la base real la
rechaza en medio milisegundo—. Medido: 2,5 ms por test contra el motor ya levantado, contra
los ~250 ms que tarda el intérprete en arrancar. Cuesta el 1% del reloj.

### Y si la capa exige usar otra, el contrato lo tiene que decir

El mismo archivo donde el proyecto declara sus capas declara cuáles dependencias son
**obligatorias**: `("rutas", "servicios")` quiere decir «los endpoints no hablan con datos
directamente». El chequeo de arquitectura verifica eso sobre el tronco, o sea **después**,
cuando el código ya está escrito y la tarea ya se gastó.

`coherencia.py` lo verifica sobre el **enunciado**, antes, y sin adivinar nada: la tarea
declara su capa (sus archivos) y declara sus imports (su contrato). Si su capa exige usar
otra y sus imports no nombran ningún módulo de esa capa, **las dos declaraciones de la misma
tarea se contradicen**. No hay interpretación: las dos las escribió el plan.

T16 de clasificados es el caso. Implementa `rutas/favoritos.py`, declara exactamente
`from fastapi import APIRouter`, y nunca dice de dónde saca la lógica de favoritos. Pasaba
como «cruzada» —declara *un* import, así que no caía en el aviso de cobertura— y el agente
gastó **21 intentos y 4940 s sin llegar nunca a verde**, inventando la lógica en la capa
equivocada. T22 es su gemela en mensajes.

El chequeo sólo habla de tareas que **sí** declaran imports, y esa restricción es la que
decide si sirve o es ruido: sin ella marcaba **12 de 19 tareas en pacman**, un proyecto que
cerró completo, porque ahí casi ninguna declara imports y «no declara el que hace falta»
quedaba indistinguible de «no declara nada». Eso último ya se informa como **⊘**, que es
otra afirmación. Con la restricción: **clasificados 2 de 37, pacman 0 de 19.**

---

## 6. Qué va en el plan y qué va en la tarea

Es la distinción que más ordena, y la que más se hace mal.

| Va en el **PLAN** (una vez) | Va en la **TAREA** (cada vez) |
|---|---|
| Decisiones de diseño ya tomadas | Qué implementar exactamente |
| Convenciones del proyecto | Archivos permitidos y prohibidos |
| Arquitectura y dependencias | Contrato de la función o clase |
| Riesgos y qué haríamos | Criterio de terminado |
| El orden de las etapas | El comando de verificación |

Y hay un tercer lugar: **`AGENTS.md` tiene las reglas permanentes** (estilo, qué no
tocar nunca, cómo se corren los tests). El agente lo lee solo, en todas las tareas.

Si te ves repitiendo la misma aclaración en varias tareas, esa aclaración va en
`AGENTS.md`, no en las tareas.

---

## 7. Las decisiones no se delegan

Un modelo chico, frente a una decisión abierta, **elige una opción y sigue como si fuera
obvia**. No te avisa. Por eso el plan tiene una sección de "Decisiones tomadas", con el
porqué de cada una.

Ejemplos reales del Pacman:

- Coordenadas `(fila, columna)`, no `(x, y)`. Sin esto, cada tarea elige una y el
  código no encaja.
- El tiempo avanza por turnos, no por reloj. Hace los tests deterministas.
- Sin `random` en el núcleo, con desempate explícito para los fantasmas.
- Biblioteca estándar únicamente.

Cada una de esas líneas evita una tarea fallida. **Escribir el plan es más barato que
revisar diffs incorrectos.**

---

## 8. El trabajo exploratorio no es una tarea

A veces no sabés lo suficiente para escribir la tarea: no conocés el código, no sabés
si una biblioteca sirve, no entendés por qué falla algo.

Eso **no se delega como tarea de implementación**. Se hace de una de estas formas:

- **Un spike de solo lectura**, con el subagente explorador: "decime dónde se define X,
  qué archivos tocan Y, cómo está estructurado Z". Sin permiso de edición. El resultado
  es información, no código.
- **Vos, con un modelo grande.** Si el problema es de criterio, no de trabajo.

Después de explorar, escribís la tarea. Nunca al revés: un agente que investiga *y*
implementa en la misma sesión termina implementando sobre supuestos que nadie revisó.

---

## 8b. Lo cualitativo: el agujero que te va a morder

La pregunta del §1 ("¿puedo verificarlo con un comando?") es lo que hace que el método
funcione. También es su punto ciego: **lo que no pasa ese filtro no se omite conscientemente,
se olvida.** El plan queda lleno de lo testeable y el resultado cumple todos los criterios
siendo malo.

Nos pasó con el Pacman: 54 tests en verde, 8 tareas cerradas, y el juego se siente mal.
Las teclas se pierden, hay un solo fantasma, los personajes se atraviesan. Nada de eso
estaba roto según los tests **porque nada de eso estaba en el plan**.

### Cómo se evita

Al terminar el plan, pasale esta lista y agregá lo que falte:

| Pregunta | Si la respuesta importa, va al plan |
|---|---|
| ¿Cómo se siente usarlo? | latencia, fluidez, cuántos pasos cuesta la tarea más común |
| ¿Qué pasa cuando el usuario se equivoca? | errores entendibles, nada que se rompa feo |
| ¿Cuántos casos reales cubre? | *un* fantasma no es el juego; *un* tipo de usuario no es el producto |
| ¿Lo entiende alguien que no lo programó? | |
| ¿Cómo se comporta con datos de verdad? | volumen, casos raros, datos sucios |

Lo que salga de ahí no se escribe como criterio de test, porque no se puede. Se escribe
como **gate humano** en el plan, con preguntas cerradas y un responsable:

```markdown
## G3 — prueba de uso (responsable: X, 10 min)
- [ ] pregunta concreta, respondible con sí o no
```

### La regla corta

> Si te importa y no se puede testear, **escribilo igual como gate humano**.
> Lo que no está en el plan, no lo construye nadie.

Y una advertencia sobre las decisiones cerradas del §7: cerrar decisiones evita que el
agente improvise, pero **cada simplificación que cerrás también achica el resultado**.
"Sin pathfinding, todos los fantasmas iguales" hizo el plan ejecutable **y** el juego
aburrido. Cerrá lo que hace falta para que la tarea sea ejecutable, no más.

## 8c. Los tests van antes, no después

Medido en 14 tareas: **el agente implementa bien lo que está especificado y escribe mal
los tests.** Cuatro veces escribió tests con los nombres exigidos cuyos asserts pasaban
igual con el código viejo.

No es descuido: escribir un test que distinga exige imaginar **el caso donde el código
nuevo y el viejo se comportan distinto**. Eso es razonamiento contrafáctico, y es
justamente lo que un modelo de 30B no hace.

**Entonces el test es parte de la especificación, no del trabajo.**

| Forma vieja | Forma nueva |
|---|---|
| "Implementá X y escribí tests" | "Estos tests fallan; hacelos pasar" |
| El agente decide qué verificar | El test define el contrato, sin ambigüedad |
| El gate verifica lo que el agente quiso | El gate verifica lo que vos querías |

Escribir el test primero cuesta más al planificar y **elimina la clase de falla más difícil
de detectar**. Además fuerza a que el criterio de terminado sea real: si no podés escribir
el test, la tarea no estaba bien entendida.

Ejemplo del caso que hizo falta para T13 (BFS contra Manhattan codicioso): un laberinto
donde la vecina que más acerca en línea recta es un callejón.

```
#######
#...#P#     Desde (1,1) hacia (1,5): la vecina (1,2) baja el Manhattan de 5 a 3
#.###.#     pero muere en el callejón. El BFS elige (2,1), que parece alejarse,
#.....#     y llega en 8 pasos dando la vuelta.
#######
```

El assert es `mover(...) == (2,1)`, no "se movió". **Eso** distingue.

## 9. Qué no delegar nunca

- **Decisiones de arquitectura.** Ya lo dijimos, pero es el que más se viola.
- **Refactors que cruzan muchos archivos.** El modelo pierde el hilo a mitad de camino.
- **Debugging sutil**: concurrencia, estado compartido, condiciones de carrera.
- **Cualquier cosa donde el criterio importe más que el código.** Nombres de API
  públicas, contratos con terceros, decisiones de producto.
- **Lo que no sabés verificar.** Si no tenés forma de saber si está bien, delegarlo
  es acumular deuda.

Una tarea que falla dos veces te está diciendo algo: **o está mal especificada, o no
era delegable.** No la mandes una tercera vez.

---

## 10. Receta, de proyecto a primera tarea

1. **Escribí el objetivo en 4 líneas**, y qué NO es parte. Lo segundo importa más.
2. **Listá las decisiones abiertas** y cerralas. Cada una, una línea con su porqué.
3. **Dibujá los módulos y quién depende de quién.** Texto plano alcanza.
4. **Cortá por costuras** (módulo, contrato, capa, caso de uso), no por capas horizontales.
5. **Ordená por dependencias** y agrupá en etapas paralelizables.
6. **Marcá los choques de archivo**: las que escriben el mismo archivo van en serie.
7. **Escribí la primera tarea entera.** Si no podés escribir su criterio de terminado
   en tres líneas verificables, volvé al paso 4.
8. **Construí el gate antes de lanzar nada.** Sin juez no hay tarea terminada.
9. **Hacé vos la primera tarea**, a mano o con modelo grande. Queda como referencia de
   calidad: el agente va a imitar lo que ya está.
10. **Lanzá la segunda con un agente** y mirá qué sale. Ajustá el formato de tarea con
    lo que aprendas, antes de lanzar diez.

El paso 9 es el que más se saltea y el que más rinde: **un modelo chico imita mucho
mejor de lo que inventa.** Si el repo ya tiene un módulo bien hecho con sus tests, las
tareas siguientes salen parecidas.

---

## 11. Cómo saber si la descomposición fue buena

Medilo, no lo intuyas:

| Métrica | Qué significa |
|---|---|
| **Gate verde al primer intento > 60%** | la descomposición funciona |
| **Entre 30% y 60%** | tareas demasiado grandes o criterios flojos |
| **Menos del 30%** | el problema está en el plan, no en el modelo |
| **Revisar toma más que hacerlo a mano** | esa clase de tarea no conviene delegarla |

La última fila es la más honesta de todas: **no todo conviene delegar**, y el método
sirve tanto para decidir qué sí como para ejecutar lo que sí.

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
| Archivos que toca | 1 o 2 | 5+ |
| Objetivo | una frase sin "y" | una lista |
| Criterio de terminado | 3 a 6 condiciones verificables | "que funcione" |
| Tiempo humano equivalente | 30 a 90 minutos | una tarde |
| Contexto que necesita leer | 1 o 2 archivos + el plan | medio repo |
| Decisiones que debe tomar | ninguna | "elegí la mejor forma de..." |

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

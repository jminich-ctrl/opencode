# Bitácora — qué pasó al usar esto de verdad

Registro de las corridas reales. Sirve para dos cosas: ver el método funcionando con
números, y no volver a tropezar con lo mismo.

---

## 2026-09-20 · Primera corrida (T02 + T03 en paralelo)

**Entorno:** OpenCode 1.18.30 · Qwen3.8-27B FP8 como `build` · los 4 modelos calientes.

### Qué se rompió

**1. Dos `opencode run` en paralelo → `Error: database is locked`**

T03 murió a los 2 segundos. OpenCode guarda sesiones en una sola SQLite
(`~/.local/share/opencode/opencode.db`) y dos procesos se pelean por el lock.

*Arreglo:* cada tarea con su propio `XDG_DATA_HOME` dentro del worktree.
*Verificado después:* 3 `opencode run` simultáneos, las tres terminan bien.
*Importante:* aislar solo `XDG_DATA_HOME`, **nunca** `XDG_CONFIG_HOME`, o las tareas
se quedan sin provider ni modelos.

**2. El gate daba VERDE sobre una tarea que no se hizo**

Como T03 murió sin tocar nada, el gate encontró la suite en verde, no vio cambios, y
lo reportó como éxito con un simpático "¿todavía no empezaste?".

*Arreglo:* sin cambios = ROJO.
*Lección:* **un gate que aprueba una tarea vacía es peor que no tener gate**, porque da
confianza falsa. Todo gate necesita un caso "no se hizo nada" y tiene que fallar ahí.

**3. Las tareas ya hechas figuraban "pendiente"**

`estado.sh` deducía el estado solo de la existencia del worktree, así que T01 —hecha y
mergeada— aparecía como pendiente.

*Arreglo:* leer el `**Estado:** ✅` del archivo de tarea.

### Qué salió bien

- Los worktrees: dos tareas, dos ramas, cero interferencia.
- El gate atrapó un error humano: al escribir los tests de T01 puse `(2,2)` como celda
  libre cuando es pared. **El primer bug que encontró el gate fue mío, no del agente.**

### Final de la corrida: las dos tareas fallaron, y el gate igual dijo verde

T02 esperó **20 minutos** al 27B (que se había enfriado por el mantenimiento) y murió con
`{"message":"inference timed out or returned no result"}`. T03 ya había muerto por el lock
de SQLite. Ninguna tocó un archivo.

Y sin embargo las dos reportaron **GATE VERDE**. Tres causas encadenadas, las tres
instructivas:

**4. El worktree congela el código al momento de crearse**

Arreglé `gate.sh` (sin cambios = rojo) *después* de crear los worktrees, así que las
tareas corrieron con la versión vieja del gate. Un worktree se crea desde `HEAD`: lo que
no está commiteado no viaja.

*Arreglo:* commitear los cambios de herramientas **antes** de lanzar. Queda avisado en el runner.

**5. Editar un script de bash mientras corre lo rompe**

`scripts/correr-tarea.sh: line 57: unexpected EOF`. Bash lee el script por partes mientras
lo ejecuta: si lo editás en el medio, sigue leyendo desde un offset que ya no corresponde.

*Arreglo:* no tocar un script en ejecución. Si hay que arreglarlo, se para, se edita y se relanza.

**6. Un error del agente tiene que ganarle al gate**

El gate mira el repo, no al agente. Si el agente nunca llegó a trabajar, el gate ve un
repo sano y aprueba. Ahora el runner marca ROJO si el log tiene un error de OpenCode
(`Error:`, `inference timed out`, `database is locked`), sin importar lo que diga el gate.

*Lección general:* **cada verificador tiene un punto ciego, y el punto ciego del gate es
todo lo que pasa fuera del repo.** Por eso hacen falta las dos señales: que el agente
haya terminado bien, y que el repo quede verde.

### Interrumpida

La corrida se cortó porque el equipo de la plataforma se puso a recargar modelos y todo
quedó frío. Regla que ya aprendimos tres veces: **no medir ni sacar conclusiones mientras
la plataforma está en mantenimiento.**

Pendiente para la próxima: relanzar T02 y T03 con los arreglos puestos, y medir la
concurrencia real por modelo antes de decidir cuántas tareas lanzar juntas.

---

---

## 2026-09-21 · Segunda corrida: el agente mintió sobre el gate

Con el ejecutor cambiado a Qwen3-Coder-30B (ver abajo), **las dos tareas por fin
produjeron código**: T02 escribió `entidades.py` + tests, T03 `juego.py` + tests.
Las dos con el gate en rojo por tests que fallan, que es el ciclo normal.

Pero apareció algo peor que un test roto:

**7. El agente afirmó "GATE VERDE" con el gate en rojo — y el runner le creyó**

En el log de T02:

```
línea  392: GATE ROJO (1 fallo/s)
línea  655: GATE ROJO (1 fallo/s)
línea  745: GATE ROJO (1 fallo/s)
línea 1262: "El gate.sh indica \"GATE VERDE\" (todos los criterios cumplidos)"   ← el agente
línea 1293: GATE ROJO (1 fallo/s)                                              ← el gate real
```

El modelo corrió el gate tres veces, lo vio fallar tres veces, y en su resumen final
escribió que estaba verde. Mi runner buscaba `GATE VERDE` en **todo** el log, así que
matcheó esa frase de la prosa del modelo y reportó la tarea como exitosa.

*Arreglo:* leer **solo** la salida del gate que corre el runner (después de `=== gate ===`),
nunca el log completo.

*Lección, y es la más importante de todas:* **la verificación nunca puede leer lo que el
agente escribe.** No alcanza con pedirle en `AGENTS.md` que no mienta — lo pide, y mintió
igual. El veredicto tiene que venir de ejecutar el comando, capturado en un lugar donde
el agente no pueda escribir.

Es el mismo principio que P2 del método, llevado un paso más lejos: no solo *el juez es
un comando*, sino que **la lectura del veredicto también tiene que estar fuera del alcance
del agente.**

### Sobre el cambio de ejecutor

Qwen3.8-27B (modelo "pensante") escribió 325 y 345 líneas de deliberación sin tocar un
solo archivo, en dos intentos. Cambiado a Qwen3-Coder-30B-A3B (instruct, sin modo
pensante), las dos tareas produjeron código en el primer intento.

**Razonador y ejecutor son perfiles distintos.** El mejor modelo del equipo no es
necesariamente el que tiene que implementar. El research posterior lo confirmó: el
candidato ideal para ejecutor es un modelo que *estructuralmente no puede* deliberar
(Qwen3-Coder-Next no genera bloques `<think>` en absoluto), no uno al que se le pide
por favor que no lo haga.

---

---

## 2026-09-21 · Cierre: el juego terminado

| Tarea | Quién | Intentos del agente | Resultado |
|---|---|---|---|
| T01 laberinto | humano | — | referencia de calidad, 15 tests |
| T02 movimiento | **agente** | 3 (deliberó ×2, tests mal ×1) | ✅ verde al 3º — **pero le faltaba el túnel** |
| T03 puntos | humano | 2 fallidos | el agente nunca llamó a `laberinto.comer()` |
| T04 fantasmas | humano | 1 sin terminar | el agente seguía explorando cuando cerré |
| T05–T08 | humano | — | modo asustado, vidas, render, loop |

**Tasa de gate verde al primer intento: 0 de 4.** Según el propio método
(`DESCOMPOSICION.md` §11), menos del 30% significa que **el problema está en el plan,
no en el modelo**. Y es cierto: T02 tenía una contradicción con el mapa, y las tareas
pedían escribir código *y* tests en el mismo paso, que es demasiado para un 27B.

### 8. Gate verde no significa tarea completa

T02 pasó el gate **sin implementar el túnel**, que su propia tarea pedía. Pudo hacerlo
porque el agente escribe el código *y* los tests: si omite un requisito entero, no hay
test que lo delate y el gate no tiene de dónde agarrarse.

*Lección:* **el gate verifica lo que los tests cubren, nada más.** Si el mismo agente
escribe ambos, el alcance queda sin verificar. Tres defensas posibles:
1. Que el criterio de terminado nombre **los tests que tienen que existir**
   (`test_tunel_izquierda_derecha`), y que el gate chequee que estén.
2. Separar en dos tareas: una escribe los tests, otra el código que los hace pasar.
3. Aceptarlo y confiar en G2 — que es lo que pasó acá: lo encontró la revisión humana.

### 9. El agente nunca commitea

Los archivos quedan sin trackear en el worktree, así que `git merge tarea/T02` no trae
nada. El integrador tiene que copiar a mano, o el runner debería commitear al dar verde.

### Lo que el ejercicio demostró

- **El método funciona**: el gate atrapó todo lo que tenía que atrapar, incluida una
  mentira del agente y un error mío en los tests de T01.
- **Las tareas estaban mal dimensionadas**: "escribí el módulo y sus tests" es dos
  tareas para un modelo de este tamaño.
- **La regla de no insistir es correcta**: T03 falló dos veces por la misma causa
  (no vaciar la celda). Hacerla a mano llevó 10 minutos.
- **Lo más valioso no fue el código, fueron los 9 hallazgos** de esta bitácora.

---

---

## 2026-09-21 · Post-mortem: el juego terminó verde y malo

Lo jugamos. Es malo. Con 54 tests en verde y las 8 tareas cerradas.

Lo que se ve en el primer minuto de juego:

| Problema | De dónde vino |
|---|---|
| Un solo fantasma | **plan**: el mapa tenía una sola `G` y ninguna tarea pidió cuatro |
| Pacman y el fantasma se atraviesan | **plan**: T05 decía "colisión" sin definir el intercambio de celdas |
| El fantasma se traba oscilando | **plan**: "Manhattan codicioso, sin pathfinding" fue decisión explícita |
| Se pierden teclas, se siente trabado | **plan**: T08 especificaba `getch()` una vez por turno de 150 ms |
| Los tests no detectaron nada | **método**: ninguno de los cuatro era testeable |

**Casi todo fue planificación, no ejecución.** Los agentes y el gate hicieron lo que
les pedimos; lo que les pedimos estaba incompleto.

### Los dos errores de fondo

**1. Lo no verificable por comando se cayó del plan.** P2 exige criterios verificables,
y eso sesga la descomposición hacia lo testeable. "Que se sienta fluido", "que haya
varios fantasmas", "que el fantasma dé miedo" no pasaban ese filtro, así que no entraron
en ninguna tarea — y nadie los construyó. El gate verde dio sensación de terminado.

**2. Saltamos nuestro propio G3.** El plan decía, textual: *"integración: gate completo
sobre el tronco, **más una partida real jugada a mano**"*. Corrimos simulaciones
automáticas, vimos que no explotaba, y dimos el juego por terminado. La partida a mano
habría encontrado los cinco problemas en 60 segundos.

**3. Cada simplificación achicó el resultado.** Las "decisiones tomadas" evitan que el
agente improvise — y funcionan. Pero "sin pathfinding, todos los fantasmas iguales,
turnos en vez de reloj" hicieron el plan ejecutable **y** el juego aburrido. Cerrá lo
necesario para que la tarea sea ejecutable, no más.

### Qué cambió en el método

- `METODO.md` P2: **lo que no es verificable por comando no desaparece del proyecto,
  desaparece del plan.** Con la defensa: convertirlo en gate humano explícito.
- `METODO.md` G3: la prueba de uso es parte del gate, con preguntas concretas y responsable.
- `DESCOMPOSICION.md` §8b: la lista de preguntas cualitativas para pasarle al plan
  antes de lanzar, y la advertencia sobre simplificar de más.
- `plantillas/PLAN.md`: G3 viene con checklist de prueba de uso.
- `plantillas/TAREA.md`: sección de verificación humana.

**El Pacman quedó como está a propósito**, como evidencia. Un ejemplo que saliera bien
enseñaría menos que este.

---

---

## 2026-09-21 · Segunda vuelta (T09–T12): iterar sobre lo que ya existe

Cuatro tareas en paralelo con las lecciones aplicadas: contratos explícitos,
**nombres de tests obligatorios** en el criterio, y verificación humana declarada.

| Tarea | Archivo | Gate 1er intento |
|---|---|---|
| T09 cruce de celdas | `juego.py` | ✅ verde |
| T10 fantasmas con personalidad | `entidades.py` | ✅ verde |
| T11 control fluido | `__main__.py` | ✅ verde |
| T12 colores y marcador | `render.py` | ✗ rojo **por culpa del gate** |

**3 de 4 al primer intento, contra 0 de 4 en la primera vuelta.** Y los **10 tests
exigidos por nombre existen todos**: pedirlos explícitamente cerró el agujero del túnel.

### 10. Las reglas de alcance hardcodeadas envejecen

T12 hizo todo bien y el gate la rechazó: tenía escrito a mano *"render.py solo se toca
en T07"*, de la primera vuelta. *Arreglo:* el gate ahora **lee los archivos permitidos
del propio archivo de tarea** (`**Archivos que podés tocar:**`). Una regla que se deduce
del plan no queda vieja cuando el plan crece.

### 11. Cinco bugs con todos los tests en verde — todos en la capa "no testeable"

*(62 tests al integrar la segunda vuelta; 73 al final, con los del loop.)*

Al jugarlo (el G3 que esta vez sí hicimos):

1. **El juego crasheaba al arrancar**: T11 pasaba `juego.asustados` donde va
   `direccion_pacman`. Argumento posicional mal puesto.
2. **Movía los fantasmas dos veces**: en su bucle propio y otra vez en `un_tick()`.
3. **Dormía sin leer el teclado** — justo lo que T11 venía a arreglar.
4. **La pantalla de fin se cerraba sola**: las teclas encoladas de la partida hacían que
   el `getch()` final devolviera al instante.

Más uno de T12: `dibujar()` reventaba fuera de curses, cuando su tarea pedía
"degradar con elegancia".

**Ninguno lo vieron los tests, porque `__main__.py` y `render.dibujar()` no tenían.**
La excusa era "necesita una terminal de verdad".

*Arreglo:* `tests/test_loop.py` con una **pantalla falsa** — un objeto que imita lo poco
que el loop usa de curses (`getch`, `addstr`, `getmaxyx`, `refresh`, `nodelay`). Once
tests que ejercitan armado, turnos, teclado, el loop entero y el fin de partida. **Los
cinco bugs habrían salido ahí.**

> **Cuando algo "no se puede testear porque necesita terminal, navegador o la nube",
> casi siempre se puede testear con un doble.** Lo que no se puede automatizar es *cómo
> se siente*, no *si arranca*.

### 12. El agente no hizo la verificación humana que su tarea pedía

T11 decía textual: *"jugá 1 minuto: es la única forma de verificar esto"*. El agente
reportó verde con los tests y nunca ejecutó el juego. Como con la mentira del gate: **una
instrucción de conducta no es una garantía.** Si la verificación humana importa, la hace
un humano — el agente no puede ni sabe.

### Lo que sigue abierto

- Los fantasmas se traban en las esquinas: es el defecto de fondo, y requiere revisar la
  decisión "sin pathfinding" del plan original.
- El emboscador puede apuntar fuera del mapa si Pacman está contra una pared.

---

## Plantilla para las próximas entradas

```markdown
## AAAA-MM-DD · <qué se corrió>

**Entorno:** <modelos, versiones, estado del cluster>

| Tarea | Gate 1er intento | Tiempo | Revisión | Notas |
|---|---|---|---|---|
| TNN | verde / rojo | Xm | mergeada / relanzada | |

**Tasa de verde al primer intento:** X de Y
**Qué se rompió:**
**Qué ajustamos en el método:**
```

Esa tabla es la que dice si la descomposición está bien: si el verde al primer intento
baja del 60%, el problema está en cómo escribís las tareas, no en el modelo.

# Pacman — reglas del proyecto

Hereda las reglas de `../AGENTS.md`. Además:


> Estas reglas son del método y valen para todo proyecto. Están copiadas acá, y no
> sólo en la raíz del repo, porque **el agente trabaja con el directorio de trabajo
> en este proyecto y lee ESTE archivo**. Las tres faltas más graves de la primera
> corrida —dos agentes editando su propio test y uno declarando haber escrito un
> test que nunca escribió— estaban prohibidas en un archivo que ninguno abrió.

## Reglas duras

1. **No toques archivos fuera de los declarados** en "Archivos que podés tocar".
   Si necesitás tocar otro, pará y decilo en la respuesta.
2. **No agregues dependencias que el proyecto no declare.** La lista vive en el
   `AGENTS.md` del proyecto; si ese archivo no declara ninguna, es biblioteca estándar y
   nada más. Una dependencia que no está en la lista se pide, no se agrega: pará y decilo.
3. **No toques un test para que pase.** Si un test falla, el que está mal es el código.
   Si el test está realmente mal, decilo y no lo cambies.
4. **No borres código que no entendés.** Preguntá.
5. **Si encontrás un bug fuera del alcance**, reportalo al final de tu respuesta.
   No lo arregles.
6. **Si el plan está mal**, pará y decilo. No improvises un rediseño.
7. **Si la tarea es imposible o se contradice** —los tests piden algo que el objetivo
   prohíbe, falta algo sin lo cual no se puede hacer, el contrato no cierra— escribí
   `IMPOSIBLE: <motivo en una línea>` y **pará ahí**. No es una falla y no te lo vamos a
   contar como error: es la información más útil que podés darnos. Lo que sí es una falla
   es hacer pasar el test de una forma que no resuelve el problema.

8. **No commitees nada generado.** `__pycache__/`, un `.pyc`, `dist/`: si aparecen en el
   diff el gate da rojo, y no por el contenido sino porque nadie puede revisar lo que no
   escribió una persona. Las dependencias instaladas —`node_modules/`, `.venv`— las pone el
   método antes de lanzarte y el gate las filtra, así que por ésas no te va a dar rojo: lo
   que no tenés que hacer es correr `pip` o `npm` (regla 2).
9. **No rompas tests que andaban.** El gate compara contra la lista de los que ya fallaban
   antes de tu tarea: si uno que pasaba deja de pasar, es tuyo, aunque no hayas tocado su
   archivo.
10. **No claves rutas absolutas en un test.** Una ruta absoluta —`/Users/...`— pasa sólo en
    la máquina donde se escribió. Las rutas se escriben desde la raíz del proyecto.
11. **Si tu implementación tiene una rama que ningún test distingue, decilo.** El gate muta
    tu código línea por línea y exige que la suite lo note: cuando **sobreviven mutantes**
    es que escribiste comportamiento que nadie verifica, y la salida dice en qué línea.

12. **No mockees lo que vinieron a probar.** Si mockeás un símbolo que vive en un archivo
    de TU tarea, estás reemplazando el sujeto: el gate lo nota porque las líneas de la
    implementación no se ejecutan. Mockeá lo de abajo, no la tarea.

## Convenciones

- Coordenadas **siempre** `(fila, columna)`, enteras, origen arriba a la izquierda.
- El núcleo (`laberinto`, `entidades`, `juego`) **no imprime ni lee teclado**. Nada de
  `print()` ni `input()` ahí: si necesitás depurar, escribí un test.
- Todo lo visual vive en `render.py`, y `render.py` solo lee el estado, nunca lo modifica.
- El tiempo avanza por `tick()`, no por reloj. Sin `random` en el núcleo: los tests
  dependen de que todo sea determinista.
- Biblioteca estándar únicamente. `curses` está permitido solo en `render.py` y `__main__.py`.

## Tests

    bash scripts/gate.sh

Un test por comportamiento, nombre en español que diga qué verifica
(`test_comer_dos_veces_la_misma_celda`, no `test_comer_2`).

`tests/test_laberinto.py` es la referencia de calidad: mirá cómo cubre los casos borde
antes de escribir los tuyos.

## Lo que más se rompe acá

- Meter lógica de juego en `render.py` → el gate lo rechaza.
- Usar `(x, y)` en vez de `(fila, columna)` → confunde todo el resto del código.
- Tests que pasan igual contra el código viejo → no prueban nada, el gate no los detecta,
  los detecta la revisión humana.

## Si te toca escribir los tests de una tarea

A veces se te pide la tarea completa —implementación **y** tests— y de ese trabajo nos
quedamos **sólo con los tests**: la implementación la escribe otro agente desde cero. Así
que los tests son el entregable y tienen que ser buenos.

- Cada test tiene que **fallar** si la implementación no hace lo que dice el alcance, y
  tiene que **distinguir**: un assert que pasaría igual con el código de antes no sirve de
  nada. Nada de `assertTrue(len(x) > 0)`.
- El agrupador que te pidan: en un `.py` es una clase `class <Nombre>`; en un `.test.ts`,
  un bloque `describe('<Nombre>', ...)`.
- **Los tests corren con el directorio de trabajo en la RAÍZ del proyecto**, no en la
  carpeta del archivo de test. Toda ruta que abras se escribe desde ahí:
  `backend/app/x.py`, `frontend/package.json`. Nunca `package.json` ni `../package.json`.
- Si para verificar algo necesitás un archivo de prueba —un módulo de ejemplo, un fixture
  en disco—, creálo **dentro** del test y borralo en un `finally`. No lo agregues al repo:
  cualquier archivo que quede cae fuera del alcance de la tarea.
- Antes de decir que terminaste, corré la suite con el comando que te indiquen y mostrá su
  salida real. Si tu test no pasa contra tu propia implementación, uno de los dos está mal
  y lo arreglás vos.

## Antes de decir que terminaste

1. Corré `bash scripts/gate.sh` y mostrá la **salida real**, sin resumirla.
2. Si el gate está rojo, no digas que terminaste. Arreglalo o explicá por qué no podés.
3. Cerrá con un resumen de 3 líneas: qué cambiaste, cómo lo verificaste, qué quedó pendiente.

**Nunca digas que corriste algo que no corriste.** Es la única falta que invalida
todo el trabajo: si no podemos confiar en lo que reportás, hay que revisar todo a mano.

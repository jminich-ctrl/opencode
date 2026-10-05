# Pacman — reglas del proyecto

Hereda las reglas de `../AGENTS.md`. Además:

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

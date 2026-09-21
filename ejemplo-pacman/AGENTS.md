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

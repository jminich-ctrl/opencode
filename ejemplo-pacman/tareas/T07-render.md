# T07 — Render con curses

**Estado:** ✅ hecha — a mano
**Depende de:** T06
**Archivos que podés tocar:** `src/pacman/render.py`, `tests/test_render.py`
**Prohibido tocar:** todo el resto de `src/pacman/`

## Objetivo

Dibujar el estado del juego en la terminal. **Sin lógica de juego acá adentro.**

## Alcance

Entra:
- `dibujar(pantalla, juego, pacman, fantasmas)`: pinta laberinto, entidades, puntaje y vidas.
- `componer(juego, pacman, fantasmas) -> list[str]`: arma las líneas como texto puro.
  Esta función **no usa curses**, y es la que se testea.
- Manejo de terminal chica: si no entra, mostrar un mensaje en vez de reventar.

No entra:
- Teclado y loop (T08).
- Cualquier decisión de juego: este módulo solo lee.

## Criterio de terminado

- [ ] `componer()` tiene tests (no requiere curses)
- [ ] Pacman y los fantasmas aparecen en su celda correcta
- [ ] Una terminal de 5x5 no hace crashear el programa
- [ ] `render.py` no importa `juego` ni `entidades` para modificarlos, solo para leer
- [ ] `bash scripts/gate.sh` en verde (correlo con `TAREA=T07`)

## Verificación

    TAREA=T07 bash scripts/gate.sh

## Nota de entorno

`curses` se porta distinto según la terminal. La parte visual se prueba **a mano**,
no por gate: `python3 -m src.pacman` y mirar.

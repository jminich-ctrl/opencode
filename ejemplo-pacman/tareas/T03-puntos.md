# T03 — Puntos y pastillas de poder

**Depende de:** T01
**Archivos que podés tocar:** `src/pacman/juego.py`, `tests/test_juego.py`
**Prohibido tocar:** `src/pacman/laberinto.py`, `src/pacman/entidades.py`, `src/pacman/render.py`

## Objetivo

El juego lleva el puntaje y sabe cuándo se limpió el nivel.

## Alcance

Entra:
- Clase `Juego` con `puntaje` y `nivel_limpio()`.
- `comer_en(pos)`: suma 10 por punto, 50 por pastilla, 0 por celda vacía.
- Comer una pastilla deja registrado que hay que activar el modo asustado
  (el modo en sí es T05: acá solo se expone el hecho).

No entra:
- Fantasmas, modo asustado, vidas (T05 y T06).
- Movimiento (T02).

## Contrato

    class Juego:
        def __init__(self, laberinto)
        puntaje: int
        def comer_en(self, pos: tuple[int, int]) -> str   # lo que se comió
        def nivel_limpio(self) -> bool
        ultima_pastilla: bool    # True si el último comer_en fue una pastilla

## Criterio de terminado

- [ ] Comer un punto suma 10; una pastilla, 50; una celda vacía, 0
- [ ] Comer la misma celda dos veces suma una sola vez
- [ ] `nivel_limpio()` es True solo cuando no quedan puntos ni pastillas
- [ ] Los tests nuevos fallan si se revierte `juego.py` (verificalo)
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

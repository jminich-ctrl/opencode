# T16 — La fruta

**Depende de:** T03, T05, T06 (hechas)
**Archivos que podés tocar:** `src/pacman/juego.py`
**Prohibido tocar:** `tests/` (los tests ya están escritos), `laberinto.py`, `entidades.py`, `render.py`, `__main__.py`

> **Los tests ya están escritos y fallan** (`tests/test_juego.py`, clase `TestFruta`).
> Hacelos pasar **sin modificarlos**. Si te parece que un test está mal, pará y decilo.

## Objetivo

Una fruta que aparece al llegar a 300 puntos, vale 100 y caduca a los 50 turnos.

## Alcance

Entra:
- `Juego.fruta`: la celda donde está, o `None` si no hay.
- Al pasar de 300 puntos aparece **una vez**, en una celda libre y sin punto.
- `comer_en(pos)` sobre la celda de la fruta devuelve `"fruta"`, suma 100 y la saca.
- `tick()` le descuenta vida: a los 50 turnos desaparece sola.
- Determinista: sin `random`. Elegí la celda libre con una regla fija y documentala.

No entra:
- Dibujarla (eso sería otra tarea, en `render.py`).
- Más de una fruta, ni que reaparezca sola después de comida.

## Contrato

    fruta: tuple[int, int] | None
    UMBRAL_FRUTA = 300
    TURNOS_FRUTA = 50

## Criterio de terminado

- [ ] Los 6 tests de `TestFruta` pasan, **sin tocarlos**
- [ ] Los 86 tests que ya existían siguen pasando
- [ ] `bash scripts/gate.sh` en verde

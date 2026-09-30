# T17 — El cruce mal detectado le cuesta vidas a Pacman

**Depende de:** T09 (hecha)
**Archivos que podés tocar:** `src/pacman/juego.py`
**Prohibido tocar:** `tests/` (los tests ya están escritos), `entidades.py`, `laberinto.py`, `render.py`, `__main__.py`

> **Los tests ya están escritos y uno falla** (`tests/test_juego.py`, clase
> `TestCruceFalsosPositivos`). Hacelo pasar **sin tocarlos**.

## El bug

Lo encontró el subagente `@reviewer` revisando `juego.py`, y 92 tests no lo habían visto.

En `colision()`, la detección de cruce mira sólo si el fantasma quedó en la celda que Pacman
dejó:

```python
if pos_anterior is not None and fantasma.pos == pos_previa_pacman:
```

**Falta verificar de dónde vino el fantasma.** Un cruce es un intercambio: el fantasma tiene
que haber salido de la celda donde Pacman está **ahora**. Como está, un fantasma que
simplemente camina hacia atrás de Pacman —siguiéndolo— cuenta como cruce y **Pacman pierde
una vida sin que nadie lo toque**.

## Objetivo

Que sólo cuente como cruce el intercambio real de celdas.

## Alcance

Entra:
- Exigir las dos condiciones: el fantasma quedó en la celda previa de Pacman **y** venía de
  la celda actual de Pacman.
- Todo lo demás de `colision()` queda igual: misma celda, modo asustado, puntajes, vidas.

No entra:
- Cambiar quién llama a `colision()` (eso está en `__main__.py`).
- Tocar los tests.

## Criterio de terminado

- [ ] Los 4 tests de `TestCruceFalsosPositivos` pasan, **sin tocarlos**
- [ ] Los 92 tests que ya existían siguen pasando
- [ ] `bash scripts/gate.sh` en verde

## Nota

`@reviewer` reportó un segundo hallazgo en `__main__.py` (que se pasa `pacman.pos` como
posición previa). **Ese es falsa alarma**: en esa segunda llamada Pacman no se movió, así
que su posición previa es la actual, y el caso ya lo cubre la detección de misma celda.
No lo toques.

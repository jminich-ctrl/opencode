# T40 — Pausar la partida

**Estado:** ✅ hecha
**Depende de:** T06 (hecha)
**Archivos que podés tocar:** src/pacman/juego.py
**Prohibido tocar:** `tests/` (los tests ya están escritos), `laberinto.py`, `entidades.py`, `render.py`, `__main__.py`

## Objetivo

Que la partida se pueda pausar: en pausa, el paso del tiempo no avanza.

## Alcance

Entra:
- Un atributo `pausado`, que arranca en `False`.
- Un método `alternar_pausa()` que lo da vuelta.
- Que `tick()` no haga nada mientras está en pausa.

No entra:
- La tecla que la activa (eso es del bucle, y no es esta tarea).
- Pausar el movimiento de los fantasmas: el bucle no los mueve si está en pausa.

## Tests

> **Si te toca IMPLEMENTAR, esta sección no es trabajo tuyo.** El archivo de test ya
> existe en el repo y **no podés tocarlo** —el gate lo verifica—. Lo que sigue es para
> quien escribió los tests, y está acá sólo para que puedas leer contra qué te juzgan.

Los tests de esta tarea se escriben **antes** que la implementación, en una corrida aparte. Si te toca implementar, ya están en el repo y fallan; si te toca escribirlos, **todavía no existen y los estás creando vos**. Archivo: `tests/test_pausa.py`, clase `TestPausa`.

## Criterio de terminado

- [ ] `juego.pausado` arranca en `False` y `alternar_pausa()` lo da vuelta.
- [ ] `tick()` no consume el modo asustado mientras está en pausa.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    python3 -m unittest discover -s tests -t . -q

## Si algo no cierra

Si encontrás un bug fuera del alcance: reportalo en la respuesta, NO lo arregles.
Si la tarea es imposible o se contradice, escribí `IMPOSIBLE: <motivo>` y pará.

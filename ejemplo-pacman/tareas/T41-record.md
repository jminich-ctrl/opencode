# T41 — Récord de puntaje

**Estado:** pendiente   ← al mergearla: `✅ hecha` (`estado.sh` lee esta línea)
**Depende de:** T03 (hecha)
**Archivos que podés tocar:** src/pacman/juego.py
**Prohibido tocar:** `tests/`, `laberinto.py`, `entidades.py`, `render.py`, `__main__.py`

## Objetivo

Que la partida recuerde el puntaje más alto alcanzado, aunque después se pierdan vidas.

## Alcance

Entra:
- Un atributo `record`, que arranca en 0.
- Que se actualice solo cuando el puntaje lo supera.
- Que **no baje nunca**, ni al perder una vida ni al reiniciar posiciones.

No entra:
- Guardarlo en disco entre partidas.
- Mostrarlo en pantalla (eso es del render).

## Tests (los escribe el tester)

Archivo: `tests/test_record.py`, clase `TestRecord`.

## Criterio de terminado

- [ ] `record` arranca en 0 y sigue al puntaje cuando sube.
- [ ] `record` no baja al perder una vida.
- [ ] `bash scripts/gate.sh` en verde.

## Verificación

    python3 -m unittest discover -s tests -t . -q

## Si algo no cierra

Si la tarea es imposible o se contradice, escribí `IMPOSIBLE: <motivo>` y pará.

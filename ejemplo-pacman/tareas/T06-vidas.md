# T06 — Vidas y fin de partida

**Estado:** ✅ hecha — a mano
**Depende de:** T05
**Archivos que podés tocar:** `src/pacman/juego.py`, `tests/test_juego.py`
**Prohibido tocar:** `src/pacman/entidades.py`, `src/pacman/laberinto.py`, `src/pacman/render.py`

## Objetivo

Pacman tiene 3 vidas; cuando se acaban, la partida termina.

## Alcance

Entra:
- `vidas` arranca en 3.
- Perder una vida reposiciona a Pacman y a los fantasmas en sus inicios y apaga el modo asustado.
- `terminado()` es True si `vidas == 0` o si el nivel está limpio.
- `resultado()` devuelve "ganó" | "perdió" | None.

No entra:
- Niveles nuevos tras ganar.
- Cualquier cosa visual.

## Criterio de terminado

- [ ] Perder las 3 vidas termina la partida con "perdió"
- [ ] Limpiar el nivel termina la partida con "ganó"
- [ ] Al perder una vida, todas las entidades vuelven a su inicio
- [ ] Al perder una vida, el modo asustado queda apagado
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

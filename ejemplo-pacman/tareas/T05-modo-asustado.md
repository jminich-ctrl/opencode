# T05 — Modo asustado y capturas

**Estado:** ✅ hecha — a mano
**Depende de:** T03, T04
**Archivos que podés tocar:** `src/pacman/juego.py`, `tests/test_juego.py`
**Prohibido tocar:** `src/pacman/entidades.py`, `src/pacman/laberinto.py`, `src/pacman/render.py`

## Objetivo

Comer una pastilla vuelve a los fantasmas comestibles por una cantidad de ticks.

## Alcance

Entra:
- Al comer una pastilla, el modo asustado dura 20 ticks.
- `tick()` descuenta el modo asustado.
- Colisión Pacman-fantasma: en modo asustado el fantasma vuelve a su inicio y suma 200;
  fuera del modo, Pacman pierde (esto lo consume T06).
- Comer fantasmas seguidos en el mismo modo duplica: 200, 400, 800, 1600.

No entra:
- Vidas ni fin de partida (T06).

## Contrato

    class Juego:
        asustado_restante: int
        def tick(self) -> None
        def colision(self, pos_pacman, fantasmas: list) -> str   # "comio" | "perdio" | "nada"

## Criterio de terminado

- [ ] El modo dura exactamente 20 ticks y después se apaga
- [ ] Comer 4 fantasmas en un mismo modo suma 200+400+800+1600
- [ ] El multiplicador se reinicia al activarse un modo nuevo
- [ ] Fuera del modo, la colisión devuelve "perdio"
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

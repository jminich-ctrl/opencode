# T09 — Colisión cuando se cruzan

**Estado:** ✅ hecha — agente (verde al 1er intento)
**Depende de:** T05, T06 (ya hechas)
**Archivos que podés tocar:** `src/pacman/juego.py`, `tests/test_juego.py`
**Prohibido tocar:** `entidades.py`, `laberinto.py`, `render.py`, `__main__.py`

## El problema

Hoy la colisión solo mira si Pacman y el fantasma quedaron **en la misma celda**. Si en
el mismo turno se intercambian —Pacman va a la celda del fantasma y el fantasma a la de
Pacman— pasan de largo sin tocarse. Jugando se ve feo: el fantasma te atraviesa.

## Objetivo

Que un cruce cuente como colisión.

## Alcance

Entra:
- `colision()` recibe además las posiciones **anteriores** de Pacman y de los fantasmas.
- Hay colisión si comparten celda **o** si se intercambiaron las celdas.
- Todo lo que ya hacía (comer fantasma con 200/400/800/1600, perder vida) sigue igual.

No entra:
- Tocar cómo se mueven (eso es `entidades.py`).
- El loop (eso es `__main__.py`, tarea T11).

## Contrato

    def colision(self, pos_pacman, fantasmas,
                 pos_previa_pacman=None, previas_fantasmas=None) -> str:
        """..."""

`previas_fantasmas` es un dict `{id(fantasma): pos_anterior}` o una lista paralela a
`fantasmas` — elegí una y documentala. Si no se pasan las previas, se comporta como antes
(solo misma celda): los tests que ya existen tienen que seguir pasando sin tocarlos.

## Criterio de terminado

Estos tests tienen que existir, **con estos nombres**:

- [ ] `test_cruce_cuenta_como_colision`
- [ ] `test_cruce_en_modo_asustado_come_al_fantasma`
- [ ] `test_sin_cruce_ni_misma_celda_no_pasa_nada`
- [ ] `test_sin_previas_se_comporta_como_antes`
- [ ] Los 54 tests que ya existen siguen pasando **sin modificarlos**
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

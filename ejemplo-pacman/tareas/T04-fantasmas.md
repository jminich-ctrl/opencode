# T04 — Fantasmas: persecución

**Estado:** ✅ hecha — a mano (el agente no terminó)
**Depende de:** T01, T02
**Archivos que podés tocar:** `src/pacman/entidades.py`, `tests/test_entidades.py`
**Prohibido tocar:** `src/pacman/juego.py`, `src/pacman/laberinto.py`, `src/pacman/render.py`

## Objetivo

Los fantasmas persiguen a Pacman con una regla simple y determinista.

## Alcance

Entra:
- Clase `Fantasma` con posición y dirección.
- `mover(laberinto, objetivo)`: elige, entre las vecinas libres, la que minimiza la
  distancia Manhattan al objetivo.
- No puede darse vuelta 180° salvo que sea la única salida (callejón).
- Desempate **estable**: si dos celdas empatan, gana la que viene primero en
  `vecinas_libres` (arriba, abajo, izquierda, derecha). Sin azar: los tests dependen de esto.

No entra:
- Modo asustado ni huida (T05).
- Personalidades distintas por fantasma: todos usan la misma regla.

## Contrato

    class Fantasma:
        def __init__(self, pos: tuple[int, int], direccion: tuple[int, int] = ARRIBA)
        pos: tuple[int, int]
        direccion: tuple[int, int]
        def mover(self, laberinto, objetivo: tuple[int, int]) -> tuple[int, int]

## Criterio de terminado

- [ ] En un pasillo recto, el fantasma se acerca al objetivo
- [ ] En un cruce, elige la celda que más lo acerca
- [ ] No se da vuelta 180° salvo en un callejón sin salida (hay test de las dos cosas)
- [ ] Con dos celdas empatadas, elige siempre la misma (test explícito del desempate)
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh

## Si algo no cierra

Nada de `random` en esta tarea. Si te parece que hace falta azar, el plan está mal: decilo.

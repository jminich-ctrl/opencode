# T08 — Loop de juego y teclado

**Estado:** ✅ hecha — a mano
**Depende de:** T07
**Archivos que podés tocar:** `src/pacman/__main__.py`
**Prohibido tocar:** todo el resto de `src/pacman/`

## Objetivo

Que el juego se pueda jugar: `python3 -m src.pacman`.

## Alcance

Entra:
- Armar laberinto, Pacman y fantasmas desde `mapas/clasico.txt`.
- Loop: leer teclado (flechas y WASD), avanzar un tick, dibujar, dormir ~150 ms.
- `q` sale. Al terminar la partida, mostrar el resultado y esperar una tecla.
- Restaurar la terminal al salir, incluso si hay una excepción.

No entra:
- Menús, pausa, niveles nuevos.

## Criterio de terminado

- [ ] `python3 -m src.pacman` abre el juego y se puede jugar
- [ ] `q` sale y deja la terminal usable
- [ ] Una excepción no deja la terminal rota
- [ ] `bash scripts/gate.sh` en verde

## Verificación

    bash scripts/gate.sh     # tests del núcleo
    python3 -m src.pacman    # prueba a mano: jugar 30 segundos

## Nota

Es la única tarea que no se puede verificar del todo por gate. La prueba es jugar.

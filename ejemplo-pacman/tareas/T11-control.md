# T11 — Control fluido y ritmo del juego

**Estado:** ✅ hecha — agente (verde al 1er intento; el loop se corrigió después, ver BITACORA.md, hallazgo 11)
**Depende de:** T08 (ya hecha)
**Archivos que podés tocar:** `src/pacman/__main__.py`
**Prohibido tocar:** todo lo demás de `src/pacman/`

## El problema

Jugando se siente trabado y se pierden teclas. La causa está en el loop: lee **una sola
tecla por turno** con `getch()`, y el turno dura 150 ms. Si apretás dos teclas rápido, la
segunda se descarta. Y si apretás justo después de que el turno empezó, esperás 150 ms.

Además todos se mueven a la misma velocidad, así que el modo asustado no cambia nada:
igual no los alcanzás.

## Objetivo

Que responda al instante y que el modo asustado se sienta.

## Alcance

Entra:
- **Vaciar el buffer de teclado en cada turno**: leer con `getch()` en un bucle hasta que
  devuelva `-1`, y quedarse con la **última** dirección válida. Así no se pierden teclas
  ni queda una vieja encolada.
- **Desacoplar entrada de turno**: dormir en tramos cortos (unos 20 ms) leyendo el teclado
  en cada tramo, en vez de un `sleep` largo a ciegas. Un giro pedido a mitad de turno se
  aplica en el turno siguiente, no dos después.
- **Fantasmas más lentos cuando están asustados**: se mueven 1 de cada 2 turnos.
- Pasar a `Fantasma.mover()` la dirección de Pacman y si están asustados (T10 los usa).
- Chequear la colisión **antes y después** de mover a los fantasmas, pasando las
  posiciones previas (T09 las usa).

No entra:
- Cambiar la lógica de los fantasmas (T10) ni la de colisión (T09).
- Colores (T12).

## Criterio de terminado

- [ ] `python3 -m src.pacman` se juega y responde al apretar una tecla sin demora perceptible
- [ ] Apretar dos direcciones rápido no pierde la segunda
- [ ] En modo asustado los fantasmas se mueven notoriamente más lento
- [ ] `q` sale y deja la terminal usable; una excepción tampoco la rompe
- [ ] `bash scripts/gate.sh` en verde (los tests del núcleo siguen pasando)

## Verificación

    bash scripts/gate.sh
    python3 -m src.pacman     # y jugá 1 minuto: es la única forma de verificar esto

## Nota

Esta tarea **no se puede verificar del todo por gate**: lo que mejora es cómo se siente.
El criterio real es jugarlo. Si no podés jugarlo, dejá anotado qué no pudiste verificar.

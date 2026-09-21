# T12 — Presentación: colores y marcador

**Estado:** ✅ hecha — agente (rojo al 1er intento por una regla vieja del gate, ver BITACORA.md, hallazgo 10)
**Depende de:** T07 (ya hecha)
**Archivos que podés tocar:** `src/pacman/render.py`, `tests/test_render.py`
**Prohibido tocar:** todo lo demás de `src/pacman/`

## El problema

Todo se dibuja en un solo color y con los mismos caracteres: el laberinto, los puntos,
Pacman y los fantasmas. Cuesta distinguir qué es qué mientras jugás, y el marcador es
una línea suelta al pie.

## Objetivo

Que se lea de un vistazo quién es quién y cómo va la partida.

## Alcance

Entra:
- **Colores con curses** (`curses.init_pair`), si la terminal los soporta: paredes en
  azul, puntos en blanco, pastillas en amarillo, Pacman en amarillo brillante, fantasmas
  en rojo y en azul cuando están asustados.
- **Degradar con elegancia**: si la terminal no tiene color (`curses.has_colors()` es
  falso), dibuja como antes sin romperse.
- **Marcador mejor**: puntaje, vidas como símbolos repetidos (`♥♥♥` o `CCC`), y cuando el
  modo asustado está activo, una barra que se vacía con los turnos que quedan.
- Los últimos 3 turnos del modo asustado **parpadean** los fantasmas (alternar entre dos
  caracteres según la paridad del contador), como aviso de que se termina.

No entra:
- Tocar la lógica del juego: `render.py` solo lee.
- Cambiar `componer()` de forma que rompa los tests que ya existen.

## Criterio de terminado

Estos tests tienen que existir, **con estos nombres**:

- [ ] `test_las_vidas_se_muestran_como_simbolos`
- [ ] `test_la_barra_de_asustado_se_vacia`
- [ ] `test_los_fantasmas_parpadean_al_final_del_modo`
- [ ] `test_componer_sigue_sin_usar_curses`
- [ ] Los tests de render que ya existen pasan **sin modificarlos**
- [ ] `bash scripts/gate.sh` en verde (correlo con `TAREA=T12`)

## Verificación

    TAREA=T12 bash scripts/gate.sh
    python3 -m src.pacman     # mirar que los colores no rompan nada

## Nota

`componer()` tiene que seguir devolviendo texto puro y testeable **sin curses**. Los
colores van en `dibujar()`, que es la parte que no se testea.

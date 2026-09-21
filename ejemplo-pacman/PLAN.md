# Plan — Pacman en Python

**Estado del gate G0:** aprobado por Jose · 2026-09-20

## Objetivo

Un Pacman jugable en la terminal, en Python puro (biblioteca estándar, `curses` para
dibujar). El núcleo del juego es lógica pura y testeable; el dibujo y el teclado viven
en una capa fina aparte.

No es parte: sonido, menús, múltiples niveles con mapas distintos, puntajes persistentes,
fantasmas con personalidades distintas (todos usan la misma estrategia).
*(La segunda vuelta revisó esto último: ver "Segunda vuelta" abajo.)*

## Decisiones tomadas

Estas no se vuelven a discutir. Si una tarea parece pedir lo contrario, el plan está mal:
pará y avisá.

- **Biblioteca estándar únicamente** — el juego tiene que correr en cualquier Python 3.11+
  sin instalar nada. Sin pygame.
- **Núcleo sin E/S** — `laberinto`, `entidades` y `juego` no imprimen ni leen teclado.
  Todo lo visual está en `render.py`. Es lo que hace que el juego sea testeable.
- **Coordenadas `(fila, columna)`**, enteras, origen arriba a la izquierda. Siempre en ese
  orden, en todo el código.
- **El tiempo avanza por turnos (`tick`)**, no por reloj. Un tick mueve a todos una celda.
  Hace el juego determinista y los tests reproducibles.
- **Los fantasmas persiguen con distancia Manhattan**, eligiendo la celda válida que más
  los acerca, con desempate estable. No hay pathfinding.
- **El mapa se escribe como texto** (`mapas/clasico.txt`), no en código.
- **La fila 9 del mapa es el túnel**: sus extremos están abiertos y el movimiento
  envuelve de un lado al otro. El resto de las filas tiene pared en los bordes.

## Arquitectura

```
src/pacman/
  laberinto.py    parsea el mapa de texto, dice qué celdas son pared y qué hay en cada una
  entidades.py    Pacman y Fantasma: posición, dirección, movimiento válido
  juego.py        estado: puntaje, vidas, modo asustado, fin de partida. Orquesta el tick
  render.py       dibuja con curses y lee el teclado. NO tiene lógica de juego
  __main__.py     arranque: arma todo y corre el loop

tests/            un archivo por módulo del núcleo
mapas/clasico.txt el mapa
```

Dependencias: `entidades` usa `laberinto`; `juego` usa las dos; `render` usa `juego`
solo para leer. Nadie depende de `render`.

## Tareas

| # | Tarea | Depende de | Archivos | Estado |
|---|---|---|---|---|
| T01 | Laberinto: parseo del mapa | — | `laberinto.py` | ✅ humano (referencia) |
| T02 | Movimiento de Pacman | T01 | `entidades.py` | ✅ agente (3er intento) + túnel a mano |
| T03 | Puntos y pastillas | T01 | `juego.py` | ✅ humano (agente falló 2 veces) |
| T04 | Fantasmas: persecución | T01, T02 | `entidades.py` | ✅ humano |
| T05 | Modo asustado y capturas | T03, T04 | `juego.py` | ✅ humano |
| T06 | Vidas y fin de partida | T05 | `juego.py` | ✅ humano |
| T07 | Render con curses | T06 | `render.py` | ✅ humano |
| T08 | Loop y teclado | T07 | `__main__.py` | ✅ humano |

**Resultado: juego terminado y jugable, 54 tests en verde.**
Tasa de gate verde al primer intento por agente: **0 de 4** (T02 verde al tercero).
El análisis está en [BITACORA.md](BITACORA.md).

### Segunda vuelta (plan v2, 2026-09-21)

Después de jugarlo (el G3 que la primera vuelta se salteó), cuatro tareas nuevas sobre lo
que ya existía. El mapa pasó a tener 4 fantasmas.

| # | Tarea | Depende de | Archivos | Estado |
|---|---|---|---|---|
| T09 | Colisión cuando se cruzan | T05, T06 | `juego.py` | ✅ agente, verde al 1er intento |
| T10 | Fantasmas con personalidad y huida | T04 | `entidades.py` | ✅ agente, verde al 1er intento |
| T11 | Control fluido y ritmo del juego | T08 | `__main__.py` | ✅ agente, verde al 1er intento (el loop se corrigió al jugarlo) |
| T12 | Presentación: colores y marcador | T07 | `render.py` | ✅ agente, rojo al 1er intento por una regla vieja del gate |

Las cuatro tocan archivos distintos y se lanzaron juntas. **3 de 4 verdes al primer
intento**, y 73 tests al final (con `tests/test_loop.py`, que prueba el loop con una
pantalla falsa). El análisis está en [BITACORA.md](BITACORA.md).

### Etapas de la primera vuelta

**Etapa 1 (en paralelo):** T02, T03 — las dos dependen solo de T01 y tocan archivos distintos
**Etapa 2:** T04 (necesita T02)
**Etapa 3:** T05, luego T06 — las dos tocan `juego.py`, van en serie
**Etapa 4:** T07, T08 — la capa visual, al final

> Ojo con T03 y T05: tocan el mismo archivo. Nunca lanzar en paralelo dos tareas que
> escriben el mismo archivo, aunque sus dependencias lo permitan.

## Gates

- **G0** este plan aprobado ✅
- **G1** por tarea: `bash scripts/gate.sh` verde (tests + alcance + higiene)
- **G2** revisión humana del diff, con `plantillas/REVISION.md`
- **G3** integración: gate completo sobre el tronco, más una partida real jugada a mano
  ⚠️ **Esta segunda parte se salteó, y por eso el juego terminó verde y malo.**
  Ver el post-mortem en [BITACORA.md](BITACORA.md).

## Riesgos

| Riesgo | Qué haríamos |
|---|---|
| El agente mete lógica de juego en `render.py` | El gate rechaza cualquier archivo que la tarea no declare en "Archivos que podés tocar" |
| Los fantasmas quedan tontos o imposibles | T04 define el desempate exacto; si no alcanza, se ajusta en una tarea aparte |
| `curses` se porta distinto en macOS | T07 es la única tarea con riesgo de entorno: se prueba a mano, no por gate |
| Dos tareas tocan `juego.py` y chocan | Van en serie, nunca en paralelo (ver etapas) |

# ejemplo-pacman

Un Pacman de terminal llevado adelante con el método de [`../METODO.md`](../METODO.md), con
agentes de OpenCode sobre modelos de ColabHive. Quedó como ejemplo trabajado **con todo lo
que salió mal a la vista**: un ejemplo que saliera bien enseñaría menos.

## Estado

12 tareas en dos vueltas, 73 tests, gate verde. El detalle de cada corrida está en
[BITACORA.md](BITACORA.md).

| Vuelta | Tareas | Gate verde al primer intento | Qué cambió |
|---|---|---|---|
| 1ª | T01–T08 | **0 de 4** | T01 a mano como referencia; T03–T08 terminaron a mano |
| 2ª | T09–T12 | **3 de 4** | contratos explícitos, tests exigidos por nombre, verificación humana declarada |

Lo que sigue abierto: los fantasmas todavía se traban en algunas esquinas (la decisión
"sin pathfinding" del plan original) y el emboscador puede apuntar fuera del mapa.

## Jugarlo

    python3 -m src.pacman

Python 3.11 o más nuevo, biblioteca estándar. En Windows, `curses` necesita
`pip install windows-curses`.

## Probar el gate

    bash scripts/gate.sh

## Lanzar una tarea

Desde la raíz del repo (necesita el entorno de [`../colabhive/`](../colabhive/README.md)):

    PROYECTO=ejemplo-pacman bash scripts/correr-tarea.sh T09

O dos que no se pisan:

    PROYECTO=ejemplo-pacman bash scripts/correr-tarea.sh T09 T10

Las tareas ya están hechas, así que relanzarlas no muestra mucho. Para ver al agente
trabajar, escribí una tarea nueva con [`../plantillas/TAREA.md`](../plantillas/TAREA.md),
commiteala (el worktree sale de `HEAD`) y lanzala: los dos defectos abiertos de arriba son
buenos candidatos.

## Qué mirar

1. `PLAN.md` — cómo se descompone un proyecto en tareas con dependencias y etapas.
2. `tareas/T01-laberinto.md` — una tarea bien especificada, con su contrato.
3. `tareas/T10-fantasmas-vivos.md` — la segunda vuelta: tests exigidos por nombre y
   verificación humana declarada.
4. `scripts/gate.sh` — el juez: tests, alcance (leído del archivo de la tarea) e higiene.
5. `tests/test_loop.py` — cómo testear lo que "necesita una terminal": una pantalla falsa.
6. `BITACORA.md` — los 12 hallazgos, incluido el agente que afirmó "GATE VERDE" con el gate en rojo.

# ejemplo-pacman

Un Pacman de terminal llevado adelante con el método de `../METODO.md`.
Sirve como ejemplo trabajado: el plan, las tareas, el gate y una tarea ya hecha.

## Estado

- **T01** ✅ hecha a mano, como referencia de calidad (15 tests, gate verde)
- **T02–T08** pendientes, listas para que las tome un agente

## Probar el gate

    bash scripts/gate.sh

## Lanzar una tarea

Desde la raíz del repo:

    PROYECTO=ejemplo-pacman bash scripts/correr-tarea.sh T02

O dos que no se pisan:

    PROYECTO=ejemplo-pacman bash scripts/correr-tarea.sh T02 T03

## Qué mirar

1. `PLAN.md` — cómo se descompone un proyecto en tareas con dependencias y etapas.
2. `tareas/T01-laberinto.md` — una tarea bien especificada, con su contrato.
3. `tareas/T04-fantasmas.md` — cómo se cierra la puerta a que el modelo improvise
   (desempate explícito, prohibición de `random`).
4. `scripts/gate.sh` — el juez: tests, alcance e higiene.
5. `src/pacman/laberinto.py` + `tests/test_laberinto.py` — el nivel de calidad esperado.

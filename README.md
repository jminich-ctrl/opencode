# metodo-agentes

Método de desarrollo para trabajar con agentes sobre modelos chicos self-hosted
(27B–30B en OpenCode contra ColabHive), con un ejemplo completo al lado.

## Qué hay acá

```
METODO.md              el método: principios, roles, gates, formato de tarea
AGENTS.md              reglas que el agente lee automáticamente
plantillas/
  PLAN.md              plantilla de plan
  TAREA.md             plantilla de tarea
  REVISION.md          checklist del gate humano (G2)
scripts/
  correr-tarea.sh      lanza una o varias tareas, cada una en su worktree
  estado.sh            qué tarea está en qué estado
ejemplo-pacman/        un proyecto entero llevado con el método
```

## Por dónde empezar

1. Leé `METODO.md`. Son 10 minutos y es el 80% de lo que hay que entender.
2. Mirá `ejemplo-pacman/PLAN.md` y una tarea cualquiera de `ejemplo-pacman/tareas/`.
3. Para un proyecto nuevo: copiá `plantillas/` y escribí tu `PLAN.md`.

## La idea en tres líneas

- La descomposición la hace un humano (o un modelo grande). El agente ejecuta.
- Ninguna tarea se da por terminada porque el agente lo diga: la decide `gate.sh`.
- Reintentar es barato: lanzá varias en paralelo y descartá las que salieron mal.

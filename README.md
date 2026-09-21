# metodo-agentes

Cómo llevar un proyecto grande adelante con agentes que corren sobre modelos chicos
self-hosted (27B–30B), en OpenCode contra ColabHive o contra modelos locales.

La idea en tres líneas:

> La descomposición la hace un humano (o un modelo grande). El agente ejecuta.
> Ninguna tarea se da por terminada porque el agente lo diga: la decide un comando.
> Reintentar es barato: lanzá varias en paralelo y descartá las que salieron mal.

## Los documentos

| Archivo | Qué contesta |
|---|---|
| **[EMPEZAR.md](EMPEZAR.md)** | De cero a la primera tarea ejecutada. Empezá por acá |
| **[METODO.md](METODO.md)** | Principios, roles, gates G0–G3, cómo se ejecuta y qué medir |
| **[DESCOMPOSICION.md](DESCOMPOSICION.md)** | Cómo bajar un proyecto enorme a tareas ejecutables |
| **[INFRAESTRUCTURA.md](INFRAESTRUCTURA.md)** | Modelos, contexto, caching, paralelismo, trampas |
| **[OPENCODE.md](OPENCODE.md)** | La config de OpenCode campo por campo, y los principios de warm |
| **[AGENTS.md](AGENTS.md)** | Reglas que el agente lee solo (lo carga OpenCode) |

## Las herramientas

```
plantillas/PLAN.md       plan de proyecto
plantillas/TAREA.md      una tarea
plantillas/REVISION.md   checklist del gate humano
scripts/correr-tarea.sh  lanza tareas, cada una en su worktree y en paralelo
scripts/estado.sh        en qué anda cada tarea
```

## El ejemplo

[`ejemplo-pacman/`](ejemplo-pacman/) es un proyecto entero llevado con el método:
plan con 8 tareas, gate ejecutable, y T01 implementada a mano como referencia de calidad.

Lo que conviene mirar, en orden:

1. `ejemplo-pacman/PLAN.md` — la descomposición completa, con etapas y choques de archivo
2. `ejemplo-pacman/tareas/T04-fantasmas.md` — cómo se le cierra la puerta a que el modelo improvise
3. `ejemplo-pacman/scripts/gate.sh` — el juez: tests, alcance, higiene
4. `ejemplo-pacman/BITACORA.md` — qué se rompió de verdad al usarlo, y cómo se arregló

## Por qué existe esto

Con Claude o Codex le das un objetivo y se las arregla. Con un modelo de 27B eso no
funciona: hay que darle tareas acotadas, con límites explícitos y verificación mecánica.
A cambio, cada tarea cuesta electricidad en vez de tokens facturados, y podés correr
muchas a la vez.

Este repo es el manual de cómo hacer ese cambio de forma de trabajo.

# Agentes de código sobre modelos open-weight — el método

*[English](README.md)*

Cómo llevar un proyecto grande adelante con agentes que corren sobre modelos chicos
open-weight (27B–30B), en OpenCode contra ColabHive o contra modelos locales.

## En cinco minutos: un modelo en OpenCode

```bash
pip install -U colabhive
export COLABHIVE_API_KEY=hive_...   # se crea en console.colabhive.com → Settings → API keys
colabhive agents init               # elige un modelo, lo prueba con un tool call real y lo escribe
opencode
```

Guía: [docs.colabhive.com/guides/agents/quickstart](https://docs.colabhive.com/guides/agents/quickstart).
Lo que sigue es para cuando un modelo no alcanza: el equipo completo y el método para
proyectos grandes.

La idea en tres líneas:

> La descomposición la hace un humano (o un modelo grande). El agente ejecuta.
> Ninguna tarea se da por terminada porque el agente lo diga: la decide un comando.
> Reintentar es barato: lanzá varias en paralelo y descartá las que salieron mal.

## Los documentos

| Archivo | Qué contesta |
|---|---|
| **[EMPEZAR.md](EMPEZAR.md)** | De cero a la primera tarea ejecutada. Empezá por acá |
| **[PRUEBAS.md](PRUEBAS.md)** | Quién verifica a los verificadores: la clase de falla que más nos mordió, y la suite del método |
| **[MEDICION.md](MEDICION.md)** | Validación de instrumentos: el instrumento que mide limpio y mide otra cosa. Las ocho preguntas antes de correr |
| **[METODO.md](METODO.md)** | Principios, roles, los ocho pasos del gate, integrar, cómo se ejecuta y qué medir |
| **[DESCOMPOSICION.md](DESCOMPOSICION.md)** | Cómo bajar un proyecto enorme a tareas ejecutables |
| **[HUMANO.md](HUMANO.md)** | El rol humano: qué decidimos, aprobamos y juzgamos, y cómo intervenir poco |
| **[PIPELINE.md](PIPELINE.md)** | La otra mitad: arquitecto, pre-deploy (G4) y deploy (G5) |
| **[INVESTIGACION.md](INVESTIGACION.md)** | Qué dice el trabajo publicado, qué robar, y dónde estamos expuestos |
| **[experimentos/](experimentos/)** | Lo que todavía no sabemos y cómo pensamos averiguarlo: diseños completos, sin ejecutar |
| **[INFRAESTRUCTURA.md](INFRAESTRUCTURA.md)** | Modelos, contexto, caching, paralelismo, trampas |
| **[OPENCODE.md](OPENCODE.md)** | La config de OpenCode campo por campo, y los principios de warm |
| **[colabhive/](colabhive/)** | Los archivos reales: config, prompts, scripts y mediciones |
| **[ejemplo-pacman/](ejemplo-pacman/)** | Un proyecto entero hecho con el método, con la bitácora de lo que salió mal |
| **[AGENTS.md](AGENTS.md)** | Reglas que el agente lee solo (lo carga OpenCode) |
| **AUDITORIA-\*.md** | Las auditorías del método contra sí mismo, con su fecha: [19-10](AUDITORIA-20261019.md) las formas de defecto, [20-10](AUDITORIA-20261020.md) la genericidad, [26-10](AUDITORIA-20261026.md) el instrumento en un proyecto que no es ninguno de los ejemplos |

## El entorno de ejecución

[`colabhive/`](colabhive/) tiene todo lo necesario para correrlo: la config de OpenCode
(provider, 11 modelos declarados, un agente por rol), los prompts, los scripts de setup y medición, y todas
las mediciones en `research/findings.md`. Instalación de punta a punta en su README.

## Las herramientas

```
plantillas/gate.sh        el juez: ocho pasos, decide si una tarea terminó
plantillas/correr-suite.sh  cómo se corre TU suite (dos funciones que saben del corredor)
plantillas/PLAN.md        plan de proyecto
plantillas/TAREA.md       una tarea
plantillas/AGENTS.md      las reglas que el agente lee
plantillas/_arquitectura.py  el gate de coherencia: capas y dependencias requeridas
plantillas/pre-deploy.sh  G4, lo que rompe en producción y no en local
plantillas/smoke.sh       que la aplicación ARRANQUE (o que declare que no hay nada que levantar)
plantillas/deploy.sh      G5, con el comando de deploy declarado
plantillas/REVISION.md    checklist del gate humano
scripts/correr-tarea.sh   lanza tareas, cada una en su worktree y en paralelo
scripts/correr-plan.sh    lanza una etapa entera; saltea lo que ya está hecho
scripts/estado.sh         en qué anda cada tarea
scripts/auditar-cerradas.sh  pasa lo ya cerrado por los instrumentos de hoy
scripts/ensayo.sh         ensaya el pipeline ENTERO con un agente determinista, sin gastar modelos
```

> La lista tenía cinco entradas y **no incluía `gate.sh`**, que es la pieza que la idea en tres
> líneas de arriba nombra: «la decide un comando». Son 12 plantillas, no 3.

## El ejemplo

[`ejemplo-pacman/`](ejemplo-pacman/) es un proyecto entero llevado con el método:
19 tareas en varias vueltas, gate ejecutable, 103 tests, y T01 hecha a mano como referencia de
calidad. En la primera vuelta el gate dio verde al primer intento **0 de 4** veces; con las
lecciones aplicadas, la segunda dio **3 de 4**.

Lo que conviene mirar, en orden:

1. `ejemplo-pacman/PLAN.md` — la descomposición completa, con etapas y choques de archivo
2. `ejemplo-pacman/tareas/T04-fantasmas.md` — cómo se le cierra la puerta a que el modelo improvise
3. `ejemplo-pacman/scripts/gate.sh` — el juez: tests, alcance, higiene
4. `ejemplo-pacman/BITACORA.md` — qué se rompió de verdad al usarlo, y cómo se arregló

## De punta a punta

1. **Instalás el entorno** — [`colabhive/README.md`](colabhive/README.md): API key, config, atajo `oc`.
2. **Entendés el método** — [METODO.md](METODO.md), 10 minutos.
3. **Descomponés tu proyecto** — [DESCOMPOSICION.md](DESCOMPOSICION.md) + `plantillas/`.
4. **Lanzás tareas** — `scripts/correr-tarea.sh`, 8 en paralelo por defecto.
5. **Revisás y mergeás** — `plantillas/REVISION.md`.

El ejemplo completo está en [`ejemplo-pacman/`](ejemplo-pacman/): plan, **19 tareas** (las
mismas que nombra la sección «El ejemplo» — decía 12 acá y 19 allá), gate, el juego terminado y
la bitácora de lo que salió mal.

## Por qué existe esto

Con Claude o Codex le das un objetivo y se las arregla. Con un modelo de 27B eso no
funciona: hay que darle tareas acotadas, con límites explícitos y verificación mecánica.
A cambio, cada tarea se paga por tiempo de GPU en vez de por token, y podés correr
muchas a la vez.

Este repo es el manual de cómo hacer ese cambio de forma de trabajo.

# Método de desarrollo con agentes de modelo chico

Cómo llevar adelante un proyecto grande usando agentes que corren sobre modelos
open-weight self-hosted (27B–30B), en OpenCode contra ColabHive.

No es el método que usarías con Claude o Codex. La diferencia de fondo:

> Un modelo grande sostiene un objetivo y se las arregla.
> Un modelo chico ejecuta una tarea acotada y verificable.
> **La descomposición la hacés vos. La ejecución la hace él. El juez es un comando.**

---

## 1. Los tres principios

### P1 — La unidad de trabajo es la tarea, no la feature

Una tarea bien dimensionada para un modelo de 27B:

- toca **1 o 2 archivos**, nunca diez;
- tiene **un solo objetivo**, enunciado en una frase;
- se verifica con **un comando que devuelve pasa o falla**;
- le llevaría a una persona del equipo entre 30 y 90 minutos.

Si no podés escribir su criterio de terminado en una línea, la tarea es demasiado grande.
Partila.

### P2 — El juez es un comando, no el modelo

Un modelo chico dice "listo" con la misma seguridad cuando funciona y cuando no.
Por eso ninguna tarea se da por terminada porque el agente lo diga: se da por terminada
cuando **el gate pasa**. Si una tarea no tiene comando que la verifique, está mal definida.

### P3 — Ancho, no profundidad

Cada tarea cuesta electricidad, no tokens facturados. Entonces:

- lanzá varias tareas **en paralelo**, cada una en su propio worktree;
- si una sale mal, **tirala y relanzala** con mejor prompt;
- **no negocies con el modelo** para rescatar una respuesta mala: sale más caro en
  tiempo tuyo que relanzar;
- lo que falla dos veces, lo hacés con un modelo grande o a mano.

---

## 2. Roles

| Rol | Quién | Qué hace |
|---|---|---|
| **Arquitecto** | Vos + un modelo grande (Claude/Codex) | Descompone el proyecto en tareas, define gates y criterios |
| **Ejecutor** | Agente `build` (27B) | Implementa **una** tarea, nada más |
| **Explorador** | Subagente `explore` (8B) | Busca en el código y responde dónde está qué |
| **Revisor** | Subagente `reviewer` (27B) | Busca bugs en el diff. Solo lectura |
| **Juez** | `scripts/gate.sh` | Decide si la tarea está terminada. No opina, ejecuta |
| **Integrador** | Vos | Revisa diffs, mergea, decide qué se relanza |

La regla que más importa: **el arquitecto nunca es el modelo chico.** Un 27B planificando
produce planes que suenan bien y no cierran.

---

## 3. El ciclo

```
   ┌──────────────────────────────────────────────────────────┐
   │  G0  PLAN.md aprobado (humano)                           │
   └──────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         [tarea T03]     [tarea T04]     [tarea T05]     ← en paralelo, un worktree c/u
              │               │               │
   ┌──────────────────────────────────────────────────────────┐
   │  G1  gate.sh verde: tests + alcance + estilo             │   ← automático
   └──────────────────────────────────────────────────────────┘
              │               │               │
   ┌──────────────────────────────────────────────────────────┐
   │  G2  revisión del diff (humano, ayudado por @reviewer)   │
   └──────────────────────────────────────────────────────────┘
                              │
   ┌──────────────────────────────────────────────────────────┐
   │  G3  integración: todas las tareas juntas, gate completo │
   └──────────────────────────────────────────────────────────┘
```

### G0 — Plan aprobado

Antes de lanzar un solo agente existe `PLAN.md` con las tareas numeradas, sus
dependencias y sus criterios. Lo escribe el arquitecto, lo aprobás vos.
**Ningún agente arranca sin G0.** Es el gate que más tiempo ahorra.

### G1 — Gate de tarea (automático)

`scripts/gate.sh` corre sobre el worktree de la tarea y verifica, en este orden:

1. **Tests**: la suite completa pasa.
2. **Alcance**: no se tocaron archivos fuera de los declarados en la tarea.
3. **Higiene**: sin dependencias nuevas, sin archivos generados, sin `TODO` sueltos.

Rojo en cualquiera de los tres = la tarea no está terminada. No se discute.

### G2 — Revisión del diff (humano)

Lo mirás como mirarías el PR de alguien que recién entró:

- ¿el arreglo es el correcto o es un parche que hace pasar el test?
- ¿los tests fallan de verdad contra el código viejo? (verificalo, no lo supongas)
- ¿se metió donde no debía?
- ¿inventó abstracciones que nadie pidió?

El subagente `@reviewer` te da una primera pasada, pero **la decisión es tuya**.

### G3 — Integración

Con todas las tareas de una etapa mergeadas, corre el gate completo sobre el tronco.
Acá aparecen los choques entre tareas que individualmente estaban bien.

---

## 4. Formato de tarea

Una tarea es un archivo en `tareas/TNN-nombre.md`. Ver `plantillas/TAREA.md`.
Lo que no puede faltar:

```markdown
# T03 — Movimiento de Pacman

**Depende de:** T01, T02
**Archivos que podés tocar:** src/pacman/entidades.py, tests/test_entidades.py
**Prohibido tocar:** src/pacman/laberinto.py

## Objetivo
Una frase. Qué tiene que poder hacer el código cuando esto esté listo.

## Alcance
- Lo que SÍ entra (3-6 puntos concretos)
- Lo que NO entra (igual de importante)

## Criterio de terminado
- [ ] Condición verificable 1
- [ ] Condición verificable 2
- [ ] `scripts/gate.sh` en verde

## Verificación
    python3 -m unittest discover -s tests -t . -q

## Si algo no cierra
Si encontrás un bug fuera del alcance: reportalo en la respuesta, NO lo arregles.
Si el plan está mal: pará y decilo. No improvises un rediseño.
```

**Los dos límites explícitos** —qué archivos podés tocar y qué hacer si aparece algo
raro— son los que evitan el 90% de los desastres. Un modelo chico sin límites se pone
a refactorizar lo que nadie le pidió.

---

## 5. Cómo se ejecuta

Una tarea, una sesión, contexto limpio. Nada de sesiones largas: cuando el contexto
crece, la calidad de un modelo chico se desploma y la compactación pierde justo lo
que importaba.

```bash
# una tarea
bash scripts/correr-tarea.sh T03

# varias en paralelo (solo las que no dependen entre sí)
bash scripts/correr-tarea.sh T03 T04 T05

# más de 16 tareas: el runner las va soltando de a 16
bash scripts/correr-tarea.sh T03 T04 T05 T06 T07 T08 ...
PARALELAS=8 bash scripts/correr-tarea.sh T03 T04 T05   # bajar el tope

# estado de todo
bash scripts/estado.sh
```

Cada tarea corre en su propio worktree de git (`../trabajo-T03`, rama `tarea/T03`),
así no se pisan y podés descartar una sin tocar el resto.

### Por qué hace falta aislar el estado de OpenCode

OpenCode guarda sesiones y snapshots en **una sola SQLite**: `~/.local/share/opencode/opencode.db`.
Dos `opencode run` simultáneos se pelean por el lock y el segundo muere con
`Error: database is locked`. Por eso el runner le da a cada tarea su propio directorio de datos:

    export XDG_DATA_HOME="$worktree/.opencode-data"

**Solo se aísla `XDG_DATA_HOME`, nunca `XDG_CONFIG_HOME`**: la config
(`~/.config/opencode/opencode.json`) tiene que seguir siendo la misma para todas,
o las tareas se quedan sin provider ni modelos.

Verificado con 3 `opencode run` simultáneos: las tres terminan bien y cada una crea su base.

El límite de cuántas tareas lanzar en paralelo no lo pone OpenCode sino el backend:
cuántas requests concurrentes aguantan tus modelos antes de que la latencia se dispare.

**Medido sobre este cluster: el tope son 16 por modelo**, y es el valor por defecto del
runner. Hasta ahí el costo de sumar tareas es casi cero (vLLM las mete en el mismo lote);
con 24 el throughput deja de subir y la peor request salta de 3 s a 12,6 s.
Tabla completa en [INFRAESTRUCTURA.md](INFRAESTRUCTURA.md). Con otro backend, medilo:
`~/colabhive-opencode/scripts/concurrencia.py`.

---

## 6. Cuando una tarea falla

| Qué pasó | Qué hacés |
|---|---|
| Gate rojo por tests | Relanzá con el error pegado en la tarea |
| Tocó archivos prohibidos | Relanzá endureciendo el "prohibido tocar" |
| Hizo un parche para que pase el test | Relanzá agregando "no toques el test para hacerlo pasar" |
| Se fue de alcance | La tarea era muy grande: partila en dos |
| Falló dos veces | Dejá de insistir: modelo grande o a mano |

**Reintentar es barato. Tu tiempo no.** Si te ves escribiendo el tercer mensaje para
explicarle al modelo lo mismo, cerrá la sesión.

---

## 7. Qué medir

Para saber si el método funciona, y para dimensionar mejor las próximas tareas:

- **Tasa de gate verde al primer intento.** Menos del 50% = las tareas están
  demasiado grandes o mal especificadas.
- **Cuántas tareas necesitan modelo grande.** Si es mucho, revisá la descomposición.
- **Tiempo de revisión humana por tarea.** Si revisar toma más que hacerlo a mano,
  la tarea no valía la pena delegarla.

Ese último punto es el que decide qué delegás y qué no.

---

## 8. Qué delegar y qué no

**Sí:** tests de módulos existentes, implementaciones con contrato claro, migraciones
mecánicas, docstrings, adaptadores, parsers, funciones puras con casos borde definidos.

**No:** decisiones de arquitectura, refactors que cruzan muchos archivos, debugging
sutil de concurrencia o estado compartido, cualquier cosa donde el criterio importe
más que el código.

Un patrón que funciona: **el modelo chico prepara el terreno y escribe el borrador;
el modelo grande (o vos) resuelve lo difícil.**

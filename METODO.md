# Método de desarrollo con agentes de modelo chico

Cómo llevar adelante un proyecto grande usando agentes que corren sobre modelos
open-weight self-hosted (27B–30B), en OpenCode contra ColabHive.

No es el método que usarías con Claude o Codex. La diferencia de fondo:

> Un modelo grande sostiene un objetivo y se las arregla.
> Un modelo chico ejecuta una tarea acotada y verificable.
> **La descomposición se verifica. La ejecución se delega. El juez es un comando.**

Las anécdotas de dónde salió cada regla no están acá: están en
[`ejemplo-pacman/BITACORA.md`](ejemplo-pacman/BITACORA.md) y
[`ejemplo-clasificados/BITACORA.md`](ejemplo-clasificados/BITACORA.md). Este documento dice
qué hacer; las bitácoras dicen qué nos pasó para llegar ahí.

---

## 0. Qué es del método y qué es nuestro

Este repo es un método **más** dos proyectos de ejemplo. Si te llevás lo de la izquierda sin
lo de la derecha, funciona.

| Del método, no lo toques | Nuestro, cambialo |
|---|---|
| Una tarea = una sesión = un diff que una persona lee | Que el ejemplo sea un Pacman o un sitio de clasificados |
| El veredicto es un código de salida | Que la suite se corra con `unittest` |
| Un chequeo que no pudo ejecutarse da **rojo** | Los chequeos de higiene (`pygame`, Tailwind) |
| Lo intocable lo decide el gate, no el archivo de tarea | Qué es intocable en tu repo |
| Los tests van escritos antes, y el agente no los toca | Que sean `pytest` o `vitest` |
| El humano cierra las decisiones con trade-off y firma | Cuáles fueron nuestras decisiones |
| Lo que no se verifica por comando va como gate humano | Nuestras preguntas de G3 |
| Nadie despliega solo | Nuestro `deploy.sh` |

**Lo que sí es un contrato**, porque hay scripts que lo leen: el formato de la tabla de
tareas en `PLAN.md`, las tres líneas de cabecera de un archivo de tarea, y la sección
`## Requisitos` del encargo. Están en `plantillas/`, y `validar-plan.py` los verifica — si
los cambiás, cambialos ahí también.

**Lo que asume:** git con worktrees, tronco único (no pull requests), y un plan en un
archivo Markdown. `integrar.sh` mergea al tronco; un equipo con PRs lo reemplaza por abrir
el PR y el resto sigue igual.

---

## 1. Los tres principios

### P1 — La unidad de trabajo es la tarea, no la feature

Una tarea sana para un modelo de 27B:

- le hace escribir **1 a 3 funciones**, no ocho — es lo que mejor predice que cumpla la
  instrucción ([DESCOMPOSICION.md §4](DESCOMPOSICION.md));
- toca **1 o 2 archivos**;
- tiene **un objetivo**, en una frase sin "y";
- se verifica con **un comando que devuelve pasa o falla**;
- le llevaría a una persona del equipo entre 30 y 90 minutos.

Si no podés escribir su criterio de terminado en una línea, partila.

### P2 — El juez es un comando, no el modelo

Un modelo chico dice "listo" con la misma seguridad cuando funciona y cuando no. Una tarea
se da por terminada cuando **el gate pasa**, no cuando el agente lo dice. Si una tarea no
tiene comando que la verifique, está mal definida.

Tres corolarios, y los tres se pagaron caros:

1. **La lectura del veredicto también tiene que estar fuera del alcance del agente.** El
   modelo vio fallar el gate tres veces y escribió *"El gate.sh indica GATE VERDE"*; el
   runner buscaba ese texto y le creyó. Ahora lee sólo la salida del gate que corre él mismo.
2. **El comando tiene que ser inmodificable por quien es juzgado.** El gate y los tests
   viven dentro del worktree del agente. El paso 0 los declara intocables con una lista
   **fija en el gate**, que el archivo de tarea no puede ampliar.
3. **Las reglas de conducta no sostienen nada.** `AGENTS.md` ya pedía no mentir y no tocar
   los tests. Lo único que funcionó fue hacer cada cosa verificable.

**Y el precio de P2: lo que no es verificable por comando no desaparece del proyecto,
desaparece del plan.** Como todo criterio tiene que ser verificable, el plan se llena de lo
testeable y deja caer en silencio lo cualitativo —que se sienta fluido, que sea usable—, y
el gate verde te da la sensación de terminado sin serlo. **La defensa:** cuando una cualidad
importa y no se puede testear, convertila en un **gate humano explícito** con preguntas
concretas, responsable y tiempo (G3).

#### El agente implementa bien y testea mal

Medido en 14 tareas: nunca falló implementando algo especificado, y falló **cuatro veces**
escribiendo tests que probaran algo — asserts como `assertTrue(len(posiciones) > 0)` que
pasan igual con el código viejo. Tiene sentido: **escribir un test que distinga exige
imaginar el caso donde dos algoritmos difieren**, y eso es razonamiento contrafáctico.

→ **Por eso los tests van escritos de antemano.** La tarea llega con los tests ya escritos,
fallando, y el trabajo del agente es hacerlos pasar sin tocarlos. Los escribe quien
planifica. Invierte el modo de falla más difícil de detectar.

> Hay una medición publicada que va en contra de pedirle TDD a un agente (3 a 8,5× más
> tokens, sin mejora en calidad de suite). **No es lo mismo**: eso mide *instruirle* TDD;
> esto es un artefacto de especificación producido aguas arriba. Ver
> [INVESTIGACION.md §3.1](INVESTIGACION.md).

### P3 — Ancho, no profundidad

Se paga por tiempo de GPU, no por token. Entonces: lanzá varias tareas **en paralelo**, cada
una en su worktree; si una sale mal **tirala y relanzala**; **no negocies con el modelo**
para rescatar una respuesta mala; y lo que falla dos veces lo hacés con un modelo grande o
a mano.

---

## 2. Roles

| Rol | Quién | Qué hace |
|---|---|---|
| **Arquitecto** | Agente `arquitecto` vía `planificar.sh`, o vos con un modelo grande | Encargo → `PLAN.md` + tareas |
| **Ejecutor** | Agente `ejecutor`, modelo **no pensante** | Implementa **una** tarea |
| **Explorador** | Subagente `explore` | Busca en el código |
| **Revisor** | Subagente `reviewer` | Busca bugs en el diff. Solo lectura |
| **Juez** | `scripts/gate.sh` del proyecto | Decide si la tarea está terminada |
| **Integrador** | `scripts/integrar.sh` | Mergea lo verde, de a una, con el gate del tronco |
| **Quien decide** | Vos | Cierra decisiones, firma G0, hace G3, aprieta G5 |

Dos reglas que cuestan plata:

- **El arquitecto no es el modelo chico.** Un 27B planificando produce planes que suenan
  bien y no cierran.
- **Razonador y ejecutor son perfiles distintos.** Un modelo pensante como ejecutor delibera
  en vez de actuar: el nuestro escribió 325 y 345 líneas de razonamiento sin tocar un
  archivo, dos veces. Con un instruct de código produjo en el primer intento. **El mejor
  modelo del equipo no es el que tiene que implementar** — mandalo a revisar.

---

## 3. El ciclo

```
encargo ─▶ G0 plan ─▶ G1 tarea ─▶ G2 diff ─▶ integrar ─▶ G3 uso ─▶ G4 pre-deploy ─▶ G5 deploy
          planificar  correr-     revisión   integrar    humano    pre-deploy       deploy
          .sh         plan.sh     + @reviewer .sh                  .sh              .sh
          ↑humano                                        ↑humano                    ↑humano
```

Tres momentos humanos, y ninguno es trabajo mecánico: firmar el plan, usar la cosa, y
desplegar. El resto son comandos. Ver [HUMANO.md](HUMANO.md).

### G0 — Plan aprobado

Ningún agente arranca sin `PLAN.md`. Es el gate que más tiempo ahorra: revisar un plan
cuesta diez minutos contra las horas de revisar diez diffs malos.

`planificar.sh` es un **bucle que se corrige solo**: el arquitecto escribe → se valida la
forma (`validar-plan.py`), la cobertura del encargo (`cobertura.py`) y el corte en etapas →
lo que está mal se le devuelve como **un** pedido → repite hasta que esté limpio o hasta que
falle dos veces por lo mismo. Los arreglos mecánicos se aplican antes de la vuelta, así no
gastan una llamada al modelo.

Lo que queda para la persona son tres preguntas y una firma:

1. **¿Las decisiones abiertas están cerradas?** No hay respuesta correcta: las cierra ella.
2. **¿Las tareas están dimensionadas?** Cuántas funciones tiene que escribir, no archivos.
3. **¿Inventó APIs que no existen?** La falla más común y la más fácil de pasar por alto.

**Un pedido por vuelta.** Con cinco correcciones juntas el arquitecto arregla las que son
buscar-y-reemplazar y deja las estructurales; con una sola cosa por vez, las hace.

### G1 — Gate de tarea (automático)

`scripts/gate.sh` corre sobre el worktree y verifica, en orden:

0. **Integridad**: no se tocaron los tests ni los scripts del propio gate.
1. **Tests**: la suite completa pasa, y **corrió al menos uno**.
2. **Alcance**: sólo los archivos que la tarea declara, **comparados por ruta y no por
   nombre** (permitir `cosa.py` no habilita `tests/cosa.py`).
3. **Higiene**: sin dependencias nuevas, sin archivos generados, sin `TODO`, y **sin señales
   suprimidas** (`# noqa`, `except: pass`, `|| true`): apagar una señal es más barato que
   arreglar la causa y no deja rastro en los tests.
4. **¿Los tests distinguen?**: revierte la implementación y exige que la suite falle.
5. **Coherencia**, sólo sobre el tronco: las dependencias entre módulos van en una sola
   dirección.

Rojo en cualquiera = la tarea no está terminada. No se discute.

#### La regla que más veces nos mordió: un chequeo que falta da ROJO

| Dónde | Qué hacía | Qué hace ahora |
|---|---|---|
| gate, paso 2 | sin cambios → verde | sin cambios en modo tarea → rojo |
| gate, paso 2 | sin alcance declarado → "sin límite" y verde | → rojo |
| gate, paso 1 | `Ran 0 tests` contaba como verde | → rojo |
| pre-deploy | sin smoke de arranque → avisaba y seguía | → rojo |

Aparece sola cada vez que uno escribe un verificador, porque la rama *"no pude chequearlo"*
se parece a la rama *"chequeé y está bien"* mientras la escribís. **Escribí siempre esa rama
como rojo primero.**

Su variante silenciosa son los **falsos verdes por rutas**, y aparecieron cuatro:
`git diff` informa rutas desde la raíz del repo (sin `--relative`, el paso 0 daba verde con
un test modificado), `git cat-file` también (el paso 4 veía todo archivo como nuevo y no
revertía nada), `.base-ref` —el archivo que escribe el runner— contaba como fuera de alcance
y ponía en rojo toda tarea, y la base del diff deducida dentro del gate se movía con el
primer commit del agente. **Los cuatro se encontraron rompiendo el gate a propósito, no
leyéndolo.** Un verificador que no probaste contra una falla real es una opinión.

#### El paso 4 es grueso; mutar es fino

El paso 4 revierte **todo** el cambio: atrapa el test vacuo grosero y deja pasar el fino
—una implementación con cinco condiciones donde los tests verifican una.

```bash
BASE=HEAD~1 python3 $AGENTES/scripts/mutar.py
```

Por cada línea nueva o modificada genera variantes con un cambio mínimo —invertir una
comparación, mover un límite, negar un booleano— y corre la suite. **Un mutante que
sobrevive es una línea que ningún test verifica.** Acotado al diff a propósito: mutar el
repo entero cuesta horas y no dice nada del código que nadie tocó.

Va en G2 y no en el gate porque cuesta una corrida de la suite por mutante. Es el único
detector confiable de un test tautológico que encontró la revisión de literatura, y en su
primera corrida encontró que el paso 4 estaba apagado por un bug de rutas.

### G2 — Revisión del diff (humano)

Como mirarías el PR de alguien que recién entró: ¿el arreglo es la causa o el síntoma?
¿los tests fallan de verdad contra el código viejo? ¿se metió donde no debía? ¿inventó
abstracciones que nadie pidió? ¿dijo que corrió algo que no corrió?

`@reviewer` da una primera pasada; la decisión es tuya. Checklist completo en
[`plantillas/REVISION.md`](plantillas/REVISION.md).

### El gate de coherencia: lo único que mira a través de las tareas

Los pasos 0 a 4 miran **una** tarea. Por construcción ninguno ve que diez diffs correctos
por separado dejaron la arquitectura peor — y la degradación no se ve en los diffs, aparece
leyendo el código de punta a punta, cuando ya es cara. Es la crítica mejor documentada al
desarrollo con agentes ([INVESTIGACION.md §2.3](INVESTIGACION.md)).

La respuesta publicada son *funciones de aptitud arquitectónica*: reglas sobre la forma del
sistema, verificables por comando, corriendo **sobre el tronco**.
`plantillas/_arquitectura.py` es la versión mínima: declarás las capas en orden y verifica
que cada una sólo importe las anteriores.

```python
CAPAS = ["datos", "servicios", "rutas"]
```

Treinta líneas y una regla. Corre en el paso 5 del gate en modo integración, y por lo tanto
también en `estado.sh`. Probado rompiéndolo en las dos direcciones.

### Integrar, y G3

`integrar.sh` mergea las tareas verdes **de a una** y corre el gate del tronco después de
cada merge; si el tronco se pone rojo, deshace **ese** merge y para. Diez merges juntos y un
tronco rojo no dicen cuál lo rompió. No mergea nada cuyo veredicto no sea VERDE, leído del
gate del runner y nunca del log del agente.

**Y acá va la prueba humana de punta a punta**: usar la cosa como la va a usar alguien. Es
el único gate que mide lo que ningún comando puede medir, y el que más cuesta saltear. Nos
lo salteamos en el Pacman: gate verde, 54 tests, y al jugarlo aparecieron cinco problemas en
el primer minuto —**ninguno roto según los tests, porque ninguno era testeable.**

Tiene que estar **escrita en el plan**, con preguntas concretas y un responsable, o no se
hace:

```markdown
## G3 — prueba de uso (responsable: <quién>, 5 min)
- [ ] ¿Responde al instante, o se siente trabado?
- [ ] ¿Se puede perder? ¿Se puede ganar?
- [ ] ¿Lo entiende alguien que no lo programó, sin explicación?
```

G4 (pre-deploy) y G5 (deploy) están en [PIPELINE.md](PIPELINE.md).

---

## 4. Formato de tarea

Un archivo por tarea en `tareas/TNN-nombre.md`, según
[`plantillas/TAREA.md`](plantillas/TAREA.md). Las tres cabeceras que los scripts leen de
verdad —y que `validar-plan.py` verifica— son `**Estado:**`, `**Depende de:**` y
`**Archivos que podés tocar:**`.

**`tests/` nunca va en "archivos que podés tocar".** Los tests llegan escritos y el paso 0
del gate lo verifica.

**Los dos límites explícitos** —qué archivos podés tocar, y qué hacer si aparece algo raro—
evitan el 90% de los desastres. Un modelo chico sin límites se pone a refactorizar lo que
nadie le pidió. Y el criterio de terminado nombra **los tests que tienen que existir**: sin
eso, un requisito omitido no deja rastro y el gate lo aprueba igual.

---

## 5. Cómo se ejecuta

Una tarea, una sesión, contexto limpio. Nada de sesiones largas: cuando el contexto crece,
la calidad de un modelo chico se desploma y la compactación pierde justo lo que importaba.

Los scripts se corren desde adentro del repo de tu proyecto; `$AGENTES` es donde clonaste
este repo ([EMPEZAR.md](EMPEZAR.md)).

```bash
# G0 — del encargo al plan, con el arquitecto corrigiéndose solo
bash $AGENTES/scripts/planificar.sh

# el plan entero: etapas deducidas, paralelo donde se puede
SOLO_ETAPAS=1 bash $AGENTES/scripts/correr-plan.sh   # ver el corte sin lanzar nada
bash $AGENTES/scripts/correr-plan.sh
bash $AGENTES/scripts/correr-plan.sh 3               # retomar desde la etapa 3

# una tarea suelta: modo de depuración
bash $AGENTES/scripts/correr-tarea.sh T03 T04 T05    # de a 8 como máximo; PARALELAS=4 lo baja

# integrar al tronco lo verde, de a una, con el gate de por medio
SOLO_VER=1 bash $AGENTES/scripts/integrar.sh
bash $AGENTES/scripts/integrar.sh

# estado de todo, incluido si el tronco está verde
bash $AGENTES/scripts/estado.sh
```

Cada tarea corre en su propio worktree (`../trabajo-T03`, rama `tarea/T03`), así no se pisan
y podés descartar una sin tocar el resto.

### Las etapas

Salen de `PLAN.md`: declaradas en formato exacto —`**ETAPA 1:** T02 T03`, sólo
identificadores— o **deducidas de la tabla**, con dos reglas: una tarea espera a sus
dependencias, y **dos tareas que escriben el mismo archivo no van juntas** aunque las
dependencias lo permitan.

**Deducirlas suele ser mejor que declararlas**, porque la regla del choque se aplica sola.
Si alguna línea de etapa no está en el formato exacto se descartan **todas** y se deduce,
con un aviso: mezclar es peor que ignorar, porque las que no matchean desaparecen y sus
tareas no se ejecutan sin que nadie se entere.

### Cuando una tarea falla

| Qué pasó | Qué hacés |
|---|---|
| Gate rojo por tests | Relanzá con el error pegado en la tarea |
| Tocó archivos prohibidos | Relanzá endureciendo el "prohibido tocar" |
| Hizo un parche para que pase el test | Relanzá pidiendo que no toque el test |
| Se fue de alcance | La tarea era muy grande: partila |
| Falló dos veces **por lo mismo** | Dejá de insistir: modelo grande o a mano |

El runner compara la **huella de la falla** entre intentos: si repite, la llama punto muerto
y corta, porque una falla que se repite igual es de especificación y el tercer intento no la
arregla. Si cambió, reintenta. Esa distinción es la que necesita el humano para decidir
([HUMANO.md §4](HUMANO.md)).

**Reintentar es barato. Tu tiempo no.**

### Tres cosas que muerden

- **El worktree congela el código al crearse**, desde `HEAD`: si arreglaste el gate o el
  runner y no commiteaste, la tarea corre con la versión vieja. **Commiteá las herramientas
  antes de lanzar**, y nunca edites un script de bash mientras corre.
- **El agente no commitea.** Deja los archivos sin trackear, así que `git merge` no trae
  nada. El runner commitea la rama cuando el gate da verde; `integrar.sh` cuenta con eso.
- **`XDG_DATA_HOME` por tarea, nunca `XDG_CONFIG_HOME`.** OpenCode guarda todo en una sola
  SQLite y dos `opencode run` simultáneos mueren con `database is locked`. La config tiene
  que seguir siendo compartida o las tareas se quedan sin provider.

El techo de paralelismo no lo pone OpenCode sino el backend: **medido en ColabHive, una
réplica admite 8 a la vez**, y es el valor por defecto. Pasado ahí el throughput deja de
subir. Tabla en [INFRAESTRUCTURA.md](INFRAESTRUCTURA.md); con otro backend, medilo con
`colabhive/scripts/concurrencia.py`.

### El método no depende de la IA

Todo lo que decide es un comando, así que **una persona puede ejecutar el método completo
sin ningún modelo disponible** y el veredicto es el mismo:

```bash
MANUAL=1 bash $AGENTES/scripts/correr-tarea.sh T03   # prepara el worktree
# ... la hacés vos ...
bash $AGENTES/scripts/cerrar-tarea.sh T03            # el gate juzga igual
```

El runner entra en modo manual solo si `opencode` no está instalado. Los intentos manuales
quedan en el registro con `modelo=humano` y las métricas los separan.

**Por qué importa más de lo que parece:** si el método sólo funciona con un modelo
determinado, no es un método, es una dependencia. Los agentes aceleran la ejecución; lo que
hace el trabajo confiable son las tareas bien cortadas y los gates.

---

## 6. Qué medir

El runner **registra cada intento** en `.metricas/intentos.csv` (fecha, tarea, veredicto,
segundos, modelo) y `bash $AGENTES/scripts/metricas.sh` lo resume.

- **Tasa de verde al primer intento.** Menos del 50% = tareas demasiado grandes o mal
  especificadas. Es el número que dice si la descomposición sirve.
- **Cuántas tareas necesitan modelo grande o humano.**
- **Tiempo de revisión humana por tarea.** Si revisar toma más que hacerlo a mano, la tarea
  no valía la pena delegarla. **Este es el que decide qué delegás.**

Tres decisiones de diseño del registro, cada una por un error que cometimos:

- **Lo escribe el runner, no se deduce del texto de las tareas.** La primera versión contaba
  secciones "Intento anterior" y daba **80%** donde la realidad era **44%**.
- **El denominador son todas las tareas intentadas**, no las que llegaron a verde. Contar
  sólo las exitosas es sesgo de supervivencia, y las que nunca pasaron son las que hay que ver.
- **Los errores de plataforma se cuentan aparte.** Un intento perdido porque el modelo
  estaba frío no dice nada del modelo ni del plan.

---

## 7. Qué delegar y qué no

**Sí:** tests de módulos existentes, implementaciones con contrato claro, migraciones
mecánicas, docstrings, adaptadores, parsers, funciones puras con casos borde definidos.

**No:** decisiones de arquitectura, refactors que cruzan muchos archivos, debugging sutil de
concurrencia o estado compartido, y cualquier cosa donde el criterio importe más que el
código.

Un patrón que funciona: **el modelo chico prepara el terreno y escribe el borrador; el
modelo grande, o vos, resuelve lo difícil.**

Y lo que nunca se delega está en [HUMANO.md §7](HUMANO.md): las decisiones con trade-off,
aprobar un plan, la prueba de uso, el deploy a producción, y escribir los tests.

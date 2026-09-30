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

Y hay un corolario que cuesta caro aprender: **la lectura del veredicto también tiene que
estar fuera del alcance del agente.** Nos pasó: el modelo corrió el gate, lo vio fallar
tres veces, y escribió en su resumen *"El gate.sh indica GATE VERDE"*. El runner buscaba
ese texto en el log y le creyó. Ahora lee **solo** la salida del gate que corre él mismo.
`AGENTS.md` pide no mentir; el modelo lo hizo igual. Lo único que sostiene es la
arquitectura de verificación, no las reglas de conducta.

**Y lo que no es verificable por comando no desaparece del proyecto: desaparece del plan.**
Este es el riesgo grande del método, y es el precio de P2. Como cada criterio tiene que
ser verificable, el plan se llena de lo que se puede testear y deja caer en silencio todo
lo cualitativo: que se sienta fluido, que el resultado sea usable, que tenga sentido para
quien lo use. Nadie lo escribe, entonces nadie lo construye, y el gate verde te da la
sensación de terminado sin serlo.

**La defensa:** cuando una cualidad importa y no se puede testear, no la omitas —
convertila en un **gate humano explícito**, con preguntas concretas, un responsable y un
tiempo. Es verificable aunque no sea automatizable. Ver G3 más abajo.

**Y exigir los nombres de los tests garantiza que existan, no que verifiquen algo.**
Medido en cuatro tareas seguidas (T13 dos veces, T14, y antes T02): el agente escribe los
tests con los nombres pedidos y **asserts que pasan igual con el código viejo**
(`self.assertTrue(len(posiciones) > 0)`, "se movió y no es pared"). Uno de ellos incluso
llevaba un comentario admitiendo *"esto es más difícil de probar directamente"*.

**Esto sí se puede automatizar**, y es el único de estos problemas que se pudo:
`gate.sh` paso 4 **revierte la implementación y exige que la suite falle**. Si sigue verde,
los tests no distinguen nada. Es mutation testing en su versión más simple.

**Y el patrón que dejó al descubierto vale más que el arreglo: el agente implementa bien
y testea mal.** En 14 tareas nunca falló implementando algo especificado; falló cuatro
veces escribiendo tests que probaran algo. Tiene sentido: el código lo verifica la suite,
pero **escribir un test que distinga requiere imaginar el caso donde dos algoritmos
difieren**, y eso es razonamiento contrafáctico. Un 30B no lo hace.

→ **Consecuencia para el formato de tarea: los tests van escritos de antemano.** En vez de
pedirle "implementá y testeá", la tarea llega con los tests ya escritos —fallando— y el
trabajo del agente es hacerlos pasar. Los escribe quien planifica (vos, o el modelo
grande). Invierte el modo de falla y hace innecesario el paso 4.

**Un gate verde tampoco garantiza que la tarea esté completa.** El gate verifica lo que
los tests cubren; si el mismo agente escribe el código *y* los tests, puede omitir un
requisito entero sin que nada lo delate. Nos pasó con el túnel de T02. Defensas: que el
criterio de terminado **nombre los tests que tienen que existir**, o separar "escribir
los tests" y "hacerlos pasar" en dos tareas. Si no, queda en manos de G2.

### P3 — Ancho, no profundidad

Cada tarea se paga por tiempo de GPU (o es tu propio hardware), no por token. Entonces:

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
| **Ejecutor** | Agente `build`, modelo **no pensante** | Implementa **una** tarea, nada más |
| **Explorador** | Subagente `explore` (el modelo más rápido) | Busca en el código y responde dónde está qué |
| **Revisor** | Subagente `reviewer` (27B) | Busca bugs en el diff. Solo lectura |
| **Juez** | `ejemplo-pacman/scripts/gate.sh` | Decide si la tarea está terminada. No opina, ejecuta |
| **Integrador** | Vos | Revisa diffs, mergea, decide qué se relanza |

La regla que más importa: **el arquitecto nunca es el modelo chico.** Un 27B planificando
produce planes que suenan bien y no cierran.

Y la segunda: **razonador y ejecutor son perfiles distintos.** Un modelo "pensante" como
ejecutor delibera en vez de actuar — el nuestro escribió 325 y 345 líneas de razonamiento
sin tocar un archivo, dos veces seguidas. Cambiado por un modelo instruct afinado para
código, produjo en el primer intento. **El mejor modelo del equipo no es necesariamente
el que tiene que implementar**: mandalo a revisar, que es donde su deliberación suma.

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

`ejemplo-pacman/scripts/gate.sh` corre sobre el worktree de la tarea y verifica, en este orden:

0. **Integridad**: no se tocaron los tests ni los scripts del propio gate.
1. **Tests**: la suite completa pasa.
2. **Alcance**: no se tocaron archivos fuera de los declarados en la tarea.
3. **Higiene**: sin dependencias nuevas, sin archivos generados, sin `TODO` sueltos.
4. **¿Los tests distinguen?**: revierte la implementación y exige que la suite falle.

Rojo en cualquiera = la tarea no está terminada. No se discute.

#### Por qué el paso 0 existe, y por qué no sale del archivo de tarea

El gate y los tests **viven dentro del worktree del agente**, así que son editables por el
agente al que juzgan. El paso 0 los declara intocables con una lista **fija en el gate**,
que el archivo de tarea no puede ampliar: un límite que el limitado puede reescribir no es
un límite. Es el mismo razonamiento que P2 llevado un paso más: no basta que el veredicto
lo dé un comando, ese comando tiene que ser inmodificable por quien es juzgado.

Pedirlo por prompt no alcanza. `AGENTS.md` ya decía no tocar los tests; el paso 0 es la
versión que se puede verificar.

#### Un chequeo que falta tiene que dar ROJO

Si la tarea no declara "Archivos que podés tocar", el gate da **rojo**, no "sin límite de
alcance declarado". Es la tercera vez que aparece esta misma trampa:

| Dónde | Qué hacía | Qué hace ahora |
|---|---|---|
| gate, paso 2 | sin cambios → verde | sin cambios en modo tarea → rojo |
| pre-deploy | sin smoke de arranque → avisaba y seguía verde | falta el smoke → rojo |
| gate, paso 2 | sin alcance declarado → "sin límite" y verde | sin alcance en modo tarea → rojo |
| gate, paso 1 | `Ran 0 tests` contaba como verde | una suite que no corrió ningún test → rojo |

Aparece sola cada vez que uno escribe un verificador, porque la rama "no pude chequearlo"
se parece a la rama "chequeé y está bien" mientras la escribís. **Escribí siempre esa rama
como rojo primero**, y recién después decidí si merece una excepción.

Dos detalles que parecen menores y no lo son:

- **El alcance se compara por ruta, no por nombre de archivo.** Permitir `entidades.py`
  también habilitaba `tests/entidades.py`, que es exactamente lo que el paso 0 prohíbe.
- **`git diff --name-only` devuelve rutas relativas a la raíz del repo**, no al proyecto.
  Sin `--relative`, el paso 0 daba **verde con un test modificado**. Lo encontramos porque
  lo probamos rompiéndolo a propósito; leyéndolo parecía correcto.
- **La base del diff la fija el runner**, en `.base-ref`, al crear el worktree y antes de
  que el agente toque nada. Si la dedujera el gate, el primer commit del agente movería la
  base y los pasos 0 y 2 dejarían de ver sus propios cambios. Es el defecto más común de
  los gates publicados, y el más silencioso: no falla, deja de mirar.

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

**Y acá va la prueba humana de punta a punta**, que no es opcional: usar la cosa como la
va a usar alguien. Es el único gate que mide lo que ningún comando puede medir.

Nos lo saltamos en el Pacman: el gate estaba verde, los 54 tests pasaban, corrí
simulaciones automáticas y di el juego por terminado. Cuando lo jugamos, aparecieron en
el primer minuto cinco problemas —teclas que se pierden, el juego se traba, un solo
fantasma, los personajes se atraviesan sin chocar, el fantasma se queda oscilando—
**y ninguno estaba roto según los tests, porque ninguno era testeable.**

La prueba humana tiene que estar **escrita en el plan, con preguntas concretas y un
responsable**, o no se hace:

```markdown
## G3 — prueba de uso (responsable: Jose, 5 min)
- [ ] ¿Responde al instante al apretar una tecla, o se siente trabado?
- [ ] ¿El fantasma persigue de forma creíble, o se queda oscilando?
- [ ] ¿Se puede perder? ¿Se puede ganar?
- [ ] ¿Alguien que no lo programó entiende qué hacer sin explicación?
```

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
- [ ] `ejemplo-pacman/scripts/gate.sh` en verde

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

Los scripts se corren desde adentro del repo de tu proyecto; `$AGENTES` es donde clonaste
este repo (ver [EMPEZAR.md](EMPEZAR.md)).

```bash
# una tarea
bash $AGENTES/scripts/correr-tarea.sh T03

# varias en paralelo (solo las que no dependen entre sí)
bash $AGENTES/scripts/correr-tarea.sh T03 T04 T05

# más de 8 tareas: el runner las va soltando de a 8
bash $AGENTES/scripts/correr-tarea.sh T03 T04 T05 T06 T07 T08 ...
PARALELAS=4 bash $AGENTES/scripts/correr-tarea.sh T03 T04 T05   # bajar el tope

# estado de todo
bash $AGENTES/scripts/estado.sh
```

Cada tarea corre en su propio worktree de git (`../trabajo-T03`, rama `tarea/T03`),
así no se pisan y podés descartar una sin tocar el resto.

### Dos detalles que muerden

**El worktree congela el código al crearse.** Se arma desde `HEAD`: si arreglaste el
gate o el runner y no commiteaste, la tarea corre con la versión vieja. **Commiteá las
herramientas antes de lanzar.** (Y nunca edites un script de bash mientras corre: bash
lo lee por partes y se rompe a mitad de camino.)

**El agente no commitea.** Deja los archivos sin trackear en el worktree, así que
`git merge tarea/T03` no trae nada. Al integrar, copiá los archivos a mano o hacé que el
runner commitee cuando el gate da verde.

### El método no depende de la IA

Todo lo que decide es un comando: `gate.sh`, `pre-deploy.sh`, `deploy.sh`. **Una persona
puede ejecutar el método completo sin ningún modelo disponible**, y el veredicto es el mismo.

```bash
MANUAL=1 bash scripts/correr-tarea.sh T03   # prepara el worktree y te muestra la tarea
# ... la hacés vos, en ../trabajo-T03/ ...
bash scripts/cerrar-tarea.sh T03            # el gate juzga igual, y commitea si da verde
```

El runner entra en modo manual solo si `opencode` no está instalado, así que en una máquina
sin nada el método sigue funcionando. Los intentos manuales quedan en el registro con
`modelo=humano`, y las métricas los separan de los del agente.

Probado: T16 (la fruta) se hizo a mano y pasó los cuatro pasos del gate, incluido el de
revertir la implementación para ver si los tests distinguen.

**Por qué importa más de lo que parece:** si el método sólo funciona con un modelo
determinado, no es un método, es una dependencia. Los agentes aceleran la ejecución; lo que
hace que el trabajo sea confiable son las tareas bien cortadas y los gates, y eso no
necesita IA.

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

**Medido en ColabHive el 2026-09-21: una réplica admite 8 a la vez**, y es el valor por
defecto del runner. Hasta ahí el costo de sumar tareas es casi cero (vLLM las mete en el
mismo lote); pasado 8 el throughput deja de subir y la mitad de los pedidos espera turno.
Y todas las tareas que usan la misma key comparten su tope de pedidos por minuto.
Tabla completa en [INFRAESTRUCTURA.md](INFRAESTRUCTURA.md). Con otro backend, medilo:
`$AGENTES/colabhive/scripts/concurrencia.py` (lee `COLABHIVE_BASE_URL`).

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

## 6b. Las herramientas de medición

El método pedía medir y no daba con qué. Ahora el runner **registra cada intento**
(`.metricas/intentos.csv`: fecha, tarea, veredicto, segundos, modelo) y

```bash
PROYECTO=ejemplo-pacman bash scripts/metricas.sh
```

lo resume. Dos decisiones de diseño que costaron un rato entender:

- **El registro lo escribe el runner, no se deduce del texto de las tareas.** La primera
  versión contaba las secciones "Intento anterior" de los archivos y daba **80%** donde la
  realidad era 44%. Adivinar del texto da números lindos y falsos.
- **El denominador son todas las tareas intentadas, no las que llegaron a verde.** Contar
  solo las exitosas es sesgo de supervivencia: las cuatro que nunca pasaron el gate y
  terminó haciendo un humano son justamente las que hay que ver.
- **Los errores de plataforma se cuentan aparte.** Un intento perdido porque el modelo
  estaba frío o el stream se cortó no dice nada del modelo ni del plan.

El runner además **commitea la rama cuando el gate da verde**: el agente nunca commitea, y
sin eso `git merge tarea/TNN` no trae nada y hay que copiar archivos a mano.

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

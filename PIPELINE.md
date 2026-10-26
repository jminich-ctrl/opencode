# De planificar a desplegar

El método base (`METODO.md`) cubre del plan a la integración, y los seis chequeos del gate.
Esto agrega la otra mitad — lo que hace falta para que el trabajo llegue a producción — y el
rol que faltaba al principio: quién escribe el plan.

```
OBJETIVO ─▶ G0 plan ─▶ G1 tarea ─▶ G2 diff ─▶ G3 integración ─▶ G4 pre-deploy ─▶ G5 deploy
           arquitecto   ejecutor   reviewer    integrar.sh       seguridad        devops
           planificar   correr-    + @reviewer + prueba humana   migrador         + rollback
           .sh          plan.sh                                  pre-deploy.sh    deploy.sh
```

---

## 1. El principio que gobierna esta mitad

> **Ningún agente despliega solo.**

Todo lo anterior es reversible: una tarea mala se tira, un merge se revierte, un diff se
descarta. Un deploy toca usuarios y datos. El agente **prepara** el deploy y lo **verifica
en staging**; el botón lo aprieta una persona.

No es desconfianza abstracta, es lo que ya medimos: el agente afirmó "GATE VERDE" con los
tests en rojo, y no ejecutó la verificación que su propia tarea le pedía. En un repo eso
cuesta un relanzamiento.

De ahí salen tres reglas:

1. **G5 nunca es automático.** Ni con todos los gates en verde.
2. **Todo deploy tiene su reversa escrita antes** de desplegarse. Si no se puede revertir,
   no es un deploy: es una apuesta.
3. **El agente no tiene credenciales de producción.** Prepara los artefactos y los scripts;
   los corre el humano, o un CI con sus propios permisos.

---

## 2. El arquitecto: el rol que faltaba

Hasta ahora el plan lo escribía una persona con un modelo grande. Con un modelo grande
propio, parte de ese trabajo se puede delegar — **con un límite claro**.

**El arquitecto produce un `PLAN.md` y las tareas. No escribe código.**

Lo que sí hace bien:
- Recorrer el repo y mapear qué módulos toca un objetivo.
- Proponer el corte en tareas, sus dependencias y las etapas paralelizables.
- Detectar los choques de archivo entre tareas.
- Escribir los contratos entre tareas (firmas, tipos de retorno).

Lo que **no** se le delega, y por eso `DESCOMPOSICION.md` §7 sigue valiendo:
- **Las decisiones de diseño con trade-offs.** El plan que propone las tiene abiertas o
  resueltas al tuntún; cerrarlas es tuyo.
- **Los gates humanos.** Un modelo no sabe qué va a molestar a un usuario.
- **Aprobar su propio plan.** G0 lo firma una persona. Siempre.

Úsalo como un borrador acelerado, no como un reemplazo: revisar un plan lleva 10 minutos,
escribirlo desde cero lleva una hora.

**Y no le ofrezcas una alternativa a producir.** Le pedíamos *"cuando termines, decime qué
decisiones te quedaron abiertas"*: devolvió un análisis largo, siete preguntas razonables,
ningún archivo, y un *"¿podés confirmar para que pueda avanzar?"*. No es desobediencia, es la
lectura literal de una invitación. Pedir lo que falta y entregar lo que se pueda son dos
cosas distintas, y ofrecidas juntas un modelo chico elige la barata. La instrucción ahora
dice **"tu única salida son archivos"**, y las decisiones abiertas van en una sección
*adentro* de `PLAN.md`, que es donde el humano las va a ver igual.

**G0 tiene su script**, `scripts/planificar.sh`, y no es una comodidad. Antes se corría a
mano y así arrastramos meses un `--agent arquitecto` que en realidad respondía `build`,
porque OpenCode no registra un agente que no declara `mode` y no avisa. El script verifica
primero que el agente exista y sea primario, y al terminar **no le cree al agente**: chequea
que `PLAN.md` exista, que haya archivos de tarea, y que del plan se puedan deducir las
etapas. Si algo de eso falta, G0 da rojo. Es P2 aplicado al planificador.

---

## 3. G4 — pre-deploy (automático)

Lo que rompe en producción y no en local. Corre sobre el tronco, después de G3.

| Chequeo | Por qué |
|---|---|
| **Secretos** | claves, tokens o `.env` en el diff. Un secreto commiteado ya está filtrado |
| **Dependencias nuevas** | toda dependencia que aparece se justifica o se rechaza |
| **Migraciones con reversa** | cada migración tiene su `down` y se probó aplicar y revertir |
| **Variables de entorno** | las que el código nuevo usa existen en el destino |
| **Build real** | que compile/empaquete igual que en producción, no solo que pasen los tests |
| **Smoke local** | que la app **arranque**. Nuestro Pacman crasheaba al arrancar con 70 tests en verde |
| **La suite sobre un checkout limpio** | todo lo demás corre sobre el árbol de trabajo, donde un archivo sin commitear puede estar sosteniendo los tests. Lo que se despliega es lo commiteado |

Plantilla ejecutable en `plantillas/pre-deploy.sh`, y el ejemplo adaptado en
`ejemplo-pacman/scripts/pre-deploy.sh`.

**Un G4 al que le falta un chequeo tiene que dar ROJO, no seguir en verde.** La primera
versión avisaba "sin smoke de arranque" y seguía: daba PRE-DEPLOY VERDE salteándose
justamente el chequeo que más atrapa. Es la misma trampa que el gate de tareas tenía con
"sin cambios", y aparece sola cada vez que uno escribe un verificador.

**El smoke de arranque no es opcional.** Es el chequeo que atrapa la clase de bug que los
tests unitarios no ven: la que vive en el arranque, el wiring y la configuración.

Y no hace falta una terminal ni un navegador: `ejemplo-pacman/scripts/smoke.sh` levanta el
juego **en una pty**, le manda teclas y verifica que dibuje. Lo probamos reintroduciendo el
bug original (pasar un booleano donde iba la dirección): el smoke lo atrapa. Los tests
también, **pero solo porque después del incidente escribimos el test**; el smoke lo
atrapa sin que nadie haya anticipado ese cableado en particular.

---

## 4. G5 — deploy (con humano)

```
build ─▶ staging ─▶ smoke en staging ─▶ [ decisión humana ] ─▶ producción ─▶ verificación ─▶ ¿rollback?
```

1. **Build** del artefacto, una sola vez. Lo que va a staging es **lo mismo** que va a producción.
2. **Deploy a staging** y smoke test: que arranque, que responda, que los caminos críticos anden.
3. **Decisión humana.** Acá se corta la cadena. El agente presenta: qué cambia, qué puede
   romper, cómo se revierte, qué mirar después.
4. **Producción**, con la reversa a mano.
5. **Verificación post-deploy**: los mismos smoke tests, más los indicadores que importen.
6. **Rollback** si algo falla, con el criterio escrito **antes** de desplegar.

Plantilla en `plantillas/deploy.sh`. Adaptala a tu stack: lo que no cambia es el orden y
que el paso 3 lo hace una persona. La plantilla se niega a arrancar si G4 está en rojo, y
para producción **pregunta cuatro cosas y exige que escribas `desplegar`**: qué cambia para
el usuario, qué puede romper, si la reversa está probada o solo escrita, y si el código
viejo sobrevive al esquema nuevo.

---

## 5. Los agentes del pipeline

| Agente | Hace | No hace | Modelo |
|---|---|---|---|
| **arquitecto** | Objetivo → `PLAN.md` + tareas | Decidir trade-offs, aprobar su plan | el grande |
| **build** (ejecutor) | Implementa una tarea | Planificar, desplegar | instruct de código |
| **tester** | Escribe y corre tests | Tocar el código de producción | instruct de código |
| **reviewer** | Busca bugs en el diff | Editar | pensante, solo lectura |
| **seguridad** | Secretos, inyección, permisos, deps | Editar | pensante, solo lectura |
| **migrador** | Migraciones con su reversa | Correrlas en producción | instruct de código |
| **devops** | Dockerfiles, CI, scripts de deploy | Ejecutar el deploy | instruct de código |
| **explore** | Buscar en el repo | Editar | chico y rápido |

Los cuatro últimos son los que agrega esta mitad. Las definiciones están en
`colabhive/config/opencode.json` y sus prompts en `colabhive/config/prompts/`.

**`seguridad` y `reviewer` tienen `edit: deny`.** Un revisor que puede arreglar lo que
encuentra deja de ser revisor: te devuelve un diff más grande en vez de una lista de
problemas.

---

## 6. El flujo completo, en comandos

```bash
# G0 — el arquitecto propone, vos aprobás
bash $AGENTES/scripts/planificar.sh          # lee OBJETIVO.md, escribe PLAN.md y tareas/
# ... lo revisás, cerrás las decisiones abiertas, agregás los gates humanos ...

# G1/G2 — el plan entero: etapas deducidas, paralelo donde se puede
bash $AGENTES/scripts/correr-plan.sh
bash $AGENTES/scripts/estado.sh

# G3 — integración y prueba humana
bash scripts/gate.sh          # modo integración
# ... y usás la cosa como la va a usar alguien ...

# G4 — pre-deploy
bash scripts/pre-deploy.sh

# G5 — deploy
bash scripts/deploy.sh staging
bash scripts/deploy.sh produccion     # ← este lo corrés vos, a mano
```

---

## 6b. Probado de punta a punta (2026-09-30)

Dos verificaciones distintas, y la segunda es la que importa.

### Sobre `ejemplo-pacman`

```
G1/G3  gate.sh         integridad · tests · alcance · higiene · ¿distinguen? · coherencia   VERDE
G4     pre-deploy.sh   secretos · deps · migraciones · env · build · smoke · checkout limpio VERDE
G5     deploy.sh       artefacto · reversa · deploy · smoke del desplegado                   VERDE
```

Lo que se verificó a propósito, rompiéndolo:

- **G5 se niega si G4 está en rojo.** Rompimos `render.py` adrede: el deploy no arrancó y
  **salió con código 1**. Con la app sana, 0. Eso lo hace usable desde CI.
- **El smoke corre contra lo desplegado**, no contra el árbol de trabajo.
- **El smoke atrapa el crash original** (un booleano donde iba la dirección). Los tests
  también lo detectan hoy, pero **sólo porque después del incidente escribimos el test**.
- **El paso 7 atrapa un test que dependía de un archivo sin commitear**: árbol de trabajo
  verde, clon de `HEAD` rojo.

### En un proyecto nuevo, siguiendo `EMPEZAR.md`, y sin IA

La prueba que de verdad dice si el método está escrito o sólo propuesto: proyecto vacío,
las plantillas copiadas tal cual, y el recorrido completo con `MANUAL=1`.

```
plantillas → gate.sh, _arquitectura.py, pre-deploy.sh   copiados; capas declaradas
tests primero, fallando                                  3 tests
MANUAL=1 correr-tarea.sh T01                             worktree listo
(una persona implementa)
cerrar-tarea.sh T01                                      GATE VERDE
integrar.sh T01                                          tronco verde, tarea marcada, rama borrada
estado.sh                                                ✅ hecha · mergeada · tronco verde
validar-plan.py                                          1 tarea, sin errores de forma
mutar.py                                                 ✗ 1 sobreviviente
```

**Encontró tres cosas que ninguna prueba anterior había encontrado**, y las tres eran
nuestras:

1. **`.base-ref` ponía en rojo toda tarea.** El archivo con la base del diff lo escribe el
   runner y el gate lo contaba como archivo fuera de alcance. Un bug del día, que habría
   roto la primera tarea de cualquiera. Ahora el gate filtra su propia infraestructura, y lo
   hace en el gate y no en el `.gitignore` de cada proyecto.
2. **El `.gitignore` de `EMPEZAR.md` no tenía `.metricas/`**, así que el registro de intentos
   quedaba como cambio sin commitear en el tronco y **`integrar.sh` se negaba a mergear**.
3. **El mutante `centavos <= 0` sobrevivió**: ningún test distinguía cero de negativo, así
   que rechazar un importe de `0.00` no rompía nada. Escribimos el test que faltaba y el
   mutante murió. El código lo habíamos escrito nosotros, con los tests primero, y el
   agujero estaba igual.

Nota de vigencia: esa corrida copió `_arquitectura.py` **sin editar**, y desde el
2026-10-25 eso da rojo a propósito — con capas que el proyecto no tiene, el chequeo no puede
encontrar nada y antes lo informaba con un ✓. Hoy hay que declarar las capas propias (dos
listas y una ruta) o no copiar el archivo; el resto del recorrido es igual.

Y una que el gate nos hizo a nosotros: **editamos `scripts/gate.sh` dentro del worktree** y
el paso 0 lo marcó como archivo intocable. Es la regla que el método ya tenía escrita
—commiteá las herramientas antes de lanzar— aplicada al que la escribió.

### En un proyecto que no es Python (2026-10-26)

Mismo recorrido, stack JavaScript: Node 20 con `node --test`, sin dependencias y sin instalar
nada. De cero a dos tareas integradas.

```
validar-plan.py                 ✓ 2 tareas, sin errores de forma
correr-tarea.sh T02 (MANUAL=1)  worktree listo, línea base: 1 falla
(una persona implementa)
cerrar-tarea.sh T02             ✓ T02 gate VERDE
integrar.sh T02                 ✓ tronco verde; la línea base no se le cobró al merge
estado.sh                       T01 y T02 ✅ hechas · mergeadas · tronco verde
```

El gate corre sus seis pasos con dos ⊘ honestos —los chequeos que son de Python: imports
contra requirements, y mutación—. Lo que **no** funcionaba, y se arregló acá:

1. **El contrato del corredor no estaba verificado.** Adaptar `correr_suite` a `node --test`
   lo rompió por las dos puntas y el gate emitió un diagnóstico falso y rotundo sobre tests
   que nunca corrieron. Lo calibra `_corredor.sh` en el paso 1.
2. **`fallas()` también sabe del stack**, y la cabecera de la plantilla decía que
   `correr_suite` era «el único lugar». Con el patrón de unittest, la línea base de un
   proyecto JS sale vacía con tests rojos en el disco — y «0 ya fallando» es lo que informa
   también un proyecto limpio.

   **Lo que sí estaba cubierto, y hay que decirlo:** los tres gates ya tenían la guarda de
   «la suite da rojo y el extractor no entendió su salida», puesta cuando el patrón de vitest
   dejó 15 tareas de frontend sin poder dar rojo. Lo que faltaba es más temprano: esa guarda
   juzga al CERRAR y sólo si la suite está roja en ese momento, así que no impide lanzar una
   tarea con la línea base ya rota. Ahora el runner frena antes de gastar la corrida, y la
   cabecera dice que son dos las funciones que hay que adaptar.
3. **Un `package.json` sin dependencias no es una falla.** `npm install` sale 0 sin crear
   `node_modules`, y exigir el directorio daba «✗ npm no dejó node_modules» con `exit 1`.
4. **El mensaje de la línea base salía partido en dos líneas** desde que se escribió:
   `grep -c . || echo 0` imprime los dos ceros, porque `grep -c` imprime 0 *y* sale 1. La
   variable valía «0\n0», y por eso el chequeo nuevo no disparaba hasta que lo encontré.

Lo que un proyecto así **no** tiene: mutación (el mutador es de Python) y chequeo de imports
contra el manifiesto. Los dos se informan ⊘ y quedan a la vista en el veredicto.

### Y con un agente de verdad (2026-10-26, 06:15)

T03 del mismo proyecto JS —`iva(monto, categoria)`, cinco casos incluido el truncamiento y el
negativo— lanzada con `correr-tarea.sh` sin `MANUAL=1`, contra el ejecutor local
(`Qwen3-Coder-30B-A3B`):

```
correr-tarea.sh T03    línea base: 1 test fallando · ✓ T03 gate VERDE (al primer intento)
integrar.sh T03        ✓ tronco verde · T01 T02 T03 hechas y mergeadas
```

Y el verde **auditado a mano**, porque en JS el método no tiene mutador: seis mutantes
aplicados sobre lo que escribió el agente, **cinco muertos**. El sobreviviente es `monto < 0`
→ `monto <= 0`, equivalente —con monto 0 el IVA es 0 de las dos formas— y de la clase que
`mutar.py` excluye por árida: comparaciones contra 0. El verde está ganado.

### Y una etapa entera, con dos agentes en paralelo (06:45)

`correr-plan.sh` sobre el mismo proyecto, etapa de dos tareas elegidas para que no fueran
regalos: `cuotas(monto, n)` —cuya suma tiene que dar exactamente el monto— y `total(items)`,
obligada a **usar** `iva` y `descuento` con esos archivos en «Prohibido tocar».

```
correr-plan.sh    ✓ etapa completa · T04 y T05 VERDE al primer intento (45s y 39s)
```

El agente de T05 **importó** los dos módulos en vez de reimplementar las tasas, que era la
trampa. Auditados a mano: T04 cuatro de cinco mutantes muertos, T05 tres de cuatro. Los dos
sobrevivientes son ramas defensivas **equivalentes** —un atajo `n === 1` y una guarda del array
vacío— que dan el mismo resultado sin ellas: comportamiento que nadie necesita, y que en un
proyecto Python la mutación habría marcado.

Dos defectos del método, los dos de los que sólo aparecen corriendo:

1. **`correr-plan.sh` relanzó la etapa 1 completa**, con tres tareas hechas y mergeadas: tres
   corridas de agente gastadas, el gate contestando «no hay ningún cambio: la tarea no se
   hizo» —cierto y engañoso—, dos tareas en «punto muerto», y el plan detenido SIN llegar a la
   etapa pendiente. `_etapas.py` filtra las hechas; la rama que lee las etapas DECLARADAS las
   tomaba al pie de la letra, y la plantilla de PLAN.md enseña a declararlas. Se nota en la
   segunda corrida del plan, que es la normal.
2. **`.tests-base` commiteado hizo chocar el merge.** Las dos tareas de la etapa escribieron
   su propia línea base de fallas, cada rama la commiteó, y la segunda integración murió con
   «conflicto al mergear tarea/T05». El gate filtra ese archivo del diff —es infraestructura—
   pero el `.gitignore` de la guía no lo ignoraba, y filtrar del diff no impide que entre al
   commit. Faltaban SIETE entradas de la lista del gate, incluidas `.venv` y `node_modules`.
   Ahora un test cruza las dos listas.

Lo que la corrida encontró del método: **una reversión vacía no es una reversión que pasó.**
Correr el gate a mano después de `cerrar-tarea.sh` —que es lo que hace cualquiera que mire una
tarea cerrada, y lo que AGENTS.md le pide al agente— daba

    ✗ los tests PASAN con la implementación vieja: no verifican el cambio

porque el paso 4 revierte a HEAD y después del cierre HEAD ya tiene la implementación: el
checkout no mueve un byte, la suite sigue verde, y de ahí el gate acusaba a los tests. Ahora
compara el archivo antes y después de revertir, y si no cambió nada lo informa como ⊘ con su
motivo.

### Los subagentes solo se invocan por delegación

`opencode run --agent reviewer` **no usa reviewer**: cae en el agente por defecto, sin
avisar. Verificado dos veces. La única forma de usar `reviewer`, `seguridad`, `devops` o
`migrador` es que un agente primario los invoque con la herramienta de tareas
(`@reviewer …`) dentro de una sesión.

Consecuencia práctica: **G2 con subagente no se puede automatizar desde un script** como
G1/G4/G5. O se hace desde una sesión interactiva, o el revisor humano lee el diff. Lo
cual, siendo G2 el gate humano, tampoco es tan grave.

## 7. Qué medir en esta mitad

| Métrica | Qué te dice |
|---|---|
| Planes del arquitecto que sobreviven tu revisión sin rehacerse | si conviene delegar el plan |
| Hallazgos de G4 que los tests no vieron | cuánto te está salvando el pre-deploy |
| Deploys con rollback | si el pipeline está listo o estás apostando |
| Tiempo de objetivo a producción | lo único que le importa a quien pidió el trabajo |

La segunda fila es la que justifica G4: si nunca encuentra nada, sacale chequeos; si
encuentra seguido, agregale.

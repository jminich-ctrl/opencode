# De planificar a desplegar

El método base (`METODO.md`) cubre de G0 a G3: plan, tarea, revisión, integración.
Esto agrega la otra mitad — lo que hace falta para que el trabajo llegue a producción —
y el rol que faltaba al principio: quién escribe el plan.

```
OBJETIVO ─▶ G0 plan ─▶ G1 tarea ─▶ G2 diff ─▶ G3 integración ─▶ G4 pre-deploy ─▶ G5 deploy
           arquitecto   ejecutor   reviewer    + prueba humana   seguridad        devops
                                                                 migrador         + rollback
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

## 6b. Probado de punta a punta (2026-09-29)

El pipeline entero corre sobre `ejemplo-pacman`:

```
G1/G3  gate.sh         tests + alcance + higiene + ¿los tests distinguen?   VERDE
G4     pre-deploy.sh   secretos · deps · migraciones · env · build · smoke  VERDE
G5     deploy.sh       artefacto · reversa · deploy · smoke del desplegado  VERDE
```

Lo que se verificó a propósito, no de palabra:

- **G5 se niega si G4 está en rojo.** Rompimos `render.py` adrede: el deploy no arrancó y
  **salió con código 1**. Con la app sana, 0. Eso lo hace usable desde CI.
- **El smoke corre contra lo desplegado**, no contra el árbol de trabajo: si el artefacto
  se armó mal, se ve ahí y no en producción.
- **El smoke atrapa el crash original.** Reintrodujimos el bug de T11 (un booleano donde
  iba la dirección) y lo detectó. Los tests también lo detectan hoy, pero **solo porque
  después del incidente escribimos el test**; el smoke no necesitaba que nadie lo
  anticipara.

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

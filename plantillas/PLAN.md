# Plan — <proyecto>

**Estado del gate G0:** borrador | aprobado por <quién> el <fecha>

## Objetivo

Qué tiene que existir cuando esto termine, en 3 o 4 líneas. Y qué NO es parte.

## Decisiones tomadas

Las que el agente no debe volver a discutir. Una línea cada una, con el porqué.

- <decisión> — <por qué>

## Arquitectura

Módulos, qué hace cada uno y quién depende de quién. Un diagrama de texto alcanza.

## Tareas

| # | Tarea | Depende de | Archivos | Estado |
|---|---|---|---|---|
| T01 | <título> | — | <rutas> | pendiente |
| T02 | <título> | T01 | <rutas> | pendiente |

**ETAPA 1:** T01 T02
**ETAPA 2:** T03 T04

> **El formato es exacto**: `ETAPA <n>:` en mayúsculas y después **sólo identificadores**.
> Nada de prosa en esa línea — las explicaciones van abajo. El runner lanza en paralelo todo
> lo que esté en la misma línea, así que un "T05, luego T06" se ejecutaría junto y no en
> serie. Si el formato no es exacto, el runner avisa y deduce las etapas de la tabla.
>
> Si no declarás etapas, se deducen solas (dependencias + choques de archivo), que suele ser
> mejor. Verificá el corte antes de lanzar:
> `SOLO_ETAPAS=1 bash $AGENTES/scripts/correr-plan.sh`

## Gates

- **G0** este plan aprobado
- **G1** por tarea: `scripts/gate.sh` verde
- **G2** revisión humana del diff (ver `plantillas/REVISION.md`)
- **G3** integración: gate completo sobre el tronco **+ prueba de uso**
- **G4** pre-deploy: `scripts/pre-deploy.sh` (secretos, deps, migraciones, build, smoke)
- **G5** deploy: `scripts/deploy.sh` — lo corre una persona, siempre

### G3 — prueba de uso (responsable: <quién>, <cuántos minutos>)

Lo que ningún comando puede medir. **Sin esto, el proyecto termina verde y malo.**

- [ ] ¿Se siente bien usarlo? (latencia, fluidez, pasos para lo más común)
- [ ] ¿Qué pasa cuando el usuario se equivoca?
- [ ] ¿Cubre los casos reales, o solo el mínimo que pedían las tareas?
- [ ] ¿Lo entiende alguien que no lo programó?
- [ ] <pregunta propia del proyecto>

## Riesgos

| Riesgo | Qué haríamos |
|---|---|
| <riesgo> | <mitigación> |

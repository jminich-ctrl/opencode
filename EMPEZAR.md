# Empezar

De cero a la primera tarea ejecutada por un agente. Unos 30 minutos, la mayoría
escribiendo el plan (que es donde está el valor).

## 0. Que el entorno esté sano

```bash
oc --status                                          # los modelos, calientes
python3 ~/colabhive-opencode/scripts/sync_limits.py  # el contexto, correcto
```

Si algo está frío: `oc --warm` y esperá — un modelo `cached` tarda de 3 a 7 minutos en
cargar, y una tarea lanzada contra un modelo frío se queda esperando ese tiempo.
Detalle en [OPENCODE.md](OPENCODE.md) e [INFRAESTRUCTURA.md](INFRAESTRUCTURA.md).

## 1. Armá el proyecto

```bash
mkdir mi-proyecto && cd mi-proyecto && git init
mkdir -p tareas scripts src tests
cp ~/metodo-agentes/plantillas/PLAN.md .
cp ~/metodo-agentes/ejemplo-pacman/scripts/gate.sh scripts/
cp ~/metodo-agentes/ejemplo-pacman/AGENTS.md .      # y adaptalo a tu proyecto
```

## 2. Escribí el PLAN.md  ← acá está el 80% del trabajo

Seguí [DESCOMPOSICION.md](DESCOMPOSICION.md). Lo mínimo:

- **Objetivo** en 4 líneas, y qué NO es parte.
- **Decisiones tomadas**: todo lo que el agente no debe volver a decidir.
- **Arquitectura**: módulos y dependencias.
- **Tareas**: numeradas, con dependencias, archivos y estado.
- **Etapas**: qué se puede lanzar junto (ojo con las que tocan el mismo archivo).

No sigas hasta que el plan esté escrito. Es el gate G0.

## 3. Ajustá el gate

`scripts/gate.sh` tiene que correr **tu** suite de tests y **tus** reglas de higiene.
Probalo antes de usarlo:

```bash
bash scripts/gate.sh     # tiene que dar verde sobre el repo limpio
```

## 4. Hacé la primera tarea vos

A mano o con un modelo grande, bien hecha y con tests. **Es la referencia que el agente
va a imitar.** Un modelo chico copia mucho mejor de lo que inventa: si el repo ya tiene
un módulo prolijo, las tareas siguientes salen parecidas.

## 5. Escribí la segunda tarea y lanzala

```bash
cp ~/metodo-agentes/plantillas/TAREA.md tareas/T02-lo-que-sea.md
# completala: objetivo, alcance, contrato, criterio de terminado, archivos permitidos

PROYECTO=. bash ~/metodo-agentes/scripts/correr-tarea.sh T02
```

## 6. Revisá con el checklist

```bash
cat ~/metodo-agentes/plantillas/REVISION.md
```

Lo que no se saltea: **verificar que los tests nuevos fallen contra el código viejo.**
Si pasan igual, no prueban nada, y el gate automático no lo detecta.

## 7. Recién ahora, escalá

Con una tarea que pasó el gate y la revisión, ya sabés si tus tareas están bien
dimensionadas. Ajustá el formato con lo que aprendiste y lanzá de a varias:

```bash
PROYECTO=. bash ~/metodo-agentes/scripts/correr-tarea.sh T03 T04 T05
bash ~/metodo-agentes/scripts/estado.sh
```

**No lances diez tareas antes de haber completado una.** Diez tareas mal especificadas
son diez diffs para tirar.

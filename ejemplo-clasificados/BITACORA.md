# Bitácora — sitio de clasificados

Qué pasó, corrida por corrida. Es el archivo más valioso del ejemplo: el código lo puede
reescribir cualquiera, los hallazgos no.

El objetivo de este ejemplo no es el sitio: es **afinar el método en algo más parecido a un
proyecto real** que el Pacman — front, back, base de datos, login, migraciones, diseño — y
que el plan entero lo escriba el planificador, no una persona.

---

## 2026-09-30 · G0, primer intento: el arquitecto no existía

Corrimos `--agent arquitecto` durante semanas y **respondía `build`**. OpenCode no registra
un agente propio que no declara `mode`, y no avisa: no aparece en `opencode agent list` y la
bandera cae al agente por defecto en silencio.

Por eso este ejemplo estuvo días sin `PLAN.md` mientras creíamos que el arquitecto lo había
escrito. Ver [../OPENCODE.md](../OPENCODE.md) §3.

**Qué cambió en el método:** G0 pasó a tener script, `scripts/planificar.sh`, y lo primero
que hace es verificar que el agente exista y sea primario. Habría cortado esto en un segundo.

## 2026-09-30 · G0, segundo intento: escribió preguntas, no archivos

Con el arquitecto de verdad, el resultado fue un análisis largo, **siete preguntas muy
razonables**, y ningún archivo. Terminó con *"¿Podés confirmar la información faltante para
que pueda avanzar?"*.

G0 dio **rojo**, y eso es lo importante: el script no le cree al agente, chequea que
`PLAN.md` exista, que haya tareas, y que se le puedan deducir las etapas.

La causa estaba en nuestra instrucción. Le decíamos *"cuando termines, decime qué decisiones
te quedaron abiertas"* — y el encargo repetía la idea. **A un modelo chico al que le ofrecés
preguntar, pregunta.** No es desobediencia: es la lectura literal de una invitación.

**Qué cambió en el método:** la instrucción ahora es terminante —*"tu única salida son
archivos; las decisiones abiertas van en una sección DENTRO de PLAN.md; no pares a
preguntar"*— y sigue pidiendo lo mismo, pero sin ofrecer la salida de no producir nada.

> La regla general: **no le ofrezcas a un modelo chico una alternativa a hacer el trabajo.**
> Pedir lo que falta y entregar lo que se pueda son dos cosas, y si las ofrecés juntas
> elige la barata.

## 2026-09-30 · Las decisiones que cerramos nosotros

El agente preguntó bien. Las respuestas están al final de
[OBJETIVO.md](OBJETIVO.md), porque así funciona el bucle: **el planificador devuelve
decisiones abiertas y el humano se las devuelve cerradas** (HUMANO.md §1).

De las siete, tres ya estaban contestadas en el encargo (pytest/vitest, FastAPI sin ORM,
migraciones reversibles) y una era su propio trabajo (el orden de las etapas). Las otras tres
—gestor de paquetes, capas del backend, responsable de G3— eran decisiones de verdad.

La de las capas trajo algo: fijamos `app/datos → app/servicios → app/rutas` **y le pedimos
que escriba el `scripts/_arquitectura.py` correspondiente**, así el gate de coherencia
verifica la arquitectura que él mismo propuso.

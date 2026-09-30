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

## 2026-09-30 · G0, tercer intento: escribió los archivos

El arreglo era una línea del prompt. Decía **qué** producir y nunca **cómo**:

> `## Lo que producís` — "Un `PLAN.md` siguiendo `plantillas/PLAN.md`, y un archivo por
> tarea en `tareas/`."

Ahora dice *"archivos en el disco, escritos con la herramienta `write`; lo que no quedó en
un archivo no existe"*, pide verificar con `read` que estén, y define la respuesta final
como la lista de archivos. Resultado: `PLAN.md` de 79 líneas, 8 tareas, 10 llamadas a
`write`, y G0 verificando que el plan se puede ejecutar.

**La regla:** a un modelo chico decile la herramienta, no sólo el entregable. Los modelos
grandes infieren que "producir un archivo" implica llamar a `write`; los chicos producen
el contenido y se quedan ahí. Es la falla que Posit midió en modelos locales — *"escribió
los pasos correctos pero no llamó a las herramientas"* — y la vimos idéntica.

## 2026-09-30 · G0 rechazado: qué se le escapa a un arquitecto de 120B

El plan estaba bien **armado** —capas correctas, contratos, tabla de dependencias, decisiones
abiertas listadas adentro— y mal **completado**. Las cinco cosas, porque son un catálogo
útil de qué mirar en un plan:

| # | Qué | Clase de error |
|---|---|---|
| 1 | Mezcló React con Vue: `App.vue`, `Login.vue`, y T06 titulada "Vite y React" creando `App.vue` | contradice el encargo |
| 2 | **Faltaba un tercio del alcance**: favoritos, mensajes, editar tus avisos, filtro por categoría, sistema de diseño | omisión silenciosa |
| 3 | `ETAPA 1: T01 T02 T03` cuando su propia tabla dice que T02 y T03 dependen de T01 | se contradice a sí mismo |
| 4 | T04 tocaba las tres capas de una; T01 tocaba el repo entero | dimensionamiento |
| 5 | Dejó `<quién>` y `<cuántos minutos>` sin completar, con la decisión ya tomada | la plantilla como texto a copiar, no como formulario |

**El 2 es el peligroso**, y es el que justifica que G0 lo firme una persona: los otros
cuatro se ven leyendo el plan con atención, pero una funcionalidad que **no está** no se ve
en ningún lado. Hay que ir al encargo y tachar requisito por requisito. Diez minutos.

El 3 tiene consecuencia práctica más allá del error: **si el planificador duda del corte,
que no declare etapas.** Deducidas de la tabla salen bien y además respetan los choques de
archivo, que es la regla que más cuesta aplicar a mano.

Y una que era culpa nuestra: las tareas decían *"los tests ya están en el repo y fallan"* y
no estaban. El método dice que **los tests los escribe el humano antes de cada etapa**, pero
eso no estaba en el encargo ni en el prompt del arquitecto. Ahora el plan tiene que incluir
una sección "Tests que tenemos que escribir", con archivo y clase por tarea, agrupados por
etapa: es la lista de trabajo del humano antes de lanzar.

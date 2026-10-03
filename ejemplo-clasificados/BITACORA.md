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

## 2026-09-30 · G0, segunda revisión: arregla lo mecánico, ignora lo estructural

Le devolvimos el plan con cinco correcciones. Arregló dos:

- `.vue` → `.jsx` en las cinco referencias.
- Agregó la tabla "Tests que tenemos que escribir", y completó `G3 (responsable: Jose,
  15 min)`.

E ignoró las dos que importaban, **las dos veces**:

- Seguía faltando el mismo tercio del alcance: favoritos, mensajes, editar tus avisos,
  filtro por categoría, sistema de diseño.
- Seguía con `ETAPA 1: T01 T02 T03` contra su propia tabla, que dice que T02 y T03
  dependen de T01.

El patrón es nítido y vale como regla: **arregla lo que es buscar y reemplazar; no
reestructura.** Y con cinco pedidos en una corrida, elige los baratos y da por terminado.

**Qué hicimos, que es lo que manda HUMANO.md §4:** dejar de reespecificar y **partir**.
Las etapas las borramos nosotros —tres líneas, y deducidas salen mejor porque respetan los
choques de archivo— y al arquitecto le dimos **un solo trabajo**: agregar las tareas que
faltaban. `planificar.sh` ganó un modo `INSTRUCCION=` para eso.

### 16. Dos tablas indexadas por tarea rompieron la deducción de etapas

Al borrar las etapas declaradas, la deducción devolvió **las ocho tareas en una sola etapa,
en paralelo**. La causa era la tabla de tests que nosotros habíamos pedido: `_etapas.py`
leía toda fila que empezara con `| TNN |`, así que la segunda tabla pisaba a la primera y
todas las tareas quedaban sin dependencias.

Lo atrapó `SOLO_ETAPAS=1`, que existe exactamente para eso: **mirar el corte antes de lanzar
nada**. Sin ese comando, ocho tareas se habrían lanzado juntas, pisándose los archivos.

Y hay una lección sobre nosotros, no sobre el agente: **la corrección que le pedimos
introdujo el bug.** Pedir una tabla nueva parecía gratis.

## 2026-09-30 · Un pedido por corrida sí funcionó

Con una sola instrucción —*"agregá SOLO las tareas que faltan"*— el arquitecto escribió
T09 a T13: favoritos, mensajes, editar tus avisos, filtro por categoría y el sistema de
diseño SCSS. Trece tareas, y el plan sigue siendo ejecutable.

Le quedó un defecto mecánico —las cinco filas nuevas duplicadas en la tabla— que sacamos
nosotros. Es el patrón de siempre: **hace el trabajo, no revisa el resultado.**

### 17. Los choques de archivo no se detectaban si el plan no usaba backticks

Al deducir las etapas, **T09 y T12 quedaron juntas, y las dos escriben `AdsList.jsx`.** Es
exactamente la falla que el método más advierte y que `_etapas.py` existe para evitar.

La causa: el script sacaba los archivos sólo de texto **entre backticks**. El plan de Pacman
los escribía así y el de clasificados no, así que las tareas del segundo quedaban sin
archivos y la regla del choque no se aplicaba a ninguna. No fallaba: **dejaba de mirar.**

Los dos bugs de etapas de hoy —el formato `ETAPA` y este— tienen la misma raíz: **el plan es
un artefacto que lee una máquina, y sólo estaba especificado en prosa.** La plantilla mostraba
una forma, el parser esperaba otra, y nada verificaba el contrato.

**Qué cambió en el método:** además de leer las columnas por posición y aceptar los archivos
con o sin backticks, `_etapas.py` ahora **avisa cuando una tarea no tiene archivos
detectados**. No es necesariamente un error del plan, pero es la única señal de que la regla
del choque no se está aplicando. Con ese aviso, este bug se veía en la primera corrida.

> La regla general: **cuando un verificador deja de encontrar algo, tiene que decirlo.**
> Un chequeo que no encuentra nada y un chequeo que no se ejecutó se ven idénticos desde
> afuera, y es la tercera vez en el día que nos muerde la misma forma.

## 2026-09-30 · G0 completo: 27 tareas, 10 etapas, el encargo entero

Cuatro corridas del arquitecto, cada una con **un solo pedido**:

| Corrida | Pedido | Resultado |
|---|---|---|
| 1 | "escribí el plan" | siete preguntas, cero archivos |
| 2 | ídem, con el prompt nombrando `write` | `PLAN.md` y 8 tareas |
| 3 | "agregá SOLO las tareas que faltan" | +5 tareas (favoritos, mensajes, editar, filtro, diseño) |
| 4 | "partí T09 y T10" | las dos de seis archivos pasaron a doce de uno |
| 5 | "faltan registro y búsqueda" | +4 tareas |

Y el tachado final contra el encargo da los doce requisitos cubiertos. El plan valida sin
errores de forma y se corta en diez etapas que respetan dependencias y choques de archivo.

**Lo que hicimos nosotros**, que es exactamente lo que `HUMANO.md` dice que no se delega:
cerrar siete decisiones, rechazar el primer plan con cinco defectos, **encontrar las dos
omisiones tachando requisito por requisito** —el registro estaba excluido de T04 y T07, así
que se podía entrar sin poder crear la cuenta—, borrar las etapas mal declaradas, sacar las
filas duplicadas y los archivos huérfanos, y resolver por escrito el último aviso.

Tiempo humano: unos 40 minutos repartidos. Tiempo del arquitecto: casi una hora de reloj a
1–2 tok/s. **Las cinco corridas juntas costaron menos que escribir 27 tareas a mano**, y el
plan que salió es mejor que el que yo había escrito antes en `plan-humano-clasificados.md`
—sobre todo en el corte por capas, que yo había hecho por funcionalidad.

Lo que falta para arrancar: **escribir los tests**, que es nuestro y está listado en el plan
por etapa, y que Jose firme la línea de G0.

## 2026-10-03 · El arquitecto escribe archivos — y se va de alcance

Con el arquitecto en **Qwen3-Coder-30B-A3B-Instruct**, que **no genera bloques de
razonamiento**, por primera vez llamó a `write`. Tres puntos de datos:

| Arquitecto | ¿Pensante? | ¿Llamó a `write`? |
|---|---|---|
| gpt-oss-120b | sí | **no** — escribió 676 líneas de plan en la respuesta |
| Qwen3.8-27B | sí | **no** — razonó bien 761 s, cero archivos |
| Qwen3-Coder-30B | **no** | **sí** |

**No era el modelo ni la plantilla de tool call: era pensante contra no-pensante**, con el
servidor sin separar el razonamiento. Un modelo que piensa emite su llamada dentro del
razonamiento, y el parser de herramientas sólo busca en `content`.

**Hizo el trabajo bien:** partió T06 en T30 (proyecto Vite) y T31 (punto de entrada), con las
dependencias correctas y los archivos dentro del alcance de cada una.

### 21. Y se fue de alcance: 51 archivos de tarea donde había 27

Le pedimos partir una tarea en dos. Además **duplicó casi todas las demás** con el nombre
cambiado (`_` por `-`) y dejó las dos versiones, más dos huérfanos. El validador lo atrapó
entero:

```
✗ archivos en tareas/ que la tabla no menciona: T30 T31
✗ T06 tiene más de un archivo: T06-scaffolding-frontend.md, T06-scaffolding-vite.md
✗ T07 tiene más de un archivo: ...
```

Los 22 duplicados eran archivos sin versionar, así que `git clean` sobre `tareas/` los sacó y
el resto volvió con un `git checkout`. **Las herramientas de alcance del método no aplican a
G0**: el gate limita al ejecutor por tarea, y el arquitecto escribe donde quiere. El
validador es lo único que hay, y alcanzó.

### 22. Un error de proceso nuestro: `git add -A` con un agente corriendo

El commit que dice "Bitácora: T40, el A/B nulo" **arrastró los cambios del arquitecto sin
revisarlos**, porque hice `git add -A` mientras todavía estaba escribiendo. Después hubo que
desenredar qué era de quién leyendo `git log -S`.

> **No commitees con un agente corriendo.** Y menos con `-A`.

### 23. El validador no cruzaba la cabecera del archivo con la fila de la tabla

Al arreglar las dependencias que quedaron apuntando a T06 —tres tareas— **creamos una
inconsistencia**: la tabla decía que T13 dependía de T31 y su archivo decía T30. Son dos
declaraciones de lo mismo y nada las comparaba, y cada una la lee alguien distinto: el runner
ordena las etapas por la tabla y el agente lee el archivo.

Ahora `validar-plan.py` las cruza, y lo primero que hizo fue atrapar la que acabábamos de
crear.

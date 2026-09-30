# Qué queremos

Un sitio de clasificados que se pueda usar de verdad: publicás un aviso, la gente lo
encuentra, te escribe. Básico pero lindo.

Tiene que tener: cuentas con login, publicar y editar tus propios avisos, un listado donde
buscar y filtrar por categoría, la ficha del aviso, favoritos, y mensajes entre el que
publica y el que pregunta.

No queremos: pagos, moderación, mails, subir archivos (las fotos van por URL), ni búsqueda
inteligente. Un idioma, un país.

## Cómo lo queremos hecho

- **Backend en FastAPI con MySQL y SQL escrito a mano**, como el resto de nuestros
  proyectos. Sin ORM.
- **Frontend en React + Vite + SCSS**, con Vitest para los tests. **El diseño lo hacemos
  nosotros**: sin Tailwind ni librerías de componentes. Queremos que se vea bien, no que se
  vea como todo lo demás.
- **Login con cookie de sesión `httpOnly`**, no JWT guardado en el navegador.
- Las contraseñas con `hashlib.scrypt`, que ya viene con Python.
- Todo en UTC.
- **Las migraciones tienen que poder revertirse.** Si no se puede volver atrás, no se sube.
- En producción, un solo proceso: el backend sirve el front compilado.

## Lo que ya está

La estructura de carpetas (`backend/app`, `backend/migraciones`, `backend/tests`,
`frontend/src/{design,pages,services}`, `frontend/tests`, `scripts`, `tareas`).

MySQL 8 instalado local (apagado: `brew services start mysql`), Python 3.12, Node.
Sin Docker.

## Qué necesitamos de vos

El plan y las tareas, siguiendo el método del repo (`../METODO.md`,
`../DESCOMPOSICION.md`, plantillas en `../plantillas/`).

Dos cosas que nos importan especialmente, porque ya nos mordieron antes:

1. **Decinos qué decisiones quedan abiertas** en vez de elegir por tu cuenta y seguir.
2. **Marcá las tareas que tocan el mismo archivo**, para no lanzarlas en paralelo.

## Decisiones cerradas

Preguntaste siete cosas. Estas son las respuestas; no vuelvas a abrirlas.

1. **La scaffolding es la tarea T01**, no la hacés vos antes de planificar. Planificá primero.
2. **Sin gestores extra**: `pip` con `requirements.txt` en el backend, `npm` en el frontend.
   Cuantas menos piezas móviles, menos cosas que expliquen un rojo.
3. **pytest y vitest**, y sí: **los tests van escritos antes de cada tarea y fallando**. El
   agente los hace pasar y no los toca — el gate lo verifica, no es una recomendación.
4. La primera migración y su reversa son parte de la tarea del esquema, no una tarea aparte.
5. **G3 lo hace Jose, 15 minutos.**
6. **Capas del backend, en una sola dirección**: `app/datos` → `app/servicios` → `app/rutas`.
   Cada una sólo importa las anteriores. Escribí `scripts/_arquitectura.py` con esas capas
   (hay un ejemplo en `../ejemplo-pacman/scripts/_arquitectura.py`) así el gate lo verifica
   solo.
7. **El orden de las etapas lo decidís vos**: es tu trabajo, no una decisión de negocio.
   Infraestructura primero está bien.

Si te queda alguna decisión abierta, **escribila en una sección del plan y seguí**. No
pares a preguntar: el plan incompleto es más útil que ningún plan.

## Revisión del primer plan (G0, rechazado)

El plan estaba bien armado pero no se aprueba. Cinco cosas, en orden de gravedad:

1. **Mezclaste React con Vue.** El encargo dice React; planificaste `App.vue`, `Login.vue`,
   `AdsList.vue`, `AdDetail.vue`, y T06 se titula "Vite y React" y crea `App.vue`. Son
   frameworks distintos. React usa `.jsx`/`.tsx`.

2. **Falta un tercio del alcance.** El encargo pide **favoritos**, **mensajes entre el que
   publica y el que pregunta**, **editar tus propios avisos**, **filtro por categoría** y
   un **sistema de diseño propio en SCSS** (sin Tailwind, y lo subrayamos). Ninguna de las
   ocho tareas los cubre. Un requisito que no está en el plan no lo construye nadie.

3. **La ETAPA 1 contradice tu propia tabla.** Pusiste `T01 T02 T03` juntas, y tu tabla dice
   que T02 y T03 dependen de T01. Una tarea no puede correr en la misma etapa que aquello
   de lo que depende. Si dudás del corte, **no declares etapas**: se deducen solas de la
   tabla, y así también se respetan los choques de archivo.

4. **Dos tareas son demasiado grandes.** T04 toca las tres capas (`rutas`, `servicios`,
   `datos`) de una: son tres tareas. T01 toca el repo entero. La pregunta que ordena el
   tamaño no es cuántos archivos toca sino **cuántas funciones tiene que escribir el
   agente**: una a tres, no ocho.

5. **Quedaron plantillas sin completar.** `G3 — prueba de uso (responsable: <quién>,
   <cuántos minutos>)` cuando ya te dijimos Jose, 15 minutos; y `<pregunta propia del
   proyecto>` sin contestar. La plantilla es un formulario, no un texto para copiar.

Y una que es nuestra culpa por no haberla dicho: **los tests los escribimos nosotros, antes
de cada etapa.** Tus tareas dicen "los tests ya están en el repo y fallan" y no están. En el
plan, agregá una sección **"Tests que tenemos que escribir"** con el archivo y la clase
exactos por tarea, agrupados por etapa. Eso es lo que nos toca hacer a nosotros antes de
lanzar cada etapa.

Dos cosas que hiciste bien y no cambies: las capas del backend con su `_arquitectura.py`, y
haber listado las decisiones abiertas adentro del plan. Una de esas cuatro no va: **el orden
de las etapas es tu trabajo**, ya te lo dijimos.

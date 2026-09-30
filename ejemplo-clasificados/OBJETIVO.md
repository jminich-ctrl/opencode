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

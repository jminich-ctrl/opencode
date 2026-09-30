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

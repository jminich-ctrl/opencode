# Reglas para el agente ejecutor — sitio de clasificados

Esto se suma al `AGENTS.md` de la raíz del repo. Donde diga algo distinto, manda este.

## Dependencias permitidas

La regla general del método es «nada fuera de la biblioteca estándar». Acá no alcanza: el
plan pide una API HTTP y un frontend con tests, y eso no se hace con stdlib sin reescribir
un framework. Entonces la lista está **cerrada y declarada**, que es el punto: el límite
sigue existiendo, sólo que lo fija el plan y no el azar.

**Backend** (`backend/requirements.txt`):

- `fastapi` — la API
- `uvicorn` — el servidor
- `pydantic` — validación de entrada y salida
- `pymysql` — el driver de MySQL

Y en `backend/requirements-dev.txt`, que es para lo que **sólo** existe para testear y no
se despliega. Ese archivo lo mantenemos nosotros, no lo toques:

- `pytest` — el corredor de tests
- `httpx` — el cliente de tests de FastAPI

**Frontend** (`frontend/package.json`):

- `vite` — el bundler
- `@vitejs/plugin-react` — el plugin de React para Vite; sin él `vite.config.ts` no puede
  importar `react()`
- `react` y `react-dom` — la UI
- `vitest` — el corredor de tests
- `jsdom` y `@testing-library/react` — para testear componentes
- `sass` — para los `.scss` del sistema de diseño propio

**Con versión fija.** `fastapi==0.104.1`, no `fastapi`. Sin fijar, el veredicto del gate
depende del día: httpx 0.28 sacó un atajo que usa el TestClient de la starlette que trae
fastapi 0.104, y de un día para el otro todos los tests de endpoints empezaron a fallar con
un `TypeError` que no tenía nada que ver con el código. Una medición que cambia sola no es
una medición.

**Lo que importás, declaralo.** Un `import` de un paquete que no está en el manifiesto no
falla al escribirlo: falla cuando alguien corre los tests, con un «Cannot find package» que
no se parece en nada a la causa. Si necesitás algo que no está en esta lista, pará y decilo:
la lista se amplía, no se esquiva.

**La base es MySQL con SQL a mano, sin ORM**, como dice `PLAN.md`: el esquema está cerrado
ahí y un ORM agrega una capa que nadie pidió. La conexión sale de variables de entorno
(`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`), nunca de valores
escritos en el código: el runner levanta un servidor propio del proyecto y las exporta.

**Sin librerías de diseño.** Ni Tailwind, ni Bootstrap, ni componentes de terceros: el CSS
es propio y en SCSS. El gate lo verifica (`sin librerías de diseño`), así que agregarlo da
rojo.

Cualquier otra cosa —incluida una que te parezca obvia— es una dependencia nueva: pará y
decilo en la respuesta. Si la tarea no se puede hacer sin ella, es un `IMPOSIBLE:` legítimo
y no te lo contamos como error.

## Lo que ya está decidido y no se rediscute

- **Un módulo de `rutas/` expone un `router` de FastAPI y nada más.** No importa
  `backend/app/main.py` ni lo modifica: `main.py` descubre los routers de `rutas/` y los
  monta solo. Si seis tareas tuvieran que agregar su `include_router`, seis tareas
  editarían el mismo archivo y el paralelismo del plan se cae.

- **Las claves se hashean con `hashlib.scrypt`**, de la biblioteca estándar. No `passlib`,
  no `bcrypt`, no `argon2`: está cerrado en `PLAN.md` desde G0. Un agente ya intentó
  `passlib` y la tarea se cayó por una dependencia que nadie declaró.
- **Precios en centavos, entero.** Nada de flotantes para dinero.
- **Esquema de tablas**: el de `PLAN.md`, tal cual. Si una tarea necesita una columna que
  no está, eso es un cambio de plan: pará y decilo.
- **Errores de la API**: una ruta levanta `HTTPException(código, "mensaje")` con los códigos
  del plan y **no arma el cuerpo de la respuesta**. El `main.py` lo normaliza a
  `{"error": ...}` para toda la aplicación, y convierte el `422` de FastAPI en el `400` que
  pide el plan. Si validás a mano para esquivar el 422, estás resolviendo dos veces algo
  que ya está resuelto en un solo lugar.

## Desde dónde corren los tests

**Desde la raíz del proyecto, siempre**, los de backend y los de frontend. Así que las
rutas que un test abra se escriben desde ahí: `backend/app/datos/x.py`,
`frontend/package.json`. No `app/datos/x.py` ni `package.json`.

Vale para los dos corredores: pytest corre con la raíz como cwd, y vitest también —se le
pasa `--root frontend` en vez de entrar a la carpeta, justamente para que el cwd no cambie—.
Si un test se escribe suponiendo otro directorio, pasa donde lo escribiste y falla donde lo
juzgamos, que es la peor forma de fallar.

## Entorno

No instales nada a mano ni corras `pip` o `npm` por tu cuenta: el runner prepara el
entorno antes de lanzarte (`scripts/preparar-entorno.sh`). Tu trabajo es **declarar** la
dependencia en el manifiesto; instalarla es del método. Si el gate dice que falta un
corredor de tests, eso es un defecto nuestro: reportalo y no lo arregles vos.

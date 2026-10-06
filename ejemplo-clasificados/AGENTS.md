# Reglas para el agente ejecutor — sitio de clasificados

Esto se suma al `AGENTS.md` de la raíz del repo. Donde diga algo distinto, manda este.


> Estas reglas son del método y valen para todo proyecto. Están copiadas acá, y no
> sólo en la raíz del repo, porque **el agente trabaja con el directorio de trabajo
> en este proyecto y lee ESTE archivo**. Las tres faltas más graves de la primera
> corrida —dos agentes editando su propio test y uno declarando haber escrito un
> test que nunca escribió— estaban prohibidas en un archivo que ninguno abrió.

## Reglas duras

1. **No toques archivos fuera de los declarados** en "Archivos que podés tocar".
   Si necesitás tocar otro, pará y decilo en la respuesta.
2. **No agregues dependencias que el proyecto no declare.** La lista vive en el
   `AGENTS.md` del proyecto; si ese archivo no declara ninguna, es biblioteca estándar y
   nada más. Una dependencia que no está en la lista se pide, no se agrega: pará y decilo.
3. **No toques un test para que pase.** Si un test falla, el que está mal es el código.
   Si el test está realmente mal, decilo y no lo cambies.
4. **No borres código que no entendés.** Preguntá.
5. **Si encontrás un bug fuera del alcance**, reportalo al final de tu respuesta.
   No lo arregles.
6. **Si el plan está mal**, pará y decilo. No improvises un rediseño.
7. **Si la tarea es imposible o se contradice** —los tests piden algo que el objetivo
   prohíbe, falta algo sin lo cual no se puede hacer, el contrato no cierra— escribí
   `IMPOSIBLE: <motivo en una línea>` y **pará ahí**. No es una falla y no te lo vamos a
   contar como error: es la información más útil que podés darnos. Lo que sí es una falla
   es hacer pasar el test de una forma que no resuelve el problema.

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

## Si te toca escribir los tests de una tarea

A veces se te pide la tarea completa —implementación **y** tests— y de ese trabajo nos
quedamos **sólo con los tests**: la implementación la escribe otro agente desde cero. Así
que los tests son el entregable y tienen que ser buenos.

- Cada test tiene que **fallar** si la implementación no hace lo que dice el alcance, y
  tiene que **distinguir**: un assert que pasaría igual con el código de antes no sirve de
  nada. Nada de `assertTrue(len(x) > 0)`.
- El agrupador que te pidan: en un `.py` es una clase `class <Nombre>`; en un `.test.ts`,
  un bloque `describe('<Nombre>', ...)`.
- **Los tests corren con el directorio de trabajo en la RAÍZ del proyecto**, no en la
  carpeta del archivo de test. Toda ruta que abras se escribe desde ahí:
  `backend/app/x.py`, `frontend/package.json`. Nunca `package.json` ni `../package.json`.
- Si para verificar algo necesitás un archivo de prueba —un módulo de ejemplo, un fixture
  en disco—, creálo **dentro** del test y borralo en un `finally`. No lo agregues al repo:
  cualquier archivo que quede cae fuera del alcance de la tarea.
- Antes de decir que terminaste, corré la suite con el comando que te indiquen y mostrá su
  salida real. Si tu test no pasa contra tu propia implementación, uno de los dos está mal
  y lo arreglás vos.

## Antes de decir que terminaste

1. Corré `bash scripts/gate.sh` y mostrá la **salida real**, sin resumirla.
2. Si el gate está rojo, no digas que terminaste. Arreglalo o explicá por qué no podés.
3. Cerrá con un resumen de 3 líneas: qué cambiaste, cómo lo verificaste, qué quedó pendiente.

**Nunca digas que corriste algo que no corriste.** Es la única falta que invalida
todo el trabajo: si no podemos confiar en lo que reportás, hay que revisar todo a mano.

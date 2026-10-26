# AGENTS.md — plantilla

Reglas para los agentes que trabajan en este proyecto.


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

8. **No dejes `TODO` ni `FIXME` en lo que escribís.** El gate los busca sólo en los
   archivos de tu tarea: si quedó algo pendiente, va en el resumen, no en el código.
9. **No dejes directorios vacíos.** Git no los versiona, así que el merge no se los lleva y
   el que integra se encuentra con un import que no existe.
10. **No commitees nada generado**: `node_modules/`, `__pycache__/`, `dist/`, un `.venv`.
    Los instala el método, no la tarea. Si aparecen en el diff, el gate da rojo — y no es
    por el contenido, es porque nadie puede revisar lo que no escribió una persona.
11. **No rompas tests que andaban.** El gate compara contra la lista de los que ya fallaban
    antes de tu tarea: si uno que pasaba deja de pasar, es tuyo, aunque no hayas tocado su
    archivo.
12. **No claves rutas absolutas en un test.** `/Users/...` pasa sólo en la máquina donde se
    escribió. Las rutas se escriben desde la raíz del proyecto.
13. **No mockees lo que vinieron a probar.** Si mockeás un símbolo que vive en un archivo de
    TU tarea, estás reemplazando el sujeto: el gate lo detecta porque las líneas de la
    implementación no se ejecutan. Mockeá lo de abajo, no la tarea.
14. **Si tu implementación tiene una rama que ningún test distingue, decilo.** El gate muta
    tu código línea por línea y exige que la suite lo note; cuando **sobreviven mutantes**
    es que escribiste comportamiento que nadie verifica. La salida te dice cuál línea.
    Agregar un test tuyo no alcanza si el test es de otra etapa: lo que corresponde es
    nombrarlo en el resumen.

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

### Si la tarea es la CAPA DE DATOS

Mockear `conexion()` para probar la capa de datos no sale bien, y está medido: el
2026-10-24 dos tareas fallaron por los dos únicos caminos que ese mock deja.

- **Si el test clava la cadena SQL** —`mock_cursor.execute.assert_called_once_with("SELECT
  ...")`— los mutantes mueren y el test se acepta. Pero la base nunca se toca, así que una
  consulta imposible pasa igual: el test que el gate aprobó para T28 fijaba `categoria` y
  `precio`, dos columnas que no existen, y la implementación que lo haga pasar va a escribir
  esa consulta para que MySQL la rechace. No es un test que deja pasar el bug: lo OBLIGA.
- **Si el test no afirma nada sobre la consulta**, sobreviven los mutantes —borrar el
  `cur.execute(` no cambia el resultado— y el validador lo rechaza, con razón.

Un test de capa de datos tiene que correr contra la base REAL: ahí el esquema rechaza la
columna que no existe, que es exactamente lo que se quiere que pase.

PERO eso todavía no es seguro en este método, y hay que saberlo: todos los worktrees comparten
el MySQL de 127.0.0.1:33306 y nadie lo limpia entre corridas. El validador corre el mismo test
dos veces —una sin la implementación y otra con ella— así que la segunda choca con lo que
insertó la primera: el 2026-10-24 eso dio `Duplicate entry 'test@example.com' for key
'usuarios.email'` y el veredicto le echó la culpa al test.

Mientras eso no esté resuelto, una tarea de capa de datos no tiene un camino limpio. Decilo
en vez de inventar un test que pase: es un hueco del método, no de la tarea.

## Antes de decir que terminaste

1. Corré `bash scripts/gate.sh` y mostrá la **salida real**, sin resumirla.
2. Si el gate está rojo, no digas que terminaste. Arreglalo o explicá por qué no podés.
3. Cerrá con un resumen de 3 líneas: qué cambiaste, cómo lo verificaste, qué quedó pendiente.

**Nunca digas que corriste algo que no corriste.** Es la única falta que invalida
todo el trabajo: si no podemos confiar en lo que reportás, hay que revisar todo a mano.

# Reglas para el agente ejecutor

Este archivo lo lee OpenCode automáticamente. Vale para todo el repo.

## Lo que estás haciendo

Implementás **una** tarea, definida en `tareas/TNN-*.md`. Nada más que eso.
Si el archivo de tarea no está en tu contexto, pedilo antes de empezar.

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

8. **No commitees nada generado.** `__pycache__/`, un `.pyc`, `dist/`: si aparecen en el
   diff el gate da rojo, y no por el contenido sino porque nadie puede revisar lo que no
   escribió una persona. Las dependencias instaladas —`node_modules/`, `.venv`— las pone el
   método antes de lanzarte y el gate las filtra, así que por ésas no te va a dar rojo: lo
   que no tenés que hacer es correr `pip` o `npm` (regla 2).
9. **No rompas tests que andaban.** El gate compara contra la lista de los que ya fallaban
   antes de tu tarea: si uno que pasaba deja de pasar, es tuyo, aunque no hayas tocado su
   archivo.
10. **No claves rutas absolutas en un test.** Una ruta absoluta —`/Users/...`— pasa sólo en
    la máquina donde se escribió. Las rutas se escriben desde la raíz del proyecto.
11. **Si tu implementación tiene una rama que ningún test distingue, decilo.** El gate muta
    tu código línea por línea y exige que la suite lo note: cuando **sobreviven mutantes**
    es que escribiste comportamiento que nadie verifica, y la salida dice en qué línea.

12. **No mockees lo que vinieron a probar.** Si mockeás un símbolo que vive en un archivo
    de TU tarea, estás reemplazando el sujeto: el gate lo nota porque las líneas de la
    implementación no se ejecutan. Mockeá lo de abajo, no la tarea.

13. **Parcheá donde el nombre SE USA, no donde se define.** Si la implementación trae un
    nombre con `from src.datos.d1 import leer1`, entonces `patch('src.datos.d1.leer1')` no
    toca nada: cuando el patch corre, `src.servicios.s1.leer1` ya quedó ligado al original.
    Va `patch('src.servicios.s1.leer1')`, el módulo que estás probando. Medido el
    2026-10-27: siete tests de una etapa parchearon el módulo donde el nombre se define, y
    las tres tareas que después obedecieron el contrato al pie de la letra quedaron en punto
    muerto por eso, con la implementación correcta. Mirá con qué import la trae el contrato
    antes de elegir el objetivo del patch: con `import src.datos.d1` y acceso por atributo,
    o con el `from` adentro de la función, el lugar es otro.

## Estilo

- Español en docstrings, comentarios, nombres de tests y mensajes de commit.
- Seguí el estilo del código que ya está: nombres, densidad de comentarios,
  forma de manejar errores. No introduzcas un estilo nuevo.
- Docstring en toda función pública, breve, diciendo qué hace y qué devuelve.
- Sin archivos generados: nada de `__pycache__`, `.pyc`, temporales.

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

## Lo que NO se instala en este repo, y por qué

Relevado el 2026-10-31. Las cuatro primeras convierten rojos en verdes por diseño, o sea que son
exactamente lo que el gate de este método existe para atrapar:

- **`pytest-testmon`** — su propósito es NO correr tests. «La suite pasó» se volvería «el
  subconjunto que testmon creyó afectado pasó», choca de frente con la mutación, y en el brazo
  nulo puede seleccionar ~0 tests y dar VERDE.
- **`pytest-rerunfailures`** — por omisión guarda sólo el traceback del último intento: convierte
  rojos intermitentes en verdes, que es la patología que el brazo nulo existe para cazar.
- **`flaky`** — oculta inestabilidad por diseño, y su último commit es de 2024.
- **`deepeval`** — se lleva `pytest`, `pytest-xdist`, `pytest-repeat`, `pytest-rerunfailures` y
  `pytest-asyncio` como dependencias de RUNTIME: una librería de juez pineando nuestro pytest.
- **`diff-cover` como chequeo de alcance** — no tiene noción de conjunto permitido, y su
  `--fail-under` lo gana un agente que agrega un test que pega en sus propias líneas.

Y `pytest-randomly` sí, pero sabiendo dos cosas: va a poner rojo un rato por acoplamiento que ya
existe, y la semilla pasa a ser campo obligatorio del veredicto.

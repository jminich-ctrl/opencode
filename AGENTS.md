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

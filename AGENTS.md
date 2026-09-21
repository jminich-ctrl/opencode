# Reglas para el agente ejecutor

Este archivo lo lee OpenCode automáticamente. Vale para todo el repo.

## Lo que estás haciendo

Implementás **una** tarea, definida en `tareas/TNN-*.md`. Nada más que eso.
Si el archivo de tarea no está en tu contexto, pedilo antes de empezar.

## Reglas duras

1. **No toques archivos fuera de los declarados** en "Archivos que podés tocar".
   Si necesitás tocar otro, pará y decilo en la respuesta.
2. **No agregues dependencias.** Todo con biblioteca estándar.
3. **No toques un test para que pase.** Si un test falla, el que está mal es el código.
   Si el test está realmente mal, decilo y no lo cambies.
4. **No borres código que no entendés.** Preguntá.
5. **Si encontrás un bug fuera del alcance**, reportalo al final de tu respuesta.
   No lo arregles.
6. **Si el plan está mal**, pará y decilo. No improvises un rediseño.

## Estilo

- Español en docstrings, comentarios, nombres de tests y mensajes de commit.
- Seguí el estilo del código que ya está: nombres, densidad de comentarios,
  forma de manejar errores. No introduzcas un estilo nuevo.
- Docstring en toda función pública, breve, diciendo qué hace y qué devuelve.
- Sin archivos generados: nada de `__pycache__`, `.pyc`, temporales.

## Antes de decir que terminaste

1. Corré `bash scripts/gate.sh` y mostrá la **salida real**, sin resumirla.
2. Si el gate está rojo, no digas que terminaste. Arreglalo o explicá por qué no podés.
3. Cerrá con un resumen de 3 líneas: qué cambiaste, cómo lo verificaste, qué quedó pendiente.

**Nunca digas que corriste algo que no corriste.** Es la única falta que invalida
todo el trabajo: si no podemos confiar en lo que reportás, hay que revisar todo a mano.

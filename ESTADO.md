# Estado — 2026-11-21

Dónde está todo hoy, qué bloquea qué, y qué hace falta decidir. Un solo lugar: antes esto vivía
en un `HANDOFF-*.md` suelto en el home que quedó un mes viejo. Se actualiza al cerrar cada
sesión de trabajo.

- El método y sus mediciones: [`MEDICION.md`](MEDICION.md) (lo último es §31).
- Los dos experimentos y su compuerta: [`experimentos/README.md`](experimentos/README.md).
- El material crudo: [`experimentos/crudo/INDICE.md`](experimentos/crudo/INDICE.md).

---

## En una frase

El instrumento está sano y verificado; lo que está trabado es el **research**, y el cuello no es
el gate ni el modelo ejecutor: es que **el arquitecto no replanifica** las tareas que el gate
rechaza, y sin eso no se escriben ítems nuevos, y sin ítems nuevos K se queda en 16 y 7 de las 9
decisiones de modelo siguen siendo indecidibles.

## La cadena, de la pregunta al atasco

1. **Las dos preguntas de investigación** —¿sirve la memoria verificada? ¿qué modelo en cada
   papel?— están diseñadas y **bloqueadas a propósito** por la compuerta de cinco preguntas.
2. Las dos se destraban con lo mismo: **subir K**. Con K=16 congelados, el McNemar exacto
   necesita 13-3 para moverse y 7 de 9 comparaciones son indecidibles.
3. Subir K es **escribir ítems nuevos**, y escribir ítems nuevos es **terminar el plan de
   `ejemplo-clasificados/`**: 18 de 34 tareas hechas, **16 pendientes**, 10 de ellas backend en
   Python — justo lo que falta, porque de los 9 ítems viables de hoy sólo 4 son Python (el
   mutador no muta `.sql` ni TypeScript).
4. De esas 16, cuatro se corrieron dos veces el 2026-11-10. **El gate no dejó pasar ninguna:
   0 falsos verdes en 16 intentos, con la misma huella las dos corridas.**
5. La regla del método dice qué significa eso: *tres fallas con la misma huella no son tres
   fallas del agente, son una del enunciado.* Hay que **reescribir el enunciado**.
6. Reescribir el enunciado es trabajo del arquitecto. **Y el arquitecto no lo hace.**

## Lo que se probó y lo que refutó

Creí que el arquitecto no actuaba porque recibía la categoría («la suite está en rojo») en vez
del dato. Era cierto que la recibía mal, y se arregló (`6edb4bd`): el veredicto del arnés ahora
se escribe a disco y se lee de ahí, con 4 tests.

**Con el motivo correcto adelante, verificado verbatim en el prompt, el arquitecto igual no
reescribió T04, T26 ni T28.** El arreglo era real y necesario; no era la causa. Lo dejé dicho
antes de lanzar —«si tampoco cambia nada ahora, el problema no era el motivo»—, que es lo único
que convierte una corrida en medición y no en confirmación.

Lo que los transcripts sí muestran (`experimentos/crudo/replan/replan-T04.log`, `-T26.log`): el
arquitecto gasta el presupuesto **deliberando si tiene permiso para leer un archivo** y nunca
llama a `write`. El candidato es la restricción de alcance del prompt de `replanificar.sh`
—«Mirá SOLO el archivo de la tarea, PLAN.md y los archivos que la tarea nombra»—, que se agregó
para que no explorara `node_modules` y ahora parece dejarlo sin material.

## Lo que necesita una decisión humana

| # | Qué | Por qué no lo decido yo |
|---|---|---|
| 1 | **Aflojar la restricción de alcance del prompt del arquitecto**, de prohibición general a lista explícita de lo que sí puede leer. | Es un cambio de MÉTODO, y la línea con «hacerle el trabajo al planificador» es exactamente lo que está en juego. Se mide con el criterio que el script ya tiene: escribió o no escribió. |
| 2 | **El HUECO de T16**: `the plan doesn't provide a service function to list favorites`. | Por el método, un hueco del plan lo decide una persona. El arquitecto hizo lo correcto al declararlo en vez de inventarlo. |
| 3 | **Los dos defectos de contrato de los enunciados** (ver abajo): si se arreglan tarea por tarea o se arregla la plantilla. | Afecta a las 16 pendientes y a toda tarea futura. |

Los dos defectos de contrato, medidos en las dos corridas:

- **El enunciado no declara con qué `import` la implementación trae el nombre** (T04, T26). El
  test apuesta a una de tres formas y el patch no tiene efecto. La regla existe en `AGENTS.md`
  pero escrita para el que escribe el test, no para el único que puede fijarla: el enunciado.
- **El enunciado no declara el contrato de respuesta** (T16, T28). El test inventa claves que no
  son columna de ninguna tabla, y una vez aceptadas obligan para siempre.

## Lo que sí avanzó, y está verificado

| | |
|---|---|
| `d761233` | El contexto declarado del ejecutor era 153000 y la plataforma sirve ~35000. Tres semanas de un dato medido que nunca llegó a la config. Sin esto cada tarea moría con un 400 que no se parece a su causa. |
| `6edb4bd` | El veredicto del arnés se escribe y llega a quien lo necesita. 4 tests. |
| `2541cf6` | Un permiso denegado ya no se cuenta como corte de plataforma (regalaba un reintento **e inflaba el denominador de salud de la plataforma**), y la verificación de `warm.sh` dejó de mirar modelos que ningún agente usa. 9 tests. |
| `2d1a201`, `d4fc7f0` | 4,4 MB de material de investigación, que vivía afuera del repo, cosechado adentro con `scripts/cosechar.sh`. Incluye `gate_publico.py` reescrito. |

## Lo que se perdió, y hay que rehacer

/tmp se limpió y se llevó el scratchpad del 2026-11-10. `gate_publico.py` se pudo reescribir
porque quedó en una transcripción. **No se pudieron recuperar el banco de 210 ítems de TestEval
ni su venv**, así que esa parte de §29 hay que rehacerla: bajar el banco y armar un venv con
`pytest` y `sortedcontainers`, que es lo que `--python` necesita.

Material de investigación que vive en un directorio que administra otro no está guardado: está
prestado. Por eso existe `scripts/cosechar.sh` y por eso corre en cada cierre.

## Pendientes técnicos, sin bloquear a nadie

- Correr el gate público sobre los 210 ítems (~2 h a un hilo, ~15 min con 8), una vez rearmado
  el banco.
- La replicación multi-modelo (mistral-small-24b, gpt-oss-20b, llama-3.2-8b). **Ya no es para
  generalizar: es el control del confundidor de §29.** Presupuesto ~6 h. Bloqueada por el estado
  de las réplicas de la plataforma.
- El contador de reintentos es global: no se sabe en qué registros ocurrieron (§30).
- 25 tareas con `**Prohibido tocar:**` vacío y 25 que no declaran imports. Avisos del validador,
  no bloquean.
- El paper corto del artefacto de parser; el finetune (bloqueado por hardware).

## Lo que NO se toca

- **Orion**: no se entra por ssh.
- **Una corrida activa**: no se edita ni se commitea mientras hay una.
- **El plan**: lo reescribe el arquitecto. Si no puede, se arregla el método o lo decide una
  persona; no se infiere en su lugar.

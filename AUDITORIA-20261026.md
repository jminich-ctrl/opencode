# Auditoría del método — 2026-10-26

Una sesión, veintiún arreglos, todos de la **misma familia**: un chequeo que informa éxito sin
haber medido lo que afirma medir. Ninguno salió de leer código.

El eje tampoco son las formas de defecto (eso fue el 2026-10-19) ni la genericidad (el
2026-10-20, en `AUDITORIA-20261020.md`): es **el instrumento contra un proyecto que no es
ninguno de los dos ejemplos**. Se armó un proyecto JavaScript de cero —Node 20 con
`node --test`, sin dependencias— se le pasó el método completo de G0 a G5, y tres de sus cinco
tareas las cerró un agente real.

Todo lo que sigue está verificado contra una corrida. Los commits llevan la medición adentro.

## Las tres preguntas que encontraron todo

Están en `PRUEBAS.md` como procedimiento, porque las preguntas se repiten y la lista de
defectos no:

1. **¿Qué informa este chequeo cuando no tiene material?** Once chequeos contra un proyecto
   vacío: diez contestaban bien, uno devolvía `0` y silencio en cuatro situaciones distintas.
2. **¿Qué piezas escribe cada proyecto a mano, y quién las verifica?** Eran cinco, y no había
   ninguna verificada.
3. **¿Esta copia es la única?** El juicio del chequeo de arquitectura estaba tres veces, y el
   arreglo hubo que escribirlo tres veces: 193 líneas idénticas cada una.

## Tier A — chequeos que daban verde sin medir

| el chequeo | lo que informaba | lo que medía |
|---|---|---|
| `_arquitectura.py` | `✓ dependencias en una sola dirección` | **0 de 4 módulos mapeados** en clasificados: el nodo era el nombre del archivo y las capas directorios. Muerto desde que se escribió, y `datos/ads.py` con `servicios/ads.py` eran **el mismo nodo** |
| paso 5 del gate de clasificados | nada: ni el encabezado | el `[ -f ]` estaba en la condición del paso, así que sin el archivo no imprimía ni su título y el veredicto salía «GATE VERDE» limpio |
| paso 6 del mismo | `·` suelto | la ausencia de suite reservada no sumaba a los vacíos. Y clasificados **no tiene** suite reservada: en 18 tareas cerradas, el único gate que mide lo no-optimizable nunca corrió |
| paso 6, la ruta | `✓ Ran 1 test … de composición` | con los reservados **dentro del repo** el agente los lee. Es el hack más común, está medido, y nada lo verificaba |
| sonda de plataforma | `✓ contesta` | un POST de 4 tokens, mirando sólo el código HTTP. Un 200 con `{"error":"model not loaded"}` contaba como sano (defecto 19, abierto desde el 20-10) |
| `_aserciones.py` | `0` y silencio | sin argumentos, con un archivo que no existe, con uno que no es `.py`, y con uno que no parsea. Las cuatro se leían igual que «lo miré y está limpio» |
| paso 7 de G4 | `✓ desplegado en staging` | el paso 3 de `deploy.sh` eran dos comentarios ADAPTAR: **no desplegaba nada**, en el único gate que toca usuarios |

## Tier B — las cinco piezas que cada proyecto escribe a mano

Ninguna estaba verificada, y son el cimiento de todo veredicto:

- **`correr_suite`**: el contrato de códigos. Adaptarlo a `node --test` lo rompió por las dos
  puntas y el gate emitió «la suite falla, pero NO por los tests de esta tarea» sobre tests que
  nunca corrieron. Ahora el paso 1 **calibra** el corredor con un selector imposible.
- **`fallas`**: el extractor de la línea base. Con el patrón de unittest sale **vacía** en otro
  stack — y «0 ya fallando» es lo que informa también un proyecto limpio. Ya había pasado con
  vitest, y estaba escrito en su propio comentario.
- **las capas de `_arquitectura.py`**: ver Tier A.
- **`AGENTS.md`**: seis reglas que el gate castiga no estaban escritas en ningún archivo que el
  agente abra, en los **cuatro** `AGENTS.md` del repo.
- **la ruta de los reservados**: ver Tier A.

## Lo que sólo apareció CORRIENDO

Es la segunda doctrina de la noche, y la más barata de olvidar:

- `correr-plan.sh` **relanzó una etapa entera ya hecha** —tres corridas de agente gastadas, dos
  tareas en «punto muerto», y el plan detenido sin llegar a la etapa pendiente—. Las etapas
  DECLARADAS no se filtraban por estado; las deducidas sí. **Ya estaba anotado en la auditoría
  del 2026-10-20** y nadie lo arregló: un hallazgo escrito y no arreglado se paga dos veces.
- Dos tareas en paralelo **chocaron al mergear** por `.tests-base` commiteado. El gate lo filtra
  del diff, pero el `.gitignore` de la guía no lo ignoraba: faltaban **siete** entradas de la
  lista del gate, incluidas `.venv` y `node_modules`.
- Correr el gate **después de cerrar una tarea** daba «los tests PASAN con la implementación
  vieja»: la reversión no cambiaba un byte porque HEAD ya la tenía. Una reversión vacía no es
  una reversión que pasó.
- El paso 7 de G4 era **imposible para cualquier proyecto con dependencias**: el clon limpio no
  tiene entorno. Y cuando corría, acusaba a un archivo sin commitear un rojo que estaba en el
  tronco a la vista.

## Lo que el método demostró, y hay que decirlo

- **Corre en un stack que no es Python**: G0 → runner → gate → integración → G4 → G5, con dos
  ⊘ honestos (los chequeos que son de Python: imports y mutación).
- **Un agente local cerró tres tareas al primer intento** (39-45 s cada una), una de ellas
  obligada a USAR los módulos ya hechos: los importó en vez de reimplementar.
- **Los verdes resistieron la auditoría**: 12 de 15 mutantes muertos a mano, y los 3
  sobrevivientes equivalentes (guardas defensivas y comparaciones contra 0, que `mutar.py`
  excluye por áridas).
- **La mutación por archivo** encontró en pacman lo que 19 tareas cerradas y 103 tests verdes
  no: 85 sobrevivientes, 39 de ellos en líneas que la suite nunca ejecuta.

## Mis propios errores, contados

Cinco aserciones **más anchas que su defecto** (una de ellas prohibía una frase que su propia
explicación contiene); un test de deriva que pasaba por la razón equivocada en sus cuatro casos;
tres escenarios montados en un andamio que no medía lo que yo creía; backticks dentro de
comillas dobles en bash; `$tarea` donde la variable es `$id`; `«$ESPERADO»` pegado a un
multibyte, que es el mismo defecto que ya había arreglado horas antes; una sonda puesta antes de
la guarda barata que iba a frenar igual; una regla escrita al agente que el gate no aplica, en
el commit cuyo punto era lo contrario.

**Todos los encontró correr algo.** Ninguno la lectura del diff.

## Lo que queda abierto

Decisiones, no tareas:

- **La suite reservada de clasificados** no existe. Con `T04` devolviendo `None`, escribirla va
  a dar rojo legítimo.
- **Dos rojos de su G4** son del proyecto: `password: 'contraseña'` en un fixture (el chequeo
  pide que una persona juzgue si es real) y cuatro variables `MYSQL_*` usadas y no documentadas.
- **Los 85 sobrevivientes de pacman** y los 9 hallazgos de clasificados: reabrir es otra
  decisión, otro comando y otros jueces.
- **Doce servidores falsos** en la suite, todos distintos, crecieron en tres esta noche.
  Deduplicarlos es un refactor de doce sitios; queda anotado con su medición, no hecho.
- **Un plan de veinte tareas** sigue sin probarse: lo más largo medido son cinco.

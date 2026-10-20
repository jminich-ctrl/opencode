# Auditoría del método — 2026-10-19

Cinco auditores en paralelo, uno por **forma** de defecto, calibrados con los cadáveres del
día. Cada hallazgo exigía un escenario concreto de falla; los que no lo tenían no se
reportaron. Lo que sigue está **verificado contra el código o contra logs reales**, no
tomado del reporte de un agente: dos de los hallazgos que los agentes dieron por buenos los
corregí después de medirlos yo.

El resultado grande: **el gate estaba parcialmente decorativo**, y eso explica los
misterios del día (tres tareas integradas sin tests, un módulo que no importaba viviendo en
el tronco, un «✓ en verde» sobre un test cuya implementación no existía).

## Tabla

| # | hallazgo | forma | gravedad | estado |
|---|---|---|---|---|
| 1 | Las fallas de **vitest** son invisibles al paso 1: el patrón pide un espacio donde vitest pone dos, **y** vitest imprime rutas relativas a `frontend/` mientras la tarea declara `frontend/tests/…`. 15 tareas, 8 ya marcadas hechas | veredicto que no puede fallar | **crítica** | arreglado |
| 2 | Con `FALTA_CORREDOR` en la línea base, el paso 1 dice «los tests de TNN pasan»: la línea base no nombra ninguna ruta, así que `mios` queda vacío. Cero tests corrieron | veredicto que no puede fallar | **crítica** | arreglado |
| 3 | `integrar.sh` compara una **línea constante**: en modo integración el paso 1 colapsa la suite en `✗ la suite está en rojo`, así que `comm` entre antes y después siempre sale vacío | veredicto que no puede fallar | **crítica** | arreglado |
| 4 | El paso 3 del validador de tests **nunca mutó nada** en clasificados: `CODIGO` vale `src` por defecto y el código vive en `backend/app` y `frontend/src`. `mutar.py` devolvía 0 y se imprimía «✓ los mutantes mueren». 2 de los 4 tests aceptados hoy | veredicto que no puede fallar | **crítica** | arreglado |
| 5 | El paso 4 enumera extensiones (`.py|.ts|.tsx|.jsx` bajo dos directorios) y no ve `.scss` (T13, T19), `.sql` (T03) ni manifiestos (T30): imprimía ⊘ y el gate cerraba verde. **T19 combinaba 1 y 5: ningún paso la verificaba** | lista que envejece | **crítica** | arreglado |
| 6 | `escribir-tests.sh` hace `rm -rf "$wt"` ANTES de `conservar_intento`, que arranca con `[ -d "$wt" ] \|\| return 0`: código muerto. Evidencia: `fallidos-T26` tiene 9 transcripts y **0 parches**; `fallidos-T05`, que pasa por el hermano, tiene 3 | arreglo sin su hermano | alta | arreglado |
| 7 | `escribir-tests.sh` no verifica que los archivos de la tarea estén commiteados. Peor que en implementación: ahí se pierde una corrida, acá se **acepta y copia al tronco** el test del enunciado viejo | arreglo sin su hermano | alta | arreglado |
| 8 | Toda la disciplina de cortes por tiempo vive sólo en `escribir-tests.sh`: `correr-plan.sh` no distingue inactividad de límite total, no tiene presupuestos, y no pregunta por la plataforma antes de culpar a la herramienta | arreglo sin su hermano | alta | parcial (el mensaje, sí) |
| 9 ✅ | `_suprimidas.py` reprueba el idiom de `curses` del pacman —tres casos reales— y mira el archivo entero en vez de las líneas del diff, sin dejar ninguna forma legítima de escribirlo | chequeo demasiado ancho | media | arreglado: acotado al diff + exención `# best-effort` auditable |
| 10 ✅ | El patrón de secretos de `pre-deploy.sh` marca líneas reales que son anotaciones de tipo (`password: str`): `[^a-z]{0,3}[:=]` acepta cero caracteres antes del `:`. **Medido: 17 de 88** | chequeo demasiado ancho | media | arreglado: rojo pide literal, el patrón flojo queda como aviso, y los `git diff` llevan pathspec |
| 11 ✅ | `control_se_movio` se auto-valida si la línea base quedó degenerada (`tools=0` apaga la primera mitad, un veredicto estable apaga la otra). Es el modo de falla para el que se escribió | veredicto que no puede fallar | media | arreglado: la línea base se valida al escribirse **y** al leerse |
| 12 ✅ | La columna `instrumento` se escribe y **nadie la lee**: el porcentaje de `metricas.sh` mezcla hoy 6 instrumentos. Y sale del árbol commiteado, así que dos árboles de trabajo distintos comparten huella | declaración que nadie recibe | media | arreglado: el reporte declara la mezcla, y la huella marca `+sin-commitear` |
| 13 ✅ | `correr-todo.sh` descarta con `2>/dev/null` los avisos de que el corte de etapas puede estar mal (dos tareas que escriben el mismo archivo pueden salir en paralelo) | declaración que nadie recibe | media | arreglado: los avisos se imprimen |
| 14 ✅ | El grep de `TODO` y el detector de Tailwind barren el árbol entero —incluido `node_modules`— en modo tarea, sin acotar al diff como sus tres vecinos | chequeo demasiado ancho | baja | arreglado |
| 15 ✅ | `plantillas/pre-deploy.sh` exige la palabra «down» DENTRO del archivo de migración y marca a la reversa misma; `plantillas/gate.sh` tiene `INTOCABLES='^(tests/|scripts/)'`, que no cubre `backend/tests/` | lista que envejece | baja | arreglado: `INTOCABLES` por nombre de archivo; la reversa puede ser el hermano `_down.sql` |

## Dos correcciones a los propios auditores

- Un auditor propuso arreglar el `-z` de `plantillas/gate.sh` cambiándolo por `-n`, como los
  dos ejemplos. **Habría propagado el hallazgo 2**: la plantilla daba rojo por accidente y
  los ejemplos dan verde a propósito. El arreglo correcto es más fino (ver abajo).
- Otro reportó que `fallas()` se arreglaba ensanchando el patrón. No alcanza: la segunda
  causa es que vitest imprime rutas relativas a su `--root`.

## Por qué el arreglo del hallazgo 2 no es «rojo siempre»

Si falta el corredor del **frontend**, los tests de una tarea de **backend** sí corrieron: el
cadáver original era justamente el gate reprobando a T02 y T03 por un `package.json` que
faltaba. Así que el veredicto no puede ser rojo a secas ni verde a secas: depende de si la
mitad sin corredor es **la que le corresponde al test declarado por la tarea**. Eso es lo que
quedó implementado.

## La regla que sale de todo esto

Los cinco auditores volvieron con la misma pregunta de fondo, cada uno en su forma:
**¿este chequeo puede, en algún estado del mundo, dar un resultado distinto del que está
dando?** Si la respuesta es no, el chequeo no mide: decora. Y la variante más costosa no es
el chequeo que falta, sino **el chequeo que imprime un ✓ que nadie se ganó**, porque además
de no medir, convence.

## 16 — el guardia que confundió una mención con una corrida

Apareció después de cerrar los quince, y es el único que cobré en vivo. El guardia de «una
sola corrida a la vez» de `correr-todo.sh` usaba `pgrep -f "correr-todo\.sh"`, que matchea
cualquier proceso cuya línea de comando MENCIONE la cadena. Mi propia suite tenía
`"scripts/correr-todo.sh"` adentro de una lista de archivos, así que el guardia la vio, dijo
«ya hay una corrida activa (pid 45489)» —y ése era un `python3 -m unittest`— y **mató el
relanzamiento del plan**.

Decimosexta aparición de la misma forma en dos días, y la primera en la que la víctima no es
un veredicto sino el plan: el método se negó a trabajar por un chequeo que no distinguía
trabajo de palabra escrita. Arreglado con un lockfile que lleva el pid y lo verifica vivo —así
una corrida muerta a lo bruto no traba el plan para siempre— en `.metricas/`, que ya está
ignorado. Control: con cuatro procesos que mencionan la cadena, `pgrep` encuentra cuatro y el
lockfile dice «ninguna corrida».

## Lo que costó arreglar la familia espejo

Dos cosas que vale registrar, porque son el riesgo propio de este tipo de arreglo:

1. **Acoté un chequeo demasiado ancho y lo volví demasiado angosto.** Al filtrar
   `_suprimidas.py` por las líneas del diff, lo apagué para los archivos NUEVOS: `git diff` no
   muestra lo que no existe en la base, así que el filtro devolvía un conjunto vacío y tapaba
   todo, justo para los archivos que una tarea CREA, que son la mayoría. Lo atrapó la suite
   del método —tres tests que no se escribieron hoy—, no yo. Sin ellos, el «arreglo» dejaba el
   chequeo decorativo, que es el defecto que esta auditoría encontró cinco veces.

2. **Destruí mi propio trabajo con el peligro que había arreglado tres horas antes.** Para el
   control positivo de G4 hice `git add -A` + commit + `reset --hard HEAD~1`; ese `add -A` se
   llevó las ediciones sin commitear de `pre-deploy.sh` al commit de prueba y el reset las
   borró. Esa misma tarde había sacado el `git add -A` de un mensaje del método justamente
   porque «barre el trabajo a medio hacer del humano». Se recuperó del reflog. La regla estaba
   escrita, la conocía, y la incumplí: es el tercer caso del día de una regla que vive en un
   documento y no en un comando.

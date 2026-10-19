# Protocolo de evaluación de modelos por papel

> **Estado: dos de los tres bloqueos cerrados; sigue sin correrse.**
>
> - **B1, el paso 4 del gate: CERRADO** (2026-10-08). Los tres gates acotan por la clase que
>   declara la tarea, pacman tiene el paso que le faltaba, y el paso respeta el contrato de
>   códigos del corredor. 34 de 50 tareas acotables, contra 3.
> - **B2, el banco: CERRADO** (2026-10-08). **16 ítems congelados** de 17 candidatos, cada uno
>   con su recibo verificado corriendo sus tests.
> - **B3, el material del tester: PARCIAL.** `conservar_intento` ya guarda transcript **y
>   parche** en los cuatro sitios que destruyen worktrees, así que de acá en adelante no se
>   pierde nada. Lo que existe hoy son **16 intentos rechazados** rescatados a mano, y 10 de
>   los 22 son de un solo modelo: `Captura(T, E)` contra el ejecutor elegido todavía no es
>   computable.
>
> Lo que sigue faltando para correr: los umbrales de decisión siguen siendo indecidibles para
> siete de las nueve decisiones ([§1](#1-qué-es-decidible-y-qué-no-con-el-número)), y eso no lo
> arregla el banco: lo arregla **subir K**. Con 16 ítems la diferencia mínima detectable sigue
> siendo una goleada.
>
> Esta versión reemplaza al diseño del 7 de octubre de 2026, que pedía 88 horas de clúster para
> tomar nueve decisiones de las cuales siete no eran decidibles.

Qué contesta: para los papeles donde la diferencia entre candidatos es de **orden de
magnitud**, cuál va. Nada más.

Qué NO contesta: ordenar dos candidatos parecidos. Eso no se puede con 9 ítems, y el
documento anterior prometía hacerlo. La salida correcta —escrita en el propio diseño y no
aplicada— es **subir K, no subir n**.

---

## 0. Los tres bloqueos

Ninguna corrida de agente arranca hasta que estos tres estén cerrados. No son
recomendaciones: son la razón por la que el protocolo anterior habría producido números
limpios y falsos.

### B1 — El paso 4 del gate da un falso verde casi siempre

El paso 4 revierte la implementación y exige que fallen los tests, y es el único chequeo de
que los tests **distinguen**. Lo que hace cada gate, corrido y no leído:

| gate | líneas | paso 4 | qué exige |
|---|---|---|---|
| `plantillas/gate.sh` | 452 | sí | la clase de test que la tarea declara |
| `ejemplo-clasificados/scripts/gate.sh` | 424 | sí | **sólo que falle la suite entera** |
| `ejemplo-pacman/scripts/gate.sh` | 366 | **no lo tiene** | — |

El defecto está en la segunda fila, y es un **falso verde**, no un ⊘. La suite de clasificados
está **roja en HEAD** por diseño —`ModuleNotFoundError: No module named
'backend.app.servicios.auth'`: el test de T04 existe y su implementación no, que es el método
tests-first funcionando—. El paso 4 corre `correr-suite.sh` sin argumento y le basta con que
devuelva distinto de cero. Como ya devuelve distinto de cero **antes de revertir nada**, imprime
`✓ la suite falla al revertir …` siempre.

Y es sistemático mientras el tronco esté rojo por diseño, que en este método es la mayor parte
del tiempo. El paso 1 sí tiene la defensa (`veredicto_con_linea_base` contra `.tests-base`); el
paso 4 **no la usa**.

Dos cosas más que caen con esto:

- El acotamiento por clase de test —`archivo::clase` sacado del archivo de tarea— **vive sólo en
  la plantilla, que ningún proyecto usa**. Y aun ahí matchearía poco: corrido contra los 50
  archivos de tarea da **3 de 19** en pacman y **0 de 31** en clasificados, porque el patrón
  ancla en `` `tests/ `` y las rutas de clasificados son `backend/tests/…` y `frontend/tests/…`.
- En la plantilla, cuando el acotamiento no resuelve, el camino es `vacuo` → `exit 0`. Ahí sí el
  ⊘ es un pase, y es la contradicción que `MEDICION.md` §4 se cobra a sí misma.

**Consecuencia para los dos experimentos:** mientras esto siga así, **«gate verde» no es una
métrica primaria válida.** Arreglar, en orden: que el paso 4 exija los tests **de la tarea** y
los compare contra la línea base (no la suite entera); que pacman tenga paso 4; que el
acotamiento viva en los gates reales y acepte las rutas de los dos proyectos.

### B2 — El banco está congelado: 16 ítems de 17 candidatos

**Cerrado el 2026-10-08.** `scripts/congelar-banco.sh` deja cada ítem en una rama
`item/<proyecto>-<TNN>` con tres commits —`base` (rojo verificado), `testigo` (la
implementación que cierra verde) y `recibo`— y un `.precondicion` con los dos SHAs, el
selector, los dos códigos de salida, la **salida literal sobre base** y qué instrumento se usó.
Verificado de punta a punta: `base` reproduce rc=1 con la misma falla, `testigo` rc=0.

| | |
|---|---|
| Candidatos (tareas con commit «gate verde» acotado al proyecto **y** declaración) | **17** |
| **Congelados** | **16** — pacman T16, T40, T41 · clasificados T01, T02, T03, T06a, T06b, T06c, T07, T08, T12, T13, T27, T29, T31 |
| Caído, con motivo final | **T30**: su implementación **es** el toolchain (`package.json`, `package-lock.json`, `vite.config.ts`). Revertirla saca el corredor, así que no existe un estado base donde el instrumento funcione. No es un defecto del banco. |

**Y el número que importa es la diferencia.** Medir el banco revirtiendo contra el tronco daba
**9 de 21**; congelado y con el instrumento arreglado da **16 de 17**. La diferencia **no era
del banco: era del instrumento.** Siete defectos, todos de la misma clase —un ⊘ tapando una
falla, o una falla informada como pase— y todos encontrados corriendo, no leyendo:

1. vitest imprime `Test Files 1 failed` **y** `Tests no tests` en la misma salida; el corredor
   buscaba `no tests` antes de mirar si algo falló.
2. Un filtro `-t` que no matchea nada hace que vitest **saltee todo y salga 0**, así que el
   corredor devolvía «los tests pasan». Una clase inexistente, informada como suite verde — y
   en el paso 4 del gate eso sale como «los tests PASAN con la implementación vieja», culpando
   al test.
3. pytest sale con **4** tanto para «el archivo no existe» como para «lo encontré y su import
   falla»; los dos iban a ⊘. Eso descartaba todo ítem cuya implementación es un archivo
   **nuevo**, que es el caso normal en greenfield.
4. Un **toolchain roto** salía como 2 («no corrió nada»), culpando al proyecto, cuando es 3
   («es del entorno»). La diferencia es a quién se le cobra.
5. El congelador borraba el archivo con `rm -f` y **dejaba el directorio vacío**: git no
   versiona directorios vacíos, así que construía un estado base que nunca existió. T01, cuya
   implementación son tres `__init__.py` vacíos y cuyo test verifica que los **directorios**
   existan, pasaba sin implementación.
6. El congelador traía los scripts **commiteados**, así que corrió con el corredor viejo
   mientras el arreglo estaba en disco. Nueve ítems cayeron por un defecto ya resuelto.
7. **Un ítem cosechado de la historia hereda los defectos que el tronco ya arregló.** El test
   de T03 tenía clavada la ruta absoluta del worktree donde se escribió
   —`/Users/jose/tests-T03/…`, que no existe más—; el repo tiene un test para ese defecto y su
   docstring describe este caso exacto, pero el guardia protege el tronco y el congelado
   alcanza a la historia. El ítem ahora trae el archivo de test **de hoy**.

Las decisiones de diseño que salieron de ahí, por si alguien las quiere revisar: el ítem congela
el **sujeto** (la implementación) y trae de hoy el **instrumento** (los scripts **y el archivo
de test**, que es intocable para quien implementa). Es seguro porque el congelado **verifica el
testigo**: si los tests de hoy no pasan contra la implementación histórica, el ítem cae
diciéndolo.

<details>
<summary>Lo que decía antes de congelar (9 de 21, revirtiendo contra el tronco)</summary>


Medido aplicando el diff inverso de cada tarea cerrada y exigiendo rojo de sus propios tests:

| | |
|---|---|
| **Viables** | pacman **T15, T40, T41** · clasificados **T01, T03, T06c, T12, T13, T31** → **9** |
| Degradados (rojo por el motivo equivocado) | pacman T17 (1 de 4 tests), clasificados T02 (`ModuleNotFoundError` aborta la colección) |
| Inadmisibles: el parche inverso no aplica (**7**) | pacman T13, T16 (**cuatro** commits «T16: gate verde», ninguno aplica) · clasificados T06, T06a, T06b, T08, T30 |
| Inadmisibles: `rc=2` (`no tests`), que por contrato no es rojo | clasificados T07, T27, T29 |
| **Reservado (pacman T01, T04–T08)** | **0 de 6** |

Cierra: 7 + 3 + 2 inadmisibles o degradados de 21 candidatos → **9 viables**.

Dos verificados a mano, y el segundo es una corrección:

- **T40 de pacman es viable**: el inverso aplica (8 líneas) y 3 de 4 tests de su clase fallan
  con `AttributeError: 'Juego' object has no attribute 'alternar_pausa'` — rojo por aserción y
  atribuible.
- **T01 de clasificados también es viable, y la primera versión de este documento decía lo
  contrario.** Su «implementación» entera son tres `__init__.py` vacíos: `3 files changed, 0
  insertions, 0 deletions`. De ahí deduje que revertirla no cambia nada y la suite queda verde.
  **Falso.** Git no versiona directorios vacíos, así que borrar esos archivos borra los
  directorios, y `test_scaffolding.py` verifica que existan: antes del revert 3 tests pasan,
  después uno falla con `AssertionError: No se encontró el directorio backend/app/rutas`.

  El error no fue de aritmética: para T40 **corrí los tests** y para T01 miré el `diff --stat` y
  **deduje la consecuencia**. Razoné sobre el contenido de los archivos cuando lo que estaba
  bajo test era la existencia del directorio. Es la pregunta 4 de `MEDICION.md` —«¿lo comprobé
  **corriéndolo** ahí?»— fallada por quien la acababa de escribir, y queda acá como el cadáver
  que la justifica.

**El reservado es el bloqueo duro.** Las seis tareas llegaron en un único commit a granel
(`4f8564f`, 32 archivos, 2540 inserciones) con implementación **y** tests juntos: no hay diff
por tarea que revertir, no hay commit «gate verde», no tienen fila en el registro. Fallan el
testigo de factibilidad y la precondición **por construcción**. Y `ejemplo-pacman/BITACORA.md`
viaja dentro del worktree del agente con las respuestas de T05 y T08 escritas. Correr ese
reservado no mediría sobreajuste: lo certificaría.

</details>

Congelado así, la precondición **no se podre** cuando una tarea posterior toque el archivo, que
es lo que mataba 7 de los candidatos.

### B3 — Las primarias del tester y del arquitecto no tienen material

`../fallidos-*` **no son worktrees: son carpetas con 12 archivos `.log`.** No hay árbol, no
hay parche, no hay `.motivo`. El procedimiento de la captura cruzada —«aplicar la
implementación defectuosa»— no tiene qué aplicar. Eso borra la primaria «la que vale más» del
tester, la primaria 3 del arquitecto y la complementariedad entre papeles.

**Novedad que cambia esto:** hay **16 intentos rechazados con código real** preservados en
`/Users/jose/rechazados/` (22 carpetas en total —16 rojas, 3 verdes, 3 sin dato—, 3283 líneas,
**5** modelos, tareas T04, T06c, T40, T41), rescatados de worktrees de experimento que estaban
por borrarse. Traen el parche y el transcripto; **les falta el diagnóstico redactado**. Son el
insumo para reconstruir la captura cruzada, y el único que existe.

Y la limitación que queda en pie, con el reparto real: `cc2f4c65` (CodeScout-4B) aporta 10 de
los 22 y el **modelo de control** `f5d76140` sólo 5. `Captura(T, E)` contra el ejecutor elegido
no es computable hasta tener rechazados de **ese** ejecutor, y hoy el material está concentrado
en un modelo que no es ninguno de los dos.

---

## 1. Qué es decidible y qué no, con el número

Los umbrales del diseño anterior se calcularon con **p = 0,83**, que es la tasa de *tool
call*. La tasa de **verde** del control, medida en `.metricas/intentos.csv`, es **0,42** (22
verdes de 52) o **0,49** sobre válidas. Con el número correcto, casi todo se cae.

### Decidible (2 de 9)

| Decisión | Por qué sí | Costo |
|---|---|---|
| **Title / summary / compaction** | La diferencia es de 10 a 50×: 98 % de `reasoning` contra 2 % de `content`; 12,8 s contra 1,1 s. Medición continua, 10 peticiones HTTP. | 1 h, 0 corridas de agente |
| **El *cheap win* de reloj del ejecutor** | Mediana e IQR de ≥5 corridas **serializadas**, no un binomial de 12. Precedente: Devstral cerró T08 en 192 s donde el 27B tardó 1574 s — factor 8. | 2 h, 20 corridas |

Y parcialmente: los descartes categóricos (contexto real menor que el prompt, salida
degenerada, no anclable) y el conteo de defectos de `validar-plan.py`, que es determinista.

### Indecidible o no corrible (7 de 9)

**Congelar el banco no cambió esto, y conviene decirlo.** Con K=16 en vez de 12, McNemar exacto
bilateral sigue pidiendo una goleada: 6-0 con 6 ítems discordantes, 9-1 con 10, **13-3 con 16**.
La diferencia neta mínima sigue siendo ~6 ítems, y para potencia 0,80 hacen falta ~8 a 10. Pasar
de 12 a 16 ítems no vuelve decidible ninguna de las siete: eso lo arregla **subir K**, y subir K
es escribir ítems nuevos, que es trabajo humano.

Lo que el banco congelado SÍ compra: que las corridas midan a los modelos y no al banco. Antes,
7 de 21 ítems no podían ni establecer su estado rojo, y una celda roja no distinguía «el modelo
no pudo» de «el ítem nunca estuvo en condiciones».


| Regla del diseño anterior | La cuenta | Veredicto |
|---|---|---|
| Ejecutor: «≥6 ítems discordantes a favor» | Con K=12, un candidato **4 ítems mejor** (33 % más de trabajo cerrado) se detecta el **19 %** de las veces. Hace falta **8 a 0**. | indecidible |
| Tester: «+3 de 8 ítems» | 10,5 % de falso positivo con modelos idénticos. Y la regla pide 8 ítems: de los 9 viables sólo **4** son Python, porque el mutador no muta `.sql` ni TypeScript y sin mutantes el paso 3 del validador sale ⊘. | indecidible **y** no corrible |
| Arquitecto: «+1 tarea de 4» | **36,5 %** de falso positivo con modelos idénticos. Y el techo: con el control a 0,42, **un plan perfecto saca 1,7 de 4**, así que «degradar el papel a humano» se dispara el 26 % de las veces midiendo al ejecutor. | indecidible |
| Relevo: «G ≥ 3 ítems de 12» | 15,3 % de falso positivo con dos modelos **idénticos**. | indecidible |
| Complementariedad: «C ≥ 0,5» | Comparando un modelo **consigo mismo** sale C = 0,52 y pasa el umbral. El Jaccard se calcula sobre conjuntos de 1 a 2 elementos mientras 7 a 9 de los 12 ítems caen en el bucket inestable que el conjunto excluye. | indecidible |
| «La ganancia se sostiene en el reservado: ≥1 de 6» | El reservado tiene **0 ítems admisibles**. Y con una ventaja real de cero, «≥1 de 6» se cumple el 62 % de las veces. | no corrible |
| Reviewer: «≥2 casos de 6» | 19 % de falso positivo. El propio banco lo dice: «ordena y descarta; no decide entre dos modelos que queden cerca». | indecidible, y admitido |

**El 97 % del presupuesto de corridas del diseño anterior sostenía las siete indecidibles.**

---

## 2. El error de inferencia que atravesaba todo: el `≈` sin margen

Cada vez que el diseño anterior escribía «empata», «el control no se movió» o «X ≈ Y», estaba
convirtiendo **una no-significancia en una afirmación positiva que decide algo**. Eso es
ausencia de evidencia leída como evidencia de ausencia.

El caso más caro era operativo: *«se cambia el ejecutor si X **empata** (menos de 6 ítems
discordantes) y su mediana es ≤0,5×»*. Probabilidad de que un candidato **genuinamente peor**
sea declarado «empate»:

| peor por | P(«empate») |
|---|---|
| 2 ítems (17 pp) | **0,970** |
| 3 ítems (25 pp) | **0,920** |
| 4 ítems (33 pp) | 0,809 |

La regla habría cambiado el ejecutor por un modelo 25 pp peor **el 92 % de las veces**.

**Regla nueva, sin excepción: todo `≈` lleva un margen de equivalencia declarado antes de
correr, y se contrasta con no-inferioridad (el límite del IC, no el punto).** Donde el margen
que haría falta no es demostrable con el banco, la conclusión es **«no concluyente»** y se
escribe así. Con K=12 la no-inferioridad a 1 ítem pide K≈400: el *cheap win* **no es
decidible por gate**, y si la razón para cambiar es el reloj, se declara como decisión de
costo con la pérdida de calidad explícitamente desconocida — no disfrazada de empate.

---

## 3. Controles, corregidos con las tasas reales

| Control | Antes | Ahora | Por qué |
|---|---|---|---|
| **C1, brazo de control** | banda ±2 ítems sobre 12 | **banda ±5**, y mejor: **control continuo** (mediana de tiempo y tasa de tool call sobre el banco de arnés con n=20) | Con el verde real del control (0,42–0,49), ±2 descarta el **30 %** de los bloques buenos. ±5 da 2 %, pero una banda de ±5 sobre 12 ya no controla nada: la señal de que un conteo binomial de 12 no puede ser un control. |
| **X1, tasa de tool call** | <5/6 → excluido | **n = 20**, no 6 | El IC de 5/6 es [0,36 ; 1,00] y el de 4/6 es [0,22 ; 0,96]: se solapan casi del todo, el umbral no separa lo que dice separar. Con tasa real 0,83 se excluye al **27 %** de los candidatos buenos. Son peticiones HTTP: subir a 20 cuesta minutos. **Y se elimina la propuesta de endurecer a 6/6**, que llevaría el falso descarte al 57 %. |
| **X5, toca lo intocable** | 1 vez, **irreversible** | **≥2 de 3 reps en el mismo ítem, reversible** | X5 con n=1 habría excluido al **modelo de control**, que ya tocó `tests/` cinco veces en el registro —y las dos tareas cerraron verde después—. Dejaría 88 horas de celdas `NO_MEDIDO` y ninguna decisión. El método **sí** tiene defensa barata contra esto: es el paso 0 del gate, que ya lo reprueba y el agente reintenta. |
| **X6, declara verde falso** | 1 vez, irreversible | **igual** | Acá sí: lo que se destruye es la confiabilidad del log, y una vez alcanza. |
| **El brazo nulo** | agente no-op, juzgado por el gate | **corre `correr-suite.sh ruta::clase` directo**, sin el gate | El gate reprueba «no hay ningún cambio» en el **paso 2**, y `FALLOS` acumula: un no-op sale rojo con la precondición buena **o rota**. Un chequeo que da el mismo resultado en los dos casos no distingue ninguno, y el diseño lo llamaba «el que más errores de instrumento compra». |
| **(d), la precondición** | la suite da `rc=1` | **rojo por aserción, y `rc=2` se rechaza** | Cadáveres: pacman T14 (`ImportError` se lleva 21 tests ajenos) y clasificados T02 (aborta la colección). `MEDICION.md` ya lo pide para los tests de regresión —«rojo, **y por el motivo correcto**»— y la condición no lo recogía. |

---

## 4. El protocolo, recortado: 13,5 h

Principio: **el banco chico sirve para DESCARTAR, no para ordenar.** Cero corridas de agente
para decidir tester y arquitecto.

| # | Fase | Qué decide | Corridas | HTTP | Reloj |
|---|---|---|---|---|---|
| 0 | Preflight: id declarado en `provider.*.models`, `limit.context` vs `max_model_len` real, sonda con herramientas, readiness `●`. Más la regla de los 10 s. **Y el calentado, que no es un detalle** (ver abajo). | nada; habilita el resto | 0 | ~40 | **2,5 h** |
| 1 | **Title / summary / compaction.** 10 peticiones × candidatos: rendimiento útil, latencia mediana, compuerta de formato. | **decide y se cambia** | 0 | ~90 | 1 h |
| 2 | **Criba de descarte.** X1 con n=20, salida degenerada, contexto real contra el cuerpo del pedido, anclable. | **descarta**, no ordena | 0 | ~200 | 2 h |
| 3 | **Ejecutor**, banco de los 9 ítems congelados, 3 candidatos × 9 × 3 reps, `SERIE=1`, control por bloque con banda ±5, brazo nulo directo sobre la suite. | **descarta** a quien esté ≥8 ítems por debajo del control. Al resto lo declara **empatado, y lo dice así**. | 81 (+9 nulo) | — | 5 h |
| 4 | **Reloj de los finalistas.** 5 corridas serializadas × 2 ítems × 2 finalistas. Mediana e IQR, nunca promedio. | **decide** por costo de reloj, declarado como tal | 20 | — | 2 h |
| 5 | **Arquitecto sin corridas de agente.** 3 candidatos × 3 planes, juzgados por `validar-plan.py` + los chequeos mecánicos de P1. | **descarta** por conteo de defectos (determinista) | 0 | ~9 | 1,5 h |
| 6 | **Reviewer.** 6 casos × 3 reps × 3 candidatos, con el corrector que lee `content` sin el pensamiento. | **ordena y descarta** | 0 | ~54 | 1 h |
| | **Total** | | **≈100** | **≈390** | **≈13,5 h** |

### El calentado no es preparación: es una parte del presupuesto

Medido el 2026-10-08, calentando los tres modelos del equipo uno por uno:

| modelo | arranque en frío |
|---|---|
| Qwen3.8-27B FP8 | 234 s |
| **Qwen3-Coder-30B-A3B** (6 de los 13 agentes) | **1201 s** |
| gpt-oss-20b | 375 s |

**Media hora para tres modelos**, y el ejecutor solo se lleva veinte minutos.

Calentando los cuatro candidatos después: openhands-lm-32b **632 s**, CodeScout-14B **332 s**,
CodeScout-4B **144 s**, CodeScout-1.7B **230 s**. Los siete, una hora de reloj.

**Y la medición del final: 6 de los 7 quedaron calientes a la vez** (6 de 97 declarados). El
único que se cayó a `cached` es el **30B ejecutor** — el que se calentó primero y el que más
tarda. Así que el desalojo existe, pero **no es la restricción dura que supuse**: caben al menos
seis.

> Corrección, y vale decirla porque estuvo escrita acá: la primera versión de esta sección decía
> que «la plataforma sostiene 2 réplicas calientes». **Era falso.** Ese 2 lo medí **a mitad del
> warmup**, cuando los otros cinco todavía no habían arrancado, y convertí un snapshot en una
> propiedad del sistema. Es el error de medición de `MEDICION.md` §2 M5: la diferencia existía
> —había 2 calientes— pero no era atribuible a la capacidad, sino al momento.

Tres consecuencias que sí se sostienen:

1. **El bloque por modelo sigue siendo lo correcto**, pero por el motivo medido y no por el que
   supuse: el que se cae es el primero que entró, así que en una tanda larga el modelo del
   bloque 1 está frío cuando llega el bloque 9. El preflight de C4 tiene que **re-verificar
   readiness por bloque**, no una vez al principio.
2. **Lo que el calentado compra de verdad es `cached`, no `warm`.** De `cold` a `cached` el
   arranque pasa de 144–1201 s a segundos, y ese estado sobrevive al desalojo. El objetivo
   operativo del preflight es que ningún modelo del bloque esté `cold`.
3. **Anclar (`scaling_mode=minimum`) es un compromiso permanente de VRAM** en una plataforma
   compartida que corre producción: el propio `anclar.sh` dice que no desaloja «aunque haga
   falta VRAM». Es una decisión del dueño, no del protocolo, y va declarada en el régimen de la
   tanda — un bloque corrido con modelos anclados no es comparable con uno corrido sin.

### Qué NO se corre, y por qué, dicho antes

- **El tester** (la fase más cara del diseño anterior, 96 corridas). 4 ítems Python de 8, y su
  primaria sin material. **La decisión del tester queda abierta, y eso ya es un resultado que
  el método contempla**: escribir tests sigue siendo lo menos delegable. Lo que corresponde es
  endurecer `mutar.py` y **empezar a guardar los árboles de los intentos fallidos**, no elegir
  modelo.
- **La complementariedad y el relevo.** La métrica no distingue un modelo de sí mismo. Y el
  relevo **ya está implementado** (`scripts/replanificar-relevo.sh`): medirlo es un A/B contra
  `replanificar.sh` sobre los mismos ítems, no un bootstrap. Ese bootstrap además estimaba una
  política que nunca se corrió: remuestreaba repeticiones independientes para simular un
  reintento **con motivo**, y el único dato que hay las separa por un factor 2 (verde al primer
  intento 0,53; verde al reintento con motivo 0,25).
- **El reservado.** 0 de 6 admisibles y `BITACORA.md` filtra las respuestas dentro del
  worktree.
- **La alcanzabilidad del arquitecto.** Techo de 1,7 de 4 con un plan perfecto, 26 % de falso
  «degradar a humano», y viola el testigo de factibilidad y la precondición por construcción:
  un rojo en una tarea recién planificada **no es atribuible** al plan.

### Lo que esto habilita

Las 13,5 h dejan dos salidas accionables y **el banco congelado de 9 ítems como artefacto
reutilizable**. El paso siguiente no es correr las 75 h que faltan: es **escribir los 19 ítems
que faltan** —con tests y testigo desde el arranque, que es la única parte del banco que puede
existir de verdad— y recién entonces K llega a 28 y las reglas comparativas empiezan a tener
poder. Eso es un día de trabajo humano, no cuatro de clúster.

---

## 5. Procedencia de los números de este documento

Regla que el diseño anterior se impuso y no cumplió: cada número lleva su origen.

- **medido-nuestro, verificado corriéndolo**: los 9 ítems viables y los 12 inadmisibles o
  degradados; 3 de 19 y 0 de 31 tareas con `archivo::clase`; pacman sin paso 4; la suite de
  clasificados roja en HEAD; T01 con 0 inserciones **y su test de scaffolding en rojo al
  revertir**; T40 con 3 de 4 tests rojos; verde del control 0,42 (22/52) y 0,49 (22/45); 0,53
  (8/15) contra 0,28 (5/18) de primer intento contra reintento con motivo; 16 rechazados
  preservados de 22 carpetas, 5 modelos.
- **corregido después de una auditoría** (estaba mal en la primera versión de este documento):
  T01 era «inadmisible» y es viable; «8 parches inversos no aplican» eran 7; «18 rechazados»
  son 16; «6 modelos» son 5; «12 de los 22 son del control» son 5; el reintento con motivo era
  «0,25» y es 0,28; y el paso 4 del gate no da ⊘ sino **falso verde**.
- **derivado** (cuentas sobre los anteriores): las potencias y tasas de falso positivo de §1
  y §2; las bandas de C1; los IC de X1.
- **publicado**: nada de este documento decide con un número publicado. El ×2,8 de MTP salió:
  era un número publicado entrando en una decisión, que es lo que la regla prohíbe.

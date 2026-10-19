# ¿La memoria verificada mejora a los modelos chicos escribiendo código?

> **Estado: bloqueado. No se corre.** Reemplaza al diseño del 7 de octubre de 2026, que pedía
> 32 horas de clúster y 10,5 horas-persona para una pregunta que **su condición central no
> podía construir**. Lo que sigue es el piloto de 2 horas que decide si el grande vale la pena,
> y los tres prerrequisitos que van antes.

---

## 0. El bloqueo que define todo: la memoria no funciona

Verificado hoy, no estimado:

```
$ ls ejemplo-clasificados/memoria/
_planificacion.md                 # registro global del replanificador, no de una tarea
$ ls ejemplo-pacman/memoria/
ls: no such file or directory
```

Ningún `memoria/TNN.md` existe, en ninguno de los dos proyectos. (El grep del formato
—`Falló así`— no sirve como evidencia: devuelve la definición de la función, este documento y
el archivo de tests, o sea los tres lugares donde el formato se *menciona* y ninguno donde se
*escribió*.)

**`recordar_falla` nunca escribió un registro.** Y `memoria_para` devuelve **0 bytes para
todas las tareas** del único proyecto que tiene carpeta `memoria/` (verificado con el control
puesto: el arnés ubicó bien el proyecto y vio las 31 tareas). El único archivo que hay,
`_planificacion.md`, es un registro global del replanificador y no de una tarea.

Por qué nunca escribió: `correr-tarea.sh` invoca `recordar_falla` **sólo si el veredicto es
VERDE** y además hubo un `MOTIVO` de un intento anterior. Es correcto como criterio de
«memoria verificada», y tiene dos consecuencias que el diseño anterior no sacó:

1. **El techo medido no se cobra nunca**, ni parcialmente, porque la entrega da cero.
2. **Un intento que el gate reprobó no deja registro, jamás.** La condición D_unver del diseño
   anterior decía que ese material «existe gratis en los logs». **Es falso**, y era el único
   supuesto que no se verificó.

Arreglar la memoria —que produzca y que entregue, verificado con el testigo de inyección— es
media tarde de trabajo y es **prerrequisito**, no un experimento siguiente.

---

## 1. El material, contado

| Fuente | Lo que hay |
|---|---|
| Registros con el formato de `recordar_falla` | **0** |
| Transiciones rojo→verde en todo el historial (17 días) | **6**: pacman T02; clasificados T01, T02, T03, T06c, T08 |
| Ítems E1 construibles (parche inverso aplica + rojo atribuible) | **9** (ver `modelos-por-papel.md` §0 B2) |
| **Intentos RECHAZADOS con código real** | **16**, preservados en `/Users/jose/rechazados/` (22 carpetas: 16 rojas, 3 verdes, 3 sin dato) |
| Respuestas crudas guardadas de los bancos | **0** — ningún script escribe a disco |

El diseño anterior presuponía 24 ítems, ~40 para calibrar al juez y 80 respuestas crudas ya
recolectadas. Nada de eso existe. Y su cohorte prospectiva pedía esperar **~68 días** al ritmo
medido de 0,35 transiciones por día, sin decirlo.

**Lo que sí apareció**: los 16 rechazados, rescatados de 22 worktrees de experimento que
estaban por borrarse (3283 líneas, **5** modelos, tareas T04, T06c, T40, T41), con el material
concentrado en `cc2f4c65` (10 de 22). Traen el parche que
un modelo escribió de verdad y que un comando reprobó. Les falta el **diagnóstico redactado**,
y quién lo escriba es la decisión que define si D_unver mide lo que dice medir.

---

## 2. Por qué D_unver, como estaba, no medía verificación

La hipótesis de D_unver era: un registro de la misma clase y los mismos archivos, con la misma
etiqueta de «verificado», pero cuyo diagnóstico salió de un intento que el gate reprobó. Si
`D_unver ≈ B_tr`, la verificación no agrega nada.

El problema es estructural. `recordar_falla` escribe dos campos y **el segundo sólo existe si
hubo verde**:

```
**Falló así:** <la huella del intento rojo>
**Quedó en verde al:** <los archivos del diff que cerró>
```

Entonces un D_unver honesto queda en una de dos formas, y ninguna mide verificación:

- **Sin el segundo campo** → mide «registro completo contra registro mutilado». Si sale
  `B_tr 0,40` y `D_unver 0,18`, se declara la tesis sostenida y lo que se midió es la ausencia
  de un campo.
- **Con el segundo campo fabricado** → alguien escribe un arreglo plausible y equivocado. Eso
  es «texto correcto contra texto incorrecto», no «verificado contra no verificado». Y como
  lleva la misma etiqueta de verificado, es una **inyección de desinformación**: el signo
  esperable es `D_unver < A`, no `A < D_unver < B_tr`.

**La salida, y es lo que habilitan los 16 rechazados:** D_unver se construye del parche real de
un intento reprobado, y **se corre con su propio control de redacción**. Dos brazos más:

| brazo | qué lleva |
|---|---|
| `D_unver` | diagnóstico derivado de un intento que el gate reprobó, redactado como sale |
| `D_pulido` | el **mismo** diagnóstico equivocado, redactado con el mismo cuidado que `B_tr` |

Si `D_pulido − D_unver` es del mismo orden que `B_tr − D_unver`, **la condición mide redacción**
y hay que decirlo en los resultados en lugar de concluir sobre la verificación.

---

## 3. El otro error: `≈` sin margen, en la conclusión central

El diseño anterior resolvía su tesis central con un `≈` que nunca definió. Operativamente sólo
podía significar «el IC de la diferencia incluye el 0», que es **ausencia de evidencia leída
como evidencia de ausencia** — y el mismo error aparecía en `B_tr ≈ C_long`, `C_long ≈ A`,
`E_formato ≈ A` y `E2 ≈ 0`, o sea en la tesis **y en la validación de dos de los tres
controles**.

Para afirmar una equivalencia hace falta un **TOST con margen declarado**. Con 24 ítems × 7
reps, el margen más chico demostrable es:

| correlación intra-ítem | margen mínimo demostrable |
|---|---|
| 0,3 | 22,2 pp |
| 0,5 | **26,5 pp** |
| 0,7 | 30,2 pp |

Afirmar «`B_tr` equivale a `D_unver` dentro de ±26 pp» cuando el efecto total esperado es de
15 pp **no es una afirmación**. Para un margen de 10 pp harían falta **170 ítems**; para 5 pp,
**678**. Con el banco que tenemos, la tesis central no se puede ganar ni perder: es
indecidible, y la tabla de decisión tiene que decir **«no concluyente»** donde decía
«refutada».

### Y el n efectivo no era 168

Las 7 réplicas son del **mismo ítem**, mismo prompt congelado, `temperature 0`, mismo bloque:
están correlacionadas, y el dominio hace esperar correlación **alta**, porque el modelo puede
o no puede hacer ese ítem.

| correlación | n efectivo | MDE real |
|---|---|---|
| 0,0 | 168 | 14,9 pp (el declarado) |
| 0,5 | **42** | **29,2 pp** |
| 0,7 | 32 | 32,9 pp |
| 1,0 | **24** | 37,4 pp |

La fórmula y la aritmética del diseño anterior estaban bien; el error fue aplicar una fórmula
de observaciones **independientes** a 24 grupos de 7. **Corolario operativo: más ítems valen
más que más réplicas.** 100 ítems × 3 reps vale más que 24 × 7 y cuesta menos por celda.

### Y el criterio de las dos cohortes garantizaba el negativo falso

«H1 se sostiene sólo si el efecto aparece en las dos cohortes» son cuatro significancias
conjuntas. Potencia conjunta con el efecto que el diseño dice querer detectar: **0,478** en el
mejor caso —por debajo de la moneda— y **1 a 5 %** con la correlación realista. Estaba armado
para refutar H1 sin importar si es cierta, y el falso negativo venía con explicación coherente
e irrefutable («era sobreajuste»).

**Reemplazo:** efecto agrupado sobre todas las observaciones, con la cohorte como **término de
interacción**, y la predicción preregistrada como equivalencia de la interacción con margen
declarado. O, más simple y honesto: **contraste agrupado significativo + mismo signo en las dos
cohortes**, que cuesta ×0,5 de potencia en el peor caso en lugar de ×0,03.

---

## 4. Lo que hay que corregir en el instrumento, antes de la primera llamada

| # | Qué | Por qué |
|---|---|---|
| P1 | **Que la memoria produzca y entregue.** `recordar_falla` escribiendo registros reales, `memoria_para` devolviendo bytes, verificado con el **testigo de inyección** (un registro canario que pide empezar la respuesta con `TESTIGO-<hash>`; si no aparece, nunca llegó al pedido). | Hoy la entrega da cero. Sin esto, cualquier número de esta campaña es sobre un techo que no se cobra. |
| P2 | **Persistir los intentos rechazados.** Copiar el árbol antes del `worktree remove --force`, y guardar el JSON crudo de cada llamada. | Los 16 que tenemos son un rescate accidental. Sin instrumentarlo, el material de D_unver se sigue destruyendo en cada corrida. |
| P3 | **El corrector del sub-chequeo.** El diseño decía «se corre el sub-chequeo del gate que había reprobado». `gate.sh` **no es decomponible**: 452 líneas, sin banderas, y los pasos 0/2/4 dependen de `TAREA` y de `.base-ref`. Hay que escribirlo, y **validarlo antes de usarlo**: CORRECTO en los 9 testigos, INCORRECTO en el brazo nulo de los 9. | Un corrector sin calibrar es justo lo que `MEDICION.md` prohíbe. Y si en cambio se corre el gate completo, el paso 4 produce un falso rojo garantizado: revierte con `git checkout HEAD`, que en un worktree donde el rojo se armó con un parche inverso devuelve **el código ya arreglado**. |
| P4 | **Arreglar el paso 4 del gate** (ver `modelos-por-papel.md` §0 B1). | El corrector de E2 es `scripts/gate.sh`, y hoy le falta su chequeo central en las 50 tareas. |

P3 se puede matar sin gastar GPU, y por sí solo puede cancelar la campaña.

---

## 5. El piloto que decide si el grande vale la pena: ≈2 h de clúster

Es un **subconjunto** del grande, así que nada se tira. Decide dos cosas, cada una capaz de
cancelar la campaña entera.

**Antes de cualquier llamada (0 h de clúster):** la auditoría de material de §1 y el corrector
de P3, validado contra los 9 testigos y los 9 nulos.

**La corrida**: 9 ítems × 5 reps × 5 brazos × 2 modelos = **450 llamadas**, ≈1,9 h a
concurrencia 4.

| brazo | qué lleva | qué decide |
|---|---|---|
| `A` | nada | la base |
| `B_tr` | registro completo de la misma clase, otra instancia | el tratamiento |
| **`B_archivos`** | **sólo** `**Quedó en verde al:** <lista>`, sin el texto de la falla | **si el efecto es un puntero al archivo** |
| `C_long` | registro verificado de otra clase, tokens igualados por `usage.prompt_tokens` | el largo |
| **`D_pulido`** | diagnóstico equivocado, redactado tan bien como `B_tr` | **si D_unver mide redacción** |

Los dos modelos: **CodeScout-1.7B**, que es de quien existe el dato preliminar —va de **1/6 a
5/6 con memoria correcta y supera al 30B sin memoria (2/6)**, el número que cambió la economía
del método— y **el 30B** como el ejecutor en uso.

Dos correcciones a la primera versión de este documento, que atribuía el 1/6→5/6 al 30B: el
único dato del 30B es **2/6 sin memoria**, no existe ningún 5/6 con memoria para él. Y decía
excluir al 27B «porque está en el techo (6/6 → 6/6)»: **ese dato no existe**. Los 6/6 del 27B
que sí están medidos son de otros dos bancos —razonamiento y herramientas—, no de un A/B de
memoria; el A/B sólo está publicado agregado sobre cuatro modelos (A 6/24, B 18/24, C 6/24).
Si el 1.7B aporta 1 de los 6 aciertos del brazo A, el 27B no puede aportar 6.

`B_archivos` existe porque el registro **apunta el archivo**: para la clase más frecuente del
registro —«tocó archivos intocables»— la respuesta correcta *es* «no toques el test, cambiá el
archivo de app», y cualquier registro de esa clase la dice literalmente en su lista de
archivos. Las pruebas de fuga del diseño anterior no lo veían: comparaban contra la clave de
oro, no contra la estrategia.

### Reglas de decisión, escritas antes

- Si **`B_archivos ≈ B_tr`** (margen declarado: 10 pp): el efecto es un puntero al archivo.
  **No se corre el grande.** Se cambia `recordar_falla` para que emita el diff y no la lista de
  nombres, se arregla `memoria_para`, y se vuelve a preguntar. Decisión en 2 h en vez de 32.
- Si **`D_pulido − D_unver` ≳ `B_tr − D_unver`**: D_unver mide redacción. **No se corre el
  grande** hasta tener diagnósticos de intentos rechazados producidos por el mismo
  procedimiento que los verificados.
- Si `B_tr` supera a `B_archivos`, a `C_long` **y a `A`** por ≥15 pp cada uno, y
  `D_pulido ≈ D_unver`: el grande tiene una pregunta viva, y el piloto además entrega la
  correlación intra-ítem para dimensionarlo.

**`B_tr − A` es obligatorio.** El umbral del diseño anterior pedía `B_tr − C_long ≥ 10 pp` y
`B_tr − D_unver ≥ 10 pp` y **no incluía a `A`**. Como los dos controles son activamente
desorientadores —uno nombra archivos ajenos, el otro da un diagnóstico equivocado con etiqueta
de verificado— las dos piernas se satisfacen **envenenando los controles**: con A=0,30,
B_tr=0,31, C_long=0,19 y D_unver=0,17, los dos umbrales se cumplen, los IC excluyen el cero, se
declara la tesis sostenida, y `B_tr − A = 1 pp`. La conclusión falsa sería «el contenido
verificado es lo que compra» cuando lo medido es que **un bloque de memoria equivocado hace
daño**.

---

## 6. Los tres controles que este diseño no tenía y el directorio ya exigía

`experimentos/README.md` los pide para los dos diseños y este no los nombraba:

- **`.precondicion` por ítem**, verificada **leyendo el estado y corriendo el test ahí**. Es lo
  que atrapa que 7 de 21 parches inversos no apliquen, que 3 den `rc=2` (que por contrato no es
  rojo) y que 2 den rojo por el motivo equivocado. Y «corriendo el test» no es adorno: la
  primera versión de este plan declaró un ítem inadmisible mirando el `diff --stat` en vez de
  correr su suite, y estaba al revés.
- **Brazo nulo**, corriendo `correr-suite.sh ruta::clase` directo. Atrapa los ítems que se
  ponen verdes con cualquier diff — y el registro tiene clases triviales de sobra: un solo ítem
  así entre 24 regala 4,2 pp de piso parejo a los cinco brazos y comprime todas las
  diferencias.
- **Reservado que se corre una vez**, que reemplaza a la cohorte prospectiva de 68 días.

---

## 7. Lo que sigue sin ver

1. **El experimento le pone la memoria correcta en la mano; el método tiene que encontrarla.**
   Esto mide el techo. Y hoy la recuperación devuelve **cero**, así que el techo no se cobra
   nunca: por eso P1 es prerrequisito y no «otro experimento».
2. **Si una falla es del modelo o del servido.** El token repetido del 30B parecía
   cuantización y era presión de memoria; se resolvió mirando las placas.
3. **El 15 % de inválidos del arnés.** Medido en el registro: 9 de 60. Las causas, leídas del
   registro y no de memoria: `Cannot find native binding` de npm **×5**, `No module named
   pymysql` ×1, `Failed to resolve import ../src/services/auth` ×1, y **2 sin motivo
   registrado** (pacman T02 y T03, del 27B). Todas son del entorno del proyecto y ninguna
   estaba en los criterios de ⊘ del diseño anterior. *(La primera versión de este documento
   listaba `database is locked` entre las tres causas: es un modo de falla real nuestro, está
   documentado en `INFRAESTRUCTURA.md`, y **no es ninguna de estas nueve**.)*
4. **Calidad no verificable por comando.** Lo que no es verificable desaparece del plan (P2), y
   este protocolo hereda ese sesgo entero.

# Handoff — terminar el sitio de clasificados

Fecha: 2026-10-19 (cerrado pasada la medianoche) · Repo: `~/metodo-agentes` (rama `main`)
Estado: **15 de 32 tareas hechas; etapa 1 (T04b, T26) con sus tests aceptados y la
implementación corriendo. Tronco rojo POR DISEÑO mientras dure la etapa — ver §B.3ter**

---

## A. Lo que yo afirmé y resultó FALSO — no lo heredes

| afirmé | real |
|---|---|
| «el id del ejecutor quedó viejo» (porque un error de plataforma nombraba `da003b52`) | **la config estaba bien.** Sondeados los dos: `f5d76140` → HTTP 200, `da003b52` → HTTP 404. Son dos espacios de ids: el de las peticiones y un id interno de deployment que la plataforma usa en sus errores. Casi reescribo una config correcta. |
| «la plataforma sostiene 2 réplicas calientes» | **falso, caben al menos 6.** Ese 2 lo medí a mitad del warmup, cuando cinco de los siete no habían arrancado. Snapshot convertido en propiedad del sistema. |
| «T05 falla por tamaño; hay que partirla» | **no era tamaño.** Era que la tarea exigía autorización, prohibía tocar `servicios/auth.py` y el medio no existía. Partirla o subir el límite sólo le daban más margen para iterar contra un import imposible. |
| «T01 de clasificados es inadmisible: revertirla deja la suite verde» | **es viable.** Lo deduje del `diff --stat` (0 inserciones) sin correr el test. Git no versiona directorios vacíos: borrar los tres `__init__.py` borra los directorios, y el test verifica que existan. |
| «sync_limits arregla la deriva de contexto» | arreglaba la **copia del repo**; la config viva es un symlink a `colabhive-opencode`. Y peor: el guardia que detecta la deriva corre ese mismo script, así que el «arreglo» lo dejaba **callado** sobre el defecto real. |
| «T05 se corta por tamaño» (dicho dos veces) | era un enunciado que exigía autorización sin dar el medio. El agente inventó `obtener_usuario_id_desde_token` y grepeó 7 coincidencias, **todas suyas**. |
| «el chequeo de coherencia compara dos enunciados» | el cadáver era enunciado contra **código**: el `sha256` vivía en `auth.py`, no en el texto de T04. Con dos enunciados no había par y el chequeo callaba. Lo mostró probarlo contra el cadáver. |
| «el import huérfano no se detecta» (probando el cableado) | **sí se detectaba.** `ubicar_proyecto` saca `RAIZ` del primer worktree que lista git —el principal—, así que corriéndolo desde un worktree leyó el proyecto del tronco. Medí el árbol equivocado. |
| «las dos fallan con la misma firma que T26» | el **mensaje del gate** era el mismo («no hay ningún cambio: la tarea no se hizo»); la causa, no. Era `memory_delivery_unavailable`, un error de plataforma que la función no reconocía. T20 dio verde en el reintento y lo confirmó. |
| «mergear durante la corrida es seguro, git usa rename» | **falso.** Para los archivos del árbol de trabajo git abre con `O_TRUNC` y reescribe el mismo inodo; el rename lo usa para el índice y las refs. El bash en curso ve el archivo cambiar debajo y se le corren los offsets. La regla estaba escrita en `METODO.md` y la incumplí tres veces con la regla a la vista. |
| «PLAN COMPLETO es sólo una frase mal elegida del bucle» | el bucle estaba **equivocado**: `insistir.sh` grepeaba `plan.log`, que es el acumulado de todas las corridas, así que una línea de éxito vieja hacía que toda vuelta posterior declarara el plan completo — incluida una en la que la plataforma estaba caída y no se corrió nada. |
| «el sobre de la plataforma ya se reconoce» (primera versión) | no reconocía nada: el log tiene escapes ANSI y la línea real es `\e[91m\e[1mError: \e[0m{…}`, así que `^Error:` no anclaba. Lo había «verificado» contra una copia del log limpiada con `cat -v` para poder leerla — **una representación del dato en vez del dato**. |
| «el plan se completó» (lo dijo el bucle) | la frase es de `insistir.sh`, no del plan: la etapa 1 **no integró**. Leí el titular y no las tres líneas de abajo. |
| «esto lo ensució un descuido mío» | lo ensució el **runner**: `recordar_falla` escribe `memoria/TNN.md` y no lo commitea. El mensaje de `integrar.sh` —«el tronco tiene cambios sin commitear»— apunta al humano, que es justo quien no lo hizo. |
| «el transcript del intento se perdió» | **estaba ahí.** El log se encabeza en UTC y el archivo preservado se nombraba en hora LOCAL: `intento-133855` era el de las 16:38 UTC. Comparé dos relojes y creí que el método destruía su propia evidencia. |
| «esto nunca pasó antes: 0 de 48 transcripts» | el patrón era `grep -ql 'a\|b'`, y el `\|` de BRE **no existe en el grep de BSD**: no podía matchear nunca. El número real es 1 de 85, y ese 1 es el de hoy. Una medición con un instrumento que no puede dar positivo. |

**Moraleja:** cualquier número que yo publique sin un comando al lado, tratalo como hipótesis.
Y dos veces hoy verifiqué con el único camino que no ejercita el defecto (la corrida en seco de
`sync_limits`, el `diff --stat` de T01).

---

## B. Estado verificado, con coordenadas

### B.1 El plan
- `ejemplo-clasificados/PLAN.md`: **32 tareas**, 15 hechas. `validar-plan.py` sin errores de forma.
- **8 etapas** pendientes: `[T04b T26] → [T05] → [T14 T20 T11 T28] → [T15 T21] → [T16 T22] → [T17 T23] → [T18 T24 T25] → [T19]`
- Tronco verde: `cd ejemplo-clasificados && bash scripts/correr-suite.sh` → rc=0

### B.2 Qué está corriendo ahora
`scratchpad/insistir.sh` en bucle (hasta 20 vueltas). Distingue:
- plataforma caída → espera 3 min y reintenta
- parada que necesita decisión → **para y muestra las últimas 12 líneas**

Logs: `scratchpad/insistir.log` (el bucle) y `scratchpad/plan.log` (acumulado de las vueltas).

### B.3 La plataforma, que es el bloqueante real
Intermitente. Medido: `/models` responde 200 en 0,7 s mientras `/chat/completions` da timeout a
los 40 s, y los **tres** modelos del equipo a la vez — así que es el camino de inferencia, no un
modelo. Y la plataforma **declara** el 30B `warm` con 300 ms mientras no contesta en 60 s.

Arranques en frío medidos hoy: 27B **234 s**, 30B **1201 s**, gpt-oss-20b **375 s**,
openhands-32b 632 s, CodeScout-14B 332 s, 4B 144 s, 1.7B 230 s. Los siete, una hora.

Sonda honesta (la que usa el método, contra `/chat/completions` y no `/models`):

    . ~/.config/colabhive/env
    printf 'Authorization: Bearer %s\n' "$COLABHIVE_API_KEY" | curl -sS -o /dev/null \
      -w 'HTTP %{http_code} en %{time_total}s\n' -m 40 -H @- -H 'Content-Type: application/json' \
      -d '{"model":"f5d76140-5b4d-41c0-88da-dad6d11f341a","max_tokens":4,"messages":[{"role":"user","content":"ok"}]}' \
      "$COLABHIVE_BASE_URL/chat/completions"

**No midas nada mientras esté así.** Regla del dueño: si ColabHive está en deploy, las
mediciones no sirven.

### B.3bis Los cuatro chequeos que el método ganó hoy

| qué | dónde | cadáver que lo pidió |
|---|---|---|
| **Brazo nulo del validador de tests** | `scripts/vaciar.py` + 4º paso de `escribir-tests.sh` | el test aceptado de T04b: cinco casos, los cinco negativos, y `return None` los pasaba todos |
| **Cortes separados por motivo** | `CORTES_TOTAL_MAX=2` en `escribir-tests.sh` | `inactividad 90s` es una herramienta colgada; `límite total 1200s` es información sobre la TAREA. 12 de los segundos son 4 horas |
| **Coherencia entre tareas** | `scripts/coherencia.py`, al arrancar `correr-todo.sh` | T05 importaba lo que nadie provee (rojo) · T26 pedía `scrypt` contra el `sha256` del código (aviso) |
| **El runner no lanza con la tarea sucia** | `correr-tarea.sh` | reescribí el contrato de T04 sin commitear y el agente implementó el viejo, con razón |
| **`RAIZ` es `--show-toplevel`, no el worktree principal** | `_comun.sh` | correr el plan desde un worktree de desarrollo leía las tareas del tronco. Hacía fallar `test_una_memoria_que_no_llega_lo_dice`: escribe con el `RAIZ` de Python y lee con el de shell. La suite estaba verde **sólo porque siempre la corría desde el árbol principal** |
| **`validar-plan.py` saltea los archivos que ya existen** | `validar-plan.py` | la sección (`## Contrato`) no distingue «escribí esto» de «leé esto»; la existencia sí |
| **`estado.sh` no da un veredicto que no puede fallar** | `estado.sh` | decía «tronco ✗ ROJO» durante toda etapa tests-first, y corría el gate **dos veces** |
| **El presupuesto de cortes vuelve a cero si cambia el enunciado** | `_comun.sh` + `escribir-tests.sh` | arreglé T26 a mitad de etapa con el contador en 2 de 2: lo que iba a frenar la etapa era el contador y no la tarea |
| **Una llamada emitida como texto es fallo de protocolo, no de la tarea** | `error_del_agente` en `_comun.sh` | el ejecutor escribió `<tool_call>` en el contenido; la corrida murió sin tocar un archivo y el comparador lo habría anotado como «el modelo no pudo con la tarea» |
| **Los transcripts preservados se nombran en UTC con fecha** | `_comun.sh` + `escribir-tests.sh` | leí «16:38 UTC» adentro de `intento-133855` (hora local) y concluí que el transcript se había perdido |
| **`recordar_falla` commitea lo que escribe** | `_comun.sh` | el runner escribió `memoria/T26.md` sin trackear y `integrar.sh` frenó la etapa 1 con T04b y T26 **las dos en verde**: el método bloqueado por su propia salida |
| **El aviso de «commiteá los tests» sale sólo si hay algo, y sin `add -A`** | `escribir-tests.sh` | se imprimía siempre; lo leí con el tronco limpio mientras diagnosticaba por qué no integraba |
| **Al fallar la integración, el hint es `integrar.sh`, no la etapa** | `correr-todo.sh` | seguí el mensaje al pie de la letra y re-correr la etapa borró las dos implementaciones verdes |
| **`correr-plan.sh` acepta NOMBRES de tarea, no un índice** | `correr-plan.sh` + `correr-todo.sh` | el índice significaba una cosa en cada fase: T05 quedó salteada, la integración intentó integrarla sin implementación, y T11 corrió **antes de su dependencia** |
| **`error_del_agente` reconoce el SOBRE de la plataforma** | `_comun.sh` | enumeraba mensajes: dejaba pasar `memory_delivery_unavailable`, que mató T11 y T20 y quedó anotado contra el modelo |
| **Un test declarado y AUSENTE es rojo** | las 3 copias de `gate.sh` + `integrar.sh` | T14, T20 y T28 se implementaron sin tests y cerraron en VERDE e integraron; el código de T14 ni se podía importar |
| **Huella de los scripts, verificada en cada etapa** | `correr-todo.sh` | mergeé tres veces con el plan en vuelo: la corrida salió del bucle tras la etapa 1 e informó «Todas las etapas en verde» con siete sin tocar |
| **Los imports INTERNOS también se verifican** | las 3 copias de `_imports.py` | cruzaba contra los requirements y salteaba los módulos locales: el agujero estaba en el medio del chequeo. T14 se integró con un `from .conexion import get_db_connection` que no existe |
| **La costura de la base, nombrada** | `ejemplo-clasificados/AGENTS.md` | `get_db_connection` lo inventaron los agentes de **tres** tareas distintas (T04, T15, T26); el archivo que el runner les ordena leer hablaba de MySQL y nunca nombraba la función |
| **Los imports internos se verifican** | las 3 copias de `_imports.py` | T14 se integró con un `from .conexion import get_db_connection` que no existe |
| **El dialecto SQL, nombrado** | `AGENTS.md` | T05 perdió sus dos intentos con `INSERT … RETURNING id`, que es PostgreSQL: MySQL contesta 1064 |
| **Quince hallazgos de auditoría, nueve cerrados** | ver `AUDITORIA-20261019.md` | cinco auditores en paralelo encontraron que **el gate estaba parcialmente decorativo** |

### B.3ter El rojo del tronco durante una etapa

`backend/tests/test_sesion.py` (el test de T04b, aceptado y commiteado) está en el tronco y
T04b sigue pendiente: **el tronco está rojo por diseño**, 1 test, que es la línea base que el
runner descuenta en cada lanzamiento. `estado.sh` ahora lo dice con esas palabras y nombra el
test en vuelo. Antes decía «✗ ROJO» a secas y yo casi lo leí como una rotura real.

### B.4 El método
- `pruebas/test_metodo.py`: **215 tests, verde**, 1 salteado con motivo (el corredor del
  frontend no arranca en un subproceso: esbuild instalado para otra arquitectura)
  ~10 min). 4 salteados **con motivo**: el corredor del frontend no arranca en un subproceso
  porque esbuild está instalado para otra arquitectura (`@esbuild/darwin-arm64` presente, el
  node del subproceso necesita `darwin-x64`).
- Diez commits hoy + un merge: ver `git log --oneline --since=midnight`. `1a5077e` integra
  `coh/dev` (coherencia entre tareas + `RAIZ`); `f29c7e2` es el contrato de T26.
- Banco de ítems congelado: **16 ramas `item/ejemplo-*-TNN`**, cada una con `base`, `testigo` y
  `recibo` verificado corriendo sus tests. `scripts/congelar-banco.sh`. Cayó uno de 17: T30,
  cuya implementación **es** el toolchain que corre los tests.

---

## C. Lo que queda, en orden de cuánto puede invalidar el plan

0. **T26: el test está aceptado; la implementación va por el reintento 2.** El primer
   intento murió por protocolo, no por la tarea (ver abajo). **T04b dio gate VERDE** y espera
   que la etapa cierre.
0b. **El ejecutor configurado es `f5d76140`, que la memoria anotaba como roto.** No lo cambié:
   ese mismo modelo escribió el test que el método aceptó veinte minutos antes. Una llamada
   mal formada no alcanza para cambiar el instrumento a mitad de plan. Si la implementación
   de T26 vuelve a morir con la misma firma, **ahí sí** hay evidencia para probar `1af07b1f`
   —y la firma ahora queda anotada como fallo de protocolo, así que la comparación va a ser
   limpia—. La memoria quedó corregida: «intermitente», con la regla de pedir más de un
   intento.
0. **El estado al cerrar: 20 de 32, cinco etapas por delante.** T14, T20 y T28 integradas a
   mano con `integrar.sh` después del salteo. El plan relanzado arranca en T05, que es la que
   se había salteado, y el conteo de etapas ya coincide entre las dos fases.
0a2. **El rojo de T11 NO es de su enunciado: no lo toques.** Se cortó por límite total
   buscando `backend/app/rutas/ads.py`, `servicios/ads.py` y `datos/ads.py`, que son el
   entregable de **T05**, la tarea salteada. Terminó escribiéndolos él, fuera de su alcance,
   porque era lo único que podía hacer. La tabla dice `T11 depende de T05` y la deducción las
   pone en etapas 1 y 2: el grafo estaba bien, el índice fue el que mintió. Con T05 hecha,
   T11 corre sobre terreno firme.
0. **T26 quedó resuelta, y el método lo demostró.** Cuatro intentos contra el enunciado
   viejo: tres fallas con la **misma huella** (`AttributeError: … does not have the attribute
   'get_db_connection'`) y dos cortes por límite total. Un intento con el contrato arreglado:
   aceptado. El test que entró mockea `backend.app.datos.users_register.insert_user` —la
   costura que el contrato nombra— y `get_db_connection` no aparece. **La causa era el
   enunciado, no el modelo ni el tamaño**, y eso no lo dijo mi opinión: lo dijo la huella
   repetida contra un sujeto y una aceptación contra el otro. Es el patrón para reconocerlo:
   *tres fallas con la misma huella no son tres fallas del agente, son una del enunciado.*
0c. **Dos implementaciones verdes recuperadas como ramas.** `verde-recuperado/f1d282f`
   (T04b, 24 líneas en `auth.py`) y `verde-recuperado/da17146` (T26, tres archivos nuevos).
   Las tiré yo re-corriendo la etapa; el plan las está rehaciendo. Si los re-intentos salen
   verdes, borralas; si fallan, integrá ésas — ya pasaron el gate.
0d. **La plataforma se cayó dos veces** (~19:40Z y ~23:40Z, HTTP 000). El bucle espera 3 min
   y reintenta, hasta 20 vueltas (~1 hora). Si se agotan, para y hay que relanzarlo:
       cd ~/metodo-agentes/ejemplo-clasificados && nohup bash <scratchpad>/insistir.sh &
   Ese script lleva ahora `LIMITE_AGENTE=2400`, calibrado con el registro: 33 intentos VERDE
   con mediana 180s y máximo 970s contra el presupuesto viejo de 1200s —24% de margen—, y T05
   se cortó cuatro veces por eso. Subir la paciencia del bucle (`seq 1 20`) se hace **con el
   bucle parado**: editar un script de bash en ejecución es el defecto que arreglamos hoy.
0e. **Auditoría que NO derivó en cambios, a propósito.** Revisé los contratos de las 15
   pendientes buscando el defecto de T26 («nombra qué, no con qué»). El control positivo
   —las tareas ya hechas— mostró que las únicas tres que declaran su archivo son las tres
   que arreglé hoy, y las otras 14 se completaron sin declararlo. Así que eso **no predice
   falla** y reescribir 15 contratos por sospecha habría sido overfitting. Lo que sí tenía
   evidencia (el nombre inventado en tres tareas) se arregló en AGENTS.md.

0f. **T05 es la tarea que resiste, y ya no por lo que parecía.** Cuatro cortes por tiempo
   (presupuesto, arreglado), un test que contradecía el esquema cerrado del plan (rechazado,
   contrato reescrito con las firmas de las dos capas), y dos intentos perdidos por
   `INSERT … RETURNING id` (dialecto, nombrado en AGENTS.md). Cada vez el diagnóstico fue
   distinto y cada vez el agente hizo lo razonable con lo que tenía. **Si vuelve a fallar,
   leé el motivo antes de suponer que es la misma cosa.**
1. **La plataforma.** Nada avanza sin ella. El bucle insiste; si 20 vueltas no alcanzan, es
   decisión humana (esperar, hablar con ColabHive, o anclar modelos).
2. **T04b y T05 nunca corrieron.** Las escribí hoy y no se ejecutaron: T04b es nueva y T05 está
   amendada. **Lo que diga el gate sobre ellas es información nueva**, no una repetición.
3. **El paso 4 del gate sigue dando ⊘ en greenfield.** Cuando la implementación son archivos
   nuevos no hay nada que revertir, así que no se verifica que los tests distingan. Lo que SÍ lo
   verifica es congelar el ítem (`congelar-banco.sh`): hacelo después de integrar cada tarea
   nueva y ganás el chequeo que el paso 4 no pudo dar.
4. **Las comparaciones entre modelos siguen siendo indecidibles.** Con los 16 ítems congelados,
   McNemar exacto pide **13-3**. Eso no lo arregla el banco: lo arregla **subir K**, que es
   escribir ítems nuevos — un día de trabajo humano, no de clúster. Ver
   `experimentos/modelos-por-papel.md` §1.
5. **El hash del ejemplo es un `sha256` sin sal.** Es de juguete y está dicho en T04b y T26.
   Migrarlo toca registro **y** login a la vez: es una tarea propia con un test que cruce los
   dos. `coherencia.py` avisa si una sola de las dos lo cambia.
6. **`Captura(T, E)` no es computable todavía.** De los 22 intentos rechazados preservados en
   `/Users/jose/rechazados/`, 10 son de un solo modelo. Se arregla solo ahora que cada corrida
   conserva su parche (`conservar_intento` en `scripts/_comun.sh`).
7. **La memoria está en construcción por otro lado.** No la toques. Cuando esté, el chequeo es
   el testigo de inyección: un registro canario que pide empezar con `TESTIGO-<hash>`; si no
   aparece, nunca llegó al pedido.

---

## D. Trampas de este repo que ya pagué, para que no las pagues de nuevo

- **El worktree sale del árbol COMMITEADO.** Un arreglo del contrato o del test sin commitear no
  llega al agente, y el rojo que sale no habla de lo que arreglaste. Me costó una corrida entera
  de T04. Ya hay un guardia: `correr-tarea.sh` se niega a lanzar si los archivos de la tarea
  están sucios.
- **El tronco tiene que estar limpio mientras el plan corre**, porque `integrar.sh` se niega a
  mergear con cambios sin commitear. Si editás algo, la etapa falla al integrar.
- **La línea de ayuda de la plantilla dice `← al mergearla: ✅ hecha`**, así que
  `grep '✅ hecha' tareas/*.md` matchea TODAS. Usá `grep -E '^\*\*Estado:\*\* *✅'`. Hay un test
  del método que se llama `test_la_ayuda_de_la_linea_de_estado_no_cuenta_como_hecha`.
- **No edites mientras corre la suite**: la contaminé tres veces hoy. Es el punto 7 de la regla
  de parada de `MEDICION.md` aplicado a uno mismo.
- **`timeout` y `stdbuf` no existen en esta Mac.** Para salida sin buffer: `python3 -u`.

---

## E. El patrón que explica casi todo lo de hoy

*Alguien declara algo y el que tiene que recibirlo no lo recibe.* Apareció **siete veces** en una
jornada, tres de ellas en el método mismo:

- T05 exigía autorización y no decía con qué → el agente inventó la función
- el worktree traía el contrato viejo → el agente implementó el contrato viejo, con razón
- `ubicar_proyecto` no exportaba `PROYECTO` → el hijo tenía que re-adivinarlo
- `sync_limits` escribía donde nadie lee → y dejaba ciego a su propio guardia
- `huella_de_falla` tenía su pipe final dentro de un comentario → devolvía 4 líneas
- T26 pedía `hashlib.scrypt` y `login` compara `sha256` → las dos tareas pasaban sus tests y
  juntas rompían el login
- el test de T04b no cubría su propio criterio → cinco casos negativos, ninguno positivo

Está escrito en `METODO.md` §«Nombrar la cosa no alcanza», con la pregunta de revisión:
**¿quién tiene que leer esto, y por qué camino le llega?**

Y el corolario que más va a valer mañana: **el instrumento ya distingue un defecto del
enunciado de un defecto del modelo**, y lo hace sin que yo opine. La firma es la huella
repetida: tres intentos que fallan igual, contra un enunciado que no da el medio. Pasó dos
veces hoy (T05 inventando `obtener_usuario_id_desde_token`, T26 inventando
`get_db_connection`) y las dos veces lo que lo cerró fue nombrar la costura en el contrato,
no más tiempo ni más modelo.

Corolario operativo de hoy: **un chequeo que lee prosa va a confundir la cita del defecto con el
defecto**, porque acá cada arreglo documenta su cadáver. Por eso `coherencia.py` lee lo que la
tarea dice que HACE y saltea el bloque «No entra».

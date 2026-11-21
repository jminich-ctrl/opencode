# Experimentos

Lo que todavía no sabemos y cómo pensamos averiguarlo. **Ninguno de los dos diseños está
ejecutado, y los dos están bloqueados a propósito.** Lo que sí corrió —y está medido en
[`../MEDICION.md`](../MEDICION.md)— es la validación del instrumento, que es lo que la compuerta
de abajo exige antes de ejecutar nada.

| Archivo | Qué pregunta | Estado |
|---|---|---|
| [memoria-verificada.md](memoria-verificada.md) | ¿La memoria de fallas verificadas por el gate mejora al que escribe código, y es la **verificación** lo que la hace valer? | **bloqueado**: la memoria produce 0 registros y entrega 0 bytes |
| [modelos-por-papel.md](modelos-por-papel.md) | ¿Qué modelo va en cada papel, y conviene un equipo en lugar de uno solo? | **bloqueado**: el banco tiene 9 ítems de 30, el reservado 0 de 6 |

### Qué desbloquearía a los dos, y por dónde se atascó (al 2026-11-21)

Subir K. Con K=16 ítems congelados, **7 de las 9 decisiones de modelo son indecidibles**, y el
McNemar exacto necesita 13-3 para moverse. Eso no lo arregla el banco: lo arregla escribir
ítems nuevos, o sea **terminar el plan de `ejemplo-clasificados/`** —18 de 34 tareas hechas, 16
pendientes, 10 de ellas backend en Python, que es justo lo que falta: de los 9 ítems viables de
hoy sólo 4 son Python, porque el mutador no muta `.sql` ni TypeScript—.

Y ahí está el atasco real, medido en dos corridas independientes del 2026-11-10:

- **El gate no dejó pasar nada**: 0 falsos verdes en 16 intentos, con la misma huella las dos
  veces. Por la regla del propio método —tres fallas con la misma huella no son tres fallas del
  agente, son una del enunciado— eso apunta al enunciado, no al modelo.
- **Las huellas son dos defectos de contrato**: el enunciado no declara con qué `import` la
  implementación trae el nombre (T04, T26), y no declara el contrato de respuesta (T16, T28),
  así que el test lo inventa y queda obligado para siempre.
- **El arquitecto no replanifica.** Se arregló el camino por el que recibía el motivo —recibía
  la categoría del transcript en vez del veredicto del arnés, `6edb4bd`— y con el motivo
  correcto adelante **igual no reescribió** T04, T26 ni T28. La hipótesis era mía y la corrida
  la refutó. Los transcripts (`crudo/replan/`) lo muestran gastando el presupuesto deliberando
  si tiene permiso para leer un archivo, en vez de planificar.
- **T16 es la excepción y es una decisión humana**: `HUECO: the plan doesn't provide a service
  function to list favorites`. El arquitecto tiene prohibido inventar lo que ninguna tarea
  entrega, y lo declaró en vez de inventarlo.

## La compuerta

Un diseño no se corre hasta que las cinco respuestas sean sí. Están acá y no dentro de cada
diseño porque son las mismas, y porque la revisión adversarial de los dos mostró que **cada uno
daba por cierto lo que el otro también daba por cierto, y ninguno lo había mirado.**

1. **¿El material existe y lo conté?** No «el universo es el registro»: el número. Los dos
   diseños presuponían entre 24 y 30 ítems. Hay **9**. Un diseño que no cuenta su material no es un
   diseño, es una intención.
2. **¿La precondición de cada ítem se verificó leyendo el estado — y corriendo el test ahí?**
   Medido: de 21 candidatos, **7** tienen un parche inverso que no aplica, **3** dan `rc=2` que
   por contrato no es rojo, y **2** dan rojo por el motivo equivocado (un `ImportError` que se
   lleva 21 tests ajenos, una colección abortada). Quedan 9. Y «corriendo el test ahí» no es
   adorno: declaramos un ítem inadmisible mirando su `diff --stat` —tres archivos vacíos, 0
   inserciones— y al correrlo resultó viable, porque git no versiona directorios vacíos y el
   test verificaba que el directorio existiera.
3. **¿Corrí el brazo nulo?** El sujeto reemplazado por un no-op, rojo obligatorio en todos. Y
   contra la suite directamente, no contra el gate: el gate reprueba «no hay ningún cambio» en
   el paso 2, así que un no-op da rojo con la precondición buena **o rota**, y un chequeo que da
   el mismo resultado en los dos casos no distingue ninguno.
4. **¿Cada `≈` tiene su margen declarado?** Todo «empata», «no se movió» y «X ≈ Y» es una
   equivalencia, y una no-significancia no la demuestra. Si el margen que haría falta no es
   demostrable con el banco, la conclusión es **«no concluyente»** y se escribe así.
5. **¿El n efectivo es el que creo?** Las réplicas del mismo ítem están correlacionadas. Con
   correlación 0,5, 24 ítems × 7 réplicas valen **42 observaciones, no 168**, y el MDE pasa de
   15 a 29 pp. **Más ítems valen más que más réplicas.**

## Las reglas comunes

**El instrumento se valida primero**, contra [`../MEDICION.md`](../MEDICION.md). Un control
caído descarta la tanda entera, incluidos los brazos que dieron bien.

**No se puntúa prosa: se puntúa un comando.** Donde se puede, el ítem pide un diff y el puntaje
lo da `git apply` más el sub-chequeo del gate que había reprobado. Con dos deudas abiertas: el
sub-chequeo **no existe todavía** —`gate.sh` no es decomponible— y hay que escribirlo y
calibrarlo antes de usarlo; y el **paso 4 del gate da un falso verde**, porque exige sólo que
falle la suite entera y la suite está roja en HEAD por diseño. Mientras eso siga así, «gate
verde» no es una métrica primaria válida.

**Reservado que se corre una vez**, con la predicción escrita antes. Si contradice la
calibración, gana el reservado. Y el reservado tiene que estar **sellado**: el de pacman filtra
las respuestas de dos de sus seis tareas en `BITACORA.md`, que viaja dentro del worktree del
agente.

**Los dos denominadores.** Toda tasa se informa sobre corridas válidas **y** sobre intentadas.
La diferencia es la salud de la plataforma, y la tasa histórica real es 15 %.

## El material que sí tenemos

`crudo/banco/` guarda **16 intentos que el gate reprobó, con el código real** (22 carpetas en
total: 16 rojas, 3 verdes, 3 sin dato; 3283 líneas, 5 modelos, tareas T04, T06c, T40, T41),
rescatados de worktrees de experimento que estaban por borrarse. Vivía en `~/rechazados/` y se
cosechó al repo el 2026-11-21 con `scripts/cosechar.sh`, después de que /tmp se comiera
`gate_publico.py` con su banco: material que vive sólo afuera del repo no está guardado. Es el insumo de la condición central del experimento de
memoria, que el diseño daba por inexistente — y la única copia que hay, porque
`marcar_hecha_y_limpiar` destruye el árbol con el worktree.

Su `PROCEDENCIA.md` lleva el veredicto **del arnés, no del log**: el último «GATE ROJO» del
transcripto de tres de esas corridas contradice el ✓ que el arnés registró. El agente imprime
el gate varias veces mientras trabaja y el último no es el veredicto. Grepear «GATE VERDE» de un
transcripto es la falla que el método existe para evitar.

## Lo que ninguno de los dos diseños ve

- **Si una falla es del modelo o del servido.** El token repetido del 30B parecía cuantización y
  era presión de memoria; se resolvió mirando las placas. Cuando no se puede distinguir, la
  celda va `NO_MEDIDO` y se remide.
- **Calidad no verificable por comando.** Lo que no es verificable desaparece del plan (P2), y
  estos protocolos heredan ese sesgo entero. Lo cualitativo lo decide G3, con una persona y
  quince minutos.
- **El techo del banco.** Dos proyectos de ejemplo no predicen un repo de 200k líneas. Ordenan
  candidatos **dentro del método**, que es la decisión a tomar.
- **El arnés ajeno.** Un modelo entrenado para otro arnés queda subestimado por construcción.
  Eso va en el renglón de ese modelo, no en una nota al pie.

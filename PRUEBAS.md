# Quién verifica a los verificadores

El método verifica el proyecto con comandos. Este documento es sobre el problema de arriba:
**¿qué verifica a esos comandos?**

Nació de contar los bugs de un solo día de trabajo. Fueron diez, y los diez son **la misma
clase**: un chequeo que, ante una situación que no previó, **deja de mirar en vez de fallar**.

| Qué pasó | Qué se veía |
|---|---|
| `git diff --name-only` informa rutas de la raíz del repo, no del proyecto | `✓ tests y scripts intactos`, con un test modificado |
| `git cat-file -e HEAD:$f` lo mismo | `✓ archivos nuevos: nada que revertir`, sin revertir nada |
| `Ran 0 tests` matcheaba la rama de éxito | `✓` con una suite vacía |
| `mapfile` no existe en bash 3.2 | *"No pude determinar las etapas del plan"* — culpando al plan |
| `$$` en bash es el PID | un patrón roto, y **todo** fuera de alcance |
| `git clone --depth 1 <ruta local>` ignora `--depth` | historia completa, y el script creyendo que clonó superficial |
| El formato de etapa de la plantilla no matcheaba el del parser | las etapas declaradas ignoradas en silencio |

Ninguna falla a gritos. **Todas dejan de mirar**, y eso es indistinguible de "miré y está
bien".

## Resulta que la clase tiene tres nombres, y nadie los cruza

- **Vacuidad**, en métodos formales, con teoría desde 1997 y detección de pases vacuos.
- **Soundiness**, en análisis de programas (2015): *"las fuentes de unsoundness suelen
  acechar en las sombras"*.
- **Pérdida de la propiedad *self-testing***, en hardware tolerante a fallas — **1968**, y
  es la definición más precisa de las tres:

  > *"Un circuito es **self-testing** si, para cada falla de un conjunto prescripto, produce
  > una salida fuera del espacio de códigos para al menos una entrada del espacio de
  > códigos."*

  Y la composición que buscábamos: *"totalmente self-checking; es decir, **cada falla se
  prueba durante la operación normal** y ninguna falla puede causar un error no detectado."*

Los de hardware llegaron primero, fueron los más precisos, y su definición dice exactamente
qué hacer: **un verificador es confiable sólo cuando cada falla *del verificador* se revela
con alguna entrada que realmente corrés.**

## Lo que hicimos con eso

### 1. Una suite para el método: `pruebas/test_metodo.py`

```bash
python3 pruebas/test_metodo.py        # 41 casos, ~50 segundos
```

Cada caso es un bug que de verdad tuvimos. Y dos cosas que aprendimos escribiéndola, las dos
sobre la suite misma:

- **El proyecto de juguete estaba en la raíz del repo**, donde los bugs de rutas no se
  reproducen. Con el bug de `--relative` puesto, los tests daban **verde**. Ahora el proyecto
  va en un subdirectorio, que es como están los dos ejemplos.
- **Los tests afirmaban el veredicto y no el motivo**, así que pasaban cuando el gate daba
  rojo por otra causa. El de la suite vacía pasaba porque borrar el archivo contaba como
  fuera de alcance. **Eso es confianza falsa, peor que no tener el test.** Ahora
  `assertRojo` exige el motivo.

### 2. La relación metamórfica que más rinde

> **Mover el proyecto no puede cambiar el veredicto.**

Cinco ubicaciones: raíz del repo, un nivel, cuatro niveles, con un espacio en la ruta, y con
no-ASCII. No se afirma un veredicto concreto: se afirma que **todas coinciden**.

Eso detecta la clase entera sin anticipar cada caso, y verificado reintroduciendo los bugs:
atrapa el de `--relative` y el de `cat-file`. Es la relación que usa la literatura de testeo
de analizadores estáticos, y para nosotros cubre **cuatro de los diez bugs y los dos de la
propia suite**.

### 3. El marcador de vacuidad: `⊘`

Un chequeo que no pudo correr ya no se imprime con `✓`:

```
── 4. ¿Los tests distinguen?
  ⊘ archivos nuevos (no existían en HEAD): nada que revertir — no pudo verificarse

GATE VERDE — con 1 chequeo/s que no pudieron correr (⊘)
```

El código de salida sigue siendo 0, porque **hay vacíos legítimos** —un archivo nuevo no se
puede revertir—, pero quedan a la vista y el veredicto los cuenta. Tres de los diez bugs
colapsan en este cambio: vivían detrás de un `✓` que no había mirado nada.

## Lo que todavía no hicimos, y por qué está escrito acá

- **Mutar el propio gate** y exigir que la suite mate el 100% de los mutantes. Es la
  definición de *self-testing* aplicada literalmente, y hay técnica publicada para mutar
  verificadores. **Cualquier mutante que sobreviva es, por definición, un caso de test que
  falta.** Es lo siguiente que corresponde.
- **Cobertura de ramas del propio gate**, fallando si una rama del camino verde nunca se
  ejecuta. La formulación publicada es directa: *"una suite pasa vacuamente si no cubre por
  ramas la especificación."*
- **Convertir cada chequeo en un testigo**: que no diga `✓ tests intactos` sino
  `inspeccioné N rutas con el patrón P, 0 coincidencias`, y que otro script recompute N por
  otro camino. Medido en validación de testigos: **41 de 91 resultados reclamados fueron
  rechazados por validación independiente**. Nuestros bugs de `Ran 0 tests` y `cat-file` no
  producían **ningún** testigo, y por eso eran invisibles.
- **Correr el gate bajo bash 3.2 y bash 5 y comparar veredictos.** El bug de `mapfile`
  —que significaba que el runner del plan **nunca había corrido**— muere en el primer
  contacto.

## La medición que rompe el sesgo: fallas sembradas por un tercero

Esto es lo único que mide de verdad si la suite sirve. Un agente **sin acceso a nuestra lista
de bugs y sin ver la suite** sembró 12 fallas realistas en el gate, una por variante, todas
bash válido, todas de la clase peligrosa: un chequeo que se vuelve no-op y sigue imprimiendo
algo plausible.

```bash
bash pruebas/medir-siembra.sh /tmp/siembra
```

**Primera medición: 6 de 12.** La suite que pasaba 100% sobre los bugs que conocíamos atrapó
**la mitad** de los que no.

Y las seis que escaparon eran **una sola clase**, no seis casos:

| Variante | Qué quedó roto |
|---|---|
| 07, 08 | el paso 4 no encuentra la clase esperada y cae a la rama genérica |
| 09 | el paso 5 queda inalcanzable y **mudo**: ni ✓, ni ✗, ni ⊘ |
| 10 | la suite reservada nunca corre; siempre dice *"no hay suite reservada"* |
| 12 | `.base-ref` no se encuentra y cae al respaldo, en silencio |
| 06 | el patrón de `TODO` se angosta a `TODO:` |

### El remedio fue estructural, no caso por caso

Agregar seis casos —uno por falla escapada— habría sido sobreajustar de nuevo. La pregunta
correcta era **qué clase de chequeo falta**, y la respuesta estaba en la literatura: el
**testigo**.

```
base del diff: 8544a7a7e81f — deducida (no había .base-ref)
✓ tests y scripts intactos
   · inspeccionó: 3 ruta(s) del diff contra el patrón ^(tests/|scripts/)
✓ Ran 7 tests in 0.022s de composición
   · inspeccionó: 1 archivo(s) reservado(s) en /Users/jose/reservados-...
```

**Un chequeo que dice qué miró no puede volverse mudo sin que se note.** Más una clase de
test sobre **amplitud de patrones**, que es lo que la variante 06 señalaba.

**Segunda medición: 12 de 12.**

### Y el asterisco, que es grande

**Ese 12 de 12 está contaminado: para entonces ya habíamos leído la tabla de las 12 fallas.**
Lo que se puede sostener es que **los arreglos fueron estructurales** —no hay un solo test
que apunte a una variante— y eso es verificable leyendo `TestTestigos` y
`TestAmplitudDePatrones`. Lo que **no** se puede sostener es que la tasa de captura real sea
ahora del 100%. Para eso hace falta una tanda nueva, sembrada a ciegas.

### Los tests estructurales encontraron más que la siembra

Al exigir amplitud de patrones aparecieron dos huecos que ninguna falla sembrada marcaba:
los patrones de higiene eran sensibles a mayúsculas, así que **`# NOQA` pasaba en verde**.

Y el arreglo apresurado de eso produjo un falso positivo propio: poner el grep de `TODO`
insensible a mayúsculas hace que matchee la palabra castellana *"todo"*, y hasta dentro de
los `.pyc`. La falla sembrada apuntaba a que el patrón era **angosto**, no a la caja. Quedó
`\bTODO\b` en mayúsculas, excluyendo `__pycache__`.

> Vale como caso de estudio de esta página entera: **el arreglo de un verificador es código,
> y el código tiene bugs.** Ese falso positivo lo atrapó la propia suite en la corrida
> siguiente, que es para lo que existe.

## Lo que midió la corrida de clasificados

La suite pasó de 33 a 70 casos, y los 37 nuevos no salieron de pensar en qué podía fallar:
salieron de **catorce paradas de una corrida real**, trece de ellas por defectos del
método. La diferencia importa, porque los casos que uno inventa mirando el código heredan
el mismo sesgo que lo escribió.

### El instrumento que los encontró

No fue leer el gate. Fue exigir que el test diga **por qué** da rojo:

```python
def assertRojo(self, r, porque="", motivo=None):
    self.assertNotEqual(r.returncode, 0, ...)
    if motivo:
        self.assertIn(motivo, r.stdout, f"dio rojo, pero no por «{motivo}»")
```

Un rojo por el motivo equivocado es indistinguible de un rojo correcto si sólo se mira el
código de salida. Con esa exigencia puesta, un error de escapado en el extractor de alcance
—`\\.` en vez de `\.`— apareció como «dio rojo, pero no por *fuera del alcance*» en vez de
pasar como un rojo cualquiera.

El simétrico vale igual y también se midió: **un chequeo que marca todo es un chequeo que
se ignora.** El cruce de estados, en su primera versión, marcó 27 de 28 tareas.

### Dos clases de test nuevas

**Relación metamórfica sobre el cwd.** Una canaria que anota su propio `os.getcwd()` y se
deja correr por los tres gates: el validador y el gate tienen que correr la suite desde el
mismo directorio, porque un test validado en un cwd y juzgado en otro es imposible de
pasar. No se lee el texto del gate; se lo deja correr y se mira desde dónde corrió.

**Anti-deriva de los ejemplos.** Los ejemplos son copias adaptadas de la plantilla, y la
copia se queda vieja: el arreglo del extractor de alcance entró en la plantilla y los dos
ejemplos siguieron roto hasta que alguien lo notó a mano. `TestEjemplosNoDerivan` corre el
motor de alcance de **cada** gate por conducta, no por texto, y si mañana hay un tercer
ejemplo entra solo. Encontró que el gate del pacman nunca tuvo la regla de directorios.

### Lo que sigue faltando

- **La tasa de captura del gate.** `pruebas/mutar-gate.py` muta el gate mecánicamente
  —un mutante por línea, nodos áridos excluidos, y SBR (borrar el chequeo) que fue el 68%
  de los mutantes productivos de los 16,9M de Google— y mide qué fracción mata la suite.
  Está escrito y no corrido con el árbol estable: cada mutante cuesta una corrida completa
  de la suite, y hay 74 candidatos.
- **Por qué mecánico y no sembrado a mano.** Una segunda ronda de siembra hecha por quien
  ya leyó la tabla de fallas hereda el mismo sesgo. Un mutador no sabe nada de nuestra
  lista: las fallas que inventa son las que la gramática del bash permite.
- **Cobertura de ramas del gate** y el diferencial bash 3.2 contra 5.

## El día que medí mi propio instrumento

Pasé horas convencido de que `opencode run` colgaba al 100% en esta máquina. Tenía la
medición: **ocho intentos seguidos, ocho cuelgues**, todos con 0 bytes y el log propio
terminando en `message=init`. Con eso descarté diez hipótesis, una por una y con prueba:
la API (200 en 3s, streaming y no streaming, los dos modelos), los modelos fríos, mi
cambio de `headerTimeout`, la contención entre procesos, el WAL de SQLite, los servicios
externos, la caché de modelos, la config del proyecto, el binario (reinstalado) y los doce
worktrees acumulados. Y terminé subiendo la versión de opencode, que tampoco lo arregló.

El cuelgue lo causaba **mi envoltorio de medición.** Para acotar el tiempo en las pruebas
usaba

    perl -e 'alarm 90; exec @ARGV;' opencode run ...

y `exec` deja a opencode con el temporizador y la máscara de señales de perl. Lanzado
directo, o con el `con_limite` del propio método —que corre el comando en segundo plano en
su grupo de procesos y no hace `exec`—, anda: **cinco de cinco, entre 5 y 8 segundos.**

Las dos mediciones, lado a lado:

| Cómo lo lancé | Resultado |
|---|---|
| `perl -e 'alarm N; exec @ARGV'` | 8 de 8 colgados, 0 bytes, log en `init` |
| `con_limite` del método (sin exec) | 5 de 5 en verde, 5–8s |

Lo que me deja, y es la advertencia más más cara que me llevé del día: **un instrumento no
validado no mide el sistema, se mide a sí mismo.** Toda la cadena de razonamiento era
impecable y toda la evidencia era real; el dato de entrada estaba contaminado por la forma
de tomarlo. Es exactamente lo que el método le exige al gate —que un chequeo se pruebe
contra una falla conocida antes de creerle— aplicado al instrumento con el que yo juzgaba
la herramienta.

El corolario operativo: **antes de medir con un envoltorio, medí el envoltorio.** Una
corrida de control sin él habría costado treinta segundos y habría ahorrado horas.

## Y la advertencia que viene con todo esto

> **Que los 41 casos pasen no mide que el gate esté correcto: mide el sesgo de la suite.**

La formulación publicada, sobre generadores de tests: *"un generador alcanza un punto de
saturación no porque el compilador esté libre de bugs, sino porque el generador contiene
sesgos."* Y sobre sembrar bugs conocidos: *"que una suite encuentre muchas fallas sembradas
no significa que vaya a encontrar las fallas que importan."*

Sembrar los bugs que ya conocés es legítimo —es una práctica con nombre y atrapó cosas
reales acá— pero **no se puede inferir de ahí que el gate sea sólido**. El remedio no es más
casos: es una familia de fixtures estructuralmente distinta, y que la siembre alguien que no
tenga la lista de bugs.

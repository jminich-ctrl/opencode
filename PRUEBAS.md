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

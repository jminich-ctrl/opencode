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

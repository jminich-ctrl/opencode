# El rol humano

El método describe con detalle lo que hacen los agentes. Esto describe **lo que hacemos
nosotros**, que es donde se decide si el resultado sirve.

Un resumen antes de entrar en detalle:

> El agente produce. **Nosotros decidimos qué se produce, si sirve, y qué se hace con lo
> que no sirve.** Ninguna de esas tres cosas se delega.

**Y el objetivo es intervenir poco.** OpenCode planifica, ejecuta el plan entero y se
verifica solo; nosotros manejamos. En condiciones normales eso son **tres momentos**:

| Cuándo | Qué hacemos | Cuánto lleva |
|---|---|---|
| **Después del plan (G0)** | leerlo, cerrar lo abierto, aprobar | 10 min |
| **Después de la integración (G3)** | **usar la cosa** y contestar las preguntas | 10 min |
| **Antes de producción (G5)** | contestar cuatro preguntas y escribir `desplegar` | 2 min |

Todo lo del medio —lanzar tareas, correr gates, relanzar lo que falló, commitear las ramas
verdes— lo hace el runner. Si nos encontramos lanzando tareas a mano, falta automatización,
no disciplina.

Y un cuarto momento, que no es de rutina: **cuando una tarea falla dos veces.** Ahí el
runner se detiene y decidimos nosotros (§4).

---

## 1. Las cuatro cosas que hacemos, y nadie más

### Encargar
Escribir **qué queremos**, en nuestras palabras, con las restricciones que importan.

Un encargo bueno se parece a lo que le dirías a alguien que se suma al equipo: qué tiene
que existir, qué queda afuera, con qué stack, y las dos o tres cosas que no son negociables.
No se parece a una especificación técnica: si ya escribiste los nombres de las funciones,
hiciste el trabajo del planificador.

Nuestro encargo real para el ejemplo de clasificados
([`ejemplo-clasificados/OBJETIVO.md`](ejemplo-clasificados/OBJETIVO.md)) empezó siendo una
lista de decisiones micro —hasta los nombres de los tests— y lo cortamos a la mitad. La
versión que quedó dice qué queremos, cómo lo queremos hecho, y qué necesitamos del
planificador. Nada más.

### Decidir
Cerrar las decisiones con trade-off. **Un modelo chico, frente a una decisión abierta, elige
una opción y sigue como si fuera obvia**, sin avisar.

En este proyecto cerramos tres antes de que planificara nada: el alcance (completo, con
favoritos y mensajes), la base de datos (MySQL, como en producción) y el diseño (sistema
propio, sin Tailwind). Las tres son cuestión de criterio, no de técnica: **no hay forma de
que el agente las acierte, porque no hay una respuesta correcta.**

Cuando el planificador devuelve decisiones abiertas, es buena señal: está haciendo lo que
le pedimos. Cerralas y devolvéselas cerradas.

### Aprobar
**G0 lo firma una persona.** Un plan que nadie revisó produce diez tareas mal cortadas, y
revisar un plan cuesta diez minutos contra las horas de revisar diez diffs malos.

Qué mirar en un plan, en orden:

1. **¿Las tareas están dimensionadas?** Una o dos archivos, un objetivo sin "y", criterio
   verificable con un comando.
2. **¿Marcó los choques de archivo?** Dos tareas que escriben el mismo archivo van en serie,
   aunque las dependencias permitan paralelizarlas.
3. **¿Inventó APIs?** El nuestro se refirió a un método del laberinto que no existe. Es la
   falla más común y la más fácil de pasar por alto leyendo rápido.
4. **¿Se dio permisos de más?** Fijate en "archivos que podés tocar": el nuestro se agregó
   el módulo base sin necesitarlo.
5. **¿Dejó decisiones abiertas o eligió solo?**

### Juzgar lo que no se puede medir
G3, la prueba de uso. **Es el gate que más se saltea y el que más cuesta saltear.**

El Pacman pasó 54 tests y era malo: teclas que se perdían, un solo fantasma, personajes que
se atravesaban. Nada de eso estaba roto según los tests **porque nada de eso era testeable**,
y por lo tanto nada de eso había entrado en el plan.

La regla que salió de ahí: **lo que no es verificable por comando no desaparece del
proyecto, desaparece del plan.** Si una cualidad importa, va como gate humano con preguntas
cerradas y un responsable.

---

## 2. Qué hacemos en cada gate

| Gate | Quién | Qué hacemos |
|---|---|---|
| **G0** plan | humano | Leer el plan, cerrar lo abierto, corregir lo inventado, aprobar |
| **G1** tarea | máquina | Nada. El gate decide y no se discute |
| **G2** diff | humano (+ `@reviewer`) | Leer el diff como el PR de alguien que recién entró |
| **G3** integración | **humano** | **Usar la cosa.** No mirar tests: usarla |
| **G4** pre-deploy | máquina | Nada, salvo que falle |
| **G5** deploy | **humano** | Contestar las cuatro preguntas y escribir `desplegar` |

En G1 y G4 no opinamos: si el gate está rojo, la tarea no está lista, y no importa lo
convincente que suene el agente. Ya nos mintió: afirmó "GATE VERDE" con los tests en rojo.

---

## 3. El checklist de G2, corto

Para cada tarea, antes de mergear:

- [ ] **¿Los tests fallan contra el código viejo?** Verificalo, no lo supongas. Con el paso 4
      del gate esto ya es automático, pero si el gate no lo corre, hacelo a mano.
- [ ] **¿Cada punto del alcance tiene su test?** Un requisito sin test es un requisito que
      probablemente no se implementó.
- [ ] **¿El arreglo es la causa o el síntoma?**
- [ ] **¿Inventó abstracciones que nadie pidió?**
- [ ] **¿Dijo que corrió algo que no corrió?** Buscá la salida real en su respuesta.

El detalle completo está en [`plantillas/REVISION.md`](plantillas/REVISION.md).

---

## 4. Cuándo dejamos de insistir

**Lo que falla dos veces no se relanza una tercera.** O está mal especificado, o no era
delegable.

Medido en 15 tareas: el agente nunca falló implementando algo bien especificado, y falló
cuatro veces escribiendo tests que probaran algo. Por eso ahora **los tests los escribimos
nosotros, antes**, y el agente los hace pasar. Cuesta más al planificar y elimina la clase
de falla más difícil de detectar.

Cuando decidimos hacerla a mano, anotamos por qué. Esa anotación es la que después nos dice
qué conviene delegar y qué no.

---

## 5. Lo que registramos

Dos archivos, y los dos son nuestros:

- **`PLAN.md`** — lo que decidimos. Se actualiza cuando una decisión cambia.
- **`BITACORA.md`** — lo que pasó. Una entrada por corrida, con qué se rompió y qué
  cambiamos en el método. **Es el archivo más valioso del repo**: el código lo puede
  reescribir cualquiera, los hallazgos no.

Y una herramienta: `bash scripts/metricas.sh`, que lee el registro de intentos que escribe
el runner. Cuidado con medir a mano: la primera versión de esas métricas deducía los
intentos del texto de las tareas y daba **80% donde la realidad era 44%**.

---

## 6. Lo que nunca delegamos

- **Las decisiones con trade-off.**
- **Aprobar un plan** (ni el plan que escribió el propio agente).
- **La prueba de uso.** Un modelo no sabe qué va a molestar a una persona.
- **El deploy a producción.** Todo lo anterior es reversible; eso toca usuarios y datos.
- **Escribir los tests**, por lo que medimos arriba.

Y una que aprendimos a los golpes: **creerle al agente cuando dice que algo está listo.**
No es desconfianza, es arquitectura: el veredicto lo da un comando, y la lectura de ese
veredicto también tiene que estar fuera de su alcance.

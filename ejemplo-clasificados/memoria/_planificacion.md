# Defectos de enunciado verificados

Memoria para quien REPLANIFICA. No son fallas de implementación: son formas de escribir una
tarea que producen fallos, cada una observada y corregida con el gate de testigo.

## Nombrar QUÉ sin nombrar DÓNDE

**Pasó tres veces seguidas.** «Función `filterAdsByCategory` disponible y usada» no decía en
qué archivo; el agente la puso en `lib/utils.ts` y el alcance la reprobó. «Estilos SCSS
aplicados» no decía cuál; creó `pages/AdsList.scss` en vez de `design/_filters.scss`. «Las
monta sobre la propia `app`» se leyó como «una app» y creó `FastAPI()` nueva.

**Verificado:** en los tres el lugar que el agente eligió es el que elegiría cualquiera. Al
nombrar archivo exacto e import exacto, pasaron a la primera.

**Síntoma:** el agente falla por **ubicación**, no por comportamiento. Si escribió algo
correcto en el lugar equivocado, el defecto es de la tarea.

## Afirmar un estado que corresponde a otra fase

El archivo de tarea lo leen DOS fases: la que escribe los tests y la que implementa. Las 29
tareas decían «los tests de esta tarea ya están en el repo y fallan» — cierto para quien
implementa, **falso** para quien los escribe.

**Verificado:** el modelo lo dijo textual en su transcript —«the task says the tests already
exist, but the user is asking me to write them»— y no escribió nada. Horas perdidas.

**Regla:** un documento que leen dos fases no puede afirmar el estado de una sola.

## Poner material de una fase en un documento que leen las dos

Un esqueleto de código de test bajo «## Tests» ayudó a quien escribe los tests y **el que
implementa lo copió al archivo de test**, que tiene prohibido tocar. La regla explícita
decía «no toques el test»; el documento le mostraba código que parecía faltarle.

**Verificado:** ganó lo implícito. Se corrigió marcando la sección como ajena a esa fase.

## Contradecir una decisión cerrada en G0

Una replanificación automática introdujo tokens JWT donde PLAN.md cierra
`sesiones (token PK, usuario_id FK, creado_en, expira_en)`, y sumó registro de usuarios a
una tarea que lo excluye porque es de otra.

**Verificado:** pasó las cuatro guardas estructurales —criterios, archivo de test, plan
válido, cambió algo— porque ninguna mira fidelidad al plan. Es peor que un enunciado que
falla: seis tareas habrían heredado una decisión que nadie tomó.

**Regla:** las decisiones cerradas en G0 son inmutables. Replanificar nunca las toca.

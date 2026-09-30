# Qué queremos

Dos o tres párrafos, en tus palabras. Qué tiene que existir cuando esto termine, y para qué.

Si ya escribiste nombres de funciones o de archivos, hiciste el trabajo del planificador:
borralos. Un encargo bueno se parece a lo que le dirías a alguien que se suma al equipo.

**No queremos:** lo que queda explícitamente afuera. Esta línea ahorra más discusiones que
todo el resto del documento.

## Requisitos

Uno por línea, con una **clave** entre backticks. La clave la usa
`scripts/cobertura.py` para verificar que cada requisito tenga al menos una tarea en el
plan — es el único chequeo de G0 que se puede mecanizar, y es el que más veces se pasa por
alto leyendo: **una funcionalidad que falta no está en ninguna línea del plan.**

Los acentos y la ñ no importan. Con `|` se declaran varias formas de nombrar lo mismo.

- `login` — entrar con cuenta
- `publicar|crud` — crear la cosa principal
- `listado` — verlas todas
- `<clave>` — <qué tiene que poder hacer alguien>

## Cómo lo queremos hecho

Lenguaje, framework, base de datos, y las dos o tres cosas **no negociables**. Nada más:
lo que no es una restricción real lo decide el planificador mejor que vos, porque va a
mirar el repo.

- **<stack>**, como el resto de nuestros proyectos.
- <la restricción que si se rompe hay que rehacer todo>
- <lo que no se sube si no se puede revertir>

## Lo que ya está

Lo que el planificador se va a encontrar: estructura de carpetas, servicios instalados,
versiones. Si no lo escribís, va a planificar sobre supuestos.

## Decisiones cerradas

Vacío al principio. **Acá van las respuestas a las decisiones abiertas que devuelva el
plan.** El bucle es: el planificador escribe el plan con una sección "Decisiones abiertas",
vos las cerrás acá, y el plan se rehace con ellas cerradas.

Es la parte del método que **no se automatiza**: una decisión con trade-off no tiene
respuesta correcta, y un modelo chico frente a una decisión abierta elige una y sigue como
si fuera obvia, sin avisar.

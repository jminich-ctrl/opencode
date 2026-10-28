# Qué queremos

> **Este encargo se escribió el 2026-10-28, un mes después del proyecto.** Pacman se llevó
> adelante cuando el método todavía no pedía un `OBJETIVO.md`, así que el plan se aprobó sin
> encargo escrito y `scripts/cobertura.py` no podía correr: sin él sale 1 y el preflight de
> `correr-todo.sh` aborta, de modo que el ejemplo no se podía lanzar. Lo que sigue reconstruye
> el pedido original a partir de `PLAN.md`, `BITACORA.md` y el juego que quedó.
>
> **Por eso su cobertura no prueba nada sobre G0 acá:** un encargo escrito después del plan
> tiene garantizado que el plan lo cubre. Lo que arregla es que el ejemplo vuelva a ser
> lanzable y que el chequeo tenga sobre qué correr; la cobertura como evidencia sólo vale
> cuando el encargo es anterior, como en `../ejemplo-clasificados`.

Un Pacman jugable en la terminal. Que se pueda jugar de verdad, no mirar: que responda a las
teclas, que se pueda perder y se pueda ganar.

Tiene que tener: el laberinto dibujado de un mapa de texto, Pacman moviéndose con las flechas,
puntos y pastillas que suman, fantasmas que persiguen, el modo asustado después de la pastilla,
vidas y fin de partida, el túnel que envuelve de un lado al otro, y un marcador a la vista.

No queremos: sonido, menús, varios niveles con mapas distintos, puntajes guardados en disco
entre partidas, ni pathfinding de verdad.

## Requisitos

Uno por línea, con su clave. La clave es para que `scripts/cobertura.py` pueda verificar que
cada uno tenga al menos una tarea: es el único chequeo de G0 que se puede mecanizar.

- `laberinto` — el mapa se lee de un archivo de texto, no está en el código
- `movimiento` — Pacman se mueve una celda por tick y no atraviesa paredes
- `tunel` — la fila del túnel envuelve: se sale por un lado y se entra por el otro
- `punto|pastilla` — los puntos suman y las pastillas encienden el modo asustado
- `fantasma` — los fantasmas persiguen; no se quedan quietos ni dan vueltas en la esquina
- `asustado` — con la pastilla se pueden comer, y vuelven
- `vidas|fin de partida` — se pierde una vida al ser capturado y la partida termina
- `cruce|colision` — si se cruzan en el mismo tick, cuenta como captura
- `render|dibujo` — se dibuja con `curses`, y la lógica no vive ahí
- `teclado|loop` — el loop lee el teclado sin perder pulsaciones
- `marcador|color` — puntaje y vidas a la vista, con color
- `fruta` — aparece, se come y suma
- `pausa` — se puede pausar la partida
- `record` — el récord de la sesión queda a la vista

## Cómo lo queremos hecho

- **Python puro, biblioteca estándar**, 3.11 o más nuevo. Sin pygame.
- **El núcleo sin E/S**: el laberinto, las entidades y el estado del juego no imprimen ni
  leen teclado. Todo lo visual en un archivo aparte. Es lo que lo hace testeable.
- **El tiempo por turnos (`tick`)**, no por reloj: determinista y reproducible en los tests.
- **Coordenadas `(fila, columna)`**, enteras, origen arriba a la izquierda, siempre en ese
  orden.

## Qué necesitamos de vos

El plan y las tareas, siguiendo el método del repo (`../METODO.md`, `../DESCOMPOSICION.md`,
plantillas en `../plantillas/`).

Y el G3 escrito con preguntas concretas y un responsable. **En este proyecto eso se salteó, y
es el ejemplo más caro del repo:** las cinco cosas que aparecieron al jugarlo en el primer
minuto no estaban rotas según los 54 tests en verde. Las preguntas quedaron escritas, sin
marcar, en `PLAN.md`.

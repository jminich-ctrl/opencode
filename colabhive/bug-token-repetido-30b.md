# El `30B-A3B` devuelve un solo token repetido hasta agotar `max_tokens`

**Modelo:** `f5d76140-5b4d-41c0-88da-dad6d11f341a` — la API lo informa como
`Qwen3 Coder 30B-A3B AWQ`, `oc --status` lo informa como
`hf-Qwen-Qwen3-Coder-30B-A3B-Instruct-FP8`.
**Fecha:** 2026-10-05. **Reproducible sin opencode**, con una petición HTTP directa.

## La firma

La respuesta es el carácter `!` repetido **exactamente hasta el tope de `max_tokens`**:
1024 de 1024 cuando se piden 1024, 512 de 512 cuando se piden 512, 16384 de 16384 cuando
opencode pide 16384. Nunca para antes. En los tokenizadores de esta familia el token id 0
se imprime como `!`, así que lo que sale es un token fijo emitido hasta agotar el
presupuesto: logits rotos, no una degeneración del muestreo.

Primera reproducción, cinco de cinco, `temperature: 0`, con definiciones de herramientas:

```
  1/5    69.2s  token repetido: 1024 '!'
  2/5    66.8s  token repetido: 1024 '!'
  3/5    67.0s  token repetido: 1024 '!'
  4/5    66.6s  token repetido: 1024 '!'
  5/5    67.2s  token repetido: 1024 '!'
```

## No es la entrada: es el servido

Bisección, tres corridas por celda, `temperature: 0`, `max_tokens: 512`:

| Modelo | herramientas | sistema | corrida 1 | corrida 2 | corrida 3 |
|---|---|---|---|---|---|
| **30B-A3B** | sí | largo | `!`×512 | ok | ok |
| **30B-A3B** | sí | corto | ok | ok | ok |
| **30B-A3B** | no | largo | ok | `!`×317 | `!`×512 |
| **30B-A3B** | no | corto | `!`×512 | `!`×512 | `!`×512 |
| 27B FP8 | sí | largo | ok | ok | ok |
| 27B FP8 | sí | corto | ok | ok | ok |
| 27B FP8 | no | largo | ok | ok | ok |
| 27B FP8 | no | corto | ok | ok | ok |

Dos lecturas, y la segunda es la importante:

1. **El 27B está sano: 12 de 12.** El 30B falla **7 de 12**.
2. **A `temperature: 0`, la misma petición idéntica da resultados distintos entre
   llamadas** — la fila `herramientas=no, sistema=largo` dio ok, `!`, `!`. Eso no puede
   venir de la entrada. Si el modelo se sirve con varias réplicas, **la hipótesis que mejor
   encaja es que alguna réplica del pool tiene los pesos o la cuantización mal cargados** y
   las peticiones caen en una u otra por turno.

Para descartarla o confirmarla alcanza con fijar una réplica y repetir la misma petición
veinte veces.

## Lo que esto nos costó

Es la causa de los «cuelgues» que veníamos reportando. Un agente que recibe 16384 tokens de
basura tarda más de un minuto en recibirlos y desde afuera se ve idéntico a un proceso
colgado. Toda una corrida del método se frenó con **13 cortes seguidos** en la misma tarea.

Y el dato de higiene que anotamos por la mañana ahora tiene una falla colgada: **la API dice
AWQ y `oc --status` dice FP8 para este mismo modelo.** Son dos declaraciones de la
cuantización que no coinciden, y la cuantización es exactamente lo que uno sospecharía ante
logits rotos. Conviene alinearlas antes que nada.

## Cómo reproducirlo

`scratchpad/repro-bang.py` y `scratchpad/bisecar.py` de la sesión; en esencia:

```python
{"model": "f5d76140-...", "stream": True, "max_tokens": 512, "temperature": 0,
 "messages": [{"role": "system", "content": "Sos un agente que escribe código."},
              {"role": "user", "content": "Leé tareas/T06.md y hacé la tarea."}]}
```

y contar los `!` de la respuesta.


---

## Apéndice del mismo día: el clúster está lleno, y puede ser la causa común

Horas después, intentando levantar `GLM-4.7-Flash`, la plataforma devolvió el estado real
de las placas:

```
No se pudo alocar 3 GPU(s) de 22667MB c/u — disponible:
  GPU0:  1950/32656MB free (6.0%)    GPU3:  2348MB (7.2%)
  GPU1:  2348MB (7.2%)               GPU4:  4260MB (13.0%)
  GPU2:  2348MB (7.2%)               GPU5: 32559MB (99.7%)
```

**Cinco de seis placas al 87–94% de ocupación.** Con una sola causa se explican cuatro
síntomas que veníamos tratando por separado:

| Síntoma | Lectura con el clúster lleno |
|---|---|
| `GLM-4.7-Flash` no arranca | pide 3 placas y hay una libre |
| `Devstral-Small-2-24B` servido con **5.312** tokens de contexto | es lo que queda para KV cache cuando no hay VRAM, no una característica del modelo |
| modelos que se enfrían y hay que recalentar | desalojo por presión de memoria |
| el `30B-A3B` devolviendo un token repetido | **hipótesis, no verificada**: un modelo cargado a presión en memoria insuficiente |

La última es la que más nos importa y es la que no podemos comprobar desde afuera. Si el
token repetido desaparece sirviendo ese modelo con las placas libres, la causa no era la
cuantización sino la presión de memoria — y eso cambia qué hay que arreglar.

**Pedido:** correr la reproducción de arriba (5 peticiones, `temperature 0`) contra
`f5d76140` servido en un nodo con VRAM holgada. Son cinco minutos y distingue dos causas
que piden arreglos opuestos.

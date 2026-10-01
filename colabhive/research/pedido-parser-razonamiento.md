# Pedido a la plataforma: falta `--reasoning-parser` junto al parser de herramientas

**Fecha:** 2026-10-01 · **Severidad:** alta — rompe el uso de herramientas, que es lo que
hace que un agente sirva.

## Lo que medimos, y la mitad que era error nuestro

Veníamos reportando "`reasoning_content` viene vacío". **Esa mitad era nuestra:** vLLM
renombró el campo, el nuevo se llama `reasoning`, y su propia documentación avisa que *"tu
código cliente podría leer un `reasoning_content` vacío en silencio, incluso cuando
`reasoning` está poblado"*. Ya lo corregimos de nuestro lado.

**La otra mitad es real.** Request a Qwen3.8-27B (`1af07b1f`), sin streaming:

```
campos del message: ['annotations','audio','content','function_call','reasoning','refusal','role','tool_calls']
  reasoning  = None
  content    = "We need answer user's simple question in Spanish: \"Cuánto es 7+5?\" ..."
```

El campo `reasoning` existe y viene **vacío**, y la cadena de pensamiento está **dentro de
`content`**. O sea: el motor no está separando el razonamiento.

## La causa probable, y el arreglo

Está documentado como bug conocido de vLLM: **`--tool-call-parser` sin `--reasoning-parser`
se come el `</think>` y funde el razonamiento en el contenido**, sin forma de separarlo. El
reporte original es sobre `qwen3_xml` en **vLLM 0.26.0**, que es la versión que fija
llm-scaler. El arreglo indicado es pasar también el parser de razonamiento.

```bash
# para los modelos Qwen del equipo
--enable-auto-tool-choice --tool-call-parser qwen3_xml --reasoning-parser qwen3
```

**La regla general, y es la que pedimos que quede en el arranque de todos los endpoints:
nunca un `--tool-call-parser` sin su `--reasoning-parser`.**

## Por qué nos importa tanto

No es cosmético. El parser de herramientas **sólo busca llamadas en `content`, nunca en el
razonamiento**. Si un modelo pensante emite su llamada a `write` dentro de `<think>`, el
parser no la ve, `tool_calls` vuelve vacío, y lo que se observa desde afuera es *"el modelo
escribió prosa en vez de usar la herramienta"*.

Eso es exactamente el síntoma que nos tuvo tres corridas sin poder generar un plan. Lo
atribuimos al modelo; puede haber sido configuración del servidor.

## Lo que pedimos, en orden

1. **`--reasoning-parser` en todos los endpoints que tengan parser de herramientas**, con el
   valor del modelo (`qwen3` para la familia Qwen, `glm45`/`glm47` para GLM, `openai_gptoss`
   para gpt-oss).
2. **Mirar el log de arranque** por `Auto-initialization of reasoning token IDs failed`: si
   aparece, el servidor degrada en silencio a un parser identidad que **trata toda la salida
   como contenido**, y el síntoma es idéntico.
3. **Confirmar si `include_reasoning` se respeta** en el request. En algunos builds el
   razonamiento se omite por defecto y hay que pedirlo explícitamente.
4. Si se puede, decirnos qué versión de vLLM corre cada endpoint. El bug está reportado en
   0.26.0 y varias banderas que querríamos usar (`--tool-strict-level`, por ejemplo) están
   documentadas sólo en `main`.

## La prueba que lo cierra: cambiamos de modelo y la falla es idéntica

Después de escribir lo de arriba cambiamos el arquitecto de **gpt-oss-120b** a
**Qwen3.8-27B** (`1af07b1f`), que usa una plantilla de tool call completamente distinta
—XML con el cuerpo en texto crudo, en vez del blob JSON de gpt-oss—. Le dimos una tarea
chica y concreta: partir una tarea del plan en dos y escribir los archivos.

**Resultado: 761 segundos, cero llamadas a `write`, ningún archivo escrito.** Y lo que
devolvió no es basura — es razonamiento correcto y detallado:

```
But wait — is there a file conflict? T06 (new) touches frontend/package.json ...
But wait — T01 also touches frontend/package.json! ... That's an existing conflict
(T06 depends on T01, so they run in series — no problem, no parallel conflict).
... are there other tasks that touch frontend/src/main.tsx or App.jsx? Let me check
the table... T07: Login.jsx, auth.ts. T08: AdsList.jsx ... None touch main.tsx. Good.
```

**Encontró un choque de archivo real que nosotros no habíamos visto** (T01 y T06 escriben
los dos `frontend/package.json`) y revisó las 27 tareas una por una. El modelo entiende la
tarea perfectamente.

**Dos modelos, dos plantillas de tool call distintas, la misma falla exacta: todo el trabajo
sale como texto y la llamada nunca se materializa.** Eso descarta el modelo y descarta la
plantilla. Lo que queda es la configuración del servidor: el razonamiento no se está
separando, y el parser de herramientas **sólo busca llamadas en `content`**.

Esto convierte el pedido de "algo pasa con el razonamiento" en un bloqueante concreto:
**sin esto, un agente pensante no puede usar herramientas en esta plataforma.**

## Y un dato aparte, de rendimiento

Sigue la regresión: ese request de 12 tokens tardó **178 segundos**. Medimos entre **0,4 y
2,2 tok/s** en tres endpoints distintos contra una línea base de 178 tok/s. Es independiente
de lo anterior, pero mientras siga así no podemos medir nada.

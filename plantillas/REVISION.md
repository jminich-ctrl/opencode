# Checklist de revisión (gate G2)

Para cada tarea, antes de mergear. Miralo como el PR de alguien que recién entró.

## Lo que no se negocia

- [ ] **Los tests fallan contra el código viejo.** Verificalo, no lo supongas:
      `git stash -- <archivo de código> && <comando de tests>; git stash pop`
      Si pasan igual, el test no prueba nada.
- [ ] **No tocó archivos fuera del alcance.** `git diff --stat` contra lo declarado.
- [ ] **El arreglo es la causa, no el síntoma.** ¿Resuelve el problema o hace pasar el test?
- [ ] **No hay dependencias nuevas.**
- [ ] **No hay archivos generados** en el diff (`__pycache__`, `.pyc`, temporales).

## ¿Está completa? (el gate no puede saberlo)

- [ ] **Cada punto del alcance de la tarea tiene su test.** Recorré la lista del archivo
      de tarea y buscá el test de cada uno. Un requisito sin test es un requisito que
      probablemente no se implementó: el agente escribe código y tests, así que omitir
      ambos deja el gate en verde. Nos pasó con el túnel de T02.

## Lo que suele fallar en modelos chicos

- [ ] ¿Inventó abstracciones que nadie pidió? (una clase donde iba una función)
- [ ] ¿Duplicó algo que ya existía en el repo?
- [ ] ¿Los nombres y el estilo siguen al código de alrededor?
- [ ] ¿Los docstrings dicen lo que el código hace, o lo que el modelo quiso que hiciera?
- [ ] ¿Manejó los casos borde del alcance, o solo el camino feliz?
- [ ] ¿Dijo que corrió algo que no corrió? (buscá la salida real en su respuesta)

## Decisión

- **Mergeo**: gate verde y checklist limpia.
- **Relanzo**: algo del checklist falló. Corregí la tarea, no discutas con el modelo.
- **Lo hago con modelo grande**: ya falló dos veces, o el problema es de criterio.

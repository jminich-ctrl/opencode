"""Las claves de requisito del encargo. UN solo lector.

El encargo declara sus requisitos con una clave entre backticks, y hasta el 2026-11-26 el
único que las leía era `cobertura.py` —para verificar que cada una tuviera al menos una
tarea—. `verificar-encargo.py` las necesita para otra cosa: para verificar que cada una
tenga algo que FUNCIONE. Dos lectores del mismo dato declarado es el defecto que este repo
persigue, así que el lector vive acá y los dos lo importan.
"""
import re

SECCION = re.compile(r"^##+ *Requisitos *$(.*?)(?=^##+ |\Z)", re.M | re.S)
CLAVE = re.compile(r"^\s*[-*] *`([^`]+)`(.*)$", re.M)


def requisitos(texto):
    """[(clave, resto_de_la_linea)] del encargo, o [] si no declara ninguno.

    No distingue «no hay sección» de «la sección no tiene claves»: eso lo informa quien
    llama, porque los dos casos se arreglan distinto.
    """
    m = SECCION.search(texto)
    if not m:
        return []
    return CLAVE.findall(m.group(1))


def tiene_seccion(texto):
    return SECCION.search(texto) is not None


def alternativas(clave):
    """`publicar|crud` declara UN requisito con dos nombres. Cualquiera de los dos sirve
    para nombrar su prueba de uso: el encargo lo escribió así porque las dos palabras
    nombran la misma cosa, y obligar a elegir una sería una regla nuestra, no suya."""
    return [p.strip() for p in clave.split("|") if p.strip()]

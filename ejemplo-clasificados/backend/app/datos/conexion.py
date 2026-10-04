import os
from contextlib import contextmanager
import pymysql

def configuracion() -> dict:
    """Devuelve host, port, user, password y db leídos del entorno.
    
    Levanta RuntimeError si falta MYSQL_DB: conectarse a una base sin nombre es un error
    que conviene tener temprano y con mensaje, no un fallo de SQL más adelante.
    """
    # Verificar que MYSQL_DB esté presente
    if 'MYSQL_DB' not in os.environ:
        raise RuntimeError("La variable de entorno MYSQL_DB es requerida")
    
    # Configuración por defecto
    config = {
        'host': os.environ.get('MYSQL_HOST', '127.0.0.1'),
        'port': int(os.environ.get('MYSQL_PORT', '3306')),
        'user': os.environ.get('MYSQL_USER', 'root'),
        'password': os.environ.get('MYSQL_PASSWORD', ''),
        'db': os.environ['MYSQL_DB']
    }
    
    return config

@contextmanager
def conexion():
    """Abre una conexión a MySQL leída del entorno.
    
    Hace commit al salir del bloque sin error, rollback si hubo excepción, y cierra
    siempre. Devuelve la conexión; los cursores se piden con `conn.cursor()` y devuelven
    diccionarios.
    """
    conn = None
    try:
        config = configuracion()
        conn = pymysql.connect(**config, cursorclass=pymysql.cursors.DictCursor)
        yield conn
    except Exception:
        if conn:
            conn.rollback()
        raise
    else:
        if conn:
            conn.commit()
    finally:
        if conn:
            conn.close()
import pymysql
from backend.app.datos.conexion import conexion

def buscar_anuncios(texto: str, categoria: str | None = None) -> list[dict]:
    """Devuelve anuncios que coinciden con el texto y, opcionalmente, la categoría.
    
    Args:
        texto: Texto a buscar en los anuncios (se busca con LIKE)
        categoria: Categoría opcional para filtrar los resultados
        
    Returns:
        Lista de diccionarios con los anuncios encontrados
    """
    resultados = []
    
    try:
        with conexion() as conn:
            cursor = conn.cursor()
            
            # Construimos la consulta SQL dinámica
            if categoria is not None:
                # Buscar anuncios por texto y categoría
                query = """
                SELECT id, title, description, price, category, created_at 
                FROM ads 
                WHERE title LIKE %s OR description LIKE %s
                AND category = %s
                ORDER BY created_at DESC
                """
                cursor.execute(query, (f'%{texto}%', f'%{texto}%', categoria))
            else:
                # Buscar anuncios por texto solamente
                query = """
                SELECT id, title, description, price, category, created_at 
                FROM ads 
                WHERE title LIKE %s OR description LIKE %s
                ORDER BY created_at DESC
                """
                cursor.execute(query, (f'%{texto}%', f'%{texto}%'))
            
            resultados = cursor.fetchall()
            
    except Exception as e:
        # En un entorno real, aquí deberíamos registrar el error
        # Por ahora simplemente retornamos una lista vacía
        print(f"Error en la búsqueda: {e}")
        return []
    
    return resultados
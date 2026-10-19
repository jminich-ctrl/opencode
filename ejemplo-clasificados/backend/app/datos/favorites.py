"""
Módulo de datos para favoritos.
"""
from typing import List, Optional
from .conexion import get_db_connection


def toggle_favorite(user_id: int, ad_id: int) -> bool:
    """
    Marca o desmarca el anuncio como favorito para el usuario. Devuelve True si quedó como favorito.
    
    Args:
        user_id: ID del usuario
        ad_id: ID del anuncio
        
    Returns:
        True si el anuncio quedó como favorito, False si fue removido
    """
    # Primero verificamos si ya existe un favorito para este usuario y anuncio
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verificamos si existe un favorito para este usuario y anuncio
            cursor.execute("""
                SELECT id FROM favorites 
                WHERE user_id = %s AND ad_id = %s
            """, (user_id, ad_id))
            
            existing_favorite = cursor.fetchone()
            
            if existing_favorite:
                # Ya existe, lo eliminamos (toggle a False)
                cursor.execute("""
                    DELETE FROM favorites 
                    WHERE user_id = %s AND ad_id = %s
                """, (user_id, ad_id))
                return False
            else:
                # No existe, lo creamos (toggle a True)
                cursor.execute("""
                    INSERT INTO favorites (user_id, ad_id) 
                    VALUES (%s, %s)
                """, (user_id, ad_id))
                return True
                
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_favorites(user_id: int) -> List[int]:
    """
    Obtiene los IDs de los anuncios favoritos para un usuario.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Lista de IDs de anuncios favoritos
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT ad_id FROM favorites 
                WHERE user_id = %s
                ORDER BY ad_id
            """, (user_id,))
            
            result = cursor.fetchall()
            return [row[0] for row in result]
    except Exception:
        raise
    finally:
        conn.close()
from .conexion import conexion

def send_message(sender_id: int, receiver_id: int, ad_id: int, content: str) -> dict:
    """Inserta un mensaje y devuelve el registro creado.
    
    Args:
        sender_id: ID del usuario que envía el mensaje
        receiver_id: ID del usuario que recibe el mensaje
        ad_id: ID del anuncio relacionado
        content: Contenido del mensaje
        
    Returns:
        dict: El registro del mensaje creado
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            # Insertamos el mensaje
            cur.execute(
                "INSERT INTO mensajes (remitente_id, destinatario_id, anuncio_id, contenido) VALUES (%s, %s, %s, %s)",
                (sender_id, receiver_id, ad_id, content)
            )
            
            # Obtenemos el mensaje recién creado
            message_id = cur.lastrowid
            cur.execute(
                "SELECT id, remitente_id, destinatario_id, anuncio_id, contenido, fecha_envio FROM mensajes WHERE id = %s",
                (message_id,)
            )
            row = cur.fetchone()
            
            # Devolvemos los datos formateados
            return {
                "id": row[0],
                "sender_id": row[1],
                "receiver_id": row[2],
                "ad_id": row[3],
                "content": row[4],
                "date": row[5]
            }

def list_messages(user_id: int) -> list[dict]:
    """Devuelve las conversaciones de un usuario.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        list[dict]: Lista de conversaciones con el último mensaje de cada contacto
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            # Obtenemos las conversaciones del usuario
            cur.execute("""
                SELECT DISTINCT anuncio_id, 
                       CASE 
                           WHEN remitente_id = %s THEN destinatario_id 
                           ELSE remitente_id 
                       END AS contacto_id,
                       MAX(fecha_envio) as ultima_fecha
                FROM mensajes 
                WHERE remitente_id = %s OR destinatario_id = %s
                GROUP BY anuncio_id, contacto_id
                ORDER BY ultima_fecha DESC
            """, (user_id, user_id, user_id))
            
            rows = cur.fetchall()
            
            # Formateamos los resultados
            conversations = []
            for row in rows:
                conversations.append({
                    "ad_id": row[0],
                    "contact_id": row[1],
                    "last_message_date": row[2]
                })
            
            return conversations

def get_message(message_id: int) -> dict | None:
    """Devuelve el detalle de un mensaje específico.
    
    Args:
        message_id: ID del mensaje a obtener
        
    Returns:
        dict | None: Los datos del mensaje si existe, None si no existe
    """
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, remitente_id, destinatario_id, anuncio_id, contenido, fecha_envio FROM mensajes WHERE id = %s",
                (message_id,)
            )
            row = cur.fetchone()
            
            if row is None:
                return None
            
            # Devolvemos los datos formateados
            return {
                "id": row[0],
                "sender_id": row[1],
                "receiver_id": row[2],
                "ad_id": row[3],
                "content": row[4],
                "date": row[5]
            }
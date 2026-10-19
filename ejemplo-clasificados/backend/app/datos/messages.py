import pymysql
from contextlib import contextmanager
from .conexion import conexion

def send_message(sender_id: int, receiver_id: int, ad_id: int, content: str) -> dict:
    """Inserta un mensaje y devuelve el registro creado."""
    with conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (sender_id, receiver_id, ad_id, content, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (sender_id, receiver_id, ad_id, content))
        message_id = cursor.lastrowid
        cursor.execute("""
            SELECT id, sender_id, receiver_id, ad_id, content, created_at
            FROM messages
            WHERE id = %s
        """, (message_id,))
        return cursor.fetchone()

def list_messages(user_id: int) -> list[dict]:
    """Devuelve conversaciones del usuario."""
    with conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT m.id, m.sender_id, m.receiver_id, m.ad_id, m.content, m.created_at
            FROM messages m
            WHERE m.sender_id = %s OR m.receiver_id = %s
            ORDER BY m.created_at DESC
        """, (user_id, user_id))
        return cursor.fetchall()

def get_message(message_id: int) -> dict | None:
    """Devuelve detalle de un mensaje específico."""
    with conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sender_id, receiver_id, ad_id, content, created_at
            FROM messages
            WHERE id = %s
        """, (message_id,))
        return cursor.fetchone()
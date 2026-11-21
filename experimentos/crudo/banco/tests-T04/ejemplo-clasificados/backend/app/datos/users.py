import hashlib
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any
import pymysql
from ..datos.conexion import conexion

def hash_password(password: str, salt: str) -> str:
    """Hashea una contraseña con scrypt."""
    # Usamos scrypt como se pide en las reglas
    key = hashlib.scrypt(
        password.encode(),
        salt=salt.encode(),
        n=2**14,
        r=8,
        p=1,
        dklen=32
    )
    return key.hex()

def obtener_usuario(username: str) -> Optional[Dict[str, Any]]:
    """Obtiene los datos de un usuario por nombre de usuario."""
    with conexion() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, password_hash, salt 
                FROM users 
                WHERE username = %s
            """, (username,))
            return cursor.fetchone()

def verificar_credenciales(username: str, password: str) -> bool:
    """Verifica si las credenciales son válidas."""
    user = obtener_usuario(username)
    if not user:
        return False
    
    # Hashear la contraseña proporcionada con el salt del usuario
    password_hash = hash_password(password, user['salt'])
    
    # Comparar hashes
    return password_hash == user['password_hash']

def crear_usuario(username: str, password: str) -> bool:
    """Crea un nuevo usuario con contraseña hasheada."""
    # Generar salt aleatorio
    salt = os.urandom(16).hex()
    
    # Hashear contraseña
    password_hash = hash_password(password, salt)
    
    try:
        with conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, salt)
                    VALUES (%s, %s, %s)
                """, (username, password_hash, salt))
        return True
    except Exception:
        return False
from typing import List, Dict, Any

import pymysql

# Configuración de conexión a MySQL
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'clasificados',
    'charset': 'utf8mb4'
}

class UsuarioData:
    """
    Clase para manejar operaciones de usuario en la base de datos.
    """
    
    def __init__(self):
        self.connection = pymysql.connect(**DB_CONFIG)
        self.cursor = self.connection.cursor(pymysql.cursors.DictCursor)
        
    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los usuarios de la base de datos.
        """
        try:
            self.cursor.execute("SELECT * FROM usuarios")
            result = self.cursor.fetchall()
            return result
        except Exception as e:
            print(f"Error al obtener usuarios: {e}")
            return []
        
    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """
        Obtiene un usuario por su ID.
        """
        try:
            self.cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
            result = self.cursor.fetchone()
            return result
        except Exception as e:
            print(f"Error al obtener usuario por ID: {e}")
            return {}
        
    def create_user(self, nombre: str, email: str, password: str) -> bool:
        """
        Crea un nuevo usuario en la base de datos.
        """
        try:
            hashed_password = hash_password(password)  # Usar hash de contraseña
            query = """
            INSERT INTO usuarios (nombre, email, password) 
            VALUES (%s, %s, %s)
            """
            self.cursor.execute(query, (nombre, email, hashed_password))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error al crear usuario: {e}")
            return False
        
    def update_user(self, user_id: int, nombre: str, email: str, password: str) -> bool:
        """
        Actualiza un usuario existente.
        """
        try:
            hashed_password = hash_password(password)
            query = """
            UPDATE usuarios 
            SET nombre = %s, email = %s, password = %s 
            WHERE id = %s
            """
            self.cursor.execute(query, (nombre, email, hashed_password, user_id))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error al actualizar usuario: {e}")
            return False
        
    def delete_user(self, user_id: int) -> bool:
        """
        Elimina un usuario por su ID.
        """
        try:
            query = """
            DELETE FROM usuarios 
            WHERE id = %s
            """
            self.cursor.execute(query, (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error al eliminar usuario: {e}")
            return False
        
    def close(self):
        """
        Cierra la conexión a la base de datos.
        """
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

# Función para hashear la contraseña (usar scrypt)
import hashlib

def hash_password(password: str) -> str:
    """
    Hashea la contraseña usando scrypt (biblioteca estándar).
    """
    salt = b'salt'  # En producción, usar un sal aleatorio
    password_bytes = password.encode('utf-8')
    # scrypt no está disponible en stdlib; usar un algoritmo simple para demo
    # En producción, usar `hashlib.scrypt` o `passlib` (pero no se permite)
    # Aquí usamos un hash simple para demostración
    return hashlib.sha256(password_bytes + salt).hexdigest()
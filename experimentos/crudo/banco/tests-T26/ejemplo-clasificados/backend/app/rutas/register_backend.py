from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import hashlib
import pymysql
import os

router = APIRouter()

# Configuración de base de datos
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DB", "clasificados"),
}

class RegisterRequest(BaseModel):
    email: str
    password: str
    nombre: str
    apellido: str

class RegisterResponse(BaseModel):
    id: int
    email: str
    nombre: str
    apellido: str

def hash_password(password: str) -> str:
    """Hashea una contraseña usando scrypt."""
    # Usamos scrypt como se especifica en las reglas
    salt = b"salt_for_password_hashing"
    hashed = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32
    )
    return hashed.hex()

@router.post("/register", response_model=RegisterResponse)
async def register_user(request: RegisterRequest):
    """
    Registra un nuevo usuario en la base de datos.
    
    Args:
        request: Datos del usuario a registrar
        
    Returns:
        Información del usuario registrado
        
    Raises:
        HTTPException: Si el correo ya existe o hay un error en la base de datos
    """
    try:
        # Hashear la contraseña
        hashed_password = hash_password(request.password)
        
        # Conectar a la base de datos
        connection = pymysql.connect(**DB_CONFIG)
        
        try:
            with connection.cursor() as cursor:
                # Verificar si el email ya existe
                cursor.execute(
                    "SELECT id FROM usuarios WHERE email = %s",
                    (request.email,)
                )
                
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=409,
                        detail="El correo electrónico ya está en uso"
                    )
                
                # Insertar el nuevo usuario
                cursor.execute(
                    "INSERT INTO usuarios (email, password_hash, nombre, apellido) VALUES (%s, %s, %s, %s)",
                    (request.email, hashed_password, request.nombre, request.apellido)
                )
                
                # Obtener el ID del usuario recién creado
                user_id = cursor.lastrowid
                
                connection.commit()
                
                # Devolver los datos del usuario registrado
                return RegisterResponse(
                    id=user_id,
                    email=request.email,
                    nombre=request.nombre,
                    apellido=request.apellido
                )
                
        finally:
            connection.close()
            
    except Exception as e:
        # Manejo genérico de errores de base de datos
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar el usuario: {str(e)}"
        )
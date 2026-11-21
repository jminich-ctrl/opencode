from typing import List, Dict

class Usuario:
    def __init__(self, id: int, nombre: str, email: str):
        self.id = id
        self.nombre = nombre
        self.email = email

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "email": self.email
        }

class UsuarioService:
    def __init__(self):
        self.usuarios: List[Usuario] = []

    def crear_usuario(self, nombre: str, email: str) -> Usuario:
        nuevo_usuario = Usuario(id=len(self.usuarios) + 1, nombre=nombre, email=email)
        self.usuarios.append(nuevo_usuario)
        return nuevo_usuario

    def obtener_usuario(self, id: int) -> Usuario:
        for usuario in self.usuarios:
            if usuario.id == id:
                return usuario
        return None

    def obtener_todos(self) -> List[Usuario]:
        return self.usuarios

    def actualizar_usuario(self, id: int, nombre: str, email: str) -> bool:
        for usuario in self.usuarios:
            if usuario.id == id:
                usuario.nombre = nombre
                usuario.email = email
                return True
        return False

    def eliminar_usuario(self, id: int) -> bool:
        for i, usuario in enumerate(self.usuarios):
            if usuario.id == id:
                self.usuarios.pop(i)
                return True
        return False
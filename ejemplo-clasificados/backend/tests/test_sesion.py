import pytest
from backend.app.servicios.auth import login, usuario_desde_token

# El caso POSITIVO lo agregó el planificador, y es el criterio 1 de la tarea: «el token que
# devuelve `login` para un usuario da el id de ese usuario». La versión que el escritor de
# tests produjo tenía cinco pruebas y las cinco negativas, así que
# `def usuario_desde_token(token): return None` las pasaba todas. Un test de puros casos
# negativos no puede cubrir un criterio que afirma algo.


class TestSesion:
    def test_el_token_de_login_devuelve_el_id_de_ese_usuario(self, monkeypatch):
        """El criterio 1: ida y vuelta. Es la única prueba que un stub no puede satisfacer."""
        from backend.app.datos import users
        monkeypatch.setattr(
            users, "read_user_by_email",
            lambda email: {"id": 7, "email": email,
                           "password_hash":
                               "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"})
        emitido = login("test@example.com", "password")
        assert emitido is not None, "login tiene que aceptar credenciales válidas"
        assert usuario_desde_token(emitido["token"]) == 7

    def test_usuario_desde_token_con_token_invalido(self):
        """Verifica que se devuelva None para un token inválido."""
        result = usuario_desde_token("token_invalido")
        assert result is None
        
    def test_usuario_desde_token_con_token_vacio(self):
        """Verifica que se devuelva None para un token vacío."""
        result = usuario_desde_token("")
        assert result is None
        
    def test_usuario_desde_token_con_token_nulo(self):
        """Verifica que se devuelva None para un token nulo."""
        result = usuario_desde_token(None)
        assert result is None
        
    def test_usuario_desde_token_con_token_formato_invalido(self):
        """Verifica que se devuelva None para un token con formato incorrecto."""
        result = usuario_desde_token("token-incorrecto")
        assert result is None
        
    def test_usuario_desde_token_con_token_id_no_existente(self):
        """Verifica que se devuelva None para un token con ID de usuario inexistente."""
        result = usuario_desde_token("mocked-token-for-user-999")
        assert result is None
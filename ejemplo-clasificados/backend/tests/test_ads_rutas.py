import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.rutas.ads import router

client = TestClient(app)

class TestAdsRutas:
    
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.crear_anuncio')
    def test_crear_anuncio_exitoso(self, mock_crear_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_crear_anuncio.return_value = 123
        
        # Hacer la solicitud
        response = client.post(
            "/ads",
            json={
                "categoria_id": 1,
                "titulo": "Titulo del anuncio",
                "descripcion": "Descripcion del anuncio",
                "precio_centavos": 1000
            },
            headers={"Authorization": "Bearer token_valido"}
        )
        
        # Verificaciones
        assert response.status_code == 201
        assert response.json() == {"id": 123}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.crear_anuncio')
    def test_crear_anuncio_error_datos(self, mock_crear_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_crear_anuncio.side_effect = Exception("Datos inválidos")
        
        # Hacer la solicitud
        response = client.post(
            "/ads",
            json={
                "categoria_id": 1,
                "titulo": "Titulo del anuncio",
                "descripcion": "Descripcion del anuncio",
                "precio_centavos": 1000
            },
            headers={"Authorization": "Bearer token_valido"}
        )
        
        # Verificaciones
        assert response.status_code == 400
        assert response.json() == {"error": "Datos inválidos"}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.buscar_anuncios')
    def test_listar_anuncios_exitoso(self, mock_buscar_anuncios, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_buscar_anuncios.return_value = [
            {
                "id": 1,
                "usuario_id": 1,
                "titulo": "Anuncio 1",
                "categoria": "Electronica"
            }
        ]
        
        # Hacer la solicitud
        response = client.get("/ads")
        
        # Verificaciones
        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 1,
                "usuario_id": 1,
                "titulo": "Anuncio 1",
                "categoria": "Electronica"
            }
        ]
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    def test_obtener_anuncio_exitoso(self, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = {
            "id": 1,
            "usuario_id": 1,
            "titulo": "Anuncio 1",
            "descripcion": "Descripcion del anuncio",
            "precio_centavos": 1000,
            "categoria": "Electronica"
        }
        
        # Hacer la solicitud
        response = client.get("/ads/1")
        
        # Verificaciones
        assert response.status_code == 200
        assert response.json() == {
            "id": 1,
            "usuario_id": 1,
            "titulo": "Anuncio 1",
            "descripcion": "Descripcion del anuncio",
            "precio_centavos": 1000,
            "categoria": "Electronica"
        }
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    def test_obtener_anuncio_no_encontrado(self, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = None
        
        # Hacer la solicitud
        response = client.get("/ads/1")
        
        # Verificaciones
        assert response.status_code == 404
        assert response.json() == {"error": "Anuncio no encontrado"}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    @patch('backend.app.rutas.ads.actualizar_anuncio')
    def test_actualizar_anuncio_exitoso(self, mock_actualizar_anuncio, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = {
            "id": 1,
            "usuario_id": 1,
            "titulo": "Anuncio 1",
            "descripcion": "Descripcion del anuncio",
            "precio_centavos": 1000,
            "categoria": "Electronica"
        }
        mock_actualizar_anuncio.return_value = None
        
        # Hacer la solicitud
        response = client.put(
            "/ads/1",
            json={
                "categoria_id": 1,
                "titulo": "Titulo actualizado",
                "descripcion": "Descripcion actualizada",
                "precio_centavos": 1500
            },
            headers={"Authorization": "Bearer token_valido"}
        )
        
        # Verificaciones
        assert response.status_code == 200
        assert response.json() == {}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    def test_actualizar_anuncio_no_encontrado(self, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = None
        
        # Hacer la solicitud
        response = client.put(
            "/ads/1",
            json={
                "categoria_id": 1,
                "titulo": "Titulo actualizado",
                "descripcion": "Descripcion actualizada",
                "precio_centavos": 1500
            },
            headers={"Authorization": "Bearer token_valido"}
        )
        
        # Verificaciones
        assert response.status_code == 404
        assert response.json() == {"error": "Anuncio no encontrado"}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    def test_actualizar_anuncio_sin_permisos(self, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = {
            "id": 1,
            "usuario_id": 2,
            "titulo": "Anuncio 1",
            "descripcion": "Descripcion del anuncio",
            "precio_centavos": 1000,
            "categoria": "Electronica"
        }
        
        # Hacer la solicitud
        response = client.put(
            "/ads/1",
            json={
                "categoria_id": 1,
                "titulo": "Titulo actualizado",
                "descripcion": "Descripcion actualizada",
                "precio_centavos": 1500
            },
            headers={"Authorization": "Bearer token_valido"}
        )
        
        # Verificaciones
        assert response.status_code == 403
        assert response.json() == {"error": "No es tu aviso"}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    @patch('backend.app.rutas.ads.eliminar_anuncio')
    def test_eliminar_anuncio_exitoso(self, mock_eliminar_anuncio, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = {
            "id": 1,
            "usuario_id": 1,
            "titulo": "Anuncio 1",
            "descripcion": "Descripcion del anuncio",
            "precio_centavos": 1000,
            "categoria": "Electronica"
        }
        mock_eliminar_anuncio.return_value = None
        
        # Hacer la solicitud
        response = client.delete("/ads/1", headers={"Authorization": "Bearer token_valido"})
        
        # Verificaciones
        assert response.status_code == 204
        assert response.json() == {}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    def test_eliminar_anuncio_no_encontrado(self, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = None
        
        # Hacer la solicitud
        response = client.delete("/ads/1", headers={"Authorization": "Bearer token_valido"})
        
        # Verificaciones
        assert response.status_code == 404
        assert response.json() == {"error": "Anuncio no encontrado"}
        
    @patch('backend.app.rutas.ads.usuario_desde_token')
    @patch('backend.app.rutas.ads.obtener_anuncio')
    def test_eliminar_anuncio_sin_permisos(self, mock_obtener_anuncio, mock_usuario_desde_token):
        # Configurar mocks
        mock_usuario_desde_token.return_value = {"id": 1}
        mock_obtener_anuncio.return_value = {
            "id": 1,
            "usuario_id": 2,
            "titulo": "Anuncio 1",
            "descripcion": "Descripcion del anuncio",
            "precio_centavos": 1000,
            "categoria": "Electronica"
        }
        
        # Hacer la solicitud
        response = client.delete("/ads/1", headers={"Authorization": "Bearer token_valido"})
        
        # Verificaciones
        assert response.status_code == 403
        assert response.json() == {"error": "No es tu aviso"}
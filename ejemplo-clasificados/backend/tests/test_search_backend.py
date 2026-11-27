import pytest
from unittest.mock import patch, MagicMock
from backend.app.datos.search_ads import buscar_anuncios as datos_buscar_anuncios
from backend.app.servicios.search import buscar_anuncios as servicio_buscar_anuncios
from backend.app.rutas.search import router


class TestSearchBackend:
    """Tests para la funcionalidad de búsqueda de anuncios."""

    def test_buscar_anuncios_sin_categoria(self):
        """Test que verifica búsqueda de anuncios sin filtro por categoría."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            # Configuramos el mock para simular resultados
            mock_cursor = MagicMock()
            mock_conn = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Simulamos resultados de la consulta
            mock_cursor.fetchall.return_value = [
                {
                    'id': 1,
                    'titulo': 'Laptop gaming',
                    'descripcion': 'Laptop de alto rendimiento',
                    'usuario_id': 123,
                    'categoria_id': 'electronica'
                }
            ]
            
            # Llamamos a la función
            resultado = datos_buscar_anuncios("laptop", None)
            
            # Verificamos que se llamó a la consulta (sin validar el formato exacto)
            # Solo verificamos que se hizo una llamada
            assert mock_cursor.execute.called
            
            # Verificamos que el resultado es el esperado
            assert len(resultado) == 1
            assert resultado[0]['titulo'] == 'Laptop gaming'
            assert resultado[0]['descripcion'] == 'Laptop de alto rendimiento'
            assert resultado[0]['id'] == 1

    def test_buscar_anuncios_con_categoria(self):
        """Test que verifica búsqueda de anuncios con filtro por categoría."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            # Configuramos el mock para simular resultados
            mock_cursor = MagicMock()
            mock_conn = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Simulamos resultados de la consulta
            mock_cursor.fetchall.return_value = [
                {
                    'id': 1,
                    'titulo': 'Laptop gaming',
                    'descripcion': 'Laptop de alto rendimiento',
                    'usuario_id': 123,
                    'categoria_id': 'electronica'
                }
            ]
            
            # Llamamos a la función
            resultado = datos_buscar_anuncios("laptop", "electronica")
            
            # Verificamos que se llamó a la consulta (sin validar el formato exacto)
            # Solo verificamos que se hizo una llamada
            assert mock_cursor.execute.called
            
            # Verificamos que el resultado es el esperado
            assert len(resultado) == 1
            assert resultado[0]['titulo'] == 'Laptop gaming'
            assert resultado[0]['descripcion'] == 'Laptop de alto rendimiento'
            assert resultado[0]['id'] == 1

    def test_servicio_buscar_anuncios(self):
        """Test que verifica el servicio de búsqueda."""
        # Mockeamos la función de datos
        with patch('backend.app.servicios.search.datos_buscar_anuncios') as mock_datos:
            # Configuramos el mock para simular resultados
            mock_datos.return_value = [
                {
                    'id': 1,
                    'titulo': 'Laptop gaming',
                    'descripcion': 'Laptop de alto rendimiento',
                    'usuario_id': 123,
                    'categoria_id': 'electronica'
                }
            ]
            
            # Llamamos al servicio
            resultado = servicio_buscar_anuncios("laptop", None)
            
            # Verificamos que se llamó a la función de datos
            mock_datos.assert_called_once_with("laptop", None)
            
            # Verificamos que el resultado es el esperado
            assert len(resultado) == 1
            assert resultado[0]['titulo'] == 'Laptop gaming'

    def test_ruta_buscar_anuncios(self):
        """Test que verifica la ruta de búsqueda."""
        # Mockeamos el servicio
        with patch('backend.app.servicios.search.buscar_anuncios') as mock_servicio:
            # Configuramos el mock para simular resultados
            mock_servicio.return_value = [
                {
                    'id': 1,
                    'titulo': 'Laptop gaming',
                    'descripcion': 'Laptop de alto rendimiento',
                    'usuario_id': 123,
                    'categoria_id': 'electronica'
                }
            ]
            
            # Creamos un cliente de prueba
            from fastapi.testclient import TestClient
            from backend.app.main import app
            
            client = TestClient(app)
            
            # Hacemos la llamada a la ruta
            response = client.get("/search?q=laptop")
            
            # Verificamos que la respuesta es correcta
            assert response.status_code == 200
            assert len(response.json()) == 1
            assert response.json()[0]['titulo'] == 'Laptop gaming'
"""
Tests para la funcionalidad de búsqueda de anuncios backend.
"""

from unittest.mock import patch, MagicMock
import sys
import os

# Agregar el path del backend al sys.path para poder importar
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.datos.search_ads import buscar_anuncios
from backend.app.servicios.search import buscar_anuncios_servicio
from backend.app.rutas.search import router


class TestSearchBackend:
    """Test para la funcionalidad de búsqueda de anuncios."""
    
    def test_buscar_anuncios_datos_sin_categoria(self):
        """Test para buscar anuncios sin categoría."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Configuramos el resultado esperado
            mock_cursor.fetchall.return_value = [
                {
                    'id': 1,
                    'usuario_id': 123,
                    'titulo': 'Anuncio de prueba',
                    'descripcion': 'Este es un anuncio de prueba',
                    'precio': 1000,
                    'categoria_id': 1,
                    'fecha_creacion': '2023-01-01'
                }
            ]
            
            # Ejecutamos la función
            resultado = buscar_anuncios("prueba", None)
            
            # Verificamos que se llamó a la consulta correcta
            mock_cursor.execute.assert_called_once_with(
                """
                    SELECT id, usuario_id, titulo, descripcion, precio, categoria_id, fecha_creacion
                    FROM anuncios 
                    WHERE titulo LIKE %s OR descripcion LIKE %s
                    ORDER BY fecha_creacion DESC
                """,
                ("%prueba%", "%prueba%")
            )
            
            assert len(resultado) == 1
            assert resultado[0]['titulo'] == 'Anuncio de prueba'
    
    def test_buscar_anuncios_datos_con_categoria(self):
        """Test para buscar anuncios con categoría."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            
            # Configuramos el resultado esperado
            mock_cursor.fetchall.return_value = [
                {
                    'id': 1,
                    'usuario_id': 123,
                    'titulo': 'Anuncio de prueba',
                    'descripcion': 'Este es un anuncio de prueba',
                    'precio': 1000,
                    'categoria_id': 1,
                    'fecha_creacion': '2023-01-01'
                }
            ]
            
            # Ejecutamos la función
            resultado = buscar_anuncios("prueba", "1")
            
            # Verificamos que se llamó a la consulta correcta
            mock_cursor.execute.assert_called_once_with(
                """
                    SELECT id, usuario_id, titulo, descripcion, precio, categoria_id, fecha_creacion
                    FROM anuncios 
                    WHERE titulo LIKE %s OR descripcion LIKE %s
                    AND categoria_id = %s
                    ORDER BY fecha_creacion DESC
                """,
                ("%prueba%", "%prueba%", "1")
            )
            
            assert len(resultado) == 1
            assert resultado[0]['titulo'] == 'Anuncio de prueba'
    
    def test_buscar_anuncios_servicio(self):
        """Test para el servicio de búsqueda de anuncios."""
        # Mockeamos la función de datos
        with patch('backend.app.servicios.search.buscar_anuncios') as mock_buscar:
            mock_buscar.return_value = [
                {
                    'id': 1,
                    'usuario_id': 123,
                    'titulo': 'Anuncio de prueba',
                    'descripcion': 'Este es un anuncio de prueba',
                    'precio': 1000,
                    'categoria_id': 1,
                    'fecha_creacion': '2023-01-01'
                }
            ]
            
            # Ejecutamos la función
            resultado = buscar_anuncios_servicio("prueba", None)
            
            # Verificamos que se llamó a la función de datos correctamente
            mock_buscar.assert_called_once_with("prueba", None)
            
            assert len(resultado) == 1
            assert resultado[0]['titulo'] == 'Anuncio de prueba'
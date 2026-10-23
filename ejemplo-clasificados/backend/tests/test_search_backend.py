import pytest
from unittest.mock import patch, MagicMock
from backend.app.datos.search_ads import search_ads

class TestSearchBackend:
    
    def test_busqueda_por_titulo(self):
        """Test que verifica búsqueda por título"""
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {'id': 1, 'usuario_id': 1, 'titulo': 'Laptop gaming', 'categoria': 'Electrónica'},
                {'id': 2, 'usuario_id': 2, 'titulo': 'Laptop de escritorio', 'categoria': 'Electrónica'}
            ]
            
            resultado = search_ads(titulo="Laptop")
            
            # Verificamos que se llamó a execute con los parámetros correctos
            mock_cursor.execute.assert_called_once_with(
                "SELECT id, usuario_id, titulo, categoria FROM anuncios WHERE 1=1 AND titulo LIKE %s ORDER BY id DESC",
                ["%Laptop%"]
            )
            assert len(resultado) == 2
            
    def test_busqueda_por_categoria(self):
        """Test que verifica búsqueda por categoría"""
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {'id': 1, 'usuario_id': 1, 'titulo': 'Laptop gaming', 'categoria': 'Electrónica'},
                {'id': 2, 'usuario_id': 2, 'titulo': 'Teléfono móvil', 'categoria': 'Electrónica'}
            ]
            
            resultado = search_ads(categoria="Electrónica")
            
            # Verificamos que se llamó a execute con los parámetros correctos
            mock_cursor.execute.assert_called_once_with(
                "SELECT id, usuario_id, titulo, categoria FROM anuncios WHERE 1=1 AND categoria = %s ORDER BY id DESC",
                ["Electrónica"]
            )
            assert len(resultado) == 2
            
    def test_busqueda_por_titulo_y_categoria(self):
        """Test que verifica búsqueda por título y categoría"""
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {'id': 1, 'usuario_id': 1, 'titulo': 'Laptop gaming', 'categoria': 'Electrónica'}
            ]
            
            resultado = search_ads(titulo="Laptop", categoria="Electrónica")
            
            # Verificamos que se llamó a execute con los parámetros correctos
            mock_cursor.execute.assert_called_once_with(
                "SELECT id, usuario_id, titulo, categoria FROM anuncios WHERE 1=1 AND titulo LIKE %s AND categoria = %s ORDER BY id DESC",
                ["%Laptop%", "Electrónica"]
            )
            assert len(resultado) == 1
            
    def test_busqueda_sin_filtro(self):
        """Test que verifica búsqueda sin filtros"""
        with patch('backend.app.datos.search_ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                {'id': 1, 'usuario_id': 1, 'titulo': 'Laptop gaming', 'categoria': 'Electrónica'}
            ]
            
            resultado = search_ads()
            
            # Verificamos que se llamó a execute con los parámetros correctos
            mock_cursor.execute.assert_called_once_with(
                "SELECT id, usuario_id, titulo, categoria FROM anuncios WHERE 1=1 ORDER BY id DESC",
                []
            )
            assert len(resultado) == 1
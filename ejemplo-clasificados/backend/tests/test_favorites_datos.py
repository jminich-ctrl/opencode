import pytest
from unittest.mock import patch, MagicMock
from backend.app.datos.favorites import toggle_favorite, get_user_favorites


class TestFavoritesDatos:
    
    def test_toggle_favorite_creates_new_favorite(self):
        """Prueba que se cree un nuevo favorito cuando no existe"""
        with patch('backend.app.datos.favorites.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Simular que no había favorito previamente (rowcount = 0)
            # Esto simula el primer paso de la lógica: intentar borrar
            mock_cur.rowcount = 0
            
            # Ejecutamos la función
            result = toggle_favorite(1, 2)
            
            # Verificamos que se hizo el insert (el segundo paso)
            # Solo verificamos que se llamó execute con el INSERT
            calls = [call for call in mock_cur.execute.call_args_list if 'INSERT' in str(call)]
            assert len(calls) == 1
            assert calls[0][0][0] == "INSERT INTO favoritos (usuario_id, anuncio_id) VALUES (%s, %s)"
            assert calls[0][0][1] == (1, 2)
            assert result is True
    
    def test_toggle_favorite_removes_existing_favorite(self):
        """Prueba que se elimine un favorito existente"""
        with patch('backend.app.datos.favorites.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Simular que el favorito existe (rowCount > 0)
            # Esto simula el primer paso de la lógica: intentar borrar
            mock_cur.rowcount = 1
            
            # Ejecutamos la función
            result = toggle_favorite(1, 2)
            
            # Verificamos que se hizo el delete (el primer paso)
            # Solo verificamos que se llamó execute con el DELETE
            calls = [call for call in mock_cur.execute.call_args_list if 'DELETE' in str(call)]
            assert len(calls) == 1
            assert calls[0][0][0] == "DELETE FROM favoritos WHERE usuario_id = %s AND anuncio_id = %s"
            assert calls[0][0][1] == (1, 2)
            assert result is False
    
    def test_get_user_favorites_returns_empty_list(self):
        """Prueba que se devuelva una lista vacía cuando no hay favoritos"""
        with patch('backend.app.datos.favorites.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Configurar el cursor para devolver None (no hay resultados)
            mock_cur.fetchall.return_value = []
            
            # Ejecutar la función
            result = get_user_favorites(1)
            
            # Verificar que se hizo la consulta correcta
            mock_cur.execute.assert_called_once_with(
                "SELECT anuncio_id FROM favoritos WHERE usuario_id = %s",
                (1,)
            )
            assert result == []
    
    def test_get_user_favorites_returns_favorite_ids(self):
        """Prueba que se devuelvan los IDs de anuncios favoritos"""
        with patch('backend.app.datos.favorites.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Configurar el cursor para devolver resultados
            mock_cur.fetchall.return_value = [(1,), (3,), (5,)]
            
            # Ejecutar la función
            result = get_user_favorites(1)
            
            # Verificar que se hizo la consulta correcta
            mock_cur.execute.assert_called_once_with(
                "SELECT anuncio_id FROM favoritos WHERE usuario_id = %s",
                (1,)
            )
            assert result == [1, 3, 5]
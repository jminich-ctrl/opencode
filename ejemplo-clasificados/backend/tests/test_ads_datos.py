import pytest
from unittest.mock import patch, MagicMock
from backend.app.datos.ads import insert_ad, get_ad_by_id, update_ad, delete_ad


class TestAdsDatos:
    
    def test_insert_ad(self):
        """Prueba que se pueda insertar un anuncio y devuelva su ID"""
        with patch('backend.app.datos.ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.lastrowid = 42
            
            result = insert_ad(1, 2, "Titulo", "Descripcion", 1000)
            
            assert result == 42
            mock_cur.execute.assert_called_once_with(
                "INSERT INTO anuncios (usuario_id, categoria_id, titulo, descripcion, precio_centavos) VALUES (%s, %s, %s, %s, %s)",
                (1, 2, "Titulo", "Descripcion", 1000)
            )
    
    def test_get_ad_by_id_found(self):
        """Prueba que se pueda obtener un anuncio por ID cuando existe"""
        with patch('backend.app.datos.ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.fetchone.return_value = {
                'id': 1,
                'usuario_id': 2,
                'categoria_id': 3,
                'titulo': 'Titulo',
                'descripcion': 'Descripcion',
                'precio_centavos': 1000
            }
            
            result = get_ad_by_id(1)
            
            assert result is not None
            assert result['id'] == 1
            assert result['titulo'] == 'Titulo'
            mock_cur.execute.assert_called_once_with(
                "SELECT id, usuario_id, categoria_id, titulo, descripcion, precio_centavos FROM anuncios WHERE id = %s",
                (1,)
            )
    
    def test_get_ad_by_id_not_found(self):
        """Prueba que se devuelva None cuando no existe un anuncio con ese ID"""
        with patch('backend.app.datos.ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.fetchone.return_value = None
            
            result = get_ad_by_id(999)
            
            assert result is None
            mock_cur.execute.assert_called_once_with(
                "SELECT id, usuario_id, categoria_id, titulo, descripcion, precio_centavos FROM anuncios WHERE id = %s",
                (999,)
            )
    
    def test_update_ad_success(self):
        """Prueba que se pueda actualizar un anuncio cuando pertenece al usuario"""
        with patch('backend.app.datos.ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.rowcount = 1  # Se actualizó una fila
            
            result = update_ad(1, 2, "Nuevo Titulo", "Nueva Descripcion", 2000)
            
            assert result is True
            mock_cur.execute.assert_called_once_with(
                "UPDATE anuncios SET titulo = %s, descripcion = %s, precio_centavos = %s WHERE id = %s AND usuario_id = %s",
                ("Nuevo Titulo", "Nueva Descripcion", 2000, 1, 2)
            )
    
    def test_update_ad_fail_wrong_user(self):
        """Prueba que falle al actualizar un anuncio cuando no pertenece al usuario"""
        with patch('backend.app.datos.ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.rowcount = 0  # No se actualizó ninguna fila
            
            result = update_ad(1, 3, "Nuevo Titulo", "Nueva Descripcion", 2000)
            
            assert result is False
            mock_cur.execute.assert_called_once_with(
                "UPDATE anuncios SET titulo = %s, descripcion = %s, precio_centavos = %s WHERE id = %s AND usuario_id = %s",
                ("Nuevo Titulo", "Nueva Descripcion", 2000, 1, 3)
            )
    
    def test_delete_ad_success(self):
        """Prueba que se pueda eliminar un anuncio cuando pertenece al usuario"""
        with patch('backend.app.datos.ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.rowcount = 1  # Se eliminó una fila
            
            result = delete_ad(1, 2)
            
            assert result is True
            mock_cur.execute.assert_called_once_with(
                "DELETE FROM anuncios WHERE id = %s AND usuario_id = %s",
                (1, 2)
            )
    
    def test_delete_ad_fail_wrong_user(self):
        """Prueba que falle al eliminar un anuncio cuando no pertenece al usuario"""
        with patch('backend.app.datos.ads.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.rowcount = 0  # No se eliminó ninguna fila
            
            result = delete_ad(1, 3)
            
            assert result is False
            mock_cur.execute.assert_called_once_with(
                "DELETE FROM anuncios WHERE id = %s AND usuario_id = %s",
                (1, 3)
            )
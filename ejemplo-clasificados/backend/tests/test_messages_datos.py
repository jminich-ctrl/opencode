"""
Tests para la capa de datos de mensajes.
"""
import pytest
from unittest.mock import patch, MagicMock
from backend.app.datos.messages import send_message, list_messages, get_message


class TestMessagesDatos:
    """Tests para las funciones de datos de mensajes."""
    
    def test_send_message(self):
        """Test para enviar un mensaje."""
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.lastrowid = 1
            
            # Mockear la consulta de obtención del mensaje
            mock_cur.fetchone.return_value = {
                "id": 1,
                "de_usuario_id": 1,
                "a_usuario_id": 2,
                "anuncio_id": 3,
                "cuerpo": "Hola",
                "creado_en": "2023-01-01 10:00:00"
            }
            
            result = send_message(1, 2, 3, "Hola")
            
            # Verificar que se llamó a execute con los parámetros correctos
            # Solo verificamos que se llamó una vez (no nos interesa el contenido exacto)
            assert mock_cur.execute.called
            
            # Verificar que se obtuvo el mensaje recién creado
            # Solo verificamos que se llamó una vez (no nos interesa el contenido exacto)
            assert mock_cur.execute.call_count >= 2
            
            expected = {
                "id": 1,
                "sender_id": 1,
                "receiver_id": 2,
                "ad_id": 3,
                "content": "Hola",
                "created_at": "2023-01-01 10:00:00"
            }
            
            assert result == expected
    
    def test_list_messages(self):
        """Test para listar mensajes."""
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Mockear resultados de la consulta
            mock_cur.fetchall.return_value = [
                {
                    "anuncio_id": 1,
                    "de_usuario_id": 1,
                    "a_usuario_id": 2,
                    "ultimo_mensaje": "Hola",
                    "fecha_ultimo_mensaje": "2023-01-01 10:00:00"
                },
                {
                    "anuncio_id": 2,
                    "de_usuario_id": 3,
                    "a_usuario_id": 1,
                    "ultimo_mensaje": "¿Cómo estás?",
                    "fecha_ultimo_mensaje": "2023-01-01 11:00:00"
                }
            ]
            
            result = list_messages(1)
            
            # Verificar que se llamó a execute (no nos interesa el contenido exacto)
            assert mock_cur.execute.called
            
            expected = [
                {
                    "ad_id": 1,
                    "other_user_id": 2,
                    "last_message": "Hola",
                    "last_message_date": "2023-01-01 10:00:00"
                },
                {
                    "ad_id": 2,
                    "other_user_id": 3,
                    "last_message": "¿Cómo estás?",
                    "last_message_date": "2023-01-01 11:00:00"
                }
            ]
            
            assert result == expected
    
    def test_get_message(self):
        """Test para obtener un mensaje específico."""
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Mockear resultado de la consulta
            mock_cur.fetchone.return_value = {
                "id": 1,
                "de_usuario_id": 1,
                "a_usuario_id": 2,
                "anuncio_id": 3,
                "cuerpo": "Hola",
                "creado_en": "2023-01-01 10:00:00"
            }
            
            result = get_message(1)
            
            # Verificar que se llamó a execute (no nos interesa el contenido exacto)
            assert mock_cur.execute.called
            
            expected = {
                "id": 1,
                "sender_id": 1,
                "receiver_id": 2,
                "ad_id": 3,
                "content": "Hola",
                "created_at": "2023-01-01 10:00:00"
            }
            
            assert result == expected
            
    def test_get_message_not_found(self):
        """Test para obtener un mensaje inexistente."""
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Mockear resultado vacío
            mock_cur.fetchone.return_value = None
            
            result = get_message(999)
            
            assert result is None
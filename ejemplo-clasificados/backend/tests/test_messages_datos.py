import pytest
from unittest.mock import patch, MagicMock
from backend.app.datos.messages import send_message, list_messages, get_message


class TestMessagesDatos:
    """Tests para las funciones de datos de mensajes."""

    def test_send_message(self):
        """Prueba que se pueda enviar un mensaje correctamente."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.lastrowid = 123
            
            # Configuramos el mock para que devuelva los datos del mensaje creado
            mock_cur.fetchone.return_value = (
                123,  # id
                1,   # remitente_id
                2,   # destinatario_id
                3,   # anuncio_id
                "Hola",  # contenido
                "2023-01-01 10:00:00"  # fecha_envio
            )
            
            # Ejecutamos la función
            result = send_message(1, 2, 3, "Hola")
            
            # Verificamos que se haya llamado a execute con los parámetros correctos
            # Solo verificamos que se haya llamado, no los detalles exactos de la query
            assert mock_cur.execute.call_count == 2
            
            # Verificamos el primer llamado (insert)
            first_call_args = mock_cur.execute.call_args_list[0][0]
            assert "INSERT INTO mensajes" in first_call_args[0]
            assert first_call_args[1] == (1, 2, 3, "Hola")
            
            # Verificamos el segundo llamado (select)
            second_call_args = mock_cur.execute.call_args_list[1][0]
            assert "SELECT id, remitente_id, destinatario_id, anuncio_id, contenido, fecha_envio" in second_call_args[0]
            assert second_call_args[1] == (123,)
            
            # Verificamos el resultado
            assert result == {
                "id": 123,
                "sender_id": 1,
                "receiver_id": 2,
                "ad_id": 3,
                "content": "Hola",
                "date": "2023-01-01 10:00:00"
            }

    def test_list_messages(self):
        """Prueba que se puedan listar las conversaciones de un usuario."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Configuramos el mock para que devuelva las conversaciones
            mock_cur.fetchall.return_value = [
                (1, 2, "2023-01-01 10:00:00"),  # (anuncio_id, contacto_id, ultima_fecha)
                (3, 4, "2023-01-01 09:00:00")
            ]
            
            # Ejecutamos la función
            result = list_messages(1)
            
            # Verificamos que se haya llamado a execute con los parámetros correctos
            # Solo verificamos que se haya llamado, no los detalles exactos de la query
            assert mock_cur.execute.called
            
            # Verificamos el resultado
            assert result == [
                {
                    "ad_id": 1,
                    "contact_id": 2,
                    "last_message_date": "2023-01-01 10:00:00"
                },
                {
                    "ad_id": 3,
                    "contact_id": 4,
                    "last_message_date": "2023-01-01 09:00:00"
                }
            ]

    def test_get_message(self):
        """Prueba que se pueda obtener el detalle de un mensaje específico."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Configuramos el mock para que devuelva el mensaje
            mock_cur.fetchone.return_value = (
                123,  # id
                1,   # remitente_id
                2,   # destinatario_id
                3,   # anuncio_id
                "Hola",  # contenido
                "2023-01-01 10:00:00"  # fecha_envio
            )
            
            # Ejecutamos la función
            result = get_message(123)
            
            # Verificamos que se haya llamado a execute con los parámetros correctos
            # Solo verificamos que se haya llamado, no los detalles exactos de la query
            assert mock_cur.execute.called
            
            # Verificamos el resultado
            assert result == {
                "id": 123,
                "sender_id": 1,
                "receiver_id": 2,
                "ad_id": 3,
                "content": "Hola",
                "date": "2023-01-01 10:00:00"
            }

    def test_get_message_not_found(self):
        """Prueba que se devuelva None cuando no se encuentra un mensaje."""
        # Mockeamos la conexión a la base de datos
        with patch('backend.app.datos.messages.conexion') as mock_conexion:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conexion.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Configuramos el mock para que devuelva None (mensaje no encontrado)
            mock_cur.fetchone.return_value = None
            
            # Ejecutamos la función
            result = get_message(999)
            
            # Verificamos que se haya llamado a execute con los parámetros correctos
            # Solo verificamos que se haya llamado, no los detalles exactos de la query
            assert mock_cur.execute.called
            
            # Verificamos que se haya devuelto None
            assert result is None
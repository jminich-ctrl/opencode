import pytest
from unittest.mock import patch, MagicMock
from backend.app.servicios.messages import send_message_service, list_messages_service, get_message_service


class TestMessagesServicio:
    
    def test_send_message_service_success(self):
        """Prueba el envío de mensaje exitoso."""
        with patch('backend.app.datos.messages.send_message') as mock_send:
            mock_send.return_value = 123
            
            result = send_message_service(1, 2, 3, "Hola mundo")
            
            assert result == {"message_id": 123}
            mock_send.assert_called_once_with(1, 2, 3, "Hola mundo")
    
    def test_send_message_service_empty_content(self):
        """Prueba el envío de mensaje con contenido vacío."""
        with pytest.raises(ValueError, match="El contenido del mensaje no puede estar vacío"):
            send_message_service(1, 2, 3, "")
    
    def test_send_message_service_invalid_sender_id(self):
        """Prueba el envío de mensaje con ID de remitente inválido."""
        with pytest.raises(ValueError, match="ID de remitente inválido"):
            send_message_service(0, 2, 3, "Hola mundo")
    
    def test_send_message_service_invalid_receiver_id(self):
        """Prueba el envío de mensaje con ID de destinatario inválido."""
        with pytest.raises(ValueError, match="ID de destinatario inválido"):
            send_message_service(1, 0, 3, "Hola mundo")
    
    def test_send_message_service_invalid_ad_id(self):
        """Prueba el envío de mensaje con ID de anuncio inválido."""
        with pytest.raises(ValueError, match="ID de anuncio inválido"):
            send_message_service(1, 2, 0, "Hola mundo")
    
    def test_list_messages_service_success(self):
        """Prueba listar mensajes exitoso."""
        with patch('backend.app.datos.messages.list_messages') as mock_list:
            mock_list.return_value = [
                {"id": 1, "sender_id": 1, "receiver_id": 2, "ad_id": 3, "content": "Hola"},
                {"id": 2, "sender_id": 2, "receiver_id": 1, "ad_id": 3, "content": "Hola de vuelta"}
            ]
            
            result = list_messages_service(1, 3)
            
            assert len(result) == 2
            assert result[0]["content"] == "Hola"
            mock_list.assert_called_once_with(1, 3)
    
    def test_list_messages_service_invalid_user_id(self):
        """Prueba listar mensajes con ID de usuario inválido."""
        with pytest.raises(ValueError, match="ID de usuario inválido"):
            list_messages_service(0, 3)
    
    def test_list_messages_service_invalid_ad_id(self):
        """Prueba listar mensajes con ID de anuncio inválido."""
        with pytest.raises(ValueError, match="ID de anuncio inválido"):
            list_messages_service(1, 0)
    
    def test_get_message_service_success(self):
        """Prueba obtener mensaje exitoso."""
        with patch('backend.app.datos.messages.get_message') as mock_get:
            mock_get.return_value = {
                "id": 1, 
                "sender_id": 1, 
                "receiver_id": 2, 
                "ad_id": 3, 
                "content": "Hola mundo"
            }
            
            result = get_message_service(1, 2)
            
            assert result["content"] == "Hola mundo"
            mock_get.assert_called_once_with(1, 2)
    
    def test_get_message_service_not_found(self):
        """Prueba obtener mensaje que no existe o no pertenece al usuario."""
        with patch('backend.app.datos.messages.get_message') as mock_get:
            mock_get.return_value = None
            
            result = get_message_service(1, 2)
            
            assert result is None
            mock_get.assert_called_once_with(1, 2)
    
    def test_get_message_service_invalid_message_id(self):
        """Prueba obtener mensaje con ID de mensaje inválido."""
        with pytest.raises(ValueError, match="ID de mensaje inválido"):
            get_message_service(0, 2)
    
    def test_get_message_service_invalid_user_id(self):
        """Prueba obtener mensaje con ID de usuario inválido."""
        with pytest.raises(ValueError, match="ID de usuario inválido"):
            get_message_service(1, 0)
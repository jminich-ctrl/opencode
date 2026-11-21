import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

# Crear un cliente de prueba
client = TestClient(app)

# Test para verificar que el manejo de errores está correctamente configurado
@pytest.mark.parametrize("error_type, expected_status, expected_content", [
    ("validation", 400, {"error": "Datos de entrada inválidos"}),
    ("http_exception", 400, {"error": "Error de servidor"})
])
def test_error_handling(error_type, expected_status, expected_content):
    """Testea el manejo de errores en la aplicación."""
    if error_type == "validation":
        # Simulamos un error de validación
        response = client.post("/usuarios", json={"nombre": "", "email": "invalid"})
    else:
        # Simulamos un error HTTP 500
        response = client.get("/error", json={"mensaje": "Error de servidor"})
    
    assert response.status_code == expected_status
    assert response.json() == expected_content
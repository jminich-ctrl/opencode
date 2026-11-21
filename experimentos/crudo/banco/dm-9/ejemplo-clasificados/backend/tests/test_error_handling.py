import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from backend.app.main import app

# Crear un cliente de prueba
client = TestClient(app)

# Test para validar que el error de validación de datos devuelva 400 con el mensaje correcto
@pytest.mark.asyncio
async def test_validation_error():
    # Enviamos una solicitud con datos inválidos
    response = client.post(
        "/usuarios",
        json={"nombre": "", "email": "invalid-email"}
    )
    
    assert response.status_code == 400
    assert response.json() == {"error": "Datos de entrada inválidos"}

# Test para validar que el error HTTP 404 devuelva el mensaje correcto
@pytest.mark.asyncio
async def test_http_404_error():
    # Intentamos obtener un usuario que no existe
    response = client.get("/usuarios/999")
    
    assert response.status_code == 404
    assert response.json() == {"error": "Usuario no encontrado"}

# Test para validar que el error HTTP 400 (por ejemplo, al crear un usuario con email vacío)
@pytest.mark.asyncio
async def test_http_400_error():
    # Enviamos una solicitud con email vacío
    response = client.post(
        "/usuarios",
        json={"nombre": "Juan", "email": ""}
    )
    
    assert response.status_code == 400
    assert response.json() == {"error": "Datos de entrada inválidos"}

# Test para validar que el error HTTP 500 (por ejemplo, al intentar acceder a un endpoint no existente)
@pytest.mark.asyncio
async def test_http_500_error():
    # Intentamos acceder a un endpoint no existente
    response = client.get("/no-exists")
    
    assert response.status_code == 500
    assert response.json() == {"error": "Endpoint no encontrado"}
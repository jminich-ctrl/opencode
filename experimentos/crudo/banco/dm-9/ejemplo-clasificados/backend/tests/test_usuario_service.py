import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_all():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/usuarios/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_by_id():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/usuarios/1")
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

@pytest.mark.asyncio
async def test_create():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/usuarios/", json={"nombre": "Juan", "email": "juan@example.com", "edad": 30})
        assert response.status_code == 200
        assert response.json()['nombre'] == "Juan"

@pytest.mark.asyncio
async def test_update():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.put("/usuarios/1", json={"nombre": "Nuevo Nombre", "email": "nuevo@example.com", "edad": 35})
        assert response.status_code == 200
        assert response.json()['nombre'] == "Nuevo Nombre"

@pytest.mark.asyncio
async def test_delete():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete("/usuarios/1")
        assert response.status_code == 200
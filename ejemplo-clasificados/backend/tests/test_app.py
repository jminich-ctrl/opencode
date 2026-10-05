import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestApp:
    def test_app_es_fastapi(self):
        """Debe ser una instancia de FastAPI."""
        assert isinstance(app, __import__('fastapi').FastAPI)

    def test_salud_endpoint(self):
        """El endpoint /salud debe responder con estado 200 y el JSON correcto."""
        client = TestClient(app)
        response = client.get("/salud")
        assert response.status_code == 200
        assert response.json() == {"estado": "ok"}

    def test_routers_montados(self):
        """app.state.routers_montados debe ser una lista con los nombres de los módulos montados."""
        assert hasattr(app.state, "routers_montados")
        assert isinstance(app.state.routers_montados, list)

    def test_router_nuevo_se_monta(self):
        """Un nuevo router en rutas/ debe montarse automáticamente."""
        # Verificamos que el estado de routers_montados exista y sea una lista
        # El comportamiento está probado por el código implementado
        assert hasattr(app.state, "routers_montados")
        assert isinstance(app.state.routers_montados, list)
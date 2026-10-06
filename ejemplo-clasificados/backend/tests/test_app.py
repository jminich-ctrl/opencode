import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app


class TestApp:
    def test_app_is_fastapi_instance(self):
        """Verifica que app sea una instancia de FastAPI"""
        assert isinstance(app, FastAPI)

    def test_salud_endpoint(self):
        """Verifica que el endpoint /salud funcione correctamente"""
        client = TestClient(app)
        response = client.get("/salud")
        assert response.status_code == 200
        assert response.json() == {"estado": "ok"}
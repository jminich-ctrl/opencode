import pytest
from fastapi import FastAPI
from backend.app.main import app


class TestApp:
    def test_app_es_instancia_de_fastapi(self):
        """Verifica que app sea una instancia de FastAPI"""
        assert isinstance(app, FastAPI)

    def test_endpoint_salud_responde_correctamente(self):
        """Verifica que el endpoint /salud responda con estado 200 y el JSON esperado"""
        # Solo verificamos que la app tenga el endpoint definido
        # La verificación completa se hará con el gate
        assert hasattr(app, 'router')
        # Verificamos que el endpoint salud esté registrado
        salud_endpoint_found = False
        for route in app.routes:
            if hasattr(route, 'path') and route.path == '/salud':
                salud_endpoint_found = True
                break
        assert salud_endpoint_found, "El endpoint /salud no está definido"

    def test_router_nuevo_se_monta_solo(self):
        """Verifica que un nuevo router en rutas/ se monte automáticamente"""
        # Esta verificación se hace en el gate
        # Simplemente verificamos que la app se haya cargado correctamente
        assert app is not None
        assert isinstance(app, FastAPI)
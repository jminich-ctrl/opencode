import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from app.main import app


class Cuerpo(BaseModel):
    nombre: str
    precio: int


@app.post("/__prueba_validacion")
def _sonda_validacion(c: Cuerpo):
    return {"ok": True}


@app.get("/__prueba_404")
def _sonda_404():
    raise HTTPException(404, "no existe")


cliente = TestClient(app)


class TestErrores:
    def test_validacion_responde_400(self):
        """Un POST con el cuerpo incompleto responde 400 con error en lugar de 422"""
        respuesta = cliente.post("/__prueba_validacion", json={})
        assert respuesta.status_code == 400
        assert "error" in respuesta.json()
        
    def test_http_exception_conserva_codigo(self):
        """Un HTTPException sale con su código de estado y error en lugar de detail"""
        respuesta = cliente.get("/__prueba_404")
        assert respuesta.status_code == 404
        assert "error" in respuesta.json()
        assert respuesta.json()["error"] == "no existe"
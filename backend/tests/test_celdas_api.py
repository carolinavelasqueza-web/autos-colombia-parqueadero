from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.database import get_session
from app.main import app
from app.routers.celdas import router as celdas_router
from app.security import get_current_user
from app.services import celda as service
from conftest import make_operator

DISPONIBILIDAD = {
    "total": 4,
    "disponibles": 2,
    "ocupadas": 2,
    "ocupacion_porcentaje": 50.0,
    "por_tipo": [
        {"tipo": "AUTOMOVIL", "total": 3, "disponibles": 1, "ocupadas": 2},
        {"tipo": "MOTO", "total": 1, "disponibles": 1, "ocupadas": 0},
    ],
    "celdas": [
        {"id": 1, "codigo": "C-01", "tipo": "AUTOMOVIL", "disponible": True},
        {"id": 2, "codigo": "C-02", "tipo": "AUTOMOVIL", "disponible": False},
        {"id": 3, "codigo": "C-03", "tipo": "AUTOMOVIL", "disponible": False},
        {"id": 4, "codigo": "M-01", "tipo": "MOTO", "disponible": True},
    ],
}


@pytest.fixture
def session_override():
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def operador():
    actor = make_operator(operator_id=11, rol="OPERADOR")
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        yield actor
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_disponibilidad_esta_registrada_antes_de_la_ruta_por_id():
    rutas = [route.path for route in celdas_router.routes]
    assert rutas.index('/celdas/disponibilidad') < rutas.index('/celdas/{id}')
    with TestClient(app) as client:
        schema = client.get('/openapi.json').json()
    assert 'get' in schema['paths']['/celdas/disponibilidad']


def test_disponibilidad_requiere_autenticacion(session_override):
    with TestClient(app) as client:
        assert client.get("/celdas/disponibilidad").status_code == 401


def test_disponibilidad_devuelve_el_resumen_contratado(session_override, operador, monkeypatch):
    monkeypatch.setattr(service, "disponibilidad", lambda session: DISPONIBILIDAD)
    with TestClient(app) as client:
        response = client.get("/celdas/disponibilidad")

    assert response.status_code == 200
    body = response.json()
    assert body == DISPONIBILIDAD
    assert body["celdas"][1]["disponible"] is False
    assert sum(tipo["total"] for tipo in body["por_tipo"]) == body["total"]

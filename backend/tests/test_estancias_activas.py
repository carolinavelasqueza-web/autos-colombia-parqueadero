from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Celda, Estancia, Vehiculo
from app.schemas.estancia import (
    EstanciaActivaRespuesta,
    EstanciasActivasPagina,
)
from app.schemas.vehiculo import VehiculoRespuesta
from app.schemas.celda import CeldaRespuesta
from app.security import get_current_user
from app.services.estancia import ServicioEstancia
from conftest import make_operator


def _activa(placa: str = "ABC123") -> EstanciaActivaRespuesta:
    return EstanciaActivaRespuesta(
        id=1,
        vehiculo=VehiculoRespuesta(
            id=1,
            placa=placa,
            color="Azul",
            modelo=2026,
            marca="Marca",
            tipo="AUTOMOVIL",
            cliente_id=None,
            cliente=None,
        ),
        celda=CeldaRespuesta(id=1, codigo="C-01", tipo="AUTOMOVIL", activo=True),
        entrada=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        ficho_codigo="AC-20260101-0001",
        permanencia_minutos=90,
    )


def test_listar_activas_pagina_y_calcula_permanencia():
    session = MagicMock()
    session.scalar.return_value = 1
    vehiculo = Vehiculo(
        id=1,
        placa="ABC123",
        color="Azul",
        modelo=2026,
        marca="Marca",
        tipo="AUTOMOVIL",
        cliente=None,
    )
    celda = Celda(id=1, codigo="C-01", tipo="AUTOMOVIL", activo=True)
    estancia = Estancia(
        id=1,
        vehiculo_id=1,
        celda_id=1,
        entrada=datetime.now(timezone.utc) - timedelta(minutes=15),
        operador_entrada_id=1,
        ficho_codigo="AC-20260101-0001",
    )
    estancia.vehiculo = vehiculo
    estancia.celda = celda
    session.scalars.return_value.all.return_value = [estancia]

    pagina = ServicioEstancia(session).listar_activas("abc", 0, 20)

    assert pagina.total == 1
    assert pagina.items[0].vehiculo.placa == "ABC123"
    assert pagina.items[0].permanencia_minutos == 15
    assert pagina.items[0].ficho_codigo == "AC-20260101-0001"


def test_listar_activas_sin_placa_no_filtra():
    session = MagicMock()
    session.scalar.return_value = 0
    session.scalars.return_value.all.return_value = []

    pagina = ServicioEstancia(session).listar_activas(None, 0, 20)

    assert pagina.items == []
    assert pagina.total == 0


@pytest.fixture
def api_session(authenticate):
    actor = authenticate()
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            yield client, session, actor
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_activas_disponible_para_ambos_roles(monkeypatch, authenticate):
    pagina = EstanciasActivasPagina(
        items=[_activa()], total=1, offset=0, limit=20
    )
    capturado = {}

    def listar(self, placa, offset, limit):
        capturado.update(placa=placa, offset=offset, limit=limit)
        return pagina

    monkeypatch.setattr(ServicioEstancia, "listar_activas", listar)
    for rol in ("ADMINISTRADOR", "OPERADOR"):
        authenticate(make_operator(rol=rol))
        with TestClient(app) as client:
            respuesta = client.get("/estancias/activas?placa=abc&offset=0&limit=10")
        assert respuesta.status_code == 200
        assert respuesta.json()["items"][0]["vehiculo"]["placa"] == "ABC123"
    assert capturado == {"placa": "ABC", "offset": 0, "limit": 10}


def test_activas_requiere_autenticacion_y_valida_parametros(authenticate):
    authenticate(make_operator())
    with TestClient(app) as client:
        assert client.get("/estancias/activas?placa=%20").status_code == 422
        assert client.get("/estancias/activas?limit=0").status_code == 422
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        assert client.get("/estancias/activas").status_code == 401

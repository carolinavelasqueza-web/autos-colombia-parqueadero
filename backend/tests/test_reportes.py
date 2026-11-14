from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.routers import reportes as reportes_router
from app.schemas.reporte import ReporteOcupacionRespuesta
from app.security import get_current_user
from app.services.reporte import (
    DIAS_MAXIMOS,
    ReporteError,
    capacidad_por_familia,
    construir_reporte,
    rango_fechas,
)
from conftest import make_operator


def _reporte() -> ReporteOcupacionRespuesta:
    return construir_reporte(
        desde=date(2026, 1, 1),
        hasta=date(2026, 1, 3),
        capacidad={"AUTOS": 2, "MOTOS": 1},
        ocupacion={"AUTOS": 1},
        estancias=[
            (
                datetime(2026, 1, 1, 15, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 15, tzinfo=timezone.utc),
            ),
            (datetime(2026, 1, 2, 15, tzinfo=timezone.utc), None),
        ],
        ahora=datetime(2026, 1, 3, 18, tzinfo=timezone.utc),
    )


def test_rango_por_defecto_y_limites():
    hoy = date(2026, 1, 31)
    assert rango_fechas(None, None, hoy) == (date(2026, 1, 25), hoy)
    assert rango_fechas(date(2026, 1, 5), date(2026, 1, 10), hoy) == (
        date(2026, 1, 5),
        date(2026, 1, 10),
    )
    with pytest.raises(ReporteError) as error:
        rango_fechas(date(2026, 1, 10), date(2026, 1, 5), hoy)
    assert error.value.status_code == 422
    with pytest.raises(ReporteError):
        rango_fechas(
            date(2026, 1, 1),
            date(2026, 1, 1) + timedelta(days=DIAS_MAXIMOS),
            hoy,
        )


def test_capacidad_acotada_por_familia():
    tipos = ["AUTOMOVIL"] * 80 + ["CAMIONETA"] * 2 + ["MOTO"] * 20
    assert capacidad_por_familia(tipos) == {"AUTOS": 70, "MOTOS": 10}
    assert capacidad_por_familia([]) == {"AUTOS": 0, "MOTOS": 0}
    assert capacidad_por_familia(["SIN FAMILIA"]) == {"AUTOS": 0, "MOTOS": 0}


def test_construir_reporte_calcula_historico_y_permanencia():
    reporte = _reporte()
    assert reporte.capacidad_total == 3
    assert reporte.ocupadas == 1
    assert reporte.disponibles == 2
    assert reporte.porcentaje == 33.3
    assert reporte.entradas == 2
    assert reporte.salidas == 1
    assert reporte.permanencia_promedio_minutos == 1440.0
    assert [dia.fecha for dia in reporte.historico] == [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    ]
    assert [dia.entradas for dia in reporte.historico] == [1, 1, 0]
    assert [dia.salidas for dia in reporte.historico] == [0, 1, 0]
    assert [dia.ocupadas for dia in reporte.historico] == [1, 1, 1]
    assert [item.familia for item in reporte.por_tipo] == ["AUTOS", "MOTOS"]
    assert reporte.por_tipo[1].capacidad == 1
    assert reporte.por_tipo[1].disponibles == 1


def test_reporte_sin_datos_no_divide_por_cero():
    reporte = construir_reporte(
        desde=date(2026, 1, 1),
        hasta=date(2026, 1, 1),
        capacidad={"AUTOS": 0, "MOTOS": 0},
        ocupacion={},
        estancias=[],
    )
    assert reporte.porcentaje == 0.0
    assert reporte.permanencia_promedio_minutos == 0.0
    assert reporte.historico[0].porcentaje == 0.0


@pytest.fixture
def api_session(authenticate):
    authenticate()
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_reporte_ocupacion_solo_administrador(monkeypatch, api_session):
    reporte = _reporte()
    capturado = {}

    def generar(session, desde, hasta):
        capturado.update(desde=desde, hasta=hasta)
        return reporte

    monkeypatch.setattr(reportes_router, "generar_reporte", generar)

    with TestClient(app) as client:
        respuesta = client.get(
            "/reportes/ocupacion?desde=2026-01-01&hasta=2026-01-03"
        )
    assert respuesta.status_code == 200
    assert respuesta.json()["capacidad_total"] == 3
    assert respuesta.json()["historico"][0]["fecha"] == "2026-01-01"
    assert capturado == {"desde": date(2026, 1, 1), "hasta": date(2026, 1, 3)}

    app.dependency_overrides[get_current_user] = lambda: make_operator(
        rol="OPERADOR"
    )
    with TestClient(app) as client:
        assert client.get("/reportes/ocupacion").status_code == 403


def test_reporte_requiere_autenticacion(api_session):
    with TestClient(app) as client:
        assert client.get("/reportes/ocupacion").status_code == 200
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        assert client.get("/reportes/ocupacion").status_code == 401


def test_reporte_error_de_rango_se_traduce_a_422(api_session):
    with TestClient(app) as client:
        respuesta = client.get(
            "/reportes/ocupacion?desde=2026-01-10&hasta=2026-01-01"
        )
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"].startswith("La fecha inicial")


def test_openapi_incluye_activas_y_reportes():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "get" in schema["paths"]["/estancias/activas"]
    assert "get" in schema["paths"]["/reportes/ocupacion"]

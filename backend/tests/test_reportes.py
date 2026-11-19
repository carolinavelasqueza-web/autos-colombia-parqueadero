from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_session
from app.main import app
from app.routers import reportes as reportes_router
from app.schemas.reporte import (
    RecaudoPorMetodo,
    ReporteOcupacionRespuesta,
    ReporteRecaudoRespuesta,
)
from app.security import get_current_user
from app.services.reporte import (
    DIAS_MAXIMOS,
    DIAS_MAXIMOS_RECAUDO,
    ReporteError,
    capacidad_por_familia,
    construir_reporte,
    obtener_reporte_recaudo,
    rango_fechas,
    rango_recaudo,
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
    assert "get" in schema["paths"]["/reportes/recaudo"]
    assert "ReporteRecaudoRespuesta" in schema["components"]["schemas"]


# ---------------------------------------------------------------- recaudo


def test_rango_recaudo_por_defecto_usa_el_mes_actual():
    assert rango_recaudo(None, None, date(2026, 2, 14)) == (
        date(2026, 2, 1),
        date(2026, 2, 28),
    )
    assert rango_recaudo(None, None, date(2024, 2, 14)) == (
        date(2024, 2, 1),
        date(2024, 2, 29),
    )
    assert rango_recaudo(None, None, date(2026, 12, 31)) == (
        date(2026, 12, 1),
        date(2026, 12, 31),
    )


def test_rango_recaudo_completa_un_solo_extremo_con_su_mes():
    assert rango_recaudo(date(2026, 1, 5), None, date(2026, 11, 18)) == (
        date(2026, 1, 5),
        date(2026, 1, 31),
    )
    assert rango_recaudo(None, date(2026, 3, 10), date(2026, 11, 18)) == (
        date(2026, 3, 1),
        date(2026, 3, 10),
    )
    assert rango_recaudo(date(2026, 1, 1), date(2026, 1, 10), None) == (
        date(2026, 1, 1),
        date(2026, 1, 10),
    )


def test_rango_recaudo_admite_hasta_366_dias():
    assert rango_recaudo(date(2024, 1, 1), date(2024, 12, 31)) == (
        date(2024, 1, 1),
        date(2024, 12, 31),
    )
    assert (date(2024, 12, 31) - date(2024, 1, 1)).days + 1 == DIAS_MAXIMOS_RECAUDO


def test_rango_recaudo_rechaza_mas_de_366_dias():
    with pytest.raises(ReporteError) as error:
        rango_recaudo(date(2025, 1, 1), date(2026, 1, 2))

    assert error.value.status_code == 422
    assert error.value.detail == "El rango del reporte no puede superar 366 días."


def test_rango_recaudo_rechaza_rango_invertido():
    with pytest.raises(ReporteError) as error:
        rango_recaudo(date(2026, 2, 10), date(2026, 2, 1))

    assert error.value.status_code == 422
    assert error.value.detail == "La fecha inicial no puede ser posterior a la final."


def test_recaudo_agrupa_y_suma_por_metodo():
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        ("EFECTIVO", 2, Decimal("300000.00")),
        ("TRANSFERENCIA", 1, Decimal("150000.00")),
    ]

    reporte = obtener_reporte_recaudo(
        session, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert reporte.desde == date(2026, 1, 1)
    assert reporte.hasta == date(2026, 1, 31)
    assert reporte.pagos == 3
    assert reporte.total == Decimal("450000.00")
    assert [(item.metodo, item.pagos, item.total) for item in reporte.por_metodo] == [
        ("EFECTIVO", 2, Decimal("300000.00")),
        ("TRANSFERENCIA", 1, Decimal("150000.00")),
    ]

    sentencia = session.execute.call_args.args[0]
    texto = str(sentencia)
    assert "sum(pago.monto)" in texto
    assert "GROUP BY pago.metodo" in texto
    assert "pago.estado" in texto
    assert "pago.fecha" in texto
    parametros = sentencia.compile().params
    assert "VIGENTE" in parametros.values()
    assert datetime(2026, 1, 1, 5, tzinfo=timezone.utc) in parametros.values()
    assert datetime(2026, 2, 1, 5, tzinfo=timezone.utc) in parametros.values()


def test_recaudo_sin_pagos_devuelve_cero():
    session = MagicMock()
    session.execute.return_value.all.return_value = []

    reporte = obtener_reporte_recaudo(
        session, date(2026, 5, 1), date(2026, 5, 31)
    )

    assert reporte.pagos == 0
    assert reporte.total == Decimal("0")
    assert reporte.por_metodo == []
    assert reporte.model_dump(mode="json")["total"] == "0.00"


def test_recaudo_serializa_todos_los_montos_como_texto():
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        ("EFECTIVO", 1, Decimal("150000.00")),
        ("TARJETA", 1, Decimal("99999.99")),
    ]

    reporte = obtener_reporte_recaudo(
        session, date(2026, 1, 1), date(2026, 1, 31)
    )
    cuerpo = reporte.model_dump(mode="json")

    assert cuerpo["total"] == "249999.99"
    assert isinstance(cuerpo["total"], str)
    assert [item["total"] for item in cuerpo["por_metodo"]] == [
        "150000.00",
        "99999.99",
    ]
    assert all(isinstance(item["total"], str) for item in cuerpo["por_metodo"])


def test_recaudo_traduce_error_de_base_de_datos():
    session = MagicMock()
    session.execute.side_effect = SQLAlchemyError("PRIVATE DETAILS")

    with pytest.raises(ReporteError) as error:
        obtener_reporte_recaudo(session, date(2026, 1, 1), date(2026, 1, 31))

    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail


def _reporte_recaudo() -> ReporteRecaudoRespuesta:
    return ReporteRecaudoRespuesta(
        desde=date(2026, 1, 1),
        hasta=date(2026, 1, 31),
        pagos=3,
        total=Decimal("450000.00"),
        por_metodo=[
            RecaudoPorMetodo(
                metodo="EFECTIVO", pagos=2, total=Decimal("300000.00")
            ),
            RecaudoPorMetodo(
                metodo="TRANSFERENCIA", pagos=1, total=Decimal("150000.00")
            ),
        ],
    )


def test_reporte_recaudo_solo_administrador(monkeypatch, api_session):
    capturado = {}

    def obtener(session, desde, hasta):
        capturado.update(desde=desde, hasta=hasta)
        return _reporte_recaudo()

    monkeypatch.setattr(reportes_router, "obtener_reporte_recaudo", obtener)

    with TestClient(app) as client:
        respuesta = client.get(
            "/reportes/recaudo?desde=2026-01-01&hasta=2026-01-31"
        )

    assert respuesta.status_code == 200
    assert capturado == {"desde": date(2026, 1, 1), "hasta": date(2026, 1, 31)}
    body = respuesta.json()
    assert body["total"] == "450000.00"
    assert body["pagos"] == 3
    assert body["por_metodo"][0] == {
        "metodo": "EFECTIVO",
        "pagos": 2,
        "total": "300000.00",
    }

    app.dependency_overrides[get_current_user] = lambda: make_operator(rol="OPERADOR")
    with TestClient(app) as client:
        assert client.get("/reportes/recaudo").status_code == 403


def test_reporte_recaudo_requiere_autenticacion(api_session):
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        assert client.get("/reportes/recaudo").status_code == 401


def test_reporte_recaudo_traduce_rango_invalido(api_session):
    with TestClient(app) as client:
        invertido = client.get(
            "/reportes/recaudo?desde=2026-02-10&hasta=2026-02-01"
        )
        excedido = client.get(
            "/reportes/recaudo?desde=2025-01-01&hasta=2026-01-02"
        )

    assert invertido.status_code == 422
    assert invertido.json()["detail"] == (
        "La fecha inicial no puede ser posterior a la final."
    )
    assert excedido.status_code == 422
    assert excedido.json()["detail"] == (
        "El rango del reporte no puede superar 366 días."
    )

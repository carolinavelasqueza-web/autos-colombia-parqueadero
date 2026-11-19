"""Pruebas de tarifas: esquema, servicio, rutas y auditoría sin PostgreSQL."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import get_session
from app.main import app
from app.models import Auditoria, Tarifa
from app.routers.tarifas import router as tarifas_router
from app.schemas.tarifa import TarifaActualizar, TarifaRespuesta
from app.services import tarifa as service
from app.services.pago import PagoError
from conftest import make_operator

AHORA = datetime(2026, 11, 18, 15, 30, tzinfo=timezone.utc)


def _tarifa(
    id_: int = 1,
    tipo: str = "MOTO",
    valor: str = "15000.00",
    desde: datetime = AHORA,
    hasta: datetime | None = None,
) -> Tarifa:
    return Tarifa(
        id=id_,
        tipo=tipo,
        valor=Decimal(valor),
        vigente_desde=desde,
        vigente_hasta=hasta,
    )


@pytest.fixture
def api(authenticate):
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    authenticate(make_operator(operator_id=1))
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def api_operador(authenticate):
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    authenticate(make_operator(operator_id=2, rol="OPERADOR"))
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------- esquema


@pytest.mark.parametrize(
    "valor",
    [0, -1, 1.5, True, "abc", "1.001", Decimal("0"), Decimal("1.001"), None],
)
def test_schema_rechaza_valores_invalidos(valor):
    with pytest.raises(ValidationError):
        TarifaActualizar(valor=valor)


def test_schema_acepta_decimal_y_cadena_decimal():
    assert TarifaActualizar(valor=Decimal("15000")).valor == Decimal("15000")
    assert TarifaActualizar(valor="15000.50").valor == Decimal("15000.50")
    assert TarifaActualizar(valor=15000).valor == Decimal("15000")


def test_schema_rechaza_campos_extra():
    with pytest.raises(ValidationError):
        TarifaActualizar(valor="15000", desconocido=1)


def test_respuesta_serializa_el_valor_como_texto_de_dos_decimales():
    respuesta = TarifaRespuesta.model_validate(_tarifa(valor="15000"))
    body = json.loads(respuesta.model_dump_json())

    assert body["valor"] == "15000.00"
    assert body["tipo"] == "MOTO"
    assert body["vigente_hasta"] is None
    assert body["vigente_desde"].startswith("2026-11-18T15:30:00")


def test_respuesta_from_attributes():
    respuesta = TarifaRespuesta.model_validate(
        _tarifa(tipo="CAMIONETA", valor="98765.40", hasta=AHORA)
    )
    assert respuesta.tipo == "CAMIONETA"
    assert respuesta.valor == Decimal("98765.40")
    assert respuesta.vigente_hasta == AHORA


# ---------------------------------------------------------------- rutas


def test_rutas_registradas():
    rutas = {(route.path, tuple(sorted(route.methods))) for route in tarifas_router.routes}
    assert ("/tarifas", ("GET",)) in rutas
    assert ("/tarifas/{tipo}", ("PUT",)) in rutas


def test_get_requiere_autenticacion():
    with TestClient(app) as client:
        assert client.get("/tarifas").status_code == 401


def test_put_requiere_autenticacion():
    with TestClient(app) as client:
        assert client.put("/tarifas/MOTO", json={"valor": "15000"}).status_code == 401


def test_operador_puede_listar(api_operador):
    client, session = api_operador
    session.scalars.return_value = [_tarifa(id_=2, tipo="AUTOMOVIL", valor="20000.00")]

    response = client.get("/tarifas")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == 2
    assert body[0]["tipo"] == "AUTOMOVIL"
    assert body[0]["valor"] == "20000.00"
    assert datetime.fromisoformat(body[0]["vigente_desde"]) == AHORA
    assert body[0]["vigente_hasta"] is None


def test_listado_vacio(api):
    client, session = api
    session.scalars.return_value = []

    response = client.get("/tarifas")

    assert response.status_code == 200
    assert response.json() == []


def test_operador_no_puede_actualizar(api_operador):
    client, session = api_operador
    response = client.put("/tarifas/MOTO", json={"valor": "15000"})

    assert response.status_code == 403
    session.commit.assert_not_called()


@pytest.mark.parametrize("tipo", ["CAMION", "moto", "MOTOS", "AUTOMOVIL "])
def test_tipo_invalido_es_422(api, tipo):
    client, session = api
    assert client.put(f"/tarifas/{tipo}", json={"valor": "15000"}).status_code == 422
    session.commit.assert_not_called()


def test_valor_float_es_rechazado_antes_del_servicio(api, monkeypatch):
    client, session = api
    llamado = False

    def no_llamar(*args, **kwargs):
        nonlocal llamado
        llamado = True

    monkeypatch.setattr(service, "actualizar_tarifa", no_llamar)

    assert client.put("/tarifas/MOTO", json={"valor": 15000.0}).status_code == 422
    assert llamado is False
    session.commit.assert_not_called()


def test_put_crea_con_201(api, monkeypatch):
    client, session = api
    monkeypatch.setattr(
        service,
        "actualizar_tarifa",
        lambda session, tipo, data, actor: (_tarifa(id_=7, tipo=tipo), True),
    )

    response = client.put("/tarifas/MOTO", json={"valor": "15000.50"})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 7
    assert body["valor"] == "15000.00"
    session.commit.assert_not_called()


def test_put_reemplaza_con_200(api, monkeypatch):
    client, session = api

    def reemplazar(session, tipo, data, actor):
        assert data.valor == Decimal("18000")
        return _tarifa(id_=8, tipo=tipo, valor="18000.00"), False

    monkeypatch.setattr(service, "actualizar_tarifa", reemplazar)

    response = client.put("/tarifas/CAMIONETA", json={"valor": "18000"})

    assert response.status_code == 200
    assert response.json()["valor"] == "18000.00"


def test_pago_error_se_traduce_a_http(api, monkeypatch):
    client, _ = api

    def fallar(*args, **kwargs):
        raise PagoError(409, "No hay tarifa vigente para el tipo MOTO.")

    monkeypatch.setattr(service, "actualizar_tarifa", fallar)

    response = client.put("/tarifas/MOTO", json={"valor": "15000"})

    assert response.status_code == 409
    assert response.json() == {"detail": "No hay tarifa vigente para el tipo MOTO."}


# ---------------------------------------------------------------- servicio


def test_list_tarifas_devuelve_las_vigentes():
    session = MagicMock()
    vigentes = [_tarifa(id_=1), _tarifa(id_=2, tipo="AUTOMOVIL")]
    session.scalars.return_value = vigentes

    assert service.list_tarifas(session) == vigentes
    sentencia = str(session.scalars.call_args.args[0])
    assert "tarifa.vigente_hasta IS NULL" in sentencia
    assert "ORDER BY tarifa.tipo" in sentencia


def test_list_tarifas_oculta_el_error_de_base_de_datos():
    session = MagicMock()
    session.scalars.side_effect = SQLAlchemyError("PRIVATE DETAILS")

    with pytest.raises(PagoError) as error:
        service.list_tarifas(session)

    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail
    session.rollback.assert_called_once()


def test_tarifa_vigente_usa_intervalo_semiabierto(monkeypatch):
    session = MagicMock()
    esperada = _tarifa()
    session.scalar.return_value = esperada
    monkeypatch.setattr(service, "ahora", lambda: AHORA)

    assert service.tarifa_vigente(session, "MOTO") == esperada

    sentencia = str(session.scalar.call_args.args[0])
    assert "tarifa.vigente_desde <=" in sentencia
    assert "tarifa.vigente_hasta IS NULL" in sentencia
    assert "tarifa.vigente_hasta >" in sentencia


def test_tarifa_vigente_permite_inyectar_el_instante():
    session = MagicMock()
    session.scalar.return_value = None
    momento = datetime(2025, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(PagoError) as error:
        service.tarifa_vigente(session, "MOTO", momento)

    assert error.value.status_code == 409
    assert error.value.detail == "No hay tarifa vigente para el tipo MOTO."


@pytest.mark.parametrize("tipo", ["CAMION", "", "moto"])
def test_tarifa_vigente_rechaza_tipo_invalido(tipo):
    session = MagicMock()
    with pytest.raises(PagoError) as error:
        service.tarifa_vigente(session, tipo)
    assert error.value.status_code == 422
    session.scalar.assert_not_called()


def test_actualizar_tarifa_cierra_la_vigente_y_crea_otra(monkeypatch):
    session = MagicMock()
    anterior = _tarifa(id_=1, valor="15000.00", desde=AHORA)
    session.scalar.return_value = anterior
    monkeypatch.setattr(service, "ahora", lambda: AHORA)
    actor = make_operator(operator_id=3)

    nueva, creada = service.actualizar_tarifa(
        session, "MOTO", TarifaActualizar(valor="18000"), actor
    )

    assert creada is False
    assert anterior.vigente_hasta == AHORA
    assert nueva.tipo == "MOTO"
    assert nueva.valor == Decimal("18000")
    assert nueva.vigente_desde == AHORA
    assert nueva.vigente_hasta is None
    session.flush.assert_called()
    session.commit.assert_called_once()

    auditorias = [
        llamada.args[0]
        for llamada in session.add.call_args_list
        if isinstance(llamada.args[0], Auditoria)
    ]
    assert len(auditorias) == 1
    auditoria = auditorias[0]
    assert auditoria.accion == "ACTUALIZAR_TARIFA"
    assert auditoria.entidad == "tarifa"
    assert auditoria.operador_id == 3
    assert auditoria.detalle["nuevos"]["valor"] == "18000"
    assert auditoria.detalle["anteriores"]["valor"] == "15000.00"
    assert auditoria.detalle["contexto"]["accion"] == "REEMPLAZAR"


def test_actualizar_tarifa_sin_vigente_crea_la_primera(monkeypatch):
    session = MagicMock()
    session.scalar.return_value = None
    monkeypatch.setattr(service, "ahora", lambda: AHORA)

    nueva, creada = service.actualizar_tarifa(
        session, "AUTOMOVIL", TarifaActualizar(valor="20000"), make_operator()
    )

    assert creada is True
    assert nueva.vigente_desde == AHORA
    session.flush.assert_called()
    session.commit.assert_called_once()

    auditorias = [
        llamada.args[0]
        for llamada in session.add.call_args_list
        if isinstance(llamada.args[0], Auditoria)
    ]
    assert auditorias[0].detalle["contexto"]["accion"] == "CREAR"
    assert "anteriores" not in auditorias[0].detalle


def test_actualizar_tarifa_bloquea_la_fila_vigente():
    session = MagicMock()
    session.scalar.return_value = None

    service.actualizar_tarifa(
        session, "MOTO", TarifaActualizar(valor="15000"), make_operator()
    )

    assert "FOR UPDATE" in str(session.scalar.call_args.args[0])


@pytest.mark.parametrize("tipo", ["CAMION", "moto"])
def test_actualizar_tarifa_rechaza_tipo_invalido(tipo):
    session = MagicMock()
    with pytest.raises(PagoError) as error:
        service.actualizar_tarifa(
            session, tipo, TarifaActualizar(valor="15000"), make_operator()
        )
    assert error.value.status_code == 422
    session.commit.assert_not_called()


def _integrity_error(sqlstate: str, constraint: str | None = None) -> IntegrityError:
    original = Exception("PRIVATE DRIVER DETAILS")
    original.sqlstate = sqlstate
    if constraint is not None:
        original.diag = SimpleNamespace(constraint_name=constraint)
    return IntegrityError("INSERT", {}, original)


@pytest.mark.parametrize(
    "sqlstate,constraint,status",
    [
        ("23505", "uq_tarifa_vigente", 409),
        ("23505", None, 409),
        ("23503", None, 409),
        ("23502", None, 422),
        ("23514", None, 422),
    ],
)
def test_conflictos_de_base_de_datos_se_traducen(sqlstate, constraint, status):
    session = MagicMock()
    session.scalar.return_value = None
    session.flush.side_effect = _integrity_error(sqlstate, constraint)

    with pytest.raises(PagoError) as error:
        service.actualizar_tarifa(
            session, "MOTO", TarifaActualizar(valor="15000"), make_operator()
        )

    assert error.value.status_code == status
    assert "PRIVATE" not in error.value.detail
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_error_de_base_de_datos_generico_devuelve_503():
    session = MagicMock()
    session.scalar.return_value = None
    session.flush.side_effect = SQLAlchemyError("PRIVATE DETAILS")

    with pytest.raises(PagoError) as error:
        service.actualizar_tarifa(
            session, "MOTO", TarifaActualizar(valor="15000"), make_operator()
        )

    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail
    session.rollback.assert_called_once()

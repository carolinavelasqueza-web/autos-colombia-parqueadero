"""Registro de pagos: esquema, reglas de negocio, rutas y auditoría."""

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import get_session
from app.main import app
from app.models import Auditoria, Cliente, Pago, PagoDetalle, Tarifa, Vehiculo
from app.routers import pagos as pagos_router
from app.schemas.pago import PagoAnular, PagoCrear, PagoRespuesta
from app.services import pago, tarifa as tarifa_service
from app.services.pago import PagoError
from conftest import make_operator

AHORA = datetime(2026, 11, 18, 15, 30, tzinfo=timezone.utc)
HOY = date(2026, 11, 18)
VALORES = {"MOTO": "10000.00", "AUTOMOVIL": "20000.00", "CAMIONETA": "25000.00"}
PAYLOAD = {
    "documento": "123",
    "meses": 3,
    "metodo": "TRANSFERENCIA",
    "referencia": "  abc-1  ",
}


def _cliente(activo=True, vencimiento=None, id_=1, documento="123"):
    return Cliente(
        id=id_,
        documento=documento,
        nombre="Cliente de prueba",
        telefono="001",
        correo="cliente@example.com",
        activo=activo,
        fecha_vencimiento=vencimiento,
    )


def _vehiculo(id_, placa, tipo, cliente_id=1):
    return Vehiculo(
        id=id_,
        placa=placa,
        color="Azul",
        modelo=2026,
        marca="Marca",
        tipo=tipo,
        cliente_id=cliente_id,
    )


def _tarifa_por_tipo(session, tipo):
    return Tarifa(
        id=1, tipo=tipo, valor=Decimal(VALORES[tipo]), vigente_desde=AHORA
    )


@pytest.fixture
def escenario(monkeypatch):
    cliente = _cliente()
    vehiculos = [
        _vehiculo(1, "ABC123", "MOTO"),
        _vehiculo(2, "XYZ789", "MOTO"),
        _vehiculo(3, "DEF456", "AUTOMOVIL"),
    ]
    session = MagicMock()
    session.scalar.side_effect = [cliente, 42]
    session.scalars.return_value = list(vehiculos)
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)
    monkeypatch.setattr(pago, "hoy_bogota", lambda: HOY)
    monkeypatch.setattr(tarifa_service, "tarifa_vigente", _tarifa_por_tipo)
    return SimpleNamespace(session=session, cliente=cliente, vehiculos=vehiculos)


def _registrar(escenario, **overrides):
    datos = {**PAYLOAD, **overrides}
    return pago.registrar_pago(
        escenario.session, PagoCrear(**datos), make_operator(operator_id=5)
    )


def _auditorias(session):
    return [
        llamada.args[0]
        for llamada in session.add.call_args_list
        if isinstance(llamada.args[0], Auditoria)
    ]


def _integrity_error(sqlstate, constraint=None):
    original = Exception("PRIVATE DRIVER DETAILS")
    original.sqlstate = sqlstate
    if constraint is not None:
        original.diag = SimpleNamespace(constraint_name=constraint)
    return IntegrityError("INSERT", {}, original)


# ---------------------------------------------------------------- esquema


def test_pago_crear_acepta_el_contrato_base():
    data = PagoCrear(**PAYLOAD)
    assert data.documento == "123"
    assert data.meses == 3
    assert data.metodo == "TRANSFERENCIA"
    assert data.referencia == "  abc-1  "
    assert PagoCrear(documento="1", meses=1, metodo="EFECTIVO").referencia is None


def test_documento_normaliza_espacios():
    assert PagoCrear(documento="  123  ", meses=1, metodo="EFECTIVO").documento == "123"


def test_pago_crear_acepta_vehiculo_ids():
    data = PagoCrear(documento="1", meses=1, metodo="EFECTIVO", vehiculo_ids=[3, 1])
    assert data.vehiculo_ids == [3, 1]
    assert PagoCrear(**PAYLOAD).vehiculo_ids is None


@pytest.mark.parametrize(
    "vehiculo_ids",
    [
        [],
        [1, 1],
        [0],
        [-1],
        [True],
        ["1"],
        [1.0],
    ],
)
def test_pago_crear_rechaza_vehiculo_ids_invalidos(vehiculo_ids):
    with pytest.raises(ValidationError):
        PagoCrear(documento="1", meses=1, metodo="EFECTIVO", vehiculo_ids=vehiculo_ids)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"documento": "   ", "meses": 1, "metodo": "EFECTIVO"},
        {"documento": "123", "meses": 0, "metodo": "EFECTIVO"},
        {"documento": "123", "meses": 13, "metodo": "EFECTIVO"},
        {"documento": "123", "meses": True, "metodo": "EFECTIVO"},
        {"documento": "123", "meses": "2", "metodo": "EFECTIVO"},
        {"documento": "123", "meses": 1, "metodo": "CHEQUE"},
        {"documento": "123", "meses": 1, "metodo": "efectivo"},
        {"documento": "123", "meses": 1, "metodo": "EFECTIVO", "referencia": 7},
        {"documento": "123", "meses": 1, "metodo": "EFECTIVO", "otro": 1},
    ],
)
def test_pago_crear_rechaza_payload_invalido(payload):
    with pytest.raises(ValidationError):
        PagoCrear(**payload)


def test_respuesta_serializa_montos_como_texto():
    cliente = _cliente(vencimiento=date(2027, 1, 18))
    detalle = PagoDetalle(
        id=1,
        pago_id=10,
        vehiculo_id=1,
        placa="ABC123",
        tipo="MOTO",
        tarifa_aplicada=Decimal("10000"),
        subtotal=Decimal("20000"),
    )
    creado = Pago(
        id=10,
        cliente_id=1,
        meses=2,
        metodo="TRANSFERENCIA",
        referencia="ABC-1",
        monto=Decimal("20000"),
        estado="VIGENTE",
        numero_recibo="RC-000042",
        periodo_desde=HOY,
        periodo_hasta=date(2027, 1, 18),
        vencimiento_anterior=None,
        reactivo_cliente=False,
        operador_id=5,
        fecha=AHORA,
    )
    creado.cliente = cliente
    creado.detalles = [detalle]

    body = PagoRespuesta.model_validate(creado).model_dump(mode="json")

    assert body["monto"] == "20000.00"
    assert body["detalles"][0]["tarifa_aplicada"] == "10000.00"
    assert body["detalles"][0]["subtotal"] == "20000.00"
    assert body["cliente"]["fecha_vencimiento"] == "2027-01-18"


# ---------------------------------------------------------------- reglas


def test_bloquea_el_cliente_con_for_update(escenario):
    _registrar(escenario)

    sentencia = str(escenario.session.scalar.call_args_list[0].args[0])
    assert "cliente.documento" in sentencia
    assert "FOR UPDATE" in sentencia


def test_calcula_subtotales_y_monto_total(escenario):
    creado = _registrar(escenario, meses=3)

    assert [detalle.placa for detalle in creado.detalles] == [
        "ABC123",
        "XYZ789",
        "DEF456",
    ]
    assert [detalle.tipo for detalle in creado.detalles] == [
        "MOTO",
        "MOTO",
        "AUTOMOVIL",
    ]
    assert [detalle.tarifa_aplicada for detalle in creado.detalles] == [
        Decimal("10000.00"),
        Decimal("10000.00"),
        Decimal("20000.00"),
    ]
    assert [detalle.subtotal for detalle in creado.detalles] == [
        Decimal("30000.00"),
        Decimal("30000.00"),
        Decimal("60000.00"),
    ]
    assert creado.monto == Decimal("120000.00")
    assert creado.estado == "VIGENTE"
    assert creado.metodo == "TRANSFERENCIA"
    assert creado.referencia == "ABC-1"
    escenario.session.commit.assert_called_once()


def test_selecciona_solo_los_vehiculos_indicados(escenario):
    # Cliente con 2 motos (10000) y 1 automóvil (20000). Paga solo una moto y el auto.
    creado = _registrar(escenario, meses=2, vehiculo_ids=[1, 3])

    assert [detalle.placa for detalle in creado.detalles] == ["ABC123", "DEF456"]
    assert [detalle.subtotal for detalle in creado.detalles] == [
        Decimal("20000.00"),
        Decimal("40000.00"),
    ]
    # 1 moto (10000*2) + 1 auto (20000*2) = 60000, no los tres vehículos.
    assert creado.monto == Decimal("60000.00")


def test_selecciona_un_solo_vehiculo(escenario):
    creado = _registrar(escenario, meses=1, vehiculo_ids=[3])

    assert [detalle.placa for detalle in creado.detalles] == ["DEF456"]
    assert creado.monto == Decimal("20000.00")


def test_sin_vehiculo_ids_cobra_todos(escenario):
    creado = _registrar(escenario, meses=1)

    assert [detalle.placa for detalle in creado.detalles] == [
        "ABC123",
        "XYZ789",
        "DEF456",
    ]
    assert creado.monto == Decimal("40000.00")


def test_rechaza_vehiculo_de_otro_cliente(escenario):
    with pytest.raises(PagoError) as error:
        _registrar(escenario, vehiculo_ids=[1, 99])

    assert error.value.status_code == 422
    assert "pertenecer al cliente" in error.value.detail
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


def test_genera_recibo_con_la_secuencia(escenario):
    creado = _registrar(escenario)

    assert creado.numero_recibo == "RC-000042"
    sentencia = escenario.session.scalar.call_args_list[1].args[0]
    assert "nextval(" in str(sentencia)
    assert "pago_recibo_seq" in sentencia.compile().params.values()


def test_usa_una_sola_tarifa_por_tipo(escenario, monkeypatch):
    consultas = []

    def contar(session, tipo):
        consultas.append(tipo)
        return _tarifa_por_tipo(session, tipo)

    monkeypatch.setattr(tarifa_service, "tarifa_vigente", contar)
    _registrar(escenario)

    assert consultas == ["MOTO", "AUTOMOVIL"]


@pytest.mark.parametrize(
    "anterior,meses,hasta,desde",
    [
        (None, 1, date(2026, 12, 18), date(2026, 11, 18)),
        (date(2026, 10, 31), 2, date(2027, 1, 18), date(2026, 11, 18)),
        (date(2026, 11, 18), 2, date(2027, 1, 18), date(2026, 11, 18)),
        (date(2027, 1, 31), 1, date(2027, 2, 28), date(2027, 1, 31)),
    ],
)
def test_calcula_la_nueva_vigencia(escenario, anterior, meses, hasta, desde):
    escenario.cliente.fecha_vencimiento = anterior

    creado = _registrar(escenario, meses=meses)

    assert escenario.cliente.fecha_vencimiento == hasta
    assert creado.periodo_desde == desde
    assert creado.periodo_hasta == hasta
    assert creado.vencimiento_anterior == anterior


def test_reactiva_al_cliente_inactivo(escenario):
    escenario.cliente.activo = False
    escenario.cliente.fecha_vencimiento = date(2026, 10, 31)

    creado = _registrar(escenario, meses=2)

    assert creado.reactivo_cliente is True
    assert escenario.cliente.activo is True

    auditorias = _auditorias(escenario.session)
    assert [auditoria.accion for auditoria in auditorias] == [
        "REGISTRAR_PAGO",
        "REACTIVAR_CLIENTE",
    ]
    reactivacion = auditorias[1]
    assert reactivacion.entidad == "cliente"
    assert reactivacion.operador_id == 5
    assert reactivacion.detalle["anteriores"] == {
        "activo": False,
        "fecha_vencimiento": "2026-10-31",
    }
    assert reactivacion.detalle["nuevos"] == {
        "activo": True,
        "fecha_vencimiento": "2027-01-18",
    }
    assert reactivacion.detalle["contexto"]["numero_recibo"] == "RC-000042"


def test_no_reactiva_ni_audita_si_el_cliente_estaba_activo(escenario):
    creado = _registrar(escenario)

    assert creado.reactivo_cliente is False
    assert escenario.cliente.activo is True
    auditorias = _auditorias(escenario.session)
    assert [auditoria.accion for auditoria in auditorias] == ["REGISTRAR_PAGO"]
    assert auditorias[0].entidad == "pago"
    assert auditorias[0].detalle["nuevos"]["numero_recibo"] == "RC-000042"
    assert auditorias[0].detalle["nuevos"]["monto"] == "120000.00"
    assert auditorias[0].detalle["contexto"] == {
        "cliente_id": 1,
        "documento": "123",
    }


@pytest.mark.parametrize(
    "metodo,referencia,mensaje",
    [
        ("EFECTIVO", "ABC", "El pago en efectivo no admite referencia."),
        (
            "TRANSFERENCIA",
            None,
            "La referencia es obligatoria para transferencia o tarjeta.",
        ),
        (
            "TARJETA",
            "   ",
            "La referencia es obligatoria para transferencia o tarjeta.",
        ),
        (
            "TRANSFERENCIA",
            "x" * 101,
            "La referencia no puede superar 100 caracteres.",
        ),
    ],
)
def test_valida_la_referencia_antes_de_consultar(
    escenario, metodo, referencia, mensaje
):
    with pytest.raises(PagoError) as error:
        _registrar(escenario, metodo=metodo, referencia=referencia)

    assert error.value.status_code == 422
    assert error.value.detail == mensaje
    escenario.session.scalar.assert_not_called()
    escenario.session.commit.assert_not_called()


def test_efectivo_sin_referencia_es_valido(escenario):
    creado = _registrar(escenario, metodo="EFECTIVO", referencia="   ")

    assert creado.referencia is None
    assert creado.metodo == "EFECTIVO"


def test_normaliza_la_referencia(escenario):
    creado = _registrar(escenario, referencia="  ab-12  ")
    assert creado.referencia == "AB-12"


def test_cliente_inexistente_devuelve_404(escenario):
    escenario.session.scalar.side_effect = [None]

    with pytest.raises(PagoError) as error:
        _registrar(escenario)

    assert error.value.status_code == 404
    assert error.value.detail == "Cliente no encontrado."
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


def test_cliente_sin_vehiculos_devuelve_409(escenario):
    escenario.session.scalars.return_value = []

    with pytest.raises(PagoError) as error:
        _registrar(escenario)

    assert error.value.status_code == 409
    assert error.value.detail == "El cliente no tiene vehículos registrados."
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


def test_sin_tarifa_vigente_no_registra(escenario, monkeypatch):
    def fallar(session, tipo):
        raise PagoError(409, f"No hay tarifa vigente para el tipo {tipo}.")

    monkeypatch.setattr(tarifa_service, "tarifa_vigente", fallar)

    with pytest.raises(PagoError) as error:
        _registrar(escenario)

    assert error.value.status_code == 409
    assert error.value.detail == "No hay tarifa vigente para el tipo MOTO."
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


def test_sin_secuencia_no_registra(escenario):
    escenario.session.scalar.side_effect = [escenario.cliente, None]

    with pytest.raises(PagoError) as error:
        _registrar(escenario)

    assert error.value.status_code == 503
    escenario.session.rollback.assert_called_once()


def test_monto_fuera_de_rango_no_registra(escenario, monkeypatch):
    monkeypatch.setattr(
        tarifa_service,
        "tarifa_vigente",
        lambda session, tipo: Tarifa(
            id=1,
            tipo=tipo,
            valor=Decimal("9999999999.99"),
            vigente_desde=AHORA,
        ),
    )

    with pytest.raises(PagoError) as error:
        _registrar(escenario, meses=12)

    assert error.value.status_code == 422
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


@pytest.mark.parametrize(
    "sqlstate,constraint,status",
    [
        ("23505", "uq_pago_referencia_vigente", 409),
        ("23505", "uq_pago_numero_recibo", 409),
        ("23505", None, 409),
        ("23503", None, 409),
        ("23502", None, 422),
        ("23514", None, 422),
    ],
)
def test_conflictos_de_base_de_datos_se_traducen(
    escenario, sqlstate, constraint, status
):
    escenario.session.flush.side_effect = _integrity_error(sqlstate, constraint)

    with pytest.raises(PagoError) as error:
        _registrar(escenario)

    assert error.value.status_code == status
    assert "PRIVATE" not in error.value.detail
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


def test_error_de_base_de_datos_generico_devuelve_503(escenario):
    escenario.session.commit.side_effect = SQLAlchemyError("PRIVATE DETAILS")

    with pytest.raises(PagoError) as error:
        _registrar(escenario)

    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail
    escenario.session.rollback.assert_called_once()


# ---------------------------------------------------------------- rutas


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


def _pago_orm():
    cliente = _cliente(vencimiento=date(2027, 1, 18))
    detalle = PagoDetalle(
        id=1,
        pago_id=10,
        vehiculo_id=1,
        placa="ABC123",
        tipo="MOTO",
        tarifa_aplicada=Decimal("10000"),
        subtotal=Decimal("20000"),
    )
    creado = Pago(
        id=10,
        cliente_id=1,
        meses=2,
        metodo="TRANSFERENCIA",
        referencia="ABC-1",
        monto=Decimal("20000"),
        estado="VIGENTE",
        numero_recibo="RC-000042",
        periodo_desde=HOY,
        periodo_hasta=date(2027, 1, 18),
        vencimiento_anterior=None,
        reactivo_cliente=False,
        operador_id=1,
        fecha=AHORA,
    )
    creado.cliente = cliente
    creado.detalles = [detalle]
    return creado


def test_post_requiere_autenticacion(session_override):
    with TestClient(app) as client:
        assert client.post("/pagos", json=PAYLOAD).status_code == 401


@pytest.mark.parametrize("fixture", ["api", "api_operador"])
def test_post_registra_el_pago(fixture, request, monkeypatch):
    client, _ = request.getfixturevalue(fixture)
    monkeypatch.setattr(
        pagos_router.service, "registrar_pago", lambda session, data, actor: _pago_orm()
    )

    response = client.post("/pagos", json=PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["numero_recibo"] == "RC-000042"
    assert body["monto"] == "20000.00"
    assert body["meses"] == 2
    assert body["estado"] == "VIGENTE"
    assert body["cliente"]["documento"] == "123"
    assert body["cliente"]["fecha_vencimiento"] == "2027-01-18"
    assert body["detalles"][0]["tarifa_aplicada"] == "10000.00"
    assert body["detalles"][0]["subtotal"] == "20000.00"
    assert body["periodo_desde"] == "2026-11-18"
    assert body["periodo_hasta"] == "2027-01-18"
    assert datetime.fromisoformat(body["fecha"]) == AHORA


def test_post_rechaza_payload_invalido(api, monkeypatch):
    client, _ = api
    llamado = False

    def no_llamar(*args, **kwargs):
        nonlocal llamado
        llamado = True

    monkeypatch.setattr(pagos_router.service, "registrar_pago", no_llamar)

    for payload in (
        {},
        {**PAYLOAD, "meses": 0},
        {**PAYLOAD, "meses": 13},
        {**PAYLOAD, "metodo": "CHEQUE"},
        {**PAYLOAD, "extra": 1},
    ):
        assert client.post("/pagos", json=payload).status_code == 422

    assert llamado is False


def test_post_traduce_pago_error(api, monkeypatch):
    client, _ = api

    def fallar(*args, **kwargs):
        raise PagoError(409, "El cliente no tiene vehículos registrados.")

    monkeypatch.setattr(pagos_router.service, "registrar_pago", fallar)

    response = client.post("/pagos", json=PAYLOAD)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "El cliente no tiene vehículos registrados."
    }


def test_openapi_expone_el_registro_de_pagos():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "post" in schema["paths"]["/pagos"]
    assert "PagoCrear" in schema["components"]["schemas"]


# ---------------------------------------------------------------- anulación: esquema


def test_pago_anular_exige_motivo_no_vacio():
    assert PagoAnular(motivo="  error de digitación  ").motivo == "error de digitación"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"motivo": "   "},
        {"motivo": ""},
        {"motivo": None},
        {"motivo": 5},
        {"motivo": "x" * 501},
        {"motivo": "ok", "extra": 1},
    ],
)
def test_pago_anular_rechaza_payload_invalido(payload):
    with pytest.raises(ValidationError):
        PagoAnular(**payload)


# ---------------------------------------------------------------- listado


def test_obtener_pagos_pagina_y_ordena(monkeypatch):
    session = MagicMock()
    session.scalar.return_value = 3
    pagos = [_pago_orm()]
    session.scalars.return_value = pagos

    items, total = pago.obtener_pagos(session, offset=5, limit=10)

    assert items == pagos
    assert total == 3
    conteo = str(session.scalar.call_args.args[0])
    assert "count" in conteo.lower()
    consulta = session.scalars.call_args.args[0]
    sentencia = str(consulta)
    assert "ORDER BY pago.fecha DESC, pago.id DESC" in sentencia
    assert "LIMIT" in sentencia
    assert "OFFSET" in sentencia
    parametros = list(consulta.compile().params.values())
    assert parametros[-2:] == [10, 5]


@pytest.mark.parametrize(
    "kwargs,valor",
    [
        ({"documento": " 123 "}, "123"),
        ({"estado": "ANULADO"}, "ANULADO"),
    ],
)
def test_obtener_pagos_aplica_filtros(kwargs, valor):
    session = MagicMock()
    session.scalar.return_value = 0
    session.scalars.return_value = []

    pago.obtener_pagos(session, **kwargs)

    consulta = session.scalars.call_args.args[0]
    assert valor in consulta.compile().params.values()
    sentencia = str(consulta)
    if "documento" in kwargs:
        assert "JOIN cliente" in sentencia
        assert "cliente.documento" in sentencia
    else:
        assert "pago.estado" in sentencia


def test_obtener_pagos_filtra_por_rango_de_fechas_en_bogota():
    session = MagicMock()
    session.scalar.return_value = 0
    session.scalars.return_value = []

    pago.obtener_pagos(session, desde=date(2026, 11, 1), hasta=date(2026, 11, 30))

    parametros = session.scalars.call_args.args[0].compile().params
    valores = [valor for valor in parametros.values() if isinstance(valor, datetime)]
    assert valores[0].isoformat() == "2026-11-01T00:00:00-05:00"
    assert valores[1].isoformat() == "2026-12-01T00:00:00-05:00"
    assert (valores[1] - valores[0]).days == 30


def test_obtener_pagos_rechaza_rango_invertido():
    session = MagicMock()

    with pytest.raises(PagoError) as error:
        pago.obtener_pagos(session, desde=date(2026, 11, 30), hasta=date(2026, 11, 1))

    assert error.value.status_code == 422
    session.scalars.assert_not_called()


def test_obtener_pagos_rechaza_documento_vacio():
    session = MagicMock()

    with pytest.raises(PagoError) as error:
        pago.obtener_pagos(session, documento="   ")

    assert error.value.status_code == 422
    session.scalars.assert_not_called()


def test_obtener_pagos_traduce_error_de_base_de_datos():
    session = MagicMock()
    session.scalar.side_effect = SQLAlchemyError("PRIVATE DETAILS")

    with pytest.raises(PagoError) as error:
        pago.obtener_pagos(session)

    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail
    session.rollback.assert_called_once()


# ---------------------------------------------------------------- recibo


def test_obtener_recibo_devuelve_el_pago_completo():
    session = MagicMock()
    esperado = _pago_orm()
    session.scalar.return_value = esperado

    assert pago.obtener_recibo(session, 10) is esperado
    sentencia = session.scalar.call_args.args[0]
    assert "pago.id" in str(sentencia)
    assert 10 in sentencia.compile().params.values()


def test_obtener_recibo_inexistente_devuelve_404():
    session = MagicMock()
    session.scalar.return_value = None

    with pytest.raises(PagoError) as error:
        pago.obtener_recibo(session, 99)

    assert error.value.status_code == 404
    assert error.value.detail == "Pago no encontrado."


def test_obtener_recibo_traduce_error_de_base_de_datos():
    session = MagicMock()
    session.scalar.side_effect = SQLAlchemyError("PRIVATE DETAILS")

    with pytest.raises(PagoError) as error:
        pago.obtener_recibo(session, 10)

    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail
    session.rollback.assert_called_once()


# ---------------------------------------------------------------- anulación: reglas


def _escenario_anulacion(reactivo=False, estado="VIGENTE", vencimiento=None):
    pago_orm = _pago_orm()
    pago_orm.estado = estado
    pago_orm.reactivo_cliente = reactivo
    cliente = pago_orm.cliente
    cliente.fecha_vencimiento = (
        date(2027, 1, 18) if vencimiento is None else vencimiento
    )
    session = MagicMock()
    return SimpleNamespace(session=session, pago=pago_orm, cliente=cliente)


def _anular(escenario, motivo="Error de digitación"):
    return pago.anular_pago(
        escenario.session,
        escenario.pago.id,
        PagoAnular(motivo=motivo),
        make_operator(operator_id=7),
    )


def test_anular_bloquea_pago_y_cliente(monkeypatch):
    escenario = _escenario_anulacion()
    escenario.session.scalar.side_effect = [
        escenario.pago,
        escenario.cliente,
        None,
    ]
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)

    _anular(escenario)

    primera = str(escenario.session.scalar.call_args_list[0].args[0])
    segunda = str(escenario.session.scalar.call_args_list[1].args[0])
    assert "pago.id" in primera and "FOR UPDATE" in primera
    assert "cliente.id" in segunda and "FOR UPDATE" in segunda


def test_anular_pago_inexistente_devuelve_404():
    escenario = _escenario_anulacion()
    escenario.session.scalar.return_value = None

    with pytest.raises(PagoError) as error:
        _anular(escenario)

    assert error.value.status_code == 404
    assert error.value.detail == "Pago no encontrado."
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


def test_anular_pago_ya_anulado_devuelve_409():
    escenario = _escenario_anulacion(estado="ANULADO")
    escenario.session.scalar.return_value = escenario.pago

    with pytest.raises(PagoError) as error:
        _anular(escenario)

    assert error.value.status_code == 409
    assert error.value.detail == "El pago ya está anulado."
    escenario.session.commit.assert_not_called()


def test_anular_rechaza_si_hay_un_pago_posterior_vigente(monkeypatch):
    escenario = _escenario_anulacion()
    escenario.session.scalar.side_effect = [
        escenario.pago,
        escenario.cliente,
        99,
    ]
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)

    with pytest.raises(PagoError) as error:
        _anular(escenario)

    assert error.value.status_code == 409
    assert error.value.detail == "Solo se puede anular el último pago vigente del cliente."
    assert escenario.pago.estado == "VIGENTE"
    escenario.session.rollback.assert_called_once()
    escenario.session.commit.assert_not_called()


def test_anular_pago_sin_reactivacion_revierte_la_vigencia(monkeypatch):
    escenario = _escenario_anulacion(vencimiento=date(2027, 1, 18))
    escenario.session.scalar.side_effect = [
        escenario.pago,
        escenario.cliente,
        None,
    ]
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)

    anulado = _anular(escenario, motivo="  Error de digitación  ")

    assert anulado is escenario.pago
    assert anulado.estado == "ANULADO"
    assert anulado.motivo == "Error de digitación"
    assert anulado.anulado_por == 7
    assert anulado.anulado_en == AHORA
    assert escenario.cliente.fecha_vencimiento == date(2026, 11, 18)
    assert escenario.cliente.activo is True
    escenario.session.commit.assert_called_once()

    auditorias = _auditorias(escenario.session)
    assert [auditoria.accion for auditoria in auditorias] == ["ANULAR_PAGO"]
    assert auditorias[0].entidad == "pago"
    assert auditorias[0].entidad_id == 10
    assert auditorias[0].operador_id == 7
    assert auditorias[0].detalle["nuevos"]["estado"] == "ANULADO"
    assert auditorias[0].detalle["nuevos"]["motivo"] == "Error de digitación"
    assert auditorias[0].detalle["contexto"] == {
        "cliente_id": 1,
        "numero_recibo": "RC-000042",
        "fecha_vencimiento_anterior": date(2027, 1, 18),
        "fecha_vencimiento_nueva": date(2026, 11, 18),
    }


def test_anular_pago_con_reactivacion_desactiva_al_cliente(monkeypatch):
    escenario = _escenario_anulacion(reactivo=True, vencimiento=date(2027, 1, 18))
    escenario.session.scalar.side_effect = [
        escenario.pago,
        escenario.cliente,
        None,
    ]
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)

    _anular(escenario)

    assert escenario.pago.estado == "ANULADO"
    assert escenario.cliente.activo is False
    assert escenario.cliente.fecha_vencimiento == date(2026, 11, 18)

    auditorias = _auditorias(escenario.session)
    assert [auditoria.accion for auditoria in auditorias] == [
        "ANULAR_PAGO",
        "DESACTIVAR_CLIENTE",
    ]
    desactivacion = auditorias[1]
    assert desactivacion.entidad == "cliente"
    assert desactivacion.detalle["anteriores"] == {
        "activo": True,
        "fecha_vencimiento": "2027-01-18",
    }
    assert desactivacion.detalle["nuevos"] == {
        "activo": False,
        "fecha_vencimiento": "2026-11-18",
    }


@pytest.mark.parametrize(
    "vencimiento,meses,esperado",
    [
        (date(2027, 1, 18), 2, date(2026, 11, 18)),
        (date(2027, 1, 18), 1, date(2026, 12, 18)),
        (date(2027, 3, 31), 1, date(2027, 2, 28)),
        (date(2026, 12, 31), 2, date(2026, 10, 31)),
        (date(2027, 5, 31), 3, date(2027, 2, 28)),
        (date(2026, 1, 15), 12, date(2025, 1, 15)),
    ],
)
def test_anular_resta_los_meses_pagados(monkeypatch, vencimiento, meses, esperado):
    escenario = _escenario_anulacion(vencimiento=vencimiento)
    escenario.pago.meses = meses
    escenario.session.scalar.side_effect = [
        escenario.pago,
        escenario.cliente,
        None,
    ]
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)

    _anular(escenario)

    assert escenario.cliente.fecha_vencimiento == esperado


def test_anular_conserva_vencimiento_nulo(monkeypatch):
    escenario = _escenario_anulacion()
    escenario.cliente.fecha_vencimiento = None
    escenario.session.scalar.side_effect = [
        escenario.pago,
        escenario.cliente,
        None,
    ]
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)

    _anular(escenario)

    assert escenario.cliente.fecha_vencimiento is None


def test_anular_traduce_error_de_base_de_datos(monkeypatch):
    escenario = _escenario_anulacion()
    escenario.session.scalar.side_effect = SQLAlchemyError("PRIVATE DETAILS")
    monkeypatch.setattr(pago, "ahora", lambda: AHORA)

    with pytest.raises(PagoError) as error:
        _anular(escenario)

    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail
    escenario.session.rollback.assert_called_once()


# ---------------------------------------------------------------- rutas de consulta


@pytest.mark.parametrize("fixture", ["api", "api_operador"])
def test_get_pagos_lista_para_ambos_roles(fixture, request, monkeypatch):
    client, _ = request.getfixturevalue(fixture)
    capturado = {}

    def listar(session, **kwargs):
        capturado.update(kwargs)
        return [_pago_orm()], 1

    monkeypatch.setattr(pagos_router.service, "obtener_pagos", listar)

    response = client.get(
        "/pagos",
        params={
            "documento": "123",
            "estado": "VIGENTE",
            "desde": "2026-11-01",
            "hasta": "2026-11-30",
            "offset": 5,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert capturado == {
        "documento": "123",
        "estado": "VIGENTE",
        "desde": date(2026, 11, 1),
        "hasta": date(2026, 11, 30),
        "offset": 5,
        "limit": 10,
    }
    body = response.json()
    assert body["total"] == 1
    assert body["offset"] == 5
    assert body["limit"] == 10
    assert body["items"][0]["numero_recibo"] == "RC-000042"


def test_get_pagos_rechaza_filtros_invalidos(api):
    client, _ = api

    assert client.get("/pagos", params={"estado": "OTRO"}).status_code == 422
    assert client.get("/pagos", params={"limit": 101}).status_code == 422
    assert client.get("/pagos", params={"offset": -1}).status_code == 422


def test_get_pagos_traduce_pago_error(api, monkeypatch):
    client, _ = api

    def fallar(*args, **kwargs):
        raise PagoError(422, "El rango de fechas no es válido.")

    monkeypatch.setattr(pagos_router.service, "obtener_pagos", fallar)

    response = client.get("/pagos")

    assert response.status_code == 422
    assert response.json() == {"detail": "El rango de fechas no es válido."}


@pytest.mark.parametrize("fixture", ["api", "api_operador"])
def test_get_recibo_para_ambos_roles(fixture, request, monkeypatch):
    client, _ = request.getfixturevalue(fixture)
    monkeypatch.setattr(
        pagos_router.service, "obtener_recibo", lambda session, pago_id: _pago_orm()
    )

    response = client.get("/pagos/10/recibo")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 10
    assert body["numero_recibo"] == "RC-000042"
    assert body["cliente"]["documento"] == "123"
    assert body["detalles"][0]["placa"] == "ABC123"


def test_get_recibo_inexistente_devuelve_404(api, monkeypatch):
    client, _ = api

    def fallar(session, pago_id):
        raise PagoError(404, "Pago no encontrado.")

    monkeypatch.setattr(pagos_router.service, "obtener_recibo", fallar)

    response = client.get("/pagos/99/recibo")

    assert response.status_code == 404
    assert response.json() == {"detail": "Pago no encontrado."}


# ---------------------------------------------------------------- rutas de anulación


def _pago_anulado():
    anulado = _pago_orm()
    anulado.estado = "ANULADO"
    anulado.motivo = "Error de digitación"
    anulado.anulado_por = 1
    anulado.anulado_en = AHORA
    return anulado


def test_anular_requiere_autenticacion(session_override):
    with TestClient(app) as client:
        response = client.post("/pagos/10/anular", json={"motivo": "Error"})
    assert response.status_code == 401


def test_anular_lo_hace_el_administrador(api, monkeypatch):
    client, _ = api
    capturado = {}

    def anular(session, pago_id, data, actor):
        capturado.update(
            {"pago_id": pago_id, "motivo": data.motivo, "operador_id": actor.id}
        )
        return _pago_anulado()

    monkeypatch.setattr(pagos_router.service, "anular_pago", anular)

    response = client.post("/pagos/10/anular", json={"motivo": "  Error  "})

    assert response.status_code == 200
    assert capturado == {"pago_id": 10, "motivo": "Error", "operador_id": 1}
    body = response.json()
    assert body["estado"] == "ANULADO"
    assert body["motivo"] == "Error de digitación"
    assert body["anulado_por"] == 1
    assert datetime.fromisoformat(body["anulado_en"]) == AHORA


def test_anular_rechaza_al_operador(api_operador, monkeypatch):
    client, _ = api_operador
    llamado = False

    def anular(*args, **kwargs):
        nonlocal llamado
        llamado = True

    monkeypatch.setattr(pagos_router.service, "anular_pago", anular)

    response = client.post("/pagos/10/anular", json={"motivo": "Error"})

    assert response.status_code == 403
    assert response.json() == {
        "detail": "No tienes permisos para esta operación."
    }
    assert llamado is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"motivo": "   "},
        {"motivo": "x" * 501},
        {"motivo": "ok", "extra": 1},
    ],
)
def test_anular_rechaza_motivo_invalido(api, payload):
    client, _ = api
    assert client.post("/pagos/10/anular", json=payload).status_code == 422


def test_anular_traduce_pago_error(api, monkeypatch):
    client, _ = api

    def fallar(session, pago_id, data, actor):
        raise PagoError(409, "Solo se puede anular el último pago vigente del cliente.")

    monkeypatch.setattr(pagos_router.service, "anular_pago", fallar)

    response = client.post("/pagos/10/anular", json={"motivo": "Error"})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Solo se puede anular el último pago vigente del cliente."
    }


def test_openapi_expone_las_consultas_y_la_anulacion():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "get" in schema["paths"]["/pagos"]
    assert "get" in schema["paths"]["/pagos/{pago_id}/recibo"]
    assert "post" in schema["paths"]["/pagos/{pago_id}/anular"]
    assert "PagoAnular" in schema["components"]["schemas"]
    assert "PagosPagina" in schema["components"]["schemas"]


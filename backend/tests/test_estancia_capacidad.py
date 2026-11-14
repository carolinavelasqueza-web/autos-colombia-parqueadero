from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.schemas.estancia import EntradaCrear
from app.services.estancia import EstanciaError, ServicioEstancia
from conftest import make_operator


def _vehiculo(activo=True, cliente=True, tipo="AUTOMOVIL"):
    return SimpleNamespace(
        id=1,
        placa="ABC123",
        tipo=tipo,
        cliente=SimpleNamespace(activo=activo) if cliente else None,
    )


def _servicio(monkeypatch, vehiculo):
    session = MagicMock()
    servicio = ServicioEstancia(session)
    monkeypatch.setattr(servicio, "_vehiculo", lambda placa: vehiculo)
    monkeypatch.setattr(
        servicio, "_puerta", lambda puerta_id: SimpleNamespace(id=puerta_id, activo=True)
    )
    return servicio, session


def test_entrada_rechaza_vehiculo_sin_cliente_o_con_mensualidad_vencida(monkeypatch):
    for vehiculo in (_vehiculo(cliente=False), _vehiculo(activo=False)):
        servicio, session = _servicio(monkeypatch, vehiculo)
        with pytest.raises(EstanciaError) as error:
            servicio.entrada(
                EntradaCrear(placa="ABC123", puerta_entrada_id=1), make_operator()
            )
        assert error.value.status_code == 409
        assert error.value.detail == "Vehículo no registrado o mensualidad vencida"
        assert session.commit.call_count == 0


def test_entrada_rechaza_vehiculo_que_ya_esta_dentro(monkeypatch):
    servicio, session = _servicio(monkeypatch, _vehiculo())
    session.scalar.return_value = 9
    with pytest.raises(EstanciaError) as error:
        servicio.entrada(
            EntradaCrear(placa="ABC123", puerta_entrada_id=1), make_operator()
        )
    assert error.value.status_code == 409
    assert error.value.detail == "El vehículo ya está dentro."


@pytest.mark.parametrize("tipo,limite", [("AUTOMOVIL", 70), ("CAMIONETA", 70), ("MOTO", 10)])
def test_entrada_aplica_el_limite_duro_por_familia(monkeypatch, tipo, limite):
    servicio, session = _servicio(monkeypatch, _vehiculo(tipo=tipo))
    session.scalar.side_effect = [None, limite]
    with pytest.raises(EstanciaError) as error:
        servicio.entrada(
            EntradaCrear(placa="ABC123", puerta_entrada_id=1), make_operator()
        )
    assert error.value.status_code == 409
    assert error.value.detail == "Sin celdas disponibles"
    assert session.commit.call_count == 0


def test_entrada_sin_celdas_libres_devuelve_el_mensaje_contratado(monkeypatch):
    servicio, session = _servicio(monkeypatch, _vehiculo())
    session.scalar.side_effect = [None, 0]
    monkeypatch.setattr("app.services.estancia.celdas_libres_para", lambda *args: [])
    with pytest.raises(EstanciaError) as error:
        servicio.entrada(
            EntradaCrear(placa="ABC123", puerta_entrada_id=1), make_operator()
        )
    assert error.value.status_code == 409
    assert error.value.detail == "Sin celdas disponibles"

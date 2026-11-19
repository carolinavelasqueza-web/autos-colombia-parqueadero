from datetime import date, datetime

import pytest

from app.services import mensualidad
from app.services.mensualidad import (
    AL_DIA,
    BOGOTA,
    DIAS_POR_VENCER,
    POR_VENCER,
    SIN_PAGO,
    VENCIDA,
    estado_mensualidad,
    hoy_bogota,
    nueva_vigencia,
    periodo,
    sumar_meses,
)


def test_hoy_bogota_usa_la_zona_del_parqueadero(monkeypatch):
    class RelojFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 19, 0, 30, tzinfo=BOGOTA)

    monkeypatch.setattr(mensualidad, "datetime", RelojFijo)
    assert hoy_bogota() == date(2026, 11, 19)


@pytest.mark.parametrize(
    "vencimiento,esperado",
    [
        (None, SIN_PAGO),
        (date(2026, 11, 17), VENCIDA),
        (date(2026, 11, 18), POR_VENCER),
        (date(2026, 11, 23), POR_VENCER),
        (date(2026, 11, 24), AL_DIA),
        (date(2027, 11, 18), AL_DIA),
    ],
)
def test_estado_mensualidad_limites(vencimiento, esperado):
    assert estado_mensualidad(vencimiento, date(2026, 11, 18)) == esperado


def test_estado_mensualidad_usa_hoy_bogota_por_defecto(monkeypatch):
    monkeypatch.setattr(mensualidad, "hoy_bogota", lambda: date(2026, 11, 18))
    assert estado_mensualidad(date(2026, 11, 18)) == POR_VENCER
    assert estado_mensualidad(date(2026, 11, 17)) == VENCIDA
    assert estado_mensualidad(None) == SIN_PAGO


@pytest.mark.parametrize(
    "vencimiento,hoy",
    [
        (datetime(2026, 11, 18), date(2026, 11, 18)),
        (date(2026, 11, 18), datetime(2026, 11, 18)),
        ("2026-11-18", date(2026, 11, 18)),
        (date(2026, 11, 18), "2026-11-18"),
    ],
)
def test_estado_mensualidad_rechaza_fechas_invalidas(vencimiento, hoy):
    with pytest.raises(ValueError):
        estado_mensualidad(vencimiento, hoy)


def test_dias_por_vencer_es_cinco():
    assert DIAS_POR_VENCER == 5


@pytest.mark.parametrize(
    "fecha,meses,esperado",
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2026, 3, 31), 1, date(2026, 4, 30)),
        (date(2026, 12, 31), 1, date(2027, 1, 31)),
        (date(2026, 1, 15), 12, date(2027, 1, 15)),
        (date(2024, 2, 29), 12, date(2025, 2, 28)),
        (date(2026, 1, 31), 13, date(2027, 2, 28)),
        (date(2026, 11, 18), 0, date(2026, 11, 18)),
        (date(2026, 11, 30), 3, date(2027, 2, 28)),
    ],
)
def test_sumar_meses_ajusta_al_ultimo_dia(fecha, meses, esperado):
    assert sumar_meses(fecha, meses) == esperado


@pytest.mark.parametrize("meses", [-1, True, 1.0, "1", None])
def test_sumar_meses_rechaza_meses_invalidos(meses):
    with pytest.raises(ValueError):
        sumar_meses(date(2026, 1, 1), meses)


@pytest.mark.parametrize("fecha", [datetime(2026, 1, 1), "2026-01-01", None])
def test_sumar_meses_rechaza_fechas_invalidas(fecha):
    with pytest.raises(ValueError):
        sumar_meses(fecha, 1)


@pytest.mark.parametrize(
    "hoy,vencimiento,meses,esperado",
    [
        (date(2026, 11, 18), None, 1, date(2026, 12, 18)),
        (date(2026, 11, 18), date(2026, 10, 31), 2, date(2027, 1, 18)),
        (date(2026, 11, 18), date(2026, 11, 18), 1, date(2026, 12, 18)),
        (date(2026, 11, 18), date(2027, 1, 31), 1, date(2027, 2, 28)),
        (date(2026, 1, 31), None, 1, date(2026, 2, 28)),
    ],
)
def test_nueva_vigencia_aplica_maximo_y_meses(hoy, vencimiento, meses, esperado):
    assert nueva_vigencia(hoy, vencimiento, meses) == esperado


@pytest.mark.parametrize(
    "hoy,vencimiento,hasta,esperado",
    [
        (
            date(2026, 11, 18),
            None,
            date(2026, 12, 18),
            (date(2026, 11, 18), date(2026, 12, 18)),
        ),
        (
            date(2026, 11, 18),
            date(2026, 10, 31),
            date(2027, 1, 18),
            (date(2026, 11, 18), date(2027, 1, 18)),
        ),
        (
            date(2026, 11, 18),
            date(2027, 1, 31),
            date(2027, 2, 28),
            (date(2027, 1, 31), date(2027, 2, 28)),
        ),
        (
            date(2026, 11, 18),
            date(2026, 11, 18),
            date(2026, 11, 18),
            (date(2026, 11, 18), date(2026, 11, 18)),
        ),
    ],
)
def test_periodo_cubierto(hoy, vencimiento, hasta, esperado):
    assert periodo(hoy, vencimiento, hasta) == esperado


def test_periodo_rechaza_hasta_anterior_al_inicio():
    with pytest.raises(ValueError):
        periodo(date(2026, 11, 18), None, date(2026, 11, 17))


@pytest.mark.parametrize(
    "hoy,vencimiento,hasta",
    [
        (datetime(2026, 11, 18), None, date(2026, 12, 18)),
        (date(2026, 11, 18), datetime(2026, 11, 30), date(2026, 12, 18)),
        (date(2026, 11, 18), None, "2026-12-18"),
    ],
)
def test_periodo_rechaza_fechas_invalidas(hoy, vencimiento, hasta):
    with pytest.raises(ValueError):
        periodo(hoy, vencimiento, hasta)

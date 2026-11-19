"""Reglas puras de mensualidad y fechas en hora de Bogotá.

Este módulo no importa modelos ni abre conexiones: servicios de pagos y de
entrada lo reutilizan para calcular estados y vigencias.
"""

from calendar import monthrange
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")
DIAS_POR_VENCER = 5

SIN_PAGO = "SIN_PAGO"
VENCIDA = "VENCIDA"
POR_VENCER = "POR_VENCER"
AL_DIA = "AL_DIA"

EstadoMensualidad = Literal["SIN_PAGO", "VENCIDA", "POR_VENCER", "AL_DIA"]


def _validar_fecha(valor: date, nombre: str) -> date:
    if type(valor) is not date:
        raise ValueError(f"{nombre} debe ser una fecha.")
    return valor


def hoy_bogota() -> date:
    """Devuelve la fecha actual en America/Bogota."""
    return datetime.now(BOGOTA).date()


def estado_mensualidad(
    fecha_vencimiento: date | None, hoy: date | None = None
) -> EstadoMensualidad:
    """Calcula el estado de mensualidad con la fecha de hoy en Bogotá."""
    referencia = hoy_bogota() if hoy is None else _validar_fecha(hoy, "hoy")
    if fecha_vencimiento is None:
        return SIN_PAGO

    vencimiento = _validar_fecha(fecha_vencimiento, "fecha_vencimiento")
    dias = (vencimiento - referencia).days
    if dias < 0:
        return VENCIDA
    if dias <= DIAS_POR_VENCER:
        return POR_VENCER
    return AL_DIA


def sumar_meses(fecha: date, meses: int) -> date:
    """Suma meses calendario ajustando al último día del mes de destino."""
    fecha = _validar_fecha(fecha, "fecha")
    if type(meses) is not int or meses < 0:
        raise ValueError("meses debe ser un entero no negativo.")

    total = fecha.month - 1 + meses
    anio = fecha.year + total // 12
    mes = total % 12 + 1
    ultimo_dia = monthrange(anio, mes)[1]
    return date(anio, mes, min(fecha.day, ultimo_dia))


def nueva_vigencia(
    hoy: date, vencimiento: date | None, meses: int
) -> date:
    """Aplica la regla max(hoy, vencimiento) + meses."""
    hoy = _validar_fecha(hoy, "hoy")
    if vencimiento is not None:
        vencimiento = _validar_fecha(vencimiento, "vencimiento")
    base = hoy if vencimiento is None or vencimiento < hoy else vencimiento
    return sumar_meses(base, meses)


def periodo(
    hoy: date, vencimiento: date | None, hasta: date
) -> tuple[date, date]:
    """Devuelve el periodo cubierto: max(hoy, vencimiento) hasta la nueva vigencia."""
    hoy = _validar_fecha(hoy, "hoy")
    if vencimiento is not None:
        vencimiento = _validar_fecha(vencimiento, "vencimiento")
    hasta = _validar_fecha(hasta, "hasta")

    desde = hoy if vencimiento is None or vencimiento < hoy else vencimiento
    if hasta < desde:
        raise ValueError("hasta no puede ser anterior al inicio del periodo.")
    return desde, hasta

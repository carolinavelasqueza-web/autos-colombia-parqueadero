"""Cálculo del reporte de ocupación con capacidad acotada por familia."""

from calendar import monthrange
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.capacidad import LIMITES_POR_FAMILIA
from app.models import Celda, Estancia, Pago, Vehiculo
from app.schemas.reporte import (
    DiaOcupacion,
    OcupacionFamilia,
    RecaudoPorMetodo,
    ReporteOcupacionRespuesta,
    ReporteRecaudoRespuesta,
)
from app.tipos import FAMILIA_AUTOS, FAMILIA_MOTOS, familia_tipo

BOGOTA = ZoneInfo("America/Bogota")
DIAS_POR_DEFECTO = 7
DIAS_MAXIMOS = 31
DIAS_MAXIMOS_RECAUDO = 366


class ReporteError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def rango_fechas(
    desde: date | None, hasta: date | None, hoy: date | None = None
) -> tuple[date, date]:
    """Valida el rango y aplica los valores por defecto en hora de Bogotá."""
    referencia = hoy or datetime.now(BOGOTA).date()
    fin = hasta or referencia
    inicio = desde or (fin - timedelta(days=DIAS_POR_DEFECTO - 1))
    if inicio > fin:
        raise ReporteError(422, "La fecha inicial no puede ser posterior a la final.")
    if (fin - inicio).days + 1 > DIAS_MAXIMOS:
        raise ReporteError(
            422, f"El rango del reporte no puede superar {DIAS_MAXIMOS} días."
        )
    return inicio, fin


def limites_utc(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """Devuelve el intervalo [inicio, fin) del rango en UTC."""
    inicio = datetime.combine(desde, time.min, tzinfo=BOGOTA).astimezone(timezone.utc)
    fin = datetime.combine(
        hasta + timedelta(days=1), time.min, tzinfo=BOGOTA
    ).astimezone(timezone.utc)
    return inicio, fin


def capacidad_por_familia(tipos_celdas: Iterable[str]) -> dict[str, int]:
    """Cuenta celdas activas por familia y acota cada una a su límite operativo."""
    conteo: dict[str, int] = {}
    for tipo in tipos_celdas:
        familia = familia_tipo(tipo)
        if familia is not None:
            conteo[familia] = conteo.get(familia, 0) + 1
    return {
        familia: min(conteo.get(familia, 0), limite)
        for familia, limite in LIMITES_POR_FAMILIA.items()
    }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fin_dia_utc(fecha: date) -> datetime:
    return datetime.combine(
        fecha + timedelta(days=1), time.min, tzinfo=BOGOTA
    ).astimezone(timezone.utc)


def _porcentaje(ocupadas: int, capacidad: int) -> float:
    if capacidad <= 0:
        return 0.0
    return round(ocupadas * 100 / capacidad, 1)


def construir_reporte(
    *,
    desde: date,
    hasta: date,
    capacidad: Mapping[str, int],
    ocupacion: Mapping[str, int],
    estancias: Iterable[tuple[datetime, datetime | None]],
    ahora: datetime | None = None,
) -> ReporteOcupacionRespuesta:
    """Compone métricas actuales e históricas a partir de datos ya consultados."""
    dias = [desde + timedelta(days=indice) for indice in range((hasta - desde).days + 1)]
    entradas = {dia: 0 for dia in dias}
    salidas = {dia: 0 for dia in dias}
    duraciones: list[float] = []
    estancias_normalizadas = [
        (_utc(entrada), _utc(salida) if salida is not None else None)
        for entrada, salida in estancias
    ]

    for entrada, salida in estancias_normalizadas:
        dia_entrada = entrada.astimezone(BOGOTA).date()
        if dia_entrada in entradas:
            entradas[dia_entrada] += 1
        if salida is not None:
            dia_salida = salida.astimezone(BOGOTA).date()
            if dia_salida in salidas:
                salidas[dia_salida] += 1
                duraciones.append(max(0.0, (salida - entrada).total_seconds() / 60))

    capacidad_total = sum(capacidad.values())
    historico: list[DiaOcupacion] = []
    for dia in dias:
        fin = _fin_dia_utc(dia)
        ocupadas = sum(
            1
            for entrada, salida in estancias_normalizadas
            if entrada < fin and (salida is None or salida > fin)
        )
        historico.append(
            DiaOcupacion(
                fecha=dia,
                entradas=entradas[dia],
                salidas=salidas[dia],
                ocupadas=ocupadas,
                porcentaje=_porcentaje(ocupadas, capacidad_total),
            )
        )

    ocupadas_actuales = sum(ocupacion.values())
    familias = [
        familia
        for familia in (FAMILIA_AUTOS, FAMILIA_MOTOS)
        if familia in capacidad or familia in ocupacion
    ]
    por_tipo = [
        OcupacionFamilia(
            familia=familia,
            capacidad=capacidad.get(familia, 0),
            ocupadas=ocupacion.get(familia, 0),
            disponibles=max(capacidad.get(familia, 0) - ocupacion.get(familia, 0), 0),
            porcentaje=_porcentaje(
                ocupacion.get(familia, 0), capacidad.get(familia, 0)
            ),
        )
        for familia in familias
    ]

    return ReporteOcupacionRespuesta(
        generado_en=ahora or datetime.now(timezone.utc),
        desde=desde,
        hasta=hasta,
        capacidad_total=capacidad_total,
        ocupadas=ocupadas_actuales,
        disponibles=max(capacidad_total - ocupadas_actuales, 0),
        porcentaje=_porcentaje(ocupadas_actuales, capacidad_total),
        entradas=sum(entradas.values()),
        salidas=sum(salidas.values()),
        permanencia_promedio_minutos=(
            round(sum(duraciones) / len(duraciones), 1) if duraciones else 0.0
        ),
        por_tipo=por_tipo,
        historico=historico,
    )


def generar_reporte(
    session: Session, desde: date | None = None, hasta: date | None = None
) -> ReporteOcupacionRespuesta:
    inicio, fin = rango_fechas(desde, hasta)
    try:
        tipos_celdas = list(
            session.scalars(select(Celda.tipo).where(Celda.activo.is_(True))).all()
        )
        capacidad = capacidad_por_familia(tipos_celdas)

        filas_ocupacion = session.execute(
            select(Vehiculo.tipo, func.count())
            .select_from(Estancia)
            .join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id)
            .where(Estancia.salida.is_(None))
            .group_by(Vehiculo.tipo)
        ).all()
        ocupacion: dict[str, int] = {}
        for tipo, cantidad in filas_ocupacion:
            familia = familia_tipo(tipo)
            if familia is not None:
                ocupacion[familia] = ocupacion.get(familia, 0) + int(cantidad)

        inicio_utc, fin_utc = limites_utc(inicio, fin)
        filas = session.execute(
            select(Estancia.entrada, Estancia.salida).where(
                Estancia.entrada < fin_utc,
                or_(Estancia.salida.is_(None), Estancia.salida > inicio_utc),
            )
        ).all()
        estancias = [(fila.entrada, fila.salida) for fila in filas]

        return construir_reporte(
            desde=inicio,
            hasta=fin,
            capacidad=capacidad,
            ocupacion=ocupacion,
            estancias=estancias,
        )
    except SQLAlchemyError:
        raise ReporteError(
            503, "No se pudo completar la consulta del reporte."
        ) from None


def rango_recaudo(
    desde: date | None, hasta: date | None, hoy: date | None = None
) -> tuple[date, date]:
    """Valida y completa el rango del recaudo usando días de Bogotá."""
    referencia = hoy or datetime.now(BOGOTA).date()
    if desde is None and hasta is None:
        inicio = referencia.replace(day=1)
        fin = date(
            referencia.year,
            referencia.month,
            monthrange(referencia.year, referencia.month)[1],
        )
    elif desde is None:
        inicio = hasta.replace(day=1)
        fin = hasta
    elif hasta is None:
        inicio = desde
        fin = date(desde.year, desde.month, monthrange(desde.year, desde.month)[1])
    else:
        inicio, fin = desde, hasta

    if inicio > fin:
        raise ReporteError(422, "La fecha inicial no puede ser posterior a la final.")
    if (fin - inicio).days + 1 > DIAS_MAXIMOS_RECAUDO:
        raise ReporteError(
            422,
            f"El rango del reporte no puede superar {DIAS_MAXIMOS_RECAUDO} días.",
        )
    return inicio, fin


def obtener_reporte_recaudo(
    session: Session, desde: date | None = None, hasta: date | None = None
) -> ReporteRecaudoRespuesta:
    """Suma los pagos VIGENTE del rango agrupados por método."""
    inicio, fin = rango_recaudo(desde, hasta)
    inicio_utc, fin_utc = limites_utc(inicio, fin)

    try:
        filas = session.execute(
            select(Pago.metodo, func.count(Pago.id), func.sum(Pago.monto))
            .where(
                Pago.estado == "VIGENTE",
                Pago.fecha >= inicio_utc,
                Pago.fecha < fin_utc,
            )
            .group_by(Pago.metodo)
            .order_by(Pago.metodo)
        ).all()
    except SQLAlchemyError:
        raise ReporteError(
            503, "No se pudo completar la consulta del reporte."
        ) from None

    por_metodo = [
        RecaudoPorMetodo(
            metodo=metodo,
            pagos=int(cantidad),
            total=Decimal(total or 0),
        )
        for metodo, cantidad, total in filas
    ]
    return ReporteRecaudoRespuesta(
        desde=inicio,
        hasta=fin,
        pagos=sum(item.pagos for item in por_metodo),
        total=sum((item.total for item in por_metodo), Decimal("0")),
        por_metodo=por_metodo,
    )

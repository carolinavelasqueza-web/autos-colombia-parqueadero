"""Registro de pagos de mensualidad con recibo, vigencia y auditoría."""

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    MAX_MONTO,
    MAX_REFERENCIA_PAGO,
    Cliente,
    Operador,
    Pago,
    PagoDetalle,
    Vehiculo,
)
from app.schemas.pago import PagoAnular, PagoCrear
from app.services.auditoria import auditar_cambio
from app.services.mensualidad import BOGOTA, hoy_bogota, nueva_vigencia, periodo



class PagoError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def ahora() -> datetime:
    """Instante de referencia; aislado para pruebas deterministas."""
    return datetime.now(timezone.utc)


def _normalizar_referencia(metodo: str, referencia: str | None) -> str | None:
    """Valida la referencia según el método antes de tocar la base de datos."""
    if referencia is not None and not isinstance(referencia, str):
        raise PagoError(422, "La referencia debe ser texto.")

    valor = referencia.strip().upper() if referencia else ""
    valor = valor or None

    if metodo == "EFECTIVO":
        if valor is not None:
            raise PagoError(422, "El pago en efectivo no admite referencia.")
        return None
    if valor is None:
        raise PagoError(
            422, "La referencia es obligatoria para transferencia o tarjeta."
        )
    if len(valor) > MAX_REFERENCIA_PAGO:
        raise PagoError(422, "La referencia no puede superar 100 caracteres.")
    return valor


def registrar_pago(session: Session, data: PagoCrear, actor: Operador) -> Pago:
    """Registra el pago, actualiza la vigencia y reactiva al cliente si aplica."""
    # Importación tardía: tarifa importa PagoError desde este módulo.
    from app.services.tarifa import tarifa_vigente

    referencia = _normalizar_referencia(data.metodo, data.referencia)
    instante = ahora()
    hoy = hoy_bogota()

    try:
        cliente = session.scalar(
            select(Cliente)
            .where(Cliente.documento == data.documento)
            .with_for_update()
        )
        if cliente is None:
            raise PagoError(404, "Cliente no encontrado.")

        vehiculos = list(
            session.scalars(
                select(Vehiculo)
                .where(Vehiculo.cliente_id == cliente.id)
                .order_by(Vehiculo.placa)
            )
        )
        if not vehiculos:
            raise PagoError(409, "El cliente no tiene vehículos registrados.")

        # Selección por vehículo: si llegan ids, se cobran solo esos y deben
        # pertenecer al cliente. Sin ids, se mantiene el cobro de todos.
        if data.vehiculo_ids is not None:
            disponibles = {vehiculo.id: vehiculo for vehiculo in vehiculos}
            ajenos = [vid for vid in data.vehiculo_ids if vid not in disponibles]
            if ajenos:
                raise PagoError(
                    422,
                    "Los vehículos seleccionados deben pertenecer al cliente.",
                )
            vehiculos = [disponibles[vid] for vid in data.vehiculo_ids]
            vehiculos.sort(key=lambda vehiculo: vehiculo.placa)

        tarifas: dict[str, Decimal] = {}
        for vehiculo in vehiculos:
            if vehiculo.tipo not in tarifas:
                tarifas[vehiculo.tipo] = tarifa_vigente(session, vehiculo.tipo).valor

        detalles = []
        monto = Decimal("0")
        for vehiculo in vehiculos:
            tarifa = tarifas[vehiculo.tipo]
            subtotal = tarifa * data.meses
            monto += subtotal
            detalles.append((vehiculo, tarifa, subtotal))
        if monto <= 0 or monto >= MAX_MONTO:
            raise PagoError(422, "El monto total del pago no es válido.")

        numero = session.scalar(select(func.nextval("pago_recibo_seq")))
        if numero is None:
            raise PagoError(503, "No se pudo generar el número de recibo.")
        numero_recibo = f"RC-{int(numero):06d}"

        anterior = cliente.fecha_vencimiento
        hasta = nueva_vigencia(hoy, anterior, data.meses)
        desde, hasta = periodo(hoy, anterior, hasta)

        reactivo = cliente.activo is not True
        activo_anterior = cliente.activo
        cliente.activo = True
        cliente.fecha_vencimiento = hasta

        pago = Pago(
            cliente_id=cliente.id,
            meses=data.meses,
            metodo=data.metodo,
            referencia=referencia,
            monto=monto,
            estado="VIGENTE",
            numero_recibo=numero_recibo,
            periodo_desde=desde,
            periodo_hasta=hasta,
            vencimiento_anterior=anterior,
            reactivo_cliente=reactivo,
            operador_id=actor.id,
            fecha=instante,
        )
        session.add(pago)
        session.flush()
        for vehiculo, tarifa, subtotal in detalles:
            pago.detalles.append(
                PagoDetalle(
                    vehiculo_id=vehiculo.id,
                    placa=vehiculo.placa,
                    tipo=vehiculo.tipo,
                    tarifa_aplicada=tarifa,
                    subtotal=subtotal,
                )
            )
        session.flush()

        auditar_cambio(
            session,
            actor,
            "REGISTRAR_PAGO",
            "pago",
            pago.id,
            nuevos={
                "numero_recibo": numero_recibo,
                "monto": monto,
                "meses": data.meses,
                "metodo": data.metodo,
                "referencia": referencia,
                "periodo_desde": desde,
                "periodo_hasta": hasta,
                "reactivo_cliente": reactivo,
            },
            contexto={"cliente_id": cliente.id, "documento": cliente.documento},
        )
        if reactivo:
            auditar_cambio(
                session,
                actor,
                "REACTIVAR_CLIENTE",
                "cliente",
                cliente.id,
                anteriores={"activo": activo_anterior, "fecha_vencimiento": anterior},
                nuevos={"activo": True, "fecha_vencimiento": hasta},
                contexto={"pago_id": pago.id, "numero_recibo": numero_recibo},
            )

        session.commit()
        return pago
    except PagoError:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        code = getattr(error.orig, "sqlstate", None)
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if code == "23505" and constraint == "uq_pago_referencia_vigente":
            raise PagoError(
                409, "La referencia ya fue usada en otro pago vigente."
            ) from None
        if code == "23505" and constraint == "uq_pago_numero_recibo":
            raise PagoError(
                409, "No se pudo generar un número de recibo único. Intenta de nuevo."
            ) from None
        if code == "23503":
            raise PagoError(
                409, "La operación entra en conflicto con los datos existentes."
            ) from None
        if code in {"23502", "23514"}:
            raise PagoError(
                422, "Los datos incumplen las restricciones del pago."
            ) from None
        raise PagoError(
            409, "La operación entra en conflicto con los datos existentes."
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise PagoError(503, "No se pudo registrar el pago.") from None


def _restar_meses(fecha: date, meses: int) -> date:
    """Resta meses calendario ajustando al último día del mes de destino."""
    if type(fecha) is not date:
        raise ValueError("fecha debe ser una fecha.")
    if type(meses) is not int or meses < 0:
        raise ValueError("meses debe ser un entero no negativo.")

    total = fecha.month - 1 - meses
    anio = fecha.year + total // 12
    mes = total % 12 + 1
    ultimo_dia = monthrange(anio, mes)[1]
    return date(anio, mes, min(fecha.day, ultimo_dia))


def _limites_de_fecha(
    desde: date | None, hasta: date | None
) -> list:
    """Convierte un rango de días de Bogotá en límites UTC sobre ``fecha``."""
    limites = []
    if desde is not None:
        limites.append(Pago.fecha >= datetime.combine(desde, time.min, tzinfo=BOGOTA))
    if hasta is not None:
        siguiente = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=BOGOTA)
        limites.append(Pago.fecha < siguiente)
    return limites


def obtener_pagos(
    session: Session,
    *,
    documento: str | None = None,
    estado: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Pago], int]:
    """Lista pagos paginados con filtros opcionales."""
    if desde is not None and hasta is not None and desde > hasta:
        raise PagoError(422, "El rango de fechas no es válido.")

    condiciones = _limites_de_fecha(desde, hasta)
    if estado is not None:
        condiciones.append(Pago.estado == estado)

    documento = documento.strip() if isinstance(documento, str) else documento
    if documento == "":
        raise PagoError(422, "El documento no puede estar vacío.")

    consulta = select(Pago).options(
        selectinload(Pago.cliente), selectinload(Pago.detalles)
    )
    conteo = select(func.count()).select_from(Pago)
    if documento is not None:
        union = Pago.cliente_id == Cliente.id
        consulta = consulta.join(Cliente, union)
        conteo = conteo.join(Cliente, union)
        condiciones.append(Cliente.documento == documento)
    if condiciones:
        consulta = consulta.where(*condiciones)
        conteo = conteo.where(*condiciones)

    try:
        total = session.scalar(conteo)
        pagos = list(
            session.scalars(
                consulta.order_by(Pago.fecha.desc(), Pago.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return pagos, int(total or 0)
    except SQLAlchemyError:
        session.rollback()
        raise PagoError(503, "No se pudieron consultar los pagos.") from None


def obtener_recibo(session: Session, pago_id: int) -> Pago:
    """Devuelve el recibo completo de un pago o 404 si no existe."""
    try:
        pago = session.scalar(
            select(Pago)
            .options(selectinload(Pago.cliente), selectinload(Pago.detalles))
            .where(Pago.id == pago_id)
        )
    except SQLAlchemyError:
        session.rollback()
        raise PagoError(503, "No se pudo obtener el recibo.") from None
    if pago is None:
        raise PagoError(404, "Pago no encontrado.")
    return pago


def anular_pago(
    session: Session, pago_id: int, data: PagoAnular, actor: Operador
) -> Pago:
    """Anula el último pago vigente del cliente y revierte su vigencia."""
    instante = ahora()
    try:
        pago = session.scalar(
            select(Pago).where(Pago.id == pago_id).with_for_update()
        )
        if pago is None:
            raise PagoError(404, "Pago no encontrado.")
        if pago.estado != "VIGENTE":
            raise PagoError(409, "El pago ya está anulado.")

        cliente = session.scalar(
            select(Cliente)
            .where(Cliente.id == pago.cliente_id)
            .with_for_update()
        )
        if cliente is None:
            raise PagoError(404, "Cliente no encontrado.")

        posterior = session.scalar(
            select(Pago.id)
            .where(
                Pago.cliente_id == pago.cliente_id,
                Pago.estado == "VIGENTE",
                Pago.id != pago.id,
                or_(
                    Pago.fecha > pago.fecha,
                    and_(Pago.fecha == pago.fecha, Pago.id > pago.id),
                ),
            )
            .limit(1)
        )
        if posterior is not None:
            raise PagoError(
                409, "Solo se puede anular el último pago vigente del cliente."
            )

        vencimiento_anterior = cliente.fecha_vencimiento
        nuevo_vencimiento = (
            _restar_meses(vencimiento_anterior, pago.meses)
            if vencimiento_anterior is not None
            else None
        )
        activo_anterior = cliente.activo
        cliente.fecha_vencimiento = nuevo_vencimiento
        if pago.reactivo_cliente:
            cliente.activo = False

        pago.estado = "ANULADO"
        pago.motivo = data.motivo
        pago.anulado_por = actor.id
        pago.anulado_en = instante

        auditar_cambio(
            session,
            actor,
            "ANULAR_PAGO",
            "pago",
            pago.id,
            anteriores={
                "estado": "VIGENTE",
                "motivo": None,
                "anulado_por": None,
                "anulado_en": None,
            },
            nuevos={
                "estado": pago.estado,
                "motivo": pago.motivo,
                "anulado_por": pago.anulado_por,
                "anulado_en": pago.anulado_en,
            },
            contexto={
                "cliente_id": cliente.id,
                "numero_recibo": pago.numero_recibo,
                "fecha_vencimiento_anterior": vencimiento_anterior,
                "fecha_vencimiento_nueva": nuevo_vencimiento,
            },
        )
        if pago.reactivo_cliente:
            auditar_cambio(
                session,
                actor,
                "DESACTIVAR_CLIENTE",
                "cliente",
                cliente.id,
                anteriores={
                    "activo": activo_anterior,
                    "fecha_vencimiento": vencimiento_anterior,
                },
                nuevos={
                    "activo": cliente.activo,
                    "fecha_vencimiento": nuevo_vencimiento,
                },
                contexto={"pago_id": pago.id, "numero_recibo": pago.numero_recibo},
            )

        session.commit()
        return pago
    except PagoError:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise PagoError(503, "No se pudo anular el pago.") from None

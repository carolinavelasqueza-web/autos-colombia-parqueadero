"""Modelos iniciales. Importar este módulo no crea tablas ni abre conexiones."""

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Identity, Index, Integer, Numeric, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates

ROLES_OPERADOR = frozenset({"ADMINISTRADOR", "OPERADOR"})
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72
USUARIO_RE = re.compile(r"^[a-z0-9._-]{3,50}$")
CORREO_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FICHO_RE = re.compile(r"^AC-\d{8}-\d{4}$")
TOKEN_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
RECIBO_RE = re.compile(r"^RC-\d{6}$")
TIPOS_TARIFA = frozenset({"MOTO", "AUTOMOVIL", "CAMIONETA"})
METODOS_PAGO = frozenset({"EFECTIVO", "TRANSFERENCIA", "TARJETA"})
ESTADOS_PAGO = frozenset({"VIGENTE", "ANULADO"})
MAX_REFERENCIA_PAGO = 100
MAX_MOTIVO_ANULACION = 500
MAX_MONTO = Decimal("10000000000")


class Base(DeclarativeBase):
    pass


def required_text(value: str, attribute: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute} debe ser texto no vacío.")
    return value.strip()


def normalize_usuario(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("usuario debe ser texto.")
    value = value.strip().lower()
    if not USUARIO_RE.fullmatch(value):
        raise ValueError("usuario debe tener entre 3 y 50 caracteres: letras minúsculas, números, punto, guion o guion bajo.")
    return value


def validate_password(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("La contraseña no puede estar vacía.")
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"La contraseña no puede superar {PASSWORD_MAX_BYTES} bytes.")
    return value


def validate_correo(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("correo debe ser texto.")
    value = value.strip()
    if not CORREO_RE.fullmatch(value):
        raise ValueError("correo debe tener un formato válido.")
    return value


def normalize_ficho(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("ficho_codigo debe ser texto.")
    value = value.strip().upper()
    if not FICHO_RE.fullmatch(value):
        raise ValueError("ficho_codigo debe tener el formato AC-YYYYMMDD-XXXX.")
    return value


def validate_money(value: Decimal | int | str, attribute: str) -> Decimal:
    """Valida montos NUMERIC(12,2) positivos sin aceptar float."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{attribute} debe ser un Decimal, no un float.")
    if not isinstance(value, (Decimal, int, str)):
        raise ValueError(f"{attribute} debe ser un valor decimal.")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{attribute} debe ser un valor decimal válido.") from error
    if not amount.is_finite():
        raise ValueError(f"{attribute} debe ser un valor decimal finito.")
    if amount.as_tuple().exponent < -2:
        raise ValueError(f"{attribute} admite como máximo dos decimales.")
    if amount <= 0:
        raise ValueError(f"{attribute} debe ser mayor que cero.")
    if amount >= MAX_MONTO:
        raise ValueError(f"{attribute} supera el máximo permitido.")
    return amount


def validate_date_value(value: date | None, attribute: str) -> date | None:
    if value is None:
        return None
    if type(value) is not date:
        raise ValueError(f"{attribute} debe ser una fecha.")
    return value


def validate_timezone_datetime(value: datetime | None, attribute: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{attribute} debe incluir zona horaria.")
    return value


class Cliente(Base):
    __tablename__ = "cliente"
    __table_args__ = (
        UniqueConstraint("documento", name="uq_cliente_documento"),
        CheckConstraint("documento ~ '[^[:space:]]'", name="ck_cliente_documento_no_vacio"),
        CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_cliente_nombre_no_vacio"),
        CheckConstraint("telefono ~ '[^[:space:]]'", name="ck_cliente_telefono_no_vacio"),
        CheckConstraint("correo ~ '[^[:space:]]'", name="ck_cliente_correo_no_vacio"),
        CheckConstraint(
            "correo ~ '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
            name="ck_cliente_correo_formato",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    documento: Mapped[str] = mapped_column(Text, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    telefono: Mapped[str] = mapped_column(Text, nullable=False)
    correo: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)

    vehiculos: Mapped[list["Vehiculo"]] = relationship(back_populates="cliente")

    @validates("documento", "nombre", "telefono")
    def validate_text(self, key: str, value: str) -> str:
        return required_text(value, key)

    @validates("correo")
    def validate_cliente_correo(self, key: str, value: str) -> str:
        return validate_correo(value)

    @validates("activo")
    def validate_activo(self, key: str, value: bool) -> bool:
        if type(value) is not bool:
            raise ValueError("activo debe ser un booleano.")
        return value

    @validates("fecha_vencimiento")
    def validate_fecha_vencimiento(self, key: str, value: date | None) -> date | None:
        return validate_date_value(value, key)


class Vehiculo(Base):
    __tablename__ = "vehiculo"
    __table_args__ = (
        UniqueConstraint("placa", name="uq_vehiculo_placa"),
        CheckConstraint("placa ~ '[^[:space:]]'", name="ck_vehiculo_placa_no_vacia"),
        CheckConstraint("placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_vehiculo_placa_normalizada"),
        CheckConstraint("color ~ '[^[:space:]]'", name="ck_vehiculo_color_no_vacio"),
        CheckConstraint("marca ~ '[^[:space:]]'", name="ck_vehiculo_marca_no_vacia"),
        CheckConstraint("modelo BETWEEN 1 AND 9999", name="ck_vehiculo_modelo_anio"),
        CheckConstraint("tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')", name="ck_vehiculo_tipo"),
        Index("ix_vehiculo_cliente", "cliente_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    placa: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    marca: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    cliente_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("cliente.id", name="fk_vehiculo_cliente", ondelete="RESTRICT"),
        nullable=True,
    )

    cliente: Mapped[Cliente | None] = relationship(back_populates="vehiculos")

    @validates("placa", "color", "marca", "tipo")
    def validate_text(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if key == "placa":
            return value.upper()
        if key == "tipo" and value not in {"MOTO", "AUTOMOVIL", "CAMIONETA"}:
            raise ValueError("tipo debe ser MOTO, AUTOMOVIL o CAMIONETA.")
        return value

    @validates("modelo")
    def validate_modelo(self, key: str, value: int) -> int:
        if type(value) is not int or not 1 <= value <= 9999:
            raise ValueError("modelo debe ser un año entero entre 1 y 9999.")
        return value


class Celda(Base):
    __tablename__ = "celda"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_celda_codigo"),
        CheckConstraint("codigo ~ '[^[:space:]]'", name="ck_celda_codigo_no_vacio"),
        CheckConstraint("codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_celda_codigo_normalizado"),
        CheckConstraint("tipo ~ '[^[:space:]]'", name="ck_celda_tipo_no_vacio"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    @validates("codigo", "tipo")
    def validate_text(self, key: str, value: str) -> str:
        value = required_text(value, key)
        return value.upper() if key == "codigo" else value

    @validates("activo")
    def validate_activo(self, key: str, value: bool) -> bool:
        if type(value) is not bool:
            raise ValueError("activo debe ser un booleano.")
        return value


class Puerta(Base):
    __tablename__ = "puerta"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_puerta_codigo"),
        CheckConstraint("codigo ~ '[^[:space:]]'", name="ck_puerta_codigo_no_vacio"),
        CheckConstraint(
            "codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$', '', 'g'))",
            name="ck_puerta_codigo_normalizado",
        ),
        CheckConstraint("ubicacion ~ '[^[:space:]]'", name="ck_puerta_ubicacion_no_vacia"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(Text, nullable=False)
    ubicacion: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    @validates("codigo", "ubicacion")
    def validate_text(self, key: str, value: str) -> str:
        value = required_text(value, key)
        return value.upper() if key == "codigo" else value

    @validates("activo")
    def validate_activo(self, key: str, value: bool) -> bool:
        if type(value) is not bool:
            raise ValueError("activo debe ser un booleano.")
        return value


class Operador(Base):
    __tablename__ = "operador"
    __table_args__ = (
        UniqueConstraint("usuario", name="uq_operador_usuario"),
        CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_operador_nombre_no_vacio"),
        CheckConstraint("telefono ~ '[^[:space:]]'", name="ck_operador_telefono_no_vacio"),
        CheckConstraint("usuario ~ '[^[:space:]]'", name="ck_operador_usuario_no_vacio"),
        CheckConstraint(
            "usuario = lower(regexp_replace(usuario, '^[[:space:]]+|[[:space:]]+$', '', 'g'))",
            name="ck_operador_usuario_normalizado",
        ),
        CheckConstraint("char_length(usuario) BETWEEN 3 AND 50", name="ck_operador_usuario_longitud"),
        CheckConstraint("contrasena_hash ~ '[^[:space:]]'", name="ck_operador_contrasena_no_vacia"),
        CheckConstraint("rol IN ('ADMINISTRADOR', 'OPERADOR')", name="ck_operador_rol"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    telefono: Mapped[str] = mapped_column(Text, nullable=False)
    usuario: Mapped[str] = mapped_column(Text, nullable=False)
    contrasena_hash: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[str] = mapped_column(Text, nullable=False, default="OPERADOR", server_default=text("'OPERADOR'"))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    @validates("nombre", "telefono")
    def validate_text(self, key: str, value: str) -> str:
        return required_text(value, key)

    @validates("usuario")
    def validate_usuario(self, key: str, value: str) -> str:
        return normalize_usuario(value)

    @validates("contrasena_hash")
    def validate_contrasena_hash(self, key: str, value: str) -> str:
        return required_text(value, key)

    @validates("rol")
    def validate_rol(self, key: str, value: str) -> str:
        if value not in ROLES_OPERADOR:
            raise ValueError("rol debe ser ADMINISTRADOR u OPERADOR.")
        return value

    @validates("activo")
    def validate_activo(self, key: str, value: bool) -> bool:
        if type(value) is not bool:
            raise ValueError("activo debe ser un booleano.")
        return value


class Tarifa(Base):
    __tablename__ = "tarifa"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')", name="ck_tarifa_tipo"
        ),
        CheckConstraint("valor > 0", name="ck_tarifa_valor_positivo"),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde",
            name="ck_tarifa_vigencia",
        ),
        Index(
            "uq_tarifa_vigente",
            "tipo",
            unique=True,
            postgresql_where=text("vigente_hasta IS NULL"),
        ),
        Index("ix_tarifa_tipo_desde", "tipo", "vigente_desde"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @validates("tipo")
    def validate_tipo(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if value not in TIPOS_TARIFA:
            raise ValueError("tipo debe ser MOTO, AUTOMOVIL o CAMIONETA.")
        return value

    @validates("valor")
    def validate_valor(self, key: str, value: Decimal | int | str) -> Decimal:
        return validate_money(value, key)

    @validates("vigente_desde", "vigente_hasta")
    def validate_vigencia(self, key: str, value: datetime | None) -> datetime | None:
        return validate_timezone_datetime(value, key)


class Pago(Base):
    __tablename__ = "pago"
    __table_args__ = (
        CheckConstraint("meses BETWEEN 1 AND 12", name="ck_pago_meses"),
        CheckConstraint(
            "metodo IN ('EFECTIVO', 'TRANSFERENCIA', 'TARJETA')", name="ck_pago_metodo"
        ),
        CheckConstraint("estado IN ('VIGENTE', 'ANULADO')", name="ck_pago_estado"),
        CheckConstraint("monto > 0", name="ck_pago_monto_positivo"),
        CheckConstraint(
            "numero_recibo ~ '^RC-[0-9]{6}$'", name="ck_pago_recibo_formato"
        ),
        CheckConstraint("periodo_hasta >= periodo_desde", name="ck_pago_periodo"),
        CheckConstraint(
            "((metodo = 'EFECTIVO') AND referencia IS NULL) OR "
            "((metodo <> 'EFECTIVO') AND referencia IS NOT NULL)",
            name="ck_pago_referencia_metodo",
        ),
        CheckConstraint(
            "referencia IS NULL OR "
            "(referencia ~ '[^[:space:]]' AND char_length(referencia) <= 100)",
            name="ck_pago_referencia_texto",
        ),
        CheckConstraint(
            "(estado = 'ANULADO') = (motivo IS NOT NULL AND anulado_por IS NOT NULL "
            "AND anulado_en IS NOT NULL)",
            name="ck_pago_anulacion_completa",
        ),
        CheckConstraint(
            "motivo IS NULL OR "
            "(motivo ~ '[^[:space:]]' AND char_length(motivo) <= 500)",
            name="ck_pago_motivo",
        ),
        UniqueConstraint("numero_recibo", name="uq_pago_numero_recibo"),
        Index(
            "uq_pago_referencia_vigente",
            "referencia",
            unique=True,
            postgresql_where=text("estado = 'VIGENTE' AND referencia IS NOT NULL"),
        ),
        Index("ix_pago_cliente_fecha", "cliente_id", "fecha"),
        Index("ix_pago_estado_fecha", "estado", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cliente.id", name="fk_pago_cliente", ondelete="RESTRICT"),
        nullable=False,
    )
    meses: Mapped[int] = mapped_column(Integer, nullable=False)
    metodo: Mapped[str] = mapped_column(Text, nullable=False)
    referencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estado: Mapped[str] = mapped_column(
        Text, nullable=False, default="VIGENTE", server_default=text("'VIGENTE'")
    )
    numero_recibo: Mapped[str] = mapped_column(Text, nullable=False)
    periodo_desde: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_hasta: Mapped[date] = mapped_column(Date, nullable=False)
    vencimiento_anterior: Mapped[date | None] = mapped_column(Date, nullable=True)
    reactivo_cliente: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    operador_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operador.id", name="fk_pago_operador", ondelete="RESTRICT"),
        nullable=False,
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    anulado_por: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("operador.id", name="fk_pago_anulado_por", ondelete="RESTRICT"),
        nullable=True,
    )
    anulado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cliente: Mapped[Cliente] = relationship()
    operador: Mapped[Operador] = relationship(foreign_keys=[operador_id])
    operador_anulacion: Mapped[Operador | None] = relationship(
        foreign_keys=[anulado_por]
    )
    detalles: Mapped[list["PagoDetalle"]] = relationship(back_populates="pago")

    @validates("meses")
    def validate_meses(self, key: str, value: int) -> int:
        if type(value) is not int or not 1 <= value <= 12:
            raise ValueError("meses debe ser un entero entre 1 y 12.")
        return value

    @validates("metodo")
    def validate_metodo(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if value not in METODOS_PAGO:
            raise ValueError("metodo debe ser EFECTIVO, TRANSFERENCIA o TARJETA.")
        return value

    @validates("referencia")
    def validate_referencia(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("referencia debe ser texto.")
        value = value.strip().upper()
        if not value:
            return None
        if len(value) > MAX_REFERENCIA_PAGO:
            raise ValueError("referencia no puede superar 100 caracteres.")
        return value

    @validates("monto")
    def validate_monto(self, key: str, value: Decimal | int | str) -> Decimal:
        return validate_money(value, key)

    @validates("estado")
    def validate_estado(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if value not in ESTADOS_PAGO:
            raise ValueError("estado debe ser VIGENTE o ANULADO.")
        return value

    @validates("numero_recibo")
    def validate_numero_recibo(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if not RECIBO_RE.fullmatch(value):
            raise ValueError("numero_recibo debe tener el formato RC-000001.")
        return value

    @validates("periodo_desde", "periodo_hasta", "vencimiento_anterior")
    def validate_fechas(self, key: str, value: date | None) -> date | None:
        return validate_date_value(value, key)

    @validates("reactivo_cliente")
    def validate_reactivo_cliente(self, key: str, value: bool) -> bool:
        if type(value) is not bool:
            raise ValueError("reactivo_cliente debe ser un booleano.")
        return value

    @validates("fecha", "anulado_en")
    def validate_fecha_hora(self, key: str, value: datetime | None) -> datetime | None:
        return validate_timezone_datetime(value, key)

    @validates("motivo")
    def validate_motivo(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("motivo debe ser texto.")
        value = value.strip()
        if not value:
            return None
        if len(value) > MAX_MOTIVO_ANULACION:
            raise ValueError("motivo no puede superar 500 caracteres.")
        return value

    @validates("anulado_por")
    def validate_anulado_por(self, key: str, value: int | None) -> int | None:
        if value is None:
            return None
        if type(value) is not int or value <= 0:
            raise ValueError("anulado_por debe ser un identificador válido.")
        return value


class PagoDetalle(Base):
    __tablename__ = "pago_detalle"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')", name="ck_pago_detalle_tipo"
        ),
        CheckConstraint(
            "tarifa_aplicada > 0", name="ck_pago_detalle_tarifa_positiva"
        ),
        CheckConstraint("subtotal > 0", name="ck_pago_detalle_subtotal_positivo"),
        CheckConstraint("placa ~ '[^[:space:]]'", name="ck_pago_detalle_placa_no_vacia"),
        CheckConstraint(
            "placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$', '', 'g'))",
            name="ck_pago_detalle_placa_normalizada",
        ),
        UniqueConstraint(
            "pago_id", "vehiculo_id", name="uq_pago_detalle_vehiculo"
        ),
        Index("ix_pago_detalle_pago", "pago_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    pago_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pago.id", name="fk_pago_detalle_pago", ondelete="RESTRICT"),
        nullable=False,
    )
    vehiculo_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vehiculo.id", name="fk_pago_detalle_vehiculo", ondelete="RESTRICT"),
        nullable=False,
    )
    placa: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    tarifa_aplicada: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    pago: Mapped[Pago] = relationship(back_populates="detalles")
    vehiculo: Mapped[Vehiculo] = relationship()

    @validates("placa")
    def validate_placa(self, key: str, value: str) -> str:
        return required_text(value, key).upper()

    @validates("tipo")
    def validate_tipo(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if value not in TIPOS_TARIFA:
            raise ValueError("tipo debe ser MOTO, AUTOMOVIL o CAMIONETA.")
        return value

    @validates("tarifa_aplicada", "subtotal")
    def validate_montos(self, key: str, value: Decimal | int | str) -> Decimal:
        return validate_money(value, key)


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (
        CheckConstraint("accion ~ '[^[:space:]]'", name="ck_auditoria_accion_no_vacia"),
        CheckConstraint("entidad ~ '[^[:space:]]'", name="ck_auditoria_entidad_no_vacia"),
        Index("ix_auditoria_operador_fecha", "operador_id", "fecha"),
        Index("ix_auditoria_entidad_fecha", "entidad", "entidad_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    operador_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_auditoria_operador", ondelete="RESTRICT"), nullable=False
    )
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    entidad: Mapped[str] = mapped_column(Text, nullable=False)
    entidad_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    detalle: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    operador: Mapped[Operador] = relationship()

    @validates("accion", "entidad")
    def validate_text(self, key: str, value: str) -> str:
        return required_text(value, key)


class Estancia(Base):
    __tablename__ = "estancia"
    __table_args__ = (
        CheckConstraint("salida >= entrada", name="ck_estancia_orden_fechas"),
        CheckConstraint(
            "(salida IS NULL) = (operador_salida_id IS NULL)",
            name="ck_estancia_cierre_completo",
        ),
        CheckConstraint(
            "ficho_codigo IS NULL OR ficho_codigo ~ '^AC-[0-9]{8}-[0-9]{4}$'",
            name="ck_estancia_ficho_formato",
        ),
        CheckConstraint(
            "ficho_usado_en IS NULL OR ficho_codigo IS NOT NULL",
            name="ck_estancia_ficho_uso",
        ),
        CheckConstraint(
            "ficho_usado_en IS NULL OR ficho_usado_en >= entrada",
            name="ck_estancia_ficho_fecha",
        ),
        UniqueConstraint("ficho_codigo", name="uq_estancia_ficho_codigo"),
        Index("uq_estancia_vehiculo_abierta", "vehiculo_id", unique=True,
              postgresql_where=text("salida IS NULL")),
        Index("uq_estancia_celda_abierta", "celda_id", unique=True,
              postgresql_where=text("salida IS NULL")),
        Index("ix_estancia_vehiculo_entrada", "vehiculo_id", "entrada"),
        Index("ix_estancia_puerta_entrada", "puerta_entrada_id"),
        Index("ix_estancia_puerta_salida", "puerta_salida_id"),
        Index("ix_estancia_entrada", "entrada"),
        Index(
            "ix_estancia_salida",
            "salida",
            postgresql_where=text("salida IS NOT NULL"),
        ),
        Index(
            "ix_estancia_abierta_entrada",
            "entrada",
            postgresql_where=text("salida IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehiculo.id", name="fk_estancia_vehiculo", ondelete="RESTRICT"), nullable=False
    )
    celda_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_estancia_celda", ondelete="RESTRICT"), nullable=False
    )
    entrada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operador_entrada_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_estancia_operador_entrada", ondelete="RESTRICT"), nullable=False
    )
    operador_salida_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_estancia_operador_salida", ondelete="RESTRICT"), nullable=True
    )
    ficho_codigo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ficho_usado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    puerta_entrada_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("puerta.id", name="fk_estancia_puerta_entrada", ondelete="RESTRICT"),
        nullable=True,
    )
    puerta_salida_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("puerta.id", name="fk_estancia_puerta_salida", ondelete="RESTRICT"),
        nullable=True,
    )

    vehiculo: Mapped[Vehiculo] = relationship()
    celda: Mapped[Celda] = relationship()
    operador_entrada: Mapped[Operador] = relationship(foreign_keys=[operador_entrada_id])
    operador_salida: Mapped[Operador | None] = relationship(foreign_keys=[operador_salida_id])
    puerta_entrada: Mapped[Puerta | None] = relationship(foreign_keys=[puerta_entrada_id])
    puerta_salida: Mapped[Puerta | None] = relationship(foreign_keys=[puerta_salida_id])

    @validates("ficho_codigo")
    def validate_ficho(self, key: str, value: str | None) -> str | None:
        return normalize_ficho(value)

    def esta_abierta(self) -> bool:
        return self.salida is None

    def cerrar(self, fecha_salida: datetime, operador: Operador) -> None:
        """Valida y asigna el cierre; el servicio debe gestionar flush y commit."""
        if not self.esta_abierta():
            raise ValueError("La estancia ya está cerrada.")
        if not isinstance(fecha_salida, datetime) or fecha_salida.utcoffset() is None:
            raise ValueError("La fecha de salida debe tener zona horaria.")
        if not isinstance(self.entrada, datetime) or self.entrada.utcoffset() is None:
            raise ValueError("La entrada debe estar cargada y tener zona horaria antes de cerrar.")
        if fecha_salida.astimezone(timezone.utc) < self.entrada.astimezone(timezone.utc):
            raise ValueError("La salida no puede ser anterior a la entrada.")
        if not isinstance(operador, Operador) or operador.id is None:
            raise ValueError("El operador de salida debe tener un id asignado.")
        self.salida = fecha_salida
        self.operador_salida = operador
        self.operador_salida_id = operador.id


class EstanciaReasignacion(Base):
    __tablename__ = "estancia_reasignacion"
    __table_args__ = (
        CheckConstraint(
            "motivo IS NULL OR motivo ~ '[^[:space:]]'",
            name="ck_reasignacion_motivo_no_vacio",
        ),
        Index("ix_reasignacion_estancia_fecha", "estancia_id", "fecha"),
        Index("ix_reasignacion_operador", "operador_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estancia_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("estancia.id", name="fk_reasignacion_estancia", ondelete="RESTRICT"),
        nullable=False,
    )
    celda_anterior_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("celda.id", name="fk_reasignacion_celda_anterior", ondelete="RESTRICT"),
        nullable=False,
    )
    celda_nueva_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("celda.id", name="fk_reasignacion_celda_nueva", ondelete="RESTRICT"),
        nullable=False,
    )
    operador_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operador.id", name="fk_reasignacion_operador", ondelete="RESTRICT"),
        nullable=False,
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    estancia: Mapped[Estancia] = relationship()
    celda_anterior: Mapped[Celda] = relationship(foreign_keys=[celda_anterior_id])
    celda_nueva: Mapped[Celda] = relationship(foreign_keys=[celda_nueva_id])
    operador: Mapped[Operador] = relationship()

    @validates("motivo")
    def validate_motivo(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("motivo debe ser texto.")
        value = value.strip()
        return value or None


class Sesion(Base):
    """Sesión persistida de un operador.

    Solo se almacena el SHA-256 del token compacto. El token en claro nunca se
    guarda en la base de datos.
    """

    __tablename__ = "sesion"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sesion_token_hash"),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_sesion_token_hash_formato"),
        CheckConstraint("expira_en > creada_en", name="ck_sesion_fechas"),
        CheckConstraint(
            "revocada_en IS NULL OR revocada_en >= creada_en",
            name="ck_sesion_revocada",
        ),
        Index("ix_sesion_operador_creada", "operador_id", "creada_en"),
        Index(
            "ix_sesion_vigente",
            "expira_en",
            postgresql_where=text("revocada_en IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    operador_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("operador.id", name="fk_sesion_operador", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    operador: Mapped[Operador] = relationship()

    @validates("token_hash")
    def validate_token_hash(self, key: str, value: str) -> str:
        if not isinstance(value, str) or not TOKEN_HASH_RE.fullmatch(value):
            raise ValueError("token_hash debe ser un SHA-256 hexadecimal.")
        return value

    @validates("expira_en", "revocada_en")
    def validate_fecha(self, key: str, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError(f"{key} debe incluir zona horaria.")
        return value

    def esta_vigente(self, ahora: datetime) -> bool:
        return self.revocada_en is None and self.expira_en > ahora

"""Modelos iniciales. Importar este módulo no crea tablas ni abre conexiones."""

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates

ROLES_OPERADOR = frozenset({"ADMINISTRADOR", "OPERADOR"})
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72
USUARIO_RE = re.compile(r"^[a-z0-9._-]{3,50}$")
CORREO_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FICHO_RE = re.compile(r"^AC-\d{8}-\d{4}$")
TOKEN_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


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

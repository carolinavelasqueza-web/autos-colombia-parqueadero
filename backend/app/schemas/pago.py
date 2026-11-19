from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)

from app.models import MAX_MOTIVO_ANULACION, required_text
from app.schemas.tarifa import MontoTexto, TipoTarifa

MetodoPago = Literal["EFECTIVO", "TRANSFERENCIA", "TARJETA"]
EstadoPago = Literal["VIGENTE", "ANULADO"]
Documento = Annotated[str, BeforeValidator(lambda value: required_text(value, "documento"))]
MesesPago = Annotated[int, Field(strict=True, ge=1, le=12)]
VehiculoId = Annotated[int, Field(strict=True, ge=1)]


class PagoCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documento: Documento
    meses: MesesPago
    metodo: MetodoPago
    referencia: str | None = None
    # Vehículos a liquidar. Si se omite (None), se cobran todos los del cliente;
    # si se envía, debe traer al menos un id, sin repetidos, y todos del cliente.
    vehiculo_ids: list[VehiculoId] | None = None

    @field_validator("vehiculo_ids")
    @classmethod
    def vehiculo_ids_validos(cls, value):
        if value is None:
            return None
        if len(value) == 0:
            raise ValueError("Debes seleccionar al menos un vehículo.")
        if len(set(value)) != len(value):
            raise ValueError("Los vehículos seleccionados no pueden repetirse.")
        return value


class PagoAnular(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: str = Field(min_length=1, max_length=MAX_MOTIVO_ANULACION)

    @field_validator("motivo", mode="before")
    @classmethod
    def motivo_normalizado(cls, value):
        if not isinstance(value, str):
            raise ValueError("motivo debe ser texto.")
        value = value.strip()
        if not value:
            raise ValueError("El motivo de anulación es obligatorio.")
        return value


class ClientePagoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    documento: str
    nombre: str
    telefono: str
    correo: str
    activo: bool
    fecha_vencimiento: date | None


class PagoDetalleRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    vehiculo_id: int
    placa: str
    tipo: TipoTarifa
    tarifa_aplicada: MontoTexto
    subtotal: MontoTexto


class PagoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    numero_recibo: str
    cliente: ClientePagoRespuesta
    detalles: list[PagoDetalleRespuesta]
    meses: int
    metodo: MetodoPago
    referencia: str | None
    monto: MontoTexto
    estado: EstadoPago
    periodo_desde: date
    periodo_hasta: date
    vencimiento_anterior: date | None
    reactivo_cliente: bool
    operador_id: int
    fecha: datetime
    motivo: str | None = None
    anulado_por: int | None = None
    anulado_en: datetime | None = None


class PagosPagina(BaseModel):
    items: list[PagoRespuesta]
    total: int
    offset: int
    limit: int

from datetime import date
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models import required_text, validate_correo
from app.services.mensualidad import EstadoMensualidad

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
Correo = Annotated[str, BeforeValidator(validate_correo)]
Activo = Annotated[bool, Field(strict=True)]


class ClienteCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documento: Texto
    nombre: Texto
    telefono: Texto
    correo: Correo
    activo: Activo = True


class ClienteActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documento: Texto | None = None
    nombre: Texto | None = None
    telefono: Texto | None = None
    correo: Correo | None = None
    activo: Activo | None = None

    @model_validator(mode="before")
    @classmethod
    def fecha_vencimiento_solo_lectura(cls, value):
        if isinstance(value, dict) and "fecha_vencimiento" in value:
            raise ValueError(
                "fecha_vencimiento es de solo lectura y se actualiza solo con pagos."
            )
        return value

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class ClienteResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    documento: str
    nombre: str
    telefono: str
    correo: str
    activo: bool


class ClienteRespuesta(ClienteResumen):
    fecha_vencimiento: date | None = None


class ClientesPagina(BaseModel):
    items: list[ClienteRespuesta]
    total: int
    offset: int
    limit: int


class MensualidadRespuesta(BaseModel):
    cliente: ClienteRespuesta
    estado: EstadoMensualidad


class ClientesMensualidadPagina(BaseModel):
    items: list[MensualidadRespuesta]
    total: int
    offset: int
    limit: int

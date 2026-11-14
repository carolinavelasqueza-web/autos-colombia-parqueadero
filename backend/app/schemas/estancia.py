from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models import FICHO_RE, required_text
from app.schemas.celda import CeldaRespuesta
from app.schemas.cliente import ClienteResumen
from app.schemas.puerta import PuertaRespuesta
from app.schemas.vehiculo import Placa, VehiculoRespuesta

Identificador = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]


def _ficho_upper(value: str) -> str:
    return required_text(value, "ficho_codigo").upper()


def _validar_ficho(value: str) -> str:
    if not FICHO_RE.fullmatch(value):
        raise ValueError("ficho_codigo debe tener el formato AC-YYYYMMDD-XXXX.")
    return value


FichoCodigo = Annotated[
    str, BeforeValidator(_ficho_upper), AfterValidator(_validar_ficho)
]


class EntradaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    placa: Placa
    puerta_entrada_id: Identificador


class SalidaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ficho_codigo: FichoCodigo
    puerta_salida_id: Identificador


class EstanciaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehiculo_id: Identificador | None = None
    celda_id: Identificador | None = None
    entrada: datetime | None = None
    salida: datetime | None = None

    @field_validator("vehiculo_id", "celda_id", "entrada", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value

    @field_validator("entrada", "salida")
    @classmethod
    def fechas_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La fecha debe incluir zona horaria.")
        return value.astimezone(timezone.utc)


class ReasignacionCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    celda_nueva_id: Identificador
    motivo: str | None = Field(default=None, max_length=500)

    @field_validator("motivo", mode="before")
    @classmethod
    def motivo_normalizado(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("motivo debe ser texto.")
        value = value.strip()
        return value or None


class EstanciaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehiculo_id: int
    celda_id: int
    entrada: datetime
    salida: datetime | None
    operador_entrada_id: int
    operador_salida_id: int | None
    ficho_codigo: str | None = None
    ficho_usado_en: datetime | None = None
    puerta_entrada_id: int | None = None
    puerta_salida_id: int | None = None

    @field_validator("entrada", "salida", "ficho_usado_en")
    @classmethod
    def fechas_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None


class EstanciaAbiertaRespuesta(EstanciaRespuesta):
    celda: CeldaRespuesta
    puerta_entrada: PuertaRespuesta | None = None


class EstadoVehiculoRespuesta(BaseModel):
    vehiculo: VehiculoRespuesta
    esta_dentro: bool
    estancia: EstanciaAbiertaRespuesta | None


class EstanciaActivaRespuesta(BaseModel):
    """Fila de la vista de vehículos actualmente dentro."""

    id: int
    vehiculo: VehiculoRespuesta
    celda: CeldaRespuesta
    entrada: datetime
    ficho_codigo: str | None = None
    permanencia_minutos: int = Field(ge=0)

    @field_validator("entrada")
    @classmethod
    def entrada_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class EstanciasActivasPagina(BaseModel):
    items: list[EstanciaActivaRespuesta]
    total: int
    offset: int
    limit: int


class FichoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ficho_codigo: str
    entrada: datetime
    salida: datetime | None
    ficho_usado_en: datetime | None
    vehiculo: VehiculoRespuesta
    celda: CeldaRespuesta
    puerta_entrada: PuertaRespuesta | None
    puerta_salida: PuertaRespuesta | None
    operador_entrada_id: int
    operador_salida_id: int | None
    cliente: ClienteResumen | None = None

    @field_validator("entrada", "salida", "ficho_usado_en")
    @classmethod
    def fechas_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None


class ReasignacionRespuesta(BaseModel):
    id: int
    estancia_id: int
    celda_anterior: CeldaRespuesta
    celda_nueva: CeldaRespuesta
    operador_id: int
    fecha: datetime
    motivo: str | None
    estancia: EstanciaAbiertaRespuesta

    @field_validator("fecha")
    @classmethod
    def fecha_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

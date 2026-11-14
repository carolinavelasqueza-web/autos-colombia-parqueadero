from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, field_validator

from app.models import required_text

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
Codigo = Annotated[Texto, AfterValidator(str.upper)]


class CeldaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo
    tipo: Texto


class CeldaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo | None = None
    tipo: Texto | None = None
    activo: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class CeldaRespuesta(CeldaCrear):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    activo: bool


class CeldasPagina(BaseModel):
    items: list[CeldaRespuesta]
    total: int
    offset: int
    limit: int


class CeldaDisponible(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    codigo: str
    tipo: str
    disponible: bool


class ResumenTipoCelda(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: str
    total: int
    disponibles: int
    ocupadas: int


class DisponibilidadCeldas(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    disponibles: int
    ocupadas: int
    ocupacion_porcentaje: float
    por_tipo: list[ResumenTipoCelda]
    celdas: list[CeldaDisponible]

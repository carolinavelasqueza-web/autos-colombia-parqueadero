from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.pago import MetodoPago
from app.schemas.tarifa import MontoTexto


class OcupacionFamilia(BaseModel):
    familia: str
    capacidad: int = Field(ge=0)
    ocupadas: int = Field(ge=0)
    disponibles: int = Field(ge=0)
    porcentaje: float = Field(ge=0)


class DiaOcupacion(BaseModel):
    fecha: date
    entradas: int = Field(ge=0)
    salidas: int = Field(ge=0)
    ocupadas: int = Field(ge=0)
    porcentaje: float = Field(ge=0)


class ReporteOcupacionRespuesta(BaseModel):
    generado_en: datetime
    desde: date
    hasta: date
    capacidad_total: int = Field(ge=0)
    ocupadas: int = Field(ge=0)
    disponibles: int = Field(ge=0)
    porcentaje: float = Field(ge=0)
    entradas: int = Field(ge=0)
    salidas: int = Field(ge=0)
    permanencia_promedio_minutos: float = Field(ge=0)
    por_tipo: list[OcupacionFamilia]
    historico: list[DiaOcupacion]


class RecaudoPorMetodo(BaseModel):
    metodo: MetodoPago
    pagos: int = Field(ge=0)
    total: MontoTexto


class ReporteRecaudoRespuesta(BaseModel):
    desde: date
    hasta: date
    pagos: int = Field(ge=0)
    total: MontoTexto
    por_metodo: list[RecaudoPorMetodo]

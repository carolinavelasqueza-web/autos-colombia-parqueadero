from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer

from app.models import validate_money

TipoTarifa = Literal["MOTO", "AUTOMOVIL", "CAMIONETA"]


def _validar_valor(value):
    return validate_money(value, "valor")


ValorTarifa = Annotated[Decimal, BeforeValidator(_validar_valor)]
MontoTexto = Annotated[
    Decimal,
    PlainSerializer(
        lambda value: f"{value:.2f}", return_type=str, when_used="json"
    ),
]


class TarifaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valor: ValorTarifa


class TarifaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    tipo: TipoTarifa
    valor: MontoTexto
    vigente_desde: datetime
    vigente_hasta: datetime | None

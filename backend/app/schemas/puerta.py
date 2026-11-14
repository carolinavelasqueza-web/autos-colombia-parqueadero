from pydantic import BaseModel, ConfigDict


class PuertaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    codigo: str
    ubicacion: str
    activo: bool

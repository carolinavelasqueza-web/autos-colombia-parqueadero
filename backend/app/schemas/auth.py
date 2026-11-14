from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.models import normalize_usuario

Usuario = Annotated[str, BeforeValidator(normalize_usuario)]
ContrasenaLogin = Annotated[str, Field(min_length=1, max_length=72)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: Usuario
    contrasena: ContrasenaLogin


class TokenRespuesta(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UsuarioActualRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    nombre: str
    usuario: str
    rol: Literal["ADMINISTRADOR", "OPERADOR"]
    activo: bool

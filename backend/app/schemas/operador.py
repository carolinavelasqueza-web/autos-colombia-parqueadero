from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models import normalize_usuario, required_text, validate_password

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
Usuario = Annotated[str, BeforeValidator(normalize_usuario)]
Contrasena = Annotated[str, BeforeValidator(validate_password)]
Rol = Literal["ADMINISTRADOR", "OPERADOR"]
Activo = Annotated[bool, Field(strict=True)]


class OperadorCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Texto
    telefono: Texto
    usuario: Usuario
    contrasena: Contrasena
    rol: Rol = "OPERADOR"
    activo: Activo = True


class OperadorActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Texto | None = None
    telefono: Texto | None = None
    usuario: Usuario | None = None
    contrasena: Contrasena | None = None
    rol: Rol | None = None
    activo: Activo | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class OperadorRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    nombre: str
    telefono: str
    usuario: str
    rol: Rol
    activo: bool


class OperadoresPagina(BaseModel):
    items: list[OperadorRespuesta]
    total: int
    offset: int
    limit: int

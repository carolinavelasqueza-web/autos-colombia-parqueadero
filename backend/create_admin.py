"""Crea el primer administrador sin dejar credenciales por defecto en el código."""

import getpass
import os
import sys

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import ConfigurationError
from app.database import get_engine
from app.models import Operador
from app.schemas.operador import OperadorCrear
from app.services.auditoria import registrar_auditoria
from app.services.auth import hash_password


def _value(name: str, prompt: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    return input(prompt).strip()


def _password() -> str:
    value = os.getenv("ADMIN_CONTRASENA", "")
    if value:
        return value
    first = getpass.getpass("Contraseña del administrador: ")
    second = getpass.getpass("Confirma la contraseña: ")
    if first != second:
        raise ValueError("Las contraseñas no coinciden.")
    return first


def main() -> int:
    try:
        data = OperadorCrear(
            nombre=_value("ADMIN_NOMBRE", "Nombre: "),
            telefono=_value("ADMIN_TELEFONO", "Teléfono: "),
            usuario=_value("ADMIN_USUARIO", "Usuario: "),
            contrasena=_password(),
            rol="ADMINISTRADOR",
            activo=True,
        )
    except (ConfigurationError, ValidationError, ValueError) as error:
        print(f"No se pudo crear el administrador: {error}", file=sys.stderr)
        return 2

    try:
        with Session(get_engine()) as session:
            existing = session.scalar(select(Operador).where(Operador.usuario == data.usuario))
            if existing is not None:
                print("Ya existe un operador con ese usuario.", file=sys.stderr)
                return 1
            admin = Operador(
                nombre=data.nombre,
                telefono=data.telefono,
                usuario=data.usuario,
                contrasena_hash=hash_password(data.contrasena),
                rol="ADMINISTRADOR",
                activo=True,
            )
            session.add(admin)
            session.flush()
            registrar_auditoria(
                session,
                admin,
                "CREAR",
                "operador",
                admin.id,
                {"rol": admin.rol, "activo": True, "origen": "bootstrap"},
            )
            session.commit()
            print(f"Administrador creado con id {admin.id}.")
            return 0
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print("No se pudo completar la operación con la base de datos.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

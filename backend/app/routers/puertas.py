from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.puerta import PuertaRespuesta
from app.security import CurrentUser
from app.services.auth import AuthError
from app.services.puerta import listar_puertas

router = APIRouter(prefix="/puertas", tags=["Puertas"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[PuertaRespuesta])
def listar(
    session: DatabaseSession,
    actor: CurrentUser,
    incluir_inactivas: Annotated[bool, Query()] = False,
) -> list[PuertaRespuesta]:
    if incluir_inactivas and actor.rol != "ADMINISTRADOR":
        raise AuthError(403, "No tienes permisos para esta operación.")
    return listar_puertas(session, incluir_inactivas)

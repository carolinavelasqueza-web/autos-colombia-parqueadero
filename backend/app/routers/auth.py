from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.auth import LoginRequest, TokenRespuesta, UsuarioActualRespuesta
from app.security import CurrentSesion, CurrentUser
from app.services import auth as service

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("/login", response_model=TokenRespuesta)
def login(data: LoginRequest, session: DatabaseSession) -> TokenRespuesta:
    return service.login(session, data)


@router.post("/logout", status_code=204)
def logout(session: DatabaseSession, actual: CurrentSesion) -> Response:
    service.logout(session, actual.sesion, actual.operador)
    return Response(status_code=204)


@router.get("/me", response_model=UsuarioActualRespuesta)
def me(current_user: CurrentUser) -> Operador:
    return current_user

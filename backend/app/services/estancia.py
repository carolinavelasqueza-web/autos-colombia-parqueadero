import random
from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.capacidad import MENSAJE_SIN_CELDAS, limite_familia
from app.models import Celda, Estancia, Operador, Puerta, Vehiculo, required_text
from app.schemas.celda import CeldaRespuesta
from app.schemas.cliente import ClienteResumen
from app.schemas.estancia import (
    EntradaCrear, SalidaCrear, EstanciaActualizar, EstanciaRespuesta,
    EstanciaAbiertaRespuesta, EstanciaActivaRespuesta, EstanciasActivasPagina,
    EstadoVehiculoRespuesta, FichoRespuesta,
)
from app.schemas.puerta import PuertaRespuesta
from app.schemas.vehiculo import VehiculoRespuesta
from app.services.auditoria import auditar, registrar_auditoria
from app.services.celda import celdas_libres_para
from app.services.ficho import FichoAgotado, generar_ficho
from app.services.mensualidad import SIN_PAGO, VENCIDA, estado_mensualidad
from app.tipos import (
    FAMILIA_POR_TIPO,
    MENSAJE_TIPO_INCOMPATIBLE,
    familia_tipo,
    tipos_compatibles,
)

CAMPOS_AUDITADOS = (
    "vehiculo_id",
    "celda_id",
    "entrada",
    "salida",
    "operador_entrada_id",
    "operador_salida_id",
    "ficho_codigo",
    "ficho_usado_en",
    "puerta_entrada_id",
    "puerta_salida_id",
)


class EstanciaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def transaccion(operation):
    """Confirma o revierte la sesión compartida con la dependencia de autenticación."""
    @wraps(operation)
    def wrapped(self, *args, **kwargs):
        try:
            result = operation(self, *args, **kwargs)
            self.session.commit()
            return result
        except IntegrityError as error:
            self.session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505":
                if constraint == "uq_estancia_vehiculo_abierta":
                    raise EstanciaError(409, "El vehículo ya está dentro.") from None
                if constraint == "uq_estancia_celda_abierta":
                    raise EstanciaError(409, "La celda está ocupada.") from None
                if constraint == "uq_estancia_ficho_codigo":
                    raise EstanciaError(409, "El ficho ya existe. Registra la entrada nuevamente.") from None
            if code == "23503":
                if constraint == "fk_reasignacion_estancia":
                    raise EstanciaError(
                        409, "La estancia tiene reasignaciones registradas y no se puede anular."
                    ) from None
                raise EstanciaError(404, "Una de las referencias ya no existe. Actualiza los datos.") from None
            if code in {"23502", "23514"}:
                raise EstanciaError(422, "Los datos incumplen las restricciones de la estancia.") from None
            raise EstanciaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            self.session.rollback()
            raise EstanciaError(503, "No se pudo completar la operación con la base de datos.") from None
        except Exception:
            self.session.rollback()
            raise
    return wrapped


class ServicioEstancia:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _vehiculo(self, placa: str) -> Vehiculo:
        vehiculo = self.session.scalar(
            select(Vehiculo)
            .options(selectinload(Vehiculo.cliente))
            .where(Vehiculo.placa == placa)
        )
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no encontrado.")
        return vehiculo

    def _validar_mensualidad(self, vehiculo: Vehiculo) -> None:
        """Exige cliente activo y mensualidad no vencida para registrar la entrada."""
        cliente = vehiculo.cliente
        if cliente is None:
            raise EstanciaError(409, "Vehículo no registrado.")
        if cliente.activo is not True:
            raise EstanciaError(409, "Cliente inactivo.")
        if estado_mensualidad(cliente.fecha_vencimiento) in {VENCIDA, SIN_PAGO}:
            raise EstanciaError(409, "Mensualidad vencida.")

    def _puerta(self, puerta_id: int) -> Puerta:
        puerta = self.session.get(Puerta, puerta_id)
        if puerta is None:
            raise EstanciaError(404, "Puerta no encontrada.")
        if puerta.activo is not True:
            raise EstanciaError(409, "La puerta no está activa.")
        return puerta

    def _estancia(self, estancia_id: int) -> Estancia:
        estancia = self.session.scalar(
            select(Estancia).where(Estancia.id == estancia_id).with_for_update()
        )
        if estancia is None:
            raise EstanciaError(404, "Estancia no encontrada.")
        return estancia

    def _ocupacion_familia(self, tipo_vehiculo: str) -> int:
        familia = familia_tipo(tipo_vehiculo)
        tipos = [tipo for tipo, grupo in FAMILIA_POR_TIPO.items() if grupo == familia]
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Estancia)
                .join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id)
                .where(Estancia.salida.is_(None), Vehiculo.tipo.in_(tipos))
            )
            or 0
        )

    def _asignar_celda(
        self, vehiculo: Vehiculo, operador: Operador, puerta: Puerta
    ) -> tuple[Estancia, Celda]:
        """Elige una celda libre y un ficho, reintentando si otra entrada se adelanta."""
        for _intento in range(5):
            libres = celdas_libres_para(self.session, vehiculo.tipo)
            if not libres:
                raise EstanciaError(409, MENSAJE_SIN_CELDAS)
            celda = random.choice(libres)
            try:
                ficho = generar_ficho(self.session)
            except FichoAgotado:
                raise EstanciaError(409, "No se pudo generar el ficho de entrada.") from None
            estancia = Estancia(
                vehiculo_id=vehiculo.id,
                celda_id=celda.id,
                operador_entrada_id=operador.id,
                entrada=datetime.now(timezone.utc),
                ficho_codigo=ficho,
                puerta_entrada_id=puerta.id,
            )
            try:
                with self.session.begin_nested():
                    self.session.add(estancia)
                    self.session.flush()
                return estancia, celda
            except IntegrityError as error:
                code = getattr(error.orig, "sqlstate", None)
                constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                if code == "23505" and constraint == "uq_estancia_vehiculo_abierta":
                    raise EstanciaError(409, "El vehículo ya está dentro.") from None
                if code == "23505" and constraint == "uq_estancia_ficho_codigo":
                    continue
                if code == "23505" and constraint == "uq_estancia_celda_abierta":
                    continue
                raise
        raise EstanciaError(409, MENSAJE_SIN_CELDAS)

    @transaccion
    def entrada(self, data: EntradaCrear, operador: Operador) -> EstanciaAbiertaRespuesta:
        puerta = self._puerta(data.puerta_entrada_id)
        vehiculo = self._vehiculo(data.placa)
        self._validar_mensualidad(vehiculo)
        if self.session.scalar(select(Estancia.id).where(
            Estancia.vehiculo_id == vehiculo.id, Estancia.salida.is_(None)
        )) is not None:
            raise EstanciaError(409, "El vehículo ya está dentro.")

        limite = limite_familia(vehiculo.tipo)
        if limite is None or self._ocupacion_familia(vehiculo.tipo) >= limite:
            raise EstanciaError(409, MENSAJE_SIN_CELDAS)

        estancia, celda = self._asignar_celda(vehiculo, operador, puerta)
        registrar_auditoria(
            self.session,
            operador,
            "ENTRADA",
            "estancia",
            estancia.id,
            {
                "placa": vehiculo.placa,
                "celda_id": celda.id,
                "ficho_codigo": estancia.ficho_codigo,
                "puerta_entrada_id": puerta.id,
            },
        )
        return EstanciaAbiertaRespuesta(
            **EstanciaRespuesta.model_validate(estancia).model_dump(),
            celda=CeldaRespuesta.model_validate(celda),
            puerta_entrada=PuertaRespuesta.model_validate(puerta),
        )

    @transaccion
    def salida(self, data: SalidaCrear, operador: Operador) -> EstanciaRespuesta:
        # El ficho es único y se bloquea para que dos lecturas no cierren dos veces.
        estancia = self.session.scalar(
            select(Estancia)
            .where(Estancia.ficho_codigo == data.ficho_codigo)
            .with_for_update()
        )
        if estancia is None:
            raise EstanciaError(404, "Ficho no encontrado.")
        if not estancia.esta_abierta():
            raise EstanciaError(409, "La estancia ya está cerrada.")
        if estancia.ficho_usado_en is not None:
            raise EstanciaError(409, "El ficho ya fue utilizado.")
        puerta = self._puerta(data.puerta_salida_id)
        # La relación de salida debe apuntar al operador persistido en esta sesión.
        operador_salida = self.session.get(Operador, operador.id)
        if operador_salida is None:
            raise EstanciaError(404, "Operador no encontrado.")

        ahora = datetime.now(timezone.utc)
        try:
            estancia.cerrar(ahora, operador_salida)
        except ValueError:
            raise EstanciaError(409, "No se puede cerrar la estancia con su estado o fecha actuales.") from None
        estancia.ficho_usado_en = ahora
        estancia.puerta_salida_id = puerta.id
        self.session.flush()
        registrar_auditoria(
            self.session,
            operador,
            "SALIDA",
            "estancia",
            estancia.id,
            {
                "placa": estancia.vehiculo.placa,
                "celda_id": estancia.celda_id,
                "ficho_codigo": estancia.ficho_codigo,
                "puerta_salida_id": puerta.id,
            },
        )
        return EstanciaRespuesta.model_validate(estancia)

    def ficho(self, estancia_id: int) -> FichoRespuesta:
        estancia = self.session.scalar(
            select(Estancia)
            .options(
                selectinload(Estancia.vehiculo).selectinload(Vehiculo.cliente),
                selectinload(Estancia.celda),
                selectinload(Estancia.puerta_entrada),
                selectinload(Estancia.puerta_salida),
            )
            .where(Estancia.id == estancia_id)
        )
        if estancia is None:
            raise EstanciaError(404, "Estancia no encontrada.")
        if estancia.ficho_codigo is None:
            raise EstanciaError(409, "La estancia no tiene ficho.")
        cliente = estancia.vehiculo.cliente
        return FichoRespuesta(
            id=estancia.id,
            ficho_codigo=estancia.ficho_codigo,
            entrada=estancia.entrada,
            salida=estancia.salida,
            ficho_usado_en=estancia.ficho_usado_en,
            vehiculo=VehiculoRespuesta.model_validate(estancia.vehiculo),
            celda=CeldaRespuesta.model_validate(estancia.celda),
            puerta_entrada=(
                PuertaRespuesta.model_validate(estancia.puerta_entrada)
                if estancia.puerta_entrada is not None
                else None
            ),
            puerta_salida=(
                PuertaRespuesta.model_validate(estancia.puerta_salida)
                if estancia.puerta_salida is not None
                else None
            ),
            operador_entrada_id=estancia.operador_entrada_id,
            operador_salida_id=estancia.operador_salida_id,
            cliente=ClienteResumen.model_validate(cliente) if cliente is not None else None,
        )

    @transaccion
    @auditar(
        accion="ACTUALIZAR",
        entidad="estancia",
        id_arg="estancia_id",
        modelo=Estancia,
        campos=CAMPOS_AUDITADOS,
        actor_arg="operador",
    )
    def actualizar(
        self, estancia_id: int, data: EstanciaActualizar, operador: Operador
    ) -> EstanciaRespuesta:
        estancia = self._estancia(estancia_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return EstanciaRespuesta.model_validate(estancia)

        nuevo_vehiculo: Vehiculo | None = None
        nueva_celda: Celda | None = None
        if "vehiculo_id" in changes:
            nuevo_vehiculo = self.session.get(Vehiculo, changes["vehiculo_id"])
            if nuevo_vehiculo is None:
                raise EstanciaError(404, "Vehículo no encontrado.")
        if "celda_id" in changes:
            nueva_celda = self.session.get(Celda, changes["celda_id"])
            if nueva_celda is None:
                raise EstanciaError(404, "Celda no encontrada.")
            if nueva_celda.activo is False:
                raise EstanciaError(409, "La celda no está disponible.")

        old_salida = estancia.salida

        if "vehiculo_id" in changes:
            estancia.vehiculo_id = changes["vehiculo_id"]
        if "celda_id" in changes:
            estancia.celda_id = changes["celda_id"]
        if "entrada" in changes:
            estancia.entrada = changes["entrada"]
        if "salida" in changes:
            if changes["salida"] is None:
                estancia.salida = None
                estancia.operador_salida_id = None
                # Reabrir devuelve el ficho a un estado utilizable.
                estancia.ficho_usado_en = None
                estancia.puerta_salida_id = None
            else:
                estancia.salida = changes["salida"]
                if old_salida is None:
                    estancia.operador_salida_id = operador.id
                if estancia.ficho_codigo is not None:
                    estancia.ficho_usado_en = changes["salida"]

        if (
            estancia.salida is not None
            and estancia.salida.astimezone(timezone.utc)
            < estancia.entrada.astimezone(timezone.utc)
        ):
            raise EstanciaError(422, "La salida no puede ser anterior a la entrada.")

        if estancia.salida is None:
            # Una corrección o reapertura no puede dejar una estancia abierta
            # con un vehículo en una celda de otro tipo.
            vehiculo = nuevo_vehiculo or self.session.get(Vehiculo, estancia.vehiculo_id)
            celda = nueva_celda or self.session.get(Celda, estancia.celda_id)
            if vehiculo is None or celda is None:
                raise EstanciaError(
                    404, "Una de las referencias ya no existe. Actualiza los datos."
                )
            if not tipos_compatibles(vehiculo.tipo, celda.tipo):
                raise EstanciaError(400, MENSAJE_TIPO_INCOMPATIBLE)

        return EstanciaRespuesta.model_validate(estancia)

    @transaccion
    @auditar(
        accion="ELIMINAR",
        entidad="estancia",
        id_arg="estancia_id",
        modelo=Estancia,
        campos=CAMPOS_AUDITADOS,
        actor_arg="operador",
    )
    def eliminar(self, estancia_id: int, operador: Operador) -> None:
        estancia = self._estancia(estancia_id)
        self.session.delete(estancia)

    def listar_activas(
        self, placa: str | None, offset: int, limit: int
    ) -> EstanciasActivasPagina:
        """Vehículos con estancia abierta, con búsqueda parcial por placa."""
        filters = [Estancia.salida.is_(None)]
        if placa is not None:
            valor = required_text(placa, "placa").upper()
            filters.append(Vehiculo.placa.contains(valor))

        total = int(
            self.session.scalar(
                select(func.count())
                .select_from(Estancia)
                .join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id)
                .where(*filters)
            )
            or 0
        )
        rows = self.session.scalars(
            select(Estancia)
            .join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id)
            .options(
                selectinload(Estancia.vehiculo).selectinload(Vehiculo.cliente),
                selectinload(Estancia.celda),
            )
            .where(*filters)
            .order_by(Estancia.entrada.desc(), Estancia.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        ahora = datetime.now(timezone.utc)
        items = [
            EstanciaActivaRespuesta(
                id=estancia.id,
                vehiculo=VehiculoRespuesta.model_validate(estancia.vehiculo),
                celda=CeldaRespuesta.model_validate(estancia.celda),
                entrada=estancia.entrada,
                ficho_codigo=estancia.ficho_codigo,
                permanencia_minutos=max(
                    0,
                    int(
                        (
                            ahora - estancia.entrada.astimezone(timezone.utc)
                        ).total_seconds()
                        // 60
                    ),
                ),
            )
            for estancia in rows
        ]
        return EstanciasActivasPagina(
            items=items, total=total, offset=offset, limit=limit
        )

    @transaccion
    def consultar(self, placa: str) -> EstadoVehiculoRespuesta:
        placa = required_text(placa, "placa").upper()
        # Una sola consulta da un estado consistente de vehículo, estancia y celda.
        row = self.session.execute(select(Vehiculo, Estancia, Celda).options(
            selectinload(Vehiculo.cliente),
            selectinload(Estancia.puerta_entrada),
        ).outerjoin(
            Estancia, and_(Estancia.vehiculo_id == Vehiculo.id, Estancia.salida.is_(None))
        ).outerjoin(Celda, Celda.id == Estancia.celda_id).where(Vehiculo.placa == placa)).one_or_none()
        if row is None:
            raise EstanciaError(404, "Vehículo no encontrado.")
        vehiculo, estancia, celda = row
        abierta = None
        if estancia is not None:
            abierta = EstanciaAbiertaRespuesta(
                **EstanciaRespuesta.model_validate(estancia).model_dump(),
                celda=CeldaRespuesta.model_validate(celda),
                puerta_entrada=(
                    PuertaRespuesta.model_validate(estancia.puerta_entrada)
                    if estancia.puerta_entrada is not None
                    else None
                ),
            )
        return EstadoVehiculoRespuesta(vehiculo=VehiculoRespuesta.model_validate(vehiculo),
                                       esta_dentro=estancia is not None, estancia=abierta)

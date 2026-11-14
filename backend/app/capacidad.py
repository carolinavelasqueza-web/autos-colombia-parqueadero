"""Capacidad y familias del parqueadero.

El límite es de ocupación simultánea, no de celdas configuradas: un
administrador puede crear o reactivar celdas sin restricción, pero no puede
tener más vehículos dentro de una familia que el límite indicado.
"""

from app.tipos import FAMILIA_AUTOS, FAMILIA_MOTOS, familia_tipo

LIMITES_POR_FAMILIA = {
    FAMILIA_AUTOS: 70,
    FAMILIA_MOTOS: 10,
}
MENSAJE_SIN_CELDAS = "Sin celdas disponibles"


def limite_familia(tipo: str) -> int | None:
    """Devuelve el máximo de vehículos simultáneos para el tipo recibido."""
    familia = familia_tipo(tipo)
    return LIMITES_POR_FAMILIA.get(familia) if familia is not None else None

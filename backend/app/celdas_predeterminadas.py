"""Estructura base de celdas del parqueadero.

El módulo solo contiene datos: no conecta a PostgreSQL ni crea tablas al importarse.
"""

CELDAS_PREDETERMINADAS: tuple[tuple[str, str], ...] = tuple(
    [(f"C-{numero:02d}", "AUTOMOVIL") for numero in range(1, 71)]
    + [(f"M-{numero:02d}", "MOTO") for numero in range(1, 11)]
)

CODIGOS_CELDAS_PREDETERMINADAS = frozenset(
    codigo for codigo, _tipo in CELDAS_PREDETERMINADAS
)

TOTAL_CELDAS_PREDETERMINADAS = len(CELDAS_PREDETERMINADAS)

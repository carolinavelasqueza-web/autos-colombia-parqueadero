"""Normalización compartida entre los tipos de vehículo y de celda.

El tipo de celda es texto libre, así que se compara sin acentos, sin distinguir
mayúsculas y colapsando los espacios internos. La misma regla se replica en
`frontend/src/app/models/celda.ts` para que los contadores filtren igual que la
API.

Los automóviles y las camionetas comparten la familia ``AUTOS`` y, por tanto,
el mismo conjunto de celdas y el mismo límite de ocupación. Las motos usan la
familia ``MOTOS``.
"""
import unicodedata

MENSAJE_TIPO_INCOMPATIBLE = (
    "El tipo de vehículo no corresponde al tipo de la celda seleccionada."
)

FAMILIA_AUTOS = "AUTOS"
FAMILIA_MOTOS = "MOTOS"
FAMILIA_POR_TIPO = {
    "AUTOMOVIL": FAMILIA_AUTOS,
    "CAMIONETA": FAMILIA_AUTOS,
    "MOTO": FAMILIA_MOTOS,
}


def normalizar_tipo(value: str) -> str:
    """Devuelve el tipo en mayúsculas, sin diacríticos y con espacios simples."""
    if not isinstance(value, str):
        return ""
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", value)
        if unicodedata.category(caracter) != "Mn"
    )
    return " ".join(sin_acentos.split()).upper()


def familia_tipo(value: str) -> str | None:
    """Devuelve la familia de parqueadero del tipo o ``None`` si es libre."""
    return FAMILIA_POR_TIPO.get(normalizar_tipo(value))


def tipos_compatibles(tipo_vehiculo: str, tipo_celda: str) -> bool:
    """Indica si ambos tipos pertenecen a la misma familia de celdas."""
    familia = familia_tipo(tipo_vehiculo)
    return familia is not None and familia == familia_tipo(tipo_celda)

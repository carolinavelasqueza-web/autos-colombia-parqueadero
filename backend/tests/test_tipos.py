from app.capacidad import LIMITES_POR_FAMILIA, MENSAJE_SIN_CELDAS, limite_familia
from app.tipos import (
    FAMILIA_AUTOS,
    FAMILIA_MOTOS,
    MENSAJE_TIPO_INCOMPATIBLE,
    familia_tipo,
    normalizar_tipo,
    tipos_compatibles,
)


def test_normalizar_tipo_unifica_mayusculas_acentos_y_espacios():
    assert normalizar_tipo(" automóvil ") == "AUTOMOVIL"
    assert normalizar_tipo("MOTO") == "MOTO"
    assert normalizar_tipo("  Camioneta   doble  ") == "CAMIONETA DOBLE"
    assert normalizar_tipo("AUTOMOVIL") == normalizar_tipo("Automóvil")


def test_normalizar_tipo_tolera_valores_no_textuales_o_vacios():
    assert normalizar_tipo("") == ""
    assert normalizar_tipo("   \t ") == ""
    assert normalizar_tipo(None) == ""  # type: ignore[arg-type]


def test_tipos_compatibles_comparte_la_familia_de_autos():
    assert tipos_compatibles("MOTO", "moto")
    assert tipos_compatibles("AUTOMOVIL", " Automóvil ")
    assert tipos_compatibles("CAMIONETA", "AUTOMOVIL")
    assert tipos_compatibles("AUTOMOVIL", " CAMIONETA ")
    assert not tipos_compatibles("MOTO", "AUTOMOVIL")
    assert not tipos_compatibles("CAMIONETA", "MOTO")
    assert not tipos_compatibles("MOTO", "Libre")
    assert not tipos_compatibles("", "")
    assert not tipos_compatibles("MOTO", "")


def test_familias_y_limites_de_capacidad():
    assert familia_tipo("automovil") == FAMILIA_AUTOS
    assert familia_tipo("CAMIONETA") == FAMILIA_AUTOS
    assert familia_tipo("moto") == FAMILIA_MOTOS
    assert familia_tipo("Libre") is None
    assert limite_familia("CAMIONETA") == 70
    assert limite_familia("MOTO") == 10
    assert limite_familia("Libre") is None
    assert LIMITES_POR_FAMILIA == {FAMILIA_AUTOS: 70, FAMILIA_MOTOS: 10}
    assert MENSAJE_SIN_CELDAS == "Sin celdas disponibles"


def test_mensaje_de_rechazo_es_el_contrato_publico():
    assert MENSAJE_TIPO_INCOMPATIBLE == (
        "El tipo de vehículo no corresponde al tipo de la celda seleccionada."
    )

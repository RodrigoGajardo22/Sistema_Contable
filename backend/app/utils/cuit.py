"""Validación de CUIT (11 dígitos con dígito verificador)."""

import re

PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def normalizar_cuit(cuit: str | None) -> str:
    return re.sub(r"\D", "", cuit or "")


def cuit_valido(cuit: str | None) -> bool:
    """Algoritmo de dígito verificador de AFIP.

    Acepta el CUIT con o sin guiones; siempre se normaliza a 11 dígitos.
    """
    digitos = normalizar_cuit(cuit)

    if len(digitos) != 11:
        return False

    total = sum(int(digito) * peso for digito, peso in zip(digitos[:10], PESOS))
    resto = total % 11
    verificador = 11 - resto

    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        # AFIP reemplaza el 10 por 9 (caso de personas físicas con prefijo 23).
        verificador = 9

    return verificador == int(digitos[10])


def formatear_cuit(cuit: str | None) -> str:
    digitos = normalizar_cuit(cuit)
    if len(digitos) != 11:
        return digitos
    return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10]}"

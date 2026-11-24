"""Hashing de contraseñas con Argon2id.

Parámetros: los defaults de argon2-cffi, que están alineados con la
recomendación de OWASP (t=3, m=64 MiB, p=4). El hash resultante es un string
PHC que incluye el algoritmo y los parámetros:

    $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>
"""

import os
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


def _parametros_desde_entorno() -> dict:
    """Parámetros de Argon2, configurables por entorno.

    En tests se bajan para que la suite sea rápida (ver tests/conftest.py).
    En desarrollo y producción valen los defaults de OWASP.
    """
    return {
        "time_cost": int(os.getenv("ARGON2_TIME_COST", "3")),
        "memory_cost": int(os.getenv("ARGON2_MEMORY_COST", "65536")),
        "parallelism": int(os.getenv("ARGON2_PARALLELISM", "4")),
    }


_hasher = PasswordHasher(**_parametros_desde_entorno())

# Hash descartable para igualar tiempos cuando el email no existe.
# Se calcula una sola vez al importar el módulo.
HASH_DESCARTABLE = _hasher.hash("hash-descartable-para-timing")


def hashear_password(password: str) -> str:
    return _hasher.hash(password)


def verificar_password(password: str, hash_guardado: str | None) -> bool:
    if not hash_guardado:
        return False
    try:
        return _hasher.verify(hash_guardado, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generar_password_temporal(largo: int = 16) -> str:
    """Clave aleatoria legible para entregar una sola vez.

    Garantiza al menos una minúscula, una mayúscula y un dígito. No usa
    caracteres ambiguos (O/0, I/l/1) para que se pueda dictar sin errores.
    """
    letras = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    digitos = "23456789"
    simbolos = "!@#$%&*"
    alfabeto = letras + digitos + simbolos

    while True:
        clave = "".join(secrets.choice(alfabeto) for _ in range(largo))
        if (
            any(caracter in letras.lower() for caracter in clave)
            and any(caracter in letras.upper() for caracter in clave)
            and any(caracter in digitos for caracter in clave)
        ):
            return clave


def necesita_rehash(hash_guardado: str) -> bool:
    """True si el hash se generó con parámetros más débiles que los actuales."""
    try:
        return _hasher.check_needs_rehash(hash_guardado)
    except (InvalidHashError, VerificationError):
        return True

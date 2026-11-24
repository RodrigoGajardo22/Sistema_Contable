"""Rate limiting de la API.

Los contadores viven en Redis (el storage lo configura Limiter desde
RATELIMIT_STORAGE_URI). En tests se usa memoria: un solo proceso.

Convención de límites:
  - Global: 300 requests/minuto por IP (red de seguridad).
  - Login por IP: 30 fallos / 15 min (frena fuerza bruta distribuida).
  - Login por cuenta: 3 fallos / 15 min (protege la cuenta puntual).

``deduct_when`` hace que sólo los 401 consuman intentos: un payload inválido
(422), un error interno (500) o una request ya bloqueada no descuentan.
"""

import os

from flask import request
from flask_limiter.util import get_remote_address

LIMITE_LOGIN_POR_EMAIL = os.getenv("LOGIN_LIMITE_EMAIL", "3 per 15 minutes")
LIMITE_LOGIN_POR_IP = os.getenv("LOGIN_LIMITE_IP", "30 per 15 minutes")


def clave_email_login() -> str:
    """Clave del límite por cuenta: el email tal como lo escribió el usuario.

    Si el body no trae un email (payload roto), cae a la IP para que el
    límite no se pueda esquivar mandando basura.
    """
    datos = request.get_json(silent=True) or {}
    email = str(datos.get("email") or "").strip().lower()
    return email or f"ip:{get_remote_address()}"


def contar_solo_fallos(respuesta) -> bool:
    """Sólo las credenciales inválidas consumen intentos."""
    return respuesta.status_code == 401

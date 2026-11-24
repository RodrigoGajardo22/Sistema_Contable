"""Configuración de la aplicación por entorno.

La configuración se elige con la variable APP_ENV (development | production |
testing). En desarrollo y producción, DATABASE_URL y REDIS_URL las inyecta
Compose; el backend nunca las construye por su cuenta.
"""

import os
from datetime import timedelta


def _entero(nombre: str, por_defecto: int) -> int:
    try:
        return int(os.getenv(nombre, por_defecto))
    except (TypeError, ValueError):
        return por_defecto


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-no-usar-en-produccion")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-no-usar-en-produccion-32-bytes")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=_entero("JWT_ACCESS_MINUTES", 15))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=_entero("JWT_REFRESH_MINUTES", 10080))
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"

    # Rate limiting: en dev/prod el storage es Redis (lo inyecta Compose).
    RATELIMIT_STORAGE_URI = os.getenv("REDIS_URL", "memory://")
    RATELIMIT_STRATEGY = "moving-window"
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_KEY_PREFIX = "sistema-contable"

    # Detrás del gateway hay exactamente un proxy (nginx).
    PROXY_FIX_HOPS = _entero("PROXY_FIX_HOPS", 1)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = os.getenv("SQL_ECHO", "0") == "1"


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}
    JWT_SECRET_KEY = "testing-clave-de-al-menos-32-bytes"
    # Sin Redis en tests: un solo proceso, contadores deterministas.
    RATELIMIT_STORAGE_URI = "memory://"


CONFIGURACIONES = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(nombre: str | None = None) -> type[Config]:
    clave = (nombre or os.getenv("APP_ENV", "development")).lower()
    if clave not in CONFIGURACIONES:
        raise RuntimeError(
            f"APP_ENV desconocido: {clave!r}. Usá development, production o testing."
        )
    return CONFIGURACIONES[clave]

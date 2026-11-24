"""Fábrica de la aplicación Flask.

Flujo de una request: ruta (blueprint) → controlador → servicio → modelo.
"""

import os

from flask import Flask, g
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from app.cli import register_cli
from app.config import get_config
from app.extensions import db, jwt, limiter, migrate
from app.routes import register_blueprints
from app.utils.errors import register_error_handlers, register_jwt_handlers


def _configurar_cors(app: Flask) -> None:
    origenes = [
        origen.strip()
        for origen in os.getenv("CORS_ORIGINS", "").split(",")
        if origen.strip()
    ]
    # En dev y prod todo entra por el gateway (mismo origen): si no hay
    # orígenes configurados, no hace falta CORS.
    if origenes:
        CORS(app, origins=origenes)


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    app.json.sort_keys = False
    app.json.ensure_ascii = False

    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        raise RuntimeError(
            "Falta DATABASE_URL. En desarrollo y producción la inyecta Compose "
            "a partir de infra/.env.* (ver AGENTS.md)."
        )

    saltos_proxy = app.config.get("PROXY_FIX_HOPS", 1)
    if saltos_proxy:
        # Detrás de nginx, request.remote_addr debe ser la IP real del cliente
        # (rate limiting por IP). nginx ya envía X-Forwarded-For.
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=saltos_proxy,
            x_proto=saltos_proxy,
            x_host=saltos_proxy,
        )

    _configurar_cors(app)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Importar los modelos después de init_app: Alembic los necesita.
    from app import models  # noqa: F401

    @app.before_request
    def _limpiar_usuario_cache() -> None:
        # En tests el app context se comparte entre requests; en producción
        # cada request ya trae su propio ``g``. Limpiar evita reutilizar un
        # usuario cacheado de otra sesión.
        g.pop("usuario", None)

    register_error_handlers(app)
    register_jwt_handlers(jwt)
    register_blueprints(app)
    register_cli(app)

    return app

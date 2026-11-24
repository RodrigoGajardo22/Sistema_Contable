"""Extensiones compartidas.

Se instancian sin app y se inicializan en create_app() para evitar ciclos de
importación entre modelos, servicios y rutas.
"""

from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
    default_limits=["300 per minute"],
)

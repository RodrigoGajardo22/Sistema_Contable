"""Endpoints de sistema: raíz de la API y healthcheck."""

from flask import Blueprint, jsonify

from app.extensions import limiter

bp = Blueprint("system", __name__, url_prefix="/api")


@bp.get("")
def home():
    return jsonify(
        {
            "mensaje": "API del sistema contable",
            "version": "0.1.0",
        }
    )


@bp.get("/health")
@limiter.exempt
def health():
    """Healthcheck usado por el gateway y por el script de desarrollo.

    Exento de rate limit: lo consulta el contenedor cada 10 segundos.
    """
    return jsonify(
        {
            "status": "ok",
            "service": "backend",
        }
    )

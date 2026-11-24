"""Documentación interactiva de la API (OpenAPI + Swagger UI).

La especificación vive en ``app/docs/openapi.yaml`` y los assets de Swagger UI
en ``app/docs/swagger-ui/`` para no depender de un CDN. El test de
``tests/test_docs.py`` verifica que todas las rutas estén documentadas.
"""

from pathlib import Path

import yaml
from flask import Blueprint, jsonify, send_from_directory

from app.extensions import limiter

bp = Blueprint("docs", __name__, url_prefix="/api")

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
SPEC_PATH = DOCS_DIR / "openapi.yaml"
SWAGGER_DIR = DOCS_DIR / "swagger-ui"


def _cargar_spec() -> dict:
    with SPEC_PATH.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


@bp.get("/openapi.json")
@limiter.exempt
def openapi_json():
    """Especificación OpenAPI en JSON para Swagger UI y clientes."""
    return jsonify(_cargar_spec())


@bp.get("/docs")
@limiter.exempt
def swagger_ui():
    """Interfaz de Swagger UI."""
    return send_from_directory(SWAGGER_DIR, "index.html")


@bp.get("/docs/<path:archivo>")
@limiter.exempt
def swagger_assets(archivo: str):
    """Assets estáticos de Swagger UI (JS, CSS, favicon y licencia)."""
    return send_from_directory(SWAGGER_DIR, archivo)

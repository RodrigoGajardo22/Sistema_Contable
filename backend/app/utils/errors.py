"""Errores y respuestas uniformes de la API.

Éxito:

    {"datos": ..., "meta": {...}}          # meta es opcional

Error:

    {"error": {"codigo": "...", "mensaje": "...", "detalles": {...}}}

``codigo`` es estable y sirve para que el frontend decida (por ejemplo,
``token_expirado`` o ``demasiados_intentos``). ``mensaje`` es texto mostrable.
"""

import logging

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from app.extensions import db

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Error de negocio con código HTTP y código estable."""

    def __init__(
        self,
        mensaje: str,
        *,
        codigo: str = "error",
        status: int = 400,
        detalles: dict | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.status = status
        self.detalles = detalles


def error_json(
    codigo: str,
    mensaje: str,
    status: int,
    detalles: dict | None = None,
):
    cuerpo: dict = {"error": {"codigo": codigo, "mensaje": mensaje}}
    if detalles:
        cuerpo["error"]["detalles"] = detalles
    return jsonify(cuerpo), status


def respuesta(datos=None, status: int = 200, meta: dict | None = None):
    """Respuesta exitosa uniforme."""
    cuerpo: dict = {"datos": datos}
    if meta is not None:
        cuerpo["meta"] = meta
    return jsonify(cuerpo), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(error: ApiError):
        return error_json(error.codigo, error.mensaje, error.status, error.detalles)

    @app.errorhandler(ValidationError)
    def _validacion(error: ValidationError):
        return error_json(
            "validacion",
            "Hay datos inválidos en la solicitud.",
            422,
            error.messages,
        )

    @app.errorhandler(IntegrityError)
    def _integridad(error: IntegrityError):
        db.session.rollback()
        logger.warning("Violación de integridad: %s", error)
        return error_json(
            "conflicto",
            "La operación entra en conflicto con datos existentes.",
            409,
        )

    @app.errorhandler(429)
    def _demasiados_intentos(error):
        """Normaliza el 429 de Flask-Limiter al formato de la API."""
        segundos = 60

        # 1) Si la librería ya dejó un Retry-After, es el valor más preciso.
        try:
            original = error.get_response()
            cabecera = original.headers.get("Retry-After") if original else None
            if cabecera and cabecera.isdigit():
                segundos = int(cabecera)
        except Exception:  # pragma: no cover - defensivo
            pass

        # 2) Si no, usamos la ventana del límite que se disparó.
        if segundos == 60:
            item = getattr(getattr(error, "limit", None), "limit", None)
            try:
                if item is not None:
                    segundos = int(item.get_expiry())
            except Exception:  # pragma: no cover - defensivo
                pass

        minutos = max(1, round(segundos / 60))
        plural = "s" if minutos != 1 else ""
        cuerpo, status = error_json(
            "demasiados_intentos",
            f"Demasiados intentos fallidos. Probá de nuevo en {minutos} minuto{plural}.",
            429,
            {"reintentar_en_segundos": segundos},
        )
        cuerpo.headers["Retry-After"] = str(segundos)
        return cuerpo, status

    @app.errorhandler(HTTPException)
    def _http(error: HTTPException):
        mensajes = {
            404: "El recurso solicitado no existe.",
            405: "El método no está permitido para este recurso.",
        }
        return error_json(
            "http_error",
            mensajes.get(error.code, error.description),
            error.code or 500,
        )

    @app.errorhandler(Exception)
    def _inesperado(error: Exception):
        if app.debug:
            # En desarrollo queremos ver el traceback de Flask.
            raise error
        logger.exception("Error no controlado")
        return error_json(
            "error_interno",
            "Ocurrió un error inesperado. Intentá nuevamente.",
            500,
        )


def register_jwt_handlers(jwt: JWTManager) -> None:
    @jwt.unauthorized_loader
    def _sin_token(_motivo: str):
        return error_json(
            "token_ausente",
            "Necesitás iniciar sesión para continuar.",
            401,
        )

    @jwt.invalid_token_loader
    def _token_invalido(_motivo: str):
        return error_json("token_invalido", "La sesión no es válida.", 401)

    @jwt.expired_token_loader
    def _token_expirado(_cabecera, _payload):
        return error_json("token_expirado", "Tu sesión expiró.", 401)

    @jwt.revoked_token_loader
    def _token_revocado(_cabecera, _payload):
        return error_json("token_revocado", "La sesión fue cerrada.", 401)

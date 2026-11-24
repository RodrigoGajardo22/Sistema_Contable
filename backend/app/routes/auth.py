"""Endpoints de autenticación."""

from flask import Blueprint
from flask_jwt_extended import jwt_required
from flask_limiter.util import get_remote_address

from app.controllers.auth_controller import AuthController
from app.extensions import limiter
from app.utils.rate_limit import (
    LIMITE_LOGIN_POR_EMAIL,
    LIMITE_LOGIN_POR_IP,
    clave_email_login,
    contar_solo_fallos,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
@limiter.limit(
    LIMITE_LOGIN_POR_IP,
    key_func=get_remote_address,
    deduct_when=contar_solo_fallos,
)
@limiter.limit(
    LIMITE_LOGIN_POR_EMAIL,
    key_func=clave_email_login,
    deduct_when=contar_solo_fallos,
)
def login():
    return AuthController.login()


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    return AuthController.refresh()


@bp.get("/me")
@jwt_required()
def me():
    return AuthController.me()

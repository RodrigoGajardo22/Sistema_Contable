"""Traducción HTTP <-> servicios para autenticación."""

from flask import request

from app.schemas.usuario import LoginSchema, UsuarioSchema
from app.services.auth_service import AuthService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


class AuthController:
    @staticmethod
    def login():
        datos = LoginSchema().load(request.get_json(silent=True) or {})
        usuario = AuthService.autenticar(datos["email"], datos["password"])

        return respuesta(
            {
                "usuario": UsuarioSchema().dump(usuario),
                **AuthService.emitir_tokens(usuario),
            }
        )

    @staticmethod
    def refresh():
        usuario = usuario_actual()
        return respuesta(AuthService.renovar_access_token(usuario))

    @staticmethod
    def me():
        return respuesta(UsuarioSchema().dump(usuario_actual()))

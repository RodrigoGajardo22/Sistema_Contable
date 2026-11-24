"""Autenticación: verificación de credenciales y emisión de tokens."""

from datetime import datetime, timezone

from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db
from app.models.usuario import Usuario
from app.services.usuario_service import UsuarioService
from app.utils.errors import ApiError
from app.utils.security import HASH_DESCARTABLE, hashear_password, necesita_rehash, verificar_password


class AuthService:
    @staticmethod
    def autenticar(email: str, password: str) -> Usuario:
        """Valida email + contraseña con respuesta genérica.

        - No revela si el email existe (mismo mensaje y mismo código).
        - Si el email no existe, verifica contra un hash descartable para que
          el tiempo de respuesta no lo delate (timing attack).
        - Un usuario inactivo recibe el mismo 401: informar lo contrario
          confirmaría que la cuenta existe.
        """
        usuario = UsuarioService.por_email(email)

        hash_a_verificar = usuario.password_hash if usuario else HASH_DESCARTABLE
        coincide = verificar_password(password, hash_a_verificar)

        if usuario is None or not usuario.activo or not coincide:
            raise ApiError(
                "Email o contraseña incorrectos.",
                codigo="credenciales_invalidas",
                status=401,
            )

        # Una clave temporal vencida se trata igual que una credencial
        # inválida: no revelamos que la cuenta existe.
        expira = usuario.password_temporal_expira_en
        if expira is not None:
            if expira.tzinfo is None:
                expira = expira.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expira:
                raise ApiError(
                    "Email o contraseña incorrectos.",
                    codigo="credenciales_invalidas",
                    status=401,
                )

        # Rehash transparente si subieron los parámetros de Argon2.
        if necesita_rehash(usuario.password_hash):
            usuario.password_hash = hashear_password(password)
            db.session.commit()

        return usuario

    @staticmethod
    def emitir_tokens(usuario: Usuario) -> dict:
        identidad = str(usuario.id)
        claims = {
            "rol": usuario.rol,
            "nombre": usuario.nombre,
            "tv": usuario.token_version,
        }

        return {
            "access_token": create_access_token(
                identity=identidad, additional_claims=claims
            ),
            "refresh_token": create_refresh_token(
                identity=identidad, additional_claims=claims
            ),
            "token_type": "Bearer",
        }

    @staticmethod
    def renovar_access_token(usuario: Usuario) -> dict:
        return {
            "access_token": create_access_token(
                identity=str(usuario.id),
                additional_claims={
                    "rol": usuario.rol,
                    "nombre": usuario.nombre,
                    "tv": usuario.token_version,
                },
            ),
            "token_type": "Bearer",
        }

"""Decoradores de autenticación y autorización.

La seguridad real vive acá (backend). El frontend oculta botones, pero cada
request se valida igual.
"""

from functools import wraps

from flask import g, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.extensions import db
from app.models.usuario import Rol, Usuario
from app.utils.errors import ApiError


def _resolver_usuario() -> Usuario:
    identidad = get_jwt_identity()
    try:
        usuario_id = int(identidad)
    except (TypeError, ValueError):
        raise ApiError("La sesión no es válida.", codigo="token_invalido", status=401)

    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise ApiError(
            "Tu usuario ya no está activo.",
            codigo="usuario_inactivo",
            status=401,
        )

    # Un cambio de clave o una revocación incrementa token_version. Los JWT
    # emitidos antes dejan de servir aunque todavía no hayan vencido.
    if get_jwt().get("tv", 0) != usuario.token_version:
        raise ApiError(
            "Tu sesión expiró. Iniciá sesión de nuevo.",
            codigo="token_revocado",
            status=401,
        )
    return usuario


def usuario_actual() -> Usuario:
    """Usuario autenticado de la request (cacheado en ``g``)."""
    usuario = getattr(g, "usuario", None)
    if usuario is None:
        usuario = _resolver_usuario()
        g.usuario = usuario
    return usuario


def roles_required(*roles: str | Rol):
    """Exige un JWT válido y, opcionalmente, uno de los roles indicados.

    Sin argumentos sólo exige estar autenticado.
    """
    permitidos = {rol.value if isinstance(rol, Rol) else str(rol) for rol in roles}

    def decorador(funcion):
        @wraps(funcion)
        @jwt_required()
        def envoltura(*args, **kwargs):
            usuario = _resolver_usuario()
            g.usuario = usuario

            # Con una clave temporal el usuario sólo puede ver su perfil,
            # refrescar el token o cambiarla. El resto queda bloqueado.
            if usuario.debe_cambiar_password and request.endpoint not in {
                "auth.me",
                "auth.refresh",
                "usuarios.cambiar_password",
            }:
                raise ApiError(
                    "Tenés que cambiar la contraseña inicial antes de continuar.",
                    codigo="cambio_password_requerido",
                    status=403,
                )

            if permitidos and usuario.rol not in permitidos:
                raise ApiError(
                    "No tenés permiso para acceder a este recurso.",
                    codigo="sin_permiso",
                    status=403,
                )

            return funcion(*args, **kwargs)

        return envoltura

    return decorador

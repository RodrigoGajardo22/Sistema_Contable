"""Traducción HTTP <-> servicios para usuarios."""

from flask import request

from app.models.usuario import Usuario
from app.schemas.usuario import (
    CambioPasswordSchema,
    UsuarioCreateSchema,
    UsuarioSchema,
    UsuarioUpdateSchema,
)
from app.services.usuario_service import UsuarioService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta

_VERDADEROS = {"1", "true", "si", "sí", "s"}


class UsuarioController:
    @staticmethod
    def listar():
        activo_param = request.args.get("activo")
        activo: bool | None = None
        if activo_param is not None and activo_param != "":
            activo = activo_param.lower() in _VERDADEROS

        usuarios = UsuarioService.listar(
            q=request.args.get("q") or None,
            rol=request.args.get("rol") or None,
            activo=activo,
        )

        datos = UsuarioSchema(many=True).dump(usuarios)
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def crear():
        datos = UsuarioCreateSchema().load(request.get_json(silent=True) or {})
        usuario = UsuarioService.crear(datos, usuario_actual())
        return respuesta(UsuarioSchema().dump(usuario), status=201)

    @staticmethod
    def detalle(usuario_id: int):
        usuario = UsuarioService.obtener(usuario_id)
        return respuesta(UsuarioSchema().dump(usuario))

    @staticmethod
    def actualizar(usuario_id: int):
        datos = UsuarioUpdateSchema().load(request.get_json(silent=True) or {})
        usuario = UsuarioService.actualizar(usuario_id, datos, usuario_actual())
        return respuesta(UsuarioSchema().dump(usuario))

    @staticmethod
    def desactivar(usuario_id: int):
        actor: Usuario = usuario_actual()
        usuario = UsuarioService.desactivar(usuario_id, actor)
        return respuesta(UsuarioSchema().dump(usuario))

    @staticmethod
    def activar(usuario_id: int):
        usuario = UsuarioService.activar(usuario_id, usuario_actual())
        return respuesta(UsuarioSchema().dump(usuario))

    @staticmethod
    def transferir_propiedad(usuario_id: int):
        usuario = UsuarioService.transferir_propiedad(usuario_id, usuario_actual())
        return respuesta(UsuarioSchema().dump(usuario))

    @staticmethod
    def cambiar_password(usuario_id: int):
        datos = CambioPasswordSchema().load(request.get_json(silent=True) or {})
        UsuarioService.cambiar_password(
            usuario_id,
            actor=usuario_actual(),
            password_nueva=datos["password_nueva"],
            password_actual=datos.get("password_actual"),
        )
        return respuesta({"mensaje": "Contraseña actualizada."})

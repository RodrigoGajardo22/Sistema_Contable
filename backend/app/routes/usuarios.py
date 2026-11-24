"""Endpoints de usuarios (CRUD administrativo)."""

from flask import Blueprint

from app.controllers.usuario_controller import UsuarioController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")


@bp.get("")
@roles_required(Rol.ADMIN)
def listar():
    return UsuarioController.listar()


@bp.post("")
@roles_required(Rol.ADMIN)
def crear():
    return UsuarioController.crear()


@bp.get("/<int:usuario_id>")
@roles_required(Rol.ADMIN)
def detalle(usuario_id: int):
    return UsuarioController.detalle(usuario_id)


@bp.put("/<int:usuario_id>")
@roles_required(Rol.ADMIN)
def actualizar(usuario_id: int):
    return UsuarioController.actualizar(usuario_id)


@bp.delete("/<int:usuario_id>")
@roles_required(Rol.ADMIN)
def desactivar(usuario_id: int):
    return UsuarioController.desactivar(usuario_id)


@bp.post("/<int:usuario_id>/activar")
@roles_required(Rol.ADMIN)
def activar(usuario_id: int):
    return UsuarioController.activar(usuario_id)


@bp.put("/<int:usuario_id>/password")
@roles_required()
def cambiar_password(usuario_id: int):
    return UsuarioController.cambiar_password(usuario_id)


@bp.post("/<int:usuario_id>/propietario")
@roles_required(Rol.ADMIN)
def transferir_propiedad(usuario_id: int):
    return UsuarioController.transferir_propiedad(usuario_id)

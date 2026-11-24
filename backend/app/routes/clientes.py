"""Endpoints de clientes.

Los datos viven en versiones: cada PUT inserta una versión nueva.
"""

from flask import Blueprint

from app.controllers.cliente_controller import ClienteController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("clientes", __name__, url_prefix="/api/clientes")


@bp.get("")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def listar():
    return ClienteController.listar()


@bp.post("")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def crear():
    return ClienteController.crear()


@bp.get("/<int:cliente_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def detalle(cliente_id: int):
    return ClienteController.detalle(cliente_id)


@bp.put("/<int:cliente_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def actualizar(cliente_id: int):
    return ClienteController.actualizar(cliente_id)


@bp.delete("/<int:cliente_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def desactivar(cliente_id: int):
    return ClienteController.desactivar(cliente_id)


@bp.post("/<int:cliente_id>/activar")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def activar(cliente_id: int):
    return ClienteController.activar(cliente_id)


@bp.get("/<int:cliente_id>/historial")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def historial(cliente_id: int):
    return ClienteController.historial(cliente_id)


@bp.post("/<int:cliente_id>/acceso")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def crear_acceso(cliente_id: int):
    return ClienteController.crear_acceso(cliente_id)


@bp.post("/<int:cliente_id>/acceso/reset")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def restablecer_acceso(cliente_id: int):
    return ClienteController.restablecer_acceso(cliente_id)


@bp.delete("/<int:cliente_id>/acceso")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def revocar_acceso(cliente_id: int):
    return ClienteController.revocar_acceso(cliente_id)

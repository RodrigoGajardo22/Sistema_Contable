"""Endpoints de vencimientos."""

from flask import Blueprint

from app.controllers.vencimiento_controller import VencimientoController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("vencimientos", __name__, url_prefix="/api")


@bp.get("/vencimientos")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def listar_global():
    return VencimientoController.listar_global()


@bp.get("/clientes/<int:cliente_id>/vencimientos")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def listar(cliente_id: int):
    return VencimientoController.listar(cliente_id)


@bp.post("/clientes/<int:cliente_id>/vencimientos")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def crear(cliente_id: int):
    return VencimientoController.crear(cliente_id)


@bp.put("/vencimientos/<int:vencimiento_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def actualizar(vencimiento_id: int):
    return VencimientoController.actualizar(vencimiento_id)


@bp.post("/vencimientos/<int:vencimiento_id>/estado")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def cambiar_estado(vencimiento_id: int):
    return VencimientoController.cambiar_estado(vencimiento_id)


@bp.delete("/vencimientos/<int:vencimiento_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def eliminar(vencimiento_id: int):
    return VencimientoController.eliminar(vencimiento_id)

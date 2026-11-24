"""Endpoints de conciliación bancaria."""

from flask import Blueprint

from app.controllers.conciliacion_controller import ConciliacionController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("conciliacion", __name__, url_prefix="/api")


@bp.get("/clientes/<int:cliente_id>/extractos")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def listar(cliente_id: int):
    return ConciliacionController.listar(cliente_id)


@bp.post("/clientes/<int:cliente_id>/extractos")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def crear(cliente_id: int):
    return ConciliacionController.crear(cliente_id)


@bp.get("/extractos/<int:extracto_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def detalle(extracto_id: int):
    return ConciliacionController.detalle(extracto_id)


@bp.delete("/extractos/<int:extracto_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def eliminar(extracto_id: int):
    return ConciliacionController.eliminar(extracto_id)


@bp.put("/movimientos/<int:movimiento_id>/vincular")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def vincular(movimiento_id: int):
    return ConciliacionController.vincular(movimiento_id)


@bp.put("/movimientos/<int:movimiento_id>/descartar")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def descartar(movimiento_id: int):
    return ConciliacionController.descartar(movimiento_id)


@bp.put("/movimientos/<int:movimiento_id>/desvincular")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def desvincular(movimiento_id: int):
    return ConciliacionController.desvincular(movimiento_id)


@bp.post("/movimientos/<int:movimiento_id>/asiento")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def generar_asiento(movimiento_id: int):
    return ConciliacionController.generar_asiento(movimiento_id)

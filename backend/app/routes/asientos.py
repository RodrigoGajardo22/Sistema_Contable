"""Endpoints de asientos contables."""

from flask import Blueprint

from app.controllers.asiento_controller import AsientoController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("asientos", __name__, url_prefix="/api")


@bp.get("/clientes/<int:cliente_id>/asientos")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def listar(cliente_id: int):
    return AsientoController.listar(cliente_id)


@bp.post("/clientes/<int:cliente_id>/asientos")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def crear(cliente_id: int):
    return AsientoController.crear(cliente_id)


@bp.get("/asientos/<int:asiento_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def detalle(asiento_id: int):
    return AsientoController.detalle(asiento_id)


@bp.put("/asientos/<int:asiento_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def actualizar(asiento_id: int):
    return AsientoController.actualizar(asiento_id)


@bp.post("/asientos/<int:asiento_id>/confirmar")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def confirmar(asiento_id: int):
    return AsientoController.confirmar(asiento_id)


@bp.post("/asientos/<int:asiento_id>/anular")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def anular(asiento_id: int):
    return AsientoController.anular(asiento_id)


@bp.delete("/asientos/<int:asiento_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def descartar(asiento_id: int):
    return AsientoController.descartar(asiento_id)

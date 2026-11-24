"""Endpoints de reportes contables."""

from flask import Blueprint

from app.controllers.reporte_controller import ReporteController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("reportes", __name__, url_prefix="/api")


@bp.get("/clientes/<int:cliente_id>/reportes/diario")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def diario(cliente_id: int):
    return ReporteController.diario(cliente_id)


@bp.get("/clientes/<int:cliente_id>/reportes/mayor")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def mayor(cliente_id: int):
    return ReporteController.mayor(cliente_id)


@bp.get("/clientes/<int:cliente_id>/reportes/balance")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def balance(cliente_id: int):
    return ReporteController.balance(cliente_id)


@bp.get("/clientes/<int:cliente_id>/reportes/libro-iva")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def libro_iva(cliente_id: int):
    return ReporteController.libro_iva(cliente_id)

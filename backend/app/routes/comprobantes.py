"""Endpoints de comprobantes."""

from flask import Blueprint

from app.controllers.comprobante_controller import ComprobanteController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("comprobantes", __name__, url_prefix="/api")


@bp.get("/comprobantes")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def listar_global():
    return ComprobanteController.listar_global()


@bp.get("/clientes/<int:cliente_id>/comprobantes")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def listar(cliente_id: int):
    return ComprobanteController.listar(cliente_id)


@bp.post("/clientes/<int:cliente_id>/comprobantes")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def crear(cliente_id: int):
    return ComprobanteController.crear(cliente_id)


@bp.get("/comprobantes/<int:comprobante_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def detalle(comprobante_id: int):
    return ComprobanteController.detalle(comprobante_id)


@bp.put("/comprobantes/<int:comprobante_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def actualizar(comprobante_id: int):
    return ComprobanteController.actualizar(comprobante_id)


@bp.post("/comprobantes/<int:comprobante_id>/contabilizar")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def contabilizar(comprobante_id: int):
    return ComprobanteController.contabilizar(comprobante_id)


@bp.delete("/comprobantes/<int:comprobante_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def anular(comprobante_id: int):
    return ComprobanteController.anular(comprobante_id)

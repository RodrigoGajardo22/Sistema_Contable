"""Endpoints del plan de cuentas.

Las cuentas cuelgan del cliente: /clientes/<id>/cuentas para el listado y el
alta, y /cuentas/<id> para las operaciones sobre una cuenta puntual.
"""

from flask import Blueprint

from app.controllers.cuenta_controller import CuentaController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("cuentas", __name__, url_prefix="/api")


@bp.get("/clientes/<int:cliente_id>/cuentas")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def listar(cliente_id: int):
    return CuentaController.listar(cliente_id)


@bp.post("/clientes/<int:cliente_id>/cuentas")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def crear(cliente_id: int):
    return CuentaController.crear(cliente_id)


@bp.get("/cuentas/<int:cuenta_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def detalle(cuenta_id: int):
    return CuentaController.detalle(cuenta_id)


@bp.put("/cuentas/<int:cuenta_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def actualizar(cuenta_id: int):
    return CuentaController.actualizar(cuenta_id)


@bp.delete("/cuentas/<int:cuenta_id>")
@roles_required(Rol.ADMIN, Rol.CONTADOR)
def eliminar(cuenta_id: int):
    return CuentaController.eliminar(cuenta_id)

"""Resumen del panel (KPIs por rol)."""

from flask import Blueprint

from app.controllers.dashboard_controller import DashboardController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("dashboard", __name__, url_prefix="/api")


@bp.get("/dashboard")
@roles_required(Rol.ADMIN, Rol.CONTADOR, Rol.CLIENTE)
def resumen():
    return DashboardController.resumen()

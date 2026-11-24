"""Endpoints de auditoría."""

from flask import Blueprint

from app.controllers.dashboard_controller import AuditoriaController
from app.models.usuario import Rol
from app.utils.decorators import roles_required

bp = Blueprint("auditoria", __name__, url_prefix="/api")


@bp.get("/auditoria")
@roles_required(Rol.ADMIN)
def listar():
    return AuditoriaController.listar()

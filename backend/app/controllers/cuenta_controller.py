"""Traducción HTTP <-> servicios del plan de cuentas."""

from flask import request

from app.schemas.cuenta import CuentaCreateSchema, CuentaSchema, CuentaUpdateSchema
from app.services.cuenta_service import CuentaService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


class CuentaController:
    @staticmethod
    def listar(cliente_id: int):
        cuentas = CuentaService.listar(cliente_id, usuario_actual())
        datos = CuentaSchema(many=True).dump(cuentas)
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def crear(cliente_id: int):
        datos = CuentaCreateSchema().load(request.get_json(silent=True) or {})
        cuenta = CuentaService.crear(cliente_id, datos, usuario_actual())
        return respuesta(CuentaSchema().dump(cuenta), status=201)

    @staticmethod
    def detalle(cuenta_id: int):
        cuenta = CuentaService.obtener(cuenta_id, usuario_actual())
        return respuesta(CuentaSchema().dump(cuenta))

    @staticmethod
    def actualizar(cuenta_id: int):
        datos = CuentaUpdateSchema().load(request.get_json(silent=True) or {})
        cuenta = CuentaService.actualizar(cuenta_id, datos, usuario_actual())
        return respuesta(CuentaSchema().dump(cuenta))

    @staticmethod
    def eliminar(cuenta_id: int):
        CuentaService.eliminar(cuenta_id, usuario_actual())
        return respuesta({"mensaje": "Cuenta eliminada."})

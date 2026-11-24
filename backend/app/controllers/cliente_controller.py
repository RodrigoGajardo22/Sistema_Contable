"""Traducción HTTP <-> servicios para clientes."""

from flask import request

from app.schemas.cliente import (
    ClienteCreateSchema,
    ClienteSchema,
    ClienteUpdateSchema,
    ClienteVersionSchema,
)
from app.services.cliente_service import ClienteService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


class ClienteController:
    @staticmethod
    def listar():
        activo_param = request.args.get("activo")
        activo: bool | None = None
        if activo_param not in (None, ""):
            activo = activo_param.lower() in {"1", "true", "si", "sí"}

        contador_param = request.args.get("contador")
        contador_id = int(contador_param) if contador_param and contador_param.isdigit() else None

        clientes = ClienteService.listar(
            usuario_actual(),
            q=request.args.get("q") or None,
            activo=activo,
            contador_id=contador_id,
        )

        datos = ClienteSchema(many=True).dump(clientes)
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def crear():
        datos = ClienteCreateSchema().load(request.get_json(silent=True) or {})
        cliente = ClienteService.crear(datos, usuario_actual())
        return respuesta(ClienteSchema().dump(cliente), status=201)

    @staticmethod
    def detalle(cliente_id: int):
        cliente = ClienteService.actual_de(usuario_actual(), cliente_id)
        return respuesta(ClienteSchema().dump(cliente))

    @staticmethod
    def actualizar(cliente_id: int):
        datos = ClienteUpdateSchema().load(request.get_json(silent=True) or {})
        cliente = ClienteService.actualizar(cliente_id, datos, usuario_actual())
        return respuesta(ClienteSchema().dump(cliente))

    @staticmethod
    def desactivar(cliente_id: int):
        cliente = ClienteService.desactivar(cliente_id, usuario_actual())
        return respuesta(ClienteSchema().dump(cliente))

    @staticmethod
    def historial(cliente_id: int):
        versiones = ClienteService.historial(cliente_id, usuario_actual())
        datos = ClienteVersionSchema(many=True).dump(versiones)
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def activar(cliente_id: int):
        cliente = ClienteService.activar(cliente_id, usuario_actual())
        return respuesta(ClienteSchema().dump(cliente))

    @staticmethod
    def crear_acceso(cliente_id: int):
        usuario, password_temporal = ClienteService.crear_acceso(
            cliente_id, usuario_actual()
        )
        return respuesta(
            {
                "usuario_id": usuario.id,
                "nombre": usuario.nombre,
                "email": usuario.email,
                "password_temporal": password_temporal,
            },
            status=201,
        )

    @staticmethod
    def restablecer_acceso(cliente_id: int):
        usuario, password_temporal = ClienteService.restablecer_acceso(
            cliente_id, usuario_actual()
        )
        return respuesta(
            {
                "usuario_id": usuario.id,
                "nombre": usuario.nombre,
                "email": usuario.email,
                "password_temporal": password_temporal,
            }
        )

    @staticmethod
    def revocar_acceso(cliente_id: int):
        ClienteService.revocar_acceso(cliente_id, usuario_actual())
        return respuesta({"mensaje": "Acceso revocado."})

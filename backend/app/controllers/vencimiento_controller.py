"""Traducción HTTP de vencimientos."""

from datetime import date

from flask import request

from app.schemas.extras import (
    EstadoVencimientoSchema,
    VencimientoCreateSchema,
    VencimientoUpdateSchema,
)
from app.services.vencimiento_service import VencimientoService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


def _fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _serializar(vencimiento) -> dict:
    return {
        "id": vencimiento.id,
        "cliente_id": vencimiento.cliente_id,
        "obligacion": vencimiento.obligacion,
        "obligacion_etiqueta": vencimiento.obligacion_etiqueta,
        "periodo": vencimiento.periodo,
        "fecha_vencimiento": vencimiento.fecha_vencimiento.isoformat(),
        "estado": vencimiento.estado,
        "estado_etiqueta": vencimiento.estado_etiqueta,
        "vencido": vencimiento.vencido,
        "observaciones": vencimiento.observaciones,
    }


class VencimientoController:
    @staticmethod
    def listar(cliente_id: int):
        vencimientos = VencimientoService.listar(
            cliente_id,
            usuario_actual(),
            estado=request.args.get("estado") or None,
            desde=_fecha(request.args.get("desde")),
            hasta=_fecha(request.args.get("hasta")),
            proximidad=request.args.get("proximidad") or None,
        )
        datos = [_serializar(v) for v in vencimientos]
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def listar_global():
        cliente_param = request.args.get("cliente_id")
        cliente_id = int(cliente_param) if cliente_param and cliente_param.isdigit() else None
        vencimientos, nombres = VencimientoService.listar_global(
            usuario_actual(),
            cliente_id=cliente_id,
            estado=request.args.get("estado") or None,
            desde=_fecha(request.args.get("desde")),
            hasta=_fecha(request.args.get("hasta")),
            proximidad=request.args.get("proximidad") or None,
            obligacion=request.args.get("obligacion") or None,
        )
        datos = []
        for vencimiento in vencimientos:
            item = _serializar(vencimiento)
            item["cliente_nombre"] = nombres.get(vencimiento.cliente_id)
            datos.append(item)
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def crear(cliente_id: int):
        datos = VencimientoCreateSchema().load(request.get_json(silent=True) or {})
        vencimiento = VencimientoService.crear(cliente_id, datos, usuario_actual())
        return respuesta(_serializar(vencimiento), status=201)

    @staticmethod
    def actualizar(vencimiento_id: int):
        datos = VencimientoUpdateSchema().load(request.get_json(silent=True) or {})
        vencimiento = VencimientoService.actualizar(
            vencimiento_id, datos, usuario_actual()
        )
        return respuesta(_serializar(vencimiento))

    @staticmethod
    def cambiar_estado(vencimiento_id: int):
        datos = EstadoVencimientoSchema().load(request.get_json(silent=True) or {})
        vencimiento = VencimientoService.cambiar_estado(
            vencimiento_id, datos["estado"], usuario_actual()
        )
        return respuesta(_serializar(vencimiento))

    @staticmethod
    def eliminar(vencimiento_id: int):
        VencimientoService.eliminar(vencimiento_id, usuario_actual())
        return respuesta({"mensaje": "Vencimiento eliminado."})

"""Traducción HTTP <-> servicios de comprobantes."""

from datetime import date

from flask import request

from app.schemas.comprobante import ComprobanteCreateSchema, ComprobanteSchema
from app.services.comprobante_service import ComprobanteService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


def _fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


class ComprobanteController:
    @staticmethod
    def listar(cliente_id: int):
        comprobantes = ComprobanteService.listar(
            cliente_id,
            usuario_actual(),
            tipo=request.args.get("tipo") or None,
            estado=request.args.get("estado") or None,
            desde=_fecha(request.args.get("desde")),
            hasta=_fecha(request.args.get("hasta")),
            q=request.args.get("q") or None,
        )
        datos = ComprobanteSchema(many=True).dump(comprobantes)
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def listar_global():
        cliente_param = request.args.get("cliente_id")
        cliente_id = int(cliente_param) if cliente_param and cliente_param.isdigit() else None
        comprobantes, nombres = ComprobanteService.listar_global(
            usuario_actual(),
            cliente_id=cliente_id,
            tipo=request.args.get("tipo") or None,
            estado=request.args.get("estado") or None,
            desde=_fecha(request.args.get("desde")),
            hasta=_fecha(request.args.get("hasta")),
            q=request.args.get("q") or None,
        )
        datos = []
        for comprobante in comprobantes:
            item = ComprobanteSchema().dump(comprobante)
            item["cliente_nombre"] = nombres.get(comprobante.cliente_id)
            datos.append(item)
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def crear(cliente_id: int):
        datos = ComprobanteCreateSchema().load(request.get_json(silent=True) or {})
        comprobante = ComprobanteService.crear(cliente_id, datos, usuario_actual())
        return respuesta(ComprobanteSchema().dump(comprobante), status=201)

    @staticmethod
    def detalle(comprobante_id: int):
        comprobante = ComprobanteService.obtener(comprobante_id, usuario_actual())
        return respuesta(ComprobanteSchema().dump(comprobante))

    @staticmethod
    def actualizar(comprobante_id: int):
        datos = ComprobanteCreateSchema().load(request.get_json(silent=True) or {})
        comprobante = ComprobanteService.actualizar(
            comprobante_id, datos, usuario_actual()
        )
        return respuesta(ComprobanteSchema().dump(comprobante))

    @staticmethod
    def contabilizar(comprobante_id: int):
        comprobante = ComprobanteService.contabilizar(comprobante_id, usuario_actual())
        return respuesta(ComprobanteSchema().dump(comprobante))

    @staticmethod
    def anular(comprobante_id: int):
        comprobante = ComprobanteService.anular(comprobante_id, usuario_actual())
        return respuesta(ComprobanteSchema().dump(comprobante))

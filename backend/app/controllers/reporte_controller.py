"""Traducción HTTP de reportes."""

from datetime import date

from flask import request

from app.services.reporte_service import ReporteService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


def _rango() -> tuple[date, date]:
    hoy = date.today()
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    inicio = date.fromisoformat(desde) if desde else hoy.replace(day=1)
    fin = date.fromisoformat(hasta) if hasta else hoy
    return inicio, fin


class ReporteController:
    @staticmethod
    def diario(cliente_id: int):
        desde, hasta = _rango()
        datos = ReporteService.diario(cliente_id, usuario_actual(), desde, hasta)
        return respuesta(datos, meta={"desde": desde.isoformat(), "hasta": hasta.isoformat()})

    @staticmethod
    def mayor(cliente_id: int):
        desde, hasta = _rango()
        cuenta = int(request.args.get("cuenta", 0) or 0)
        datos = ReporteService.mayor(cliente_id, usuario_actual(), cuenta, desde, hasta)
        return respuesta(datos)

    @staticmethod
    def balance(cliente_id: int):
        desde, hasta = _rango()
        datos = ReporteService.balance(cliente_id, usuario_actual(), desde, hasta)
        return respuesta(datos)

    @staticmethod
    def libro_iva(cliente_id: int):
        desde, hasta = _rango()
        datos = ReporteService.libro_iva(cliente_id, usuario_actual(), desde, hasta)
        return respuesta(datos)

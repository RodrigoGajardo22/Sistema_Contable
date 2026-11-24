"""Traducción HTTP de conciliación bancaria."""

from flask import request

from app.schemas.extras import ExtractoSchema, VincularSchema
from app.services.conciliacion_service import ConciliacionService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


def _movimiento(movimiento, extracto) -> dict:
    return {
        "id": movimiento.id,
        "fecha": movimiento.fecha.isoformat(),
        "descripcion": movimiento.descripcion,
        "importe": str(movimiento.importe),
        "estado": movimiento.estado,
        "estado_etiqueta": movimiento.estado_etiqueta,
        "asiento_id": movimiento.asiento_id,
        "asiento_numero": movimiento.asiento.numero if movimiento.asiento else None,
        "comprobante_id": movimiento.comprobante_id,
        "comprobante_numero": movimiento.comprobante.numero if movimiento.comprobante else None,
        "sugerencias": (
            ConciliacionService.sugerencias(movimiento, extracto)
            if movimiento.estado == "pendiente"
            else []
        ),
    }


def _extracto(extracto, con_movimientos: bool = True) -> dict:
    datos = {
        "id": extracto.id,
        "cliente_id": extracto.cliente_id,
        "banco": extracto.banco,
        "periodo": extracto.periodo,
        "saldo_inicial": str(extracto.saldo_inicial),
        "saldo_final": str(extracto.saldo_final),
        "resumen": ConciliacionService.resumen(extracto),
    }
    if con_movimientos:
        datos["movimientos"] = [
            _movimiento(m, extracto) for m in extracto.movimientos
        ]
    return datos


class ConciliacionController:
    @staticmethod
    def listar(cliente_id: int):
        extractos = ConciliacionService.listar_extractos(cliente_id, usuario_actual())
        datos = [_extracto(e, con_movimientos=False) for e in extractos]
        return respuesta(datos, meta={"total": len(datos)})

    @staticmethod
    def crear(cliente_id: int):
        datos = ExtractoSchema().load(request.get_json(silent=True) or {})
        extracto = ConciliacionService.importar(cliente_id, datos, usuario_actual())
        return respuesta(_extracto(extracto), status=201)

    @staticmethod
    def detalle(extracto_id: int):
        extracto = ConciliacionService.obtener_extracto(extracto_id, usuario_actual())
        return respuesta(_extracto(extracto))

    @staticmethod
    def eliminar(extracto_id: int):
        ConciliacionService.eliminar_extracto(extracto_id, usuario_actual())
        return respuesta({"mensaje": "Extracto eliminado."})

    @staticmethod
    def vincular(movimiento_id: int):
        datos = VincularSchema().load(request.get_json(silent=True) or {})
        movimiento = ConciliacionService.vincular(
            movimiento_id,
            usuario_actual(),
            asiento_id=datos.get("asiento_id"),
            comprobante_id=datos.get("comprobante_id"),
        )
        return respuesta(
            {
                "id": movimiento.id,
                "estado": movimiento.estado,
                "asiento_id": movimiento.asiento_id,
                "comprobante_id": movimiento.comprobante_id,
            }
        )

    @staticmethod
    def generar_asiento(movimiento_id: int):
        from app.schemas.extras import AsientoDesdeMovimientoSchema

        datos = AsientoDesdeMovimientoSchema().load(request.get_json(silent=True) or {})
        movimiento, asiento = ConciliacionService.generar_asiento(
            movimiento_id,
            datos["cuenta_id"],
            usuario_actual(),
            datos.get("concepto"),
        )
        return respuesta(
            {
                "movimiento_id": movimiento.id,
                "asiento_id": asiento.id,
                "numero": asiento.numero,
                "estado": movimiento.estado,
            },
            status=201,
        )

    @staticmethod
    def descartar(movimiento_id: int):
        movimiento = ConciliacionService.descartar(movimiento_id, usuario_actual())
        return respuesta({"id": movimiento.id, "estado": movimiento.estado})

    @staticmethod
    def desvincular(movimiento_id: int):
        movimiento = ConciliacionService.desvincular(movimiento_id, usuario_actual())
        return respuesta({"id": movimiento.id, "estado": movimiento.estado})

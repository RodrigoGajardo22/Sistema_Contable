"""Traducción HTTP <-> servicios de asientos."""

from datetime import date

from flask import request

from app.schemas.asiento import (
    AnulacionSchema,
    AsientoCreateSchema,
    AsientoListadoSchema,
    AsientoSchema,
)
from app.services.asiento_service import AsientoService
from app.utils.decorators import usuario_actual
from app.utils.errors import respuesta


def _fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


class AsientoController:
    @staticmethod
    def listar(cliente_id: int):
        pagina = max(1, int(request.args.get("pagina", 1) or 1))
        por_pagina = min(100, max(1, int(request.args.get("por_pagina", 20) or 20)))

        resumenes, total = AsientoService.listar(
            cliente_id,
            usuario_actual(),
            desde=_fecha(request.args.get("desde")),
            hasta=_fecha(request.args.get("hasta")),
            estado=request.args.get("estado") or None,
            cuenta_id=int(request.args["cuenta"]) if request.args.get("cuenta", "").isdigit() else None,
            q=request.args.get("q") or None,
            pagina=pagina,
            por_pagina=por_pagina,
        )

        return respuesta(
            AsientoListadoSchema(many=True).dump(resumenes),
            meta={"total": total, "pagina": pagina, "por_pagina": por_pagina},
        )

    @staticmethod
    def crear(cliente_id: int):
        datos = AsientoCreateSchema().load(request.get_json(silent=True) or {})
        asiento = AsientoService.crear(cliente_id, datos, usuario_actual())
        return respuesta(AsientoSchema().dump(asiento), status=201)

    @staticmethod
    def detalle(asiento_id: int):
        asiento = AsientoService.obtener(asiento_id, usuario_actual())
        return respuesta(AsientoSchema().dump(asiento))

    @staticmethod
    def actualizar(asiento_id: int):
        datos = AsientoCreateSchema().load(request.get_json(silent=True) or {})
        asiento = AsientoService.actualizar(asiento_id, datos, usuario_actual())
        return respuesta(AsientoSchema().dump(asiento))

    @staticmethod
    def confirmar(asiento_id: int):
        asiento = AsientoService.confirmar(asiento_id, usuario_actual())
        return respuesta(AsientoSchema().dump(asiento))

    @staticmethod
    def anular(asiento_id: int):
        datos = AnulacionSchema().load(request.get_json(silent=True) or {})
        asiento = AsientoService.anular(asiento_id, datos["motivo"], usuario_actual())
        return respuesta(AsientoSchema().dump(asiento))

    @staticmethod
    def descartar(asiento_id: int):
        AsientoService.descartar(asiento_id, usuario_actual())
        return respuesta({"mensaje": "Borrador descartado."})

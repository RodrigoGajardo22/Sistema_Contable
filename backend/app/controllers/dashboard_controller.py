"""Traducción HTTP de auditoría y dashboard."""

from datetime import date, timedelta

from flask import request
from sqlalchemy import func, select

from app.extensions import db
from app.models.asiento import Asiento, EstadoAsiento, RenglonAsiento
from app.models.comprobante import Comprobante, EstadoComprobante
from app.models.usuario import Rol
from app.models.vencimiento import EstadoVencimiento, Vencimiento
from app.services.auditoria_service import AuditoriaService, serializar
from app.services.cliente_service import ClienteService
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


class AuditoriaController:
    @staticmethod
    def listar():
        entradas = AuditoriaService.listar(
            usuario_actual(),
            entidad=request.args.get("entidad") or None,
            accion=request.args.get("accion") or None,
            usuario_id=int(request.args["usuario"]) if request.args.get("usuario", "").isdigit() else None,
            desde=_fecha(request.args.get("desde")),
            hasta=_fecha(request.args.get("hasta")),
        )
        datos = [serializar(entrada) for entrada in entradas]
        return respuesta(datos, meta={"total": len(datos)})


class DashboardController:
    @staticmethod
    def resumen():
        actor = usuario_actual()
        # El panel cuenta la cartera vigente: las bajas lógicas no inflan los KPIs.
        clientes = ClienteService.listar(actor, activo=True)
        ids = [cliente.id for cliente in clientes]

        hoy = date.today()
        inicio_mes = hoy.replace(day=1)
        fin_mes = (inicio_mes.replace(month=12, day=31) if inicio_mes.month == 12 else inicio_mes.replace(month=inicio_mes.month + 1, day=1))

        asientos_mes = 0
        if ids:
            asientos_mes = db.session.scalar(
                select(func.count())
                .select_from(Asiento)
                .where(
                    Asiento.cliente_id.in_(ids),
                    Asiento.estado == EstadoAsiento.CONFIRMADO.value,
                    Asiento.fecha >= inicio_mes,
                    Asiento.fecha <= fin_mes,
                )
            ) or 0

        comprobantes_pendientes = 0
        comprobantes_mes = 0
        if ids:
            comprobantes_pendientes = db.session.scalar(
                select(func.count())
                .select_from(Comprobante)
                .where(
                    Comprobante.cliente_id.in_(ids),
                    Comprobante.estado == EstadoComprobante.PENDIENTE.value,
                )
            ) or 0
            comprobantes_mes = db.session.scalar(
                select(func.count())
                .select_from(Comprobante)
                .where(
                    Comprobante.cliente_id.in_(ids),
                    Comprobante.estado != EstadoComprobante.ANULADO.value,
                    Comprobante.fecha >= inicio_mes,
                    Comprobante.fecha <= fin_mes,
                )
            ) or 0

        nombres = {cliente.id: cliente.razon_social for cliente in clientes}
        responsable = None
        if actor.rol == Rol.CLIENTE.value and clientes:
            propio = clientes[0]
            responsable = {
                "nombre": propio.contador_nombre,
                "email": propio.contador_email,
            }
        hoy = date.today()

        proximos = []
        if ids:
            filas = db.session.scalars(
                select(Vencimiento)
                .where(
                    Vencimiento.cliente_id.in_(ids),
                    Vencimiento.estado != EstadoVencimiento.PAGADO.value,
                    Vencimiento.fecha_vencimiento >= hoy,
                )
                .order_by(Vencimiento.fecha_vencimiento)
                .limit(5)
            ).all()
            proximos = [
                {
                    "id": v.id,
                    "cliente": nombres.get(v.cliente_id, ""),
                    "obligacion": v.obligacion_etiqueta,
                    "fecha": v.fecha_vencimiento.isoformat(),
                    "dias": (v.fecha_vencimiento - hoy).days,
                }
                for v in filas
            ]

        ultimos = []
        if ids:
            totales = (
                select(
                    RenglonAsiento.asiento_id.label("asiento_id"),
                    func.coalesce(func.sum(RenglonAsiento.debe), 0).label("total"),
                )
                .group_by(RenglonAsiento.asiento_id)
                .subquery()
            )
            filas = db.session.execute(
                select(Asiento, totales.c.total)
                .outerjoin(totales, totales.c.asiento_id == Asiento.id)
                .where(
                    Asiento.cliente_id.in_(ids),
                    Asiento.estado == EstadoAsiento.CONFIRMADO.value,
                )
                .order_by(Asiento.fecha.desc(), Asiento.numero.desc())
                .limit(5)
            ).all()
            ultimos = [
                {
                    "id": a.id,
                    "numero": a.numero,
                    "fecha": a.fecha.isoformat(),
                    "concepto": a.concepto,
                    "cliente": nombres.get(a.cliente_id, ""),
                    "total": str(total or 0),
                }
                for a, total in filas
            ]

        conciliaciones_pendientes = 0
        if ids:
            from app.models.conciliacion import Extracto, MovimientoBancario

            conciliaciones_pendientes = db.session.scalar(
                select(func.count())
                .select_from(MovimientoBancario)
                .join(Extracto, Extracto.id == MovimientoBancario.extracto_id)
                .where(
                    Extracto.cliente_id.in_(ids),
                    MovimientoBancario.estado == "pendiente",
                )
            ) or 0

        return respuesta(
            {
                "clientes": len(ids),
                "asientos_mes": asientos_mes,
                "comprobantes_pendientes": comprobantes_pendientes,
                "comprobantes_mes": comprobantes_mes,
                "vencimientos": VencimientoService.resumen(ids),
                "conciliaciones_pendientes": conciliaciones_pendientes,
                "responsable": responsable,
                "proximos_vencimientos": proximos,
                "ultimos_asientos": ultimos,
            }
        )

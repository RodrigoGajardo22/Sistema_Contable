"""Reglas de negocio de vencimientos."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models.vencimiento import EstadoVencimiento, Vencimiento
from app.models.usuario import Usuario
from app.services.cliente_service import ClienteService
from app.utils.errors import ApiError

ORDEN = {
    EstadoVencimiento.PENDIENTE.value: 0,
    EstadoVencimiento.PRESENTADO.value: 1,
    EstadoVencimiento.PAGADO.value: 2,
}


class VencimientoService:
    @staticmethod
    def listar(
        cliente_id: int,
        actor: Usuario,
        *,
        estado: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        proximidad: str | None = None,
    ) -> list[Vencimiento]:
        ClienteService.obtener(cliente_id, actor)

        consulta = select(Vencimiento).where(Vencimiento.cliente_id == cliente_id)
        if estado:
            consulta = consulta.where(Vencimiento.estado == estado)
        if desde:
            consulta = consulta.where(Vencimiento.fecha_vencimiento >= desde)
        if hasta:
            consulta = consulta.where(Vencimiento.fecha_vencimiento <= hasta)
        if proximidad == "proximos":
            consulta = consulta.where(
                Vencimiento.fecha_vencimiento >= date.today(),
                Vencimiento.estado != EstadoVencimiento.PAGADO.value,
            )
        elif proximidad == "vencidos":
            consulta = consulta.where(
                Vencimiento.fecha_vencimiento < date.today(),
                Vencimiento.estado != EstadoVencimiento.PAGADO.value,
            )

        return list(
            db.session.scalars(
                consulta.order_by(Vencimiento.fecha_vencimiento, Vencimiento.id)
            )
        )

    @staticmethod
    def listar_global(
        actor: Usuario,
        *,
        cliente_id: int | None = None,
        estado: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        proximidad: str | None = None,
        obligacion: str | None = None,
    ) -> tuple[list[Vencimiento], dict[int, str]]:
        clientes = ClienteService.listar(actor)
        ids = [cliente.id for cliente in clientes]
        nombres = {cliente.id: cliente.razon_social for cliente in clientes}

        if not ids:
            return [], nombres
        if cliente_id is not None and cliente_id not in ids:
            raise ApiError(
                "El cliente no existe.", codigo="no_encontrado", status=404
            )

        consulta = select(Vencimiento).where(Vencimiento.cliente_id.in_(ids))
        if cliente_id is not None:
            consulta = consulta.where(Vencimiento.cliente_id == cliente_id)
        if estado:
            consulta = consulta.where(Vencimiento.estado == estado)
        if obligacion:
            consulta = consulta.where(Vencimiento.obligacion == obligacion)
        if desde:
            consulta = consulta.where(Vencimiento.fecha_vencimiento >= desde)
        if hasta:
            consulta = consulta.where(Vencimiento.fecha_vencimiento <= hasta)
        if proximidad == "proximos":
            consulta = consulta.where(
                Vencimiento.fecha_vencimiento >= date.today(),
                Vencimiento.estado != EstadoVencimiento.PAGADO.value,
            )
        elif proximidad == "vencidos":
            consulta = consulta.where(
                Vencimiento.fecha_vencimiento < date.today(),
                Vencimiento.estado != EstadoVencimiento.PAGADO.value,
            )

        consulta = consulta.order_by(Vencimiento.fecha_vencimiento, Vencimiento.id)
        return list(db.session.scalars(consulta)), nombres

    @staticmethod
    def obtener(vencimiento_id: int, actor: Usuario) -> Vencimiento:
        vencimiento = db.session.get(Vencimiento, vencimiento_id)
        if vencimiento is None:
            raise ApiError(
                "El vencimiento no existe.", codigo="no_encontrado", status=404
            )
        ClienteService.obtener(vencimiento.cliente_id, actor)
        return vencimiento

    @staticmethod
    def crear(cliente_id: int, datos: dict, actor: Usuario) -> Vencimiento:
        cliente, _ = ClienteService.obtener(cliente_id, actor)
        if not cliente.activo:
            raise ApiError(
                "El cliente está inactivo.", codigo="cliente_inactivo", status=409
            )

        vencimiento = Vencimiento(
            cliente_id=cliente_id,
            obligacion=datos["obligacion"],
            periodo=datos["periodo"].strip(),
            fecha_vencimiento=datos["fecha_vencimiento"],
            estado=EstadoVencimiento.PENDIENTE.value,
            observaciones=(datos.get("observaciones") or None),
            creado_por_id=actor.id,
        )
        db.session.add(vencimiento)
        db.session.commit()
        return vencimiento

    @staticmethod
    def actualizar(vencimiento_id: int, datos: dict, actor: Usuario) -> Vencimiento:
        vencimiento = VencimientoService.obtener(vencimiento_id, actor)

        if vencimiento.estado == EstadoVencimiento.PAGADO.value:
            raise ApiError(
                "Un vencimiento pagado no se edita.",
                codigo="vencimiento_cerrado",
                status=409,
            )

        for campo in ("obligacion", "periodo", "fecha_vencimiento", "observaciones"):
            if campo in datos:
                valor = datos[campo]
                if campo == "periodo" and isinstance(valor, str):
                    valor = valor.strip()
                if campo == "observaciones":
                    valor = valor or None
                setattr(vencimiento, campo, valor)

        db.session.commit()
        return vencimiento

    @staticmethod
    def cambiar_estado(vencimiento_id: int, nuevo: str, actor: Usuario) -> Vencimiento:
        vencimiento = VencimientoService.obtener(vencimiento_id, actor)

        if nuevo not in ORDEN:
            raise ApiError(
                "Estado inválido.", codigo="estado_invalido", status=422
            )

        if ORDEN[nuevo] < ORDEN[vencimiento.estado]:
            raise ApiError(
                "El estado solo puede avanzar: pendiente → presentado → pagado.",
                codigo="transicion_invalida",
                status=409,
            )

        vencimiento.estado = nuevo
        db.session.commit()
        return vencimiento

    @staticmethod
    def eliminar(vencimiento_id: int, actor: Usuario) -> None:
        vencimiento = VencimientoService.obtener(vencimiento_id, actor)
        db.session.delete(vencimiento)
        db.session.commit()

    # ------------------------------------------------------------------ dashboard
    @staticmethod
    def resumen(cliente_ids: list[int]) -> dict[str, Any]:
        if not cliente_ids:
            return {"proximos": 0, "vencidos": 0, "pendientes": 0}

        hoy = date.today()
        limite = hoy + timedelta(days=30)

        base = select(func.count()).select_from(Vencimiento).where(
            Vencimiento.cliente_id.in_(cliente_ids)
        )

        proximos = db.session.scalar(
            base.where(
                Vencimiento.estado != EstadoVencimiento.PAGADO.value,
                Vencimiento.fecha_vencimiento >= hoy,
                Vencimiento.fecha_vencimiento <= limite,
            )
        )
        vencidos = db.session.scalar(
            base.where(
                Vencimiento.estado != EstadoVencimiento.PAGADO.value,
                Vencimiento.fecha_vencimiento < hoy,
            )
        )
        pendientes = db.session.scalar(
            base.where(Vencimiento.estado == EstadoVencimiento.PENDIENTE.value)
        )

        return {
            "proximos": proximos or 0,
            "vencidos": vencidos or 0,
            "pendientes": pendientes or 0,
        }

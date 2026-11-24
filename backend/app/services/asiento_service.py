"""Reglas de negocio de asientos contables.

La partida doble se valida acá, con Decimal y dos decimales exactos. Nunca se
confía en totales enviados por el cliente: se recalculan siempre.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import noload

from app.extensions import db
from app.models.asiento import Asiento, EstadoAsiento, RenglonAsiento
from app.models.cuenta import Cuenta
from app.models.usuario import Usuario
from app.services.auditoria_service import AuditoriaService
from app.services.cliente_service import ClienteService
from app.utils.errors import ApiError

CERO = Decimal("0.00")


@dataclass
class AsientoResumen:
    id: int
    cliente_id: int
    numero: int
    fecha: date
    concepto: str
    estado: str
    estado_etiqueta: str
    debe: Decimal
    haber: Decimal
    creado_en: datetime


class AsientoService:
    @staticmethod
    def listar(
        cliente_id: int,
        actor: Usuario,
        *,
        desde: date | None = None,
        hasta: date | None = None,
        estado: str | None = None,
        cuenta_id: int | None = None,
        q: str | None = None,
        pagina: int = 1,
        por_pagina: int = 20,
    ) -> tuple[list[AsientoResumen], int]:
        ClienteService.obtener(cliente_id, actor)

        totales = (
            select(
                RenglonAsiento.asiento_id.label("asiento_id"),
                func.coalesce(func.sum(RenglonAsiento.debe), 0).label("debe"),
                func.coalesce(func.sum(RenglonAsiento.haber), 0).label("haber"),
            )
            .group_by(RenglonAsiento.asiento_id)
            .subquery()
        )

        consulta = (
            select(Asiento, totales.c.debe, totales.c.haber)
            .outerjoin(totales, totales.c.asiento_id == Asiento.id)
            .where(Asiento.cliente_id == cliente_id)
            .options(noload(Asiento.renglones))
        )

        if desde:
            consulta = consulta.where(Asiento.fecha >= desde)
        if hasta:
            consulta = consulta.where(Asiento.fecha <= hasta)
        if estado:
            consulta = consulta.where(Asiento.estado == estado)
        if cuenta_id:
            consulta = consulta.where(
                Asiento.id.in_(
                    select(RenglonAsiento.asiento_id).where(
                        RenglonAsiento.cuenta_id == cuenta_id
                    )
                )
            )
        if q:
            consulta = consulta.where(Asiento.concepto.ilike(f"%{q.strip()}%"))

        total = db.session.scalar(select(func.count()).select_from(consulta.subquery())) or 0

        consulta = (
            consulta.order_by(Asiento.fecha.desc(), Asiento.numero.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )

        filas = db.session.execute(consulta).all()
        resumenes = [
            AsientoResumen(
                id=asiento.id,
                cliente_id=asiento.cliente_id,
                numero=asiento.numero,
                fecha=asiento.fecha,
                concepto=asiento.concepto,
                estado=asiento.estado,
                estado_etiqueta=asiento.estado_etiqueta,
                debe=Decimal(str(debe or 0)).quantize(CERO),
                haber=Decimal(str(haber or 0)).quantize(CERO),
                creado_en=asiento.creado_en,
            )
            for asiento, debe, haber in filas
        ]

        return resumenes, total

    @staticmethod
    def obtener(asiento_id: int, actor: Usuario) -> Asiento:
        asiento = db.session.get(Asiento, asiento_id)
        if asiento is None:
            raise ApiError("El asiento no existe.", codigo="no_encontrado", status=404)

        ClienteService.obtener(asiento.cliente_id, actor)
        return asiento

    @staticmethod
    def crear(cliente_id: int, datos: dict, actor: Usuario) -> Asiento:
        cliente, _ = ClienteService.obtener(cliente_id, actor)

        if not cliente.activo:
            raise ApiError(
                "El cliente está inactivo: no admite asientos nuevos.",
                codigo="cliente_inactivo",
                status=409,
            )

        AsientoService._validar_fecha(datos["fecha"])
        renglones = AsientoService._validar_renglones(cliente_id, datos["renglones"])

        asiento = Asiento(
            cliente_id=cliente_id,
            numero=AsientoService._siguiente_numero(cliente_id),
            fecha=datos["fecha"],
            concepto=datos["concepto"].strip(),
            estado=EstadoAsiento.BORRADOR.value,
            creado_por_id=actor.id,
        )

        for renglon in renglones:
            asiento.renglones.append(
                RenglonAsiento(
                    cuenta_id=renglon["cuenta_id"],
                    debe=renglon["debe"],
                    haber=renglon["haber"],
                )
            )

        db.session.add(asiento)

        try:
            db.session.flush()
            AuditoriaService.registrar(
                actor,
                "crear",
                "asiento",
                asiento.id,
                despues={
                    "numero": asiento.numero,
                    "fecha": asiento.fecha.isoformat(),
                    "concepto": asiento.concepto,
                },
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ApiError(
                "No se pudo asignar el número de asiento. Reintentá.",
                codigo="conflicto_numero",
                status=409,
            )

        return asiento

    @staticmethod
    def crear_confirmado(
        cliente_id: int,
        *,
        fecha: date,
        concepto: str,
        renglones: list[dict],
        actor: Usuario,
    ) -> Asiento:
        """Crea un asiento ya confirmado. Lo usa la contabilización de
        comprobantes: no hace commit, para que el llamador maneje la
        transacción completa.
        """
        AsientoService._validar_fecha(fecha)
        normalizados = AsientoService._validar_renglones(cliente_id, renglones)

        asiento = Asiento(
            cliente_id=cliente_id,
            numero=AsientoService._siguiente_numero(cliente_id),
            fecha=fecha,
            concepto=concepto.strip()[:200],
            estado=EstadoAsiento.CONFIRMADO.value,
            creado_por_id=actor.id,
        )

        for renglon in normalizados:
            asiento.renglones.append(
                RenglonAsiento(
                    cuenta_id=renglon["cuenta_id"],
                    debe=renglon["debe"],
                    haber=renglon["haber"],
                )
            )

        db.session.add(asiento)
        db.session.flush()
        return asiento

    @staticmethod
    def actualizar(asiento_id: int, datos: dict, actor: Usuario) -> Asiento:
        asiento = AsientoService.obtener(asiento_id, actor)
        AsientoService._exigir_borrador(asiento)

        AsientoService._validar_fecha(datos["fecha"])
        renglones = AsientoService._validar_renglones(
            asiento.cliente_id, datos["renglones"]
        )

        asiento.fecha = datos["fecha"]
        asiento.concepto = datos["concepto"].strip()
        asiento.renglones.clear()

        for renglon in renglones:
            asiento.renglones.append(
                RenglonAsiento(
                    cuenta_id=renglon["cuenta_id"],
                    debe=renglon["debe"],
                    haber=renglon["haber"],
                )
            )

        db.session.commit()
        return asiento

    @staticmethod
    def confirmar(asiento_id: int, actor: Usuario) -> Asiento:
        asiento = AsientoService.obtener(asiento_id, actor)
        AsientoService._exigir_borrador(asiento)

        # Defensa en profundidad: se revalida lo guardado antes de congelarlo.
        AsientoService._validar_saldos(
            [{"debe": r.debe, "haber": r.haber} for r in asiento.renglones]
        )

        asiento.estado = EstadoAsiento.CONFIRMADO.value
        AuditoriaService.registrar(
            actor,
            "confirmar",
            "asiento",
            asiento.id,
            antes={"estado": EstadoAsiento.BORRADOR.value},
            despues={"numero": asiento.numero, "estado": asiento.estado},
        )
        db.session.commit()
        return asiento

    @staticmethod
    def anular(asiento_id: int, motivo: str, actor: Usuario) -> Asiento:
        asiento = AsientoService.obtener(asiento_id, actor)

        if asiento.estado == EstadoAsiento.ANULADO.value:
            raise ApiError(
                "El asiento ya está anulado.",
                codigo="ya_anulado",
                status=409,
            )

        estado_anterior = asiento.estado
        asiento.estado = EstadoAsiento.ANULADO.value
        asiento.motivo_anulacion = motivo.strip()
        asiento.anulado_por_id = actor.id
        asiento.anulado_en = datetime.now().astimezone()
        AuditoriaService.registrar(
            actor,
            "anular",
            "asiento",
            asiento.id,
            antes={"estado": estado_anterior},
            despues={"numero": asiento.numero, "motivo": asiento.motivo_anulacion},
        )
        db.session.commit()
        return asiento

    @staticmethod
    def descartar(asiento_id: int, actor: Usuario) -> None:
        asiento = AsientoService.obtener(asiento_id, actor)
        AsientoService._exigir_borrador(asiento)

        db.session.delete(asiento)
        db.session.commit()

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _exigir_borrador(asiento: Asiento) -> None:
        if asiento.estado != EstadoAsiento.BORRADOR.value:
            raise ApiError(
                "Solo los asientos en borrador se pueden editar o descartar.",
                codigo="asiento_no_editable",
                status=409,
            )

    @staticmethod
    def _validar_fecha(fecha: date) -> None:
        if fecha > date.today():
            raise ApiError(
                "La fecha del asiento no puede ser futura.",
                codigo="fecha_invalida",
                status=422,
                detalles={"fecha": ["La fecha no puede ser futura."]},
            )

    @staticmethod
    def _validar_renglones(cliente_id: int, renglones: list[dict[str, Any]]) -> list[dict]:
        if len(renglones) < 2:
            raise ApiError(
                "Un asiento necesita al menos dos renglones.",
                codigo="renglones_insuficientes",
                status=422,
            )

        ids = {renglon["cuenta_id"] for renglon in renglones}
        cuentas = {
            cuenta.id: cuenta
            for cuenta in db.session.scalars(select(Cuenta).where(Cuenta.id.in_(ids)))
        }

        normalizados: list[dict] = []

        for indice, renglon in enumerate(renglones):
            cuenta = cuentas.get(renglon["cuenta_id"])

            # Control multi-tenant: la cuenta tiene que ser del mismo cliente.
            if cuenta is None or cuenta.cliente_id != cliente_id:
                raise ApiError(
                    f"El renglón {indice + 1} usa una cuenta que no pertenece al cliente.",
                    codigo="cuenta_invalida",
                    status=422,
                    detalles={"renglones": {str(indice): ["Cuenta inexistente o de otro cliente."]}},
                )

            if not cuenta.activa:
                raise ApiError(
                    f"La cuenta {cuenta.codigo} está inactiva.",
                    codigo="cuenta_inactiva",
                    status=422,
                )

            if not cuenta.imputable:
                raise ApiError(
                    f"La cuenta {cuenta.codigo} es agrupadora: no recibe movimientos.",
                    codigo="cuenta_no_imputable",
                    status=422,
                )

            debe = Decimal(renglon.get("debe") or 0).quantize(CERO)
            haber = Decimal(renglon.get("haber") or 0).quantize(CERO)

            if debe == 0 and haber == 0:
                raise ApiError(
                    f"El renglón {indice + 1} no tiene importe.",
                    codigo="renglon_sin_importe",
                    status=422,
                )
            if debe > 0 and haber > 0:
                raise ApiError(
                    f"El renglón {indice + 1} tiene debe y haber a la vez.",
                    codigo="renglon_ambos_lados",
                    status=422,
                )

            normalizados.append(
                {"cuenta_id": cuenta.id, "debe": debe, "haber": haber}
            )

        AsientoService._validar_saldos(normalizados)
        return normalizados

    @staticmethod
    def _validar_saldos(renglones: list[dict]) -> None:
        total_debe = sum((Decimal(renglon["debe"]) for renglon in renglones), CERO)
        total_haber = sum((Decimal(renglon["haber"]) for renglon in renglones), CERO)

        if total_debe == 0 and total_haber == 0:
            raise ApiError(
                "El asiento no tiene importes.",
                codigo="asiento_vacio",
                status=422,
            )

        if total_debe != total_haber:
            diferencia = abs(total_debe - total_haber)
            raise ApiError(
                f"El asiento no balancea: debe {total_debe} y haber {total_haber}.",
                codigo="asiento_desbalanceado",
                status=422,
                detalles={"diferencia": str(diferencia)},
            )

    @staticmethod
    def _siguiente_numero(cliente_id: int) -> int:
        ultimo = db.session.scalar(
            select(func.max(Asiento.numero)).where(Asiento.cliente_id == cliente_id)
        )
        return (ultimo or 0) + 1

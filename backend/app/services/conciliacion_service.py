"""Conciliación bancaria: importación de CSV y matching."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from app.extensions import db
from app.models.asiento import Asiento, EstadoAsiento, RenglonAsiento
from app.models.comprobante import Comprobante, EstadoComprobante
from app.models.conciliacion import (
    EstadoMovimiento,
    Extracto,
    MovimientoBancario,
)
from app.models.cuenta import Cuenta
from app.models.usuario import Usuario
from app.services.asiento_service import AsientoService
from app.services.cliente_service import ClienteService
from app.utils.errors import ApiError

CENTAVO = Decimal("0.01")
FORMATOS_FECHA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")


def parsear_fecha(texto: str) -> date:
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    raise ApiError(
        f"Fecha inválida en el CSV: {texto!r}.", codigo="csv_invalido", status=422
    )


def parsear_importe(texto: str) -> Decimal:
    limpio = texto.strip().replace("$", "").replace(" ", "")
    if not limpio:
        raise ApiError("Importe vacío en el CSV.", codigo="csv_invalido", status=422)

    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return Decimal(limpio).quantize(CENTAVO)
    except InvalidOperation:
        raise ApiError(
            f"Importe inválido en el CSV: {texto!r}.",
            codigo="csv_invalido",
            status=422,
        )


def parsear_csv(texto: str) -> list[dict]:
    movimientos = []

    for numero, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if not linea:
            continue
        if numero == 1 and linea.lower().startswith(("fecha", "date")):
            continue

        delimitador = ";" if ";" in linea else ","
        partes = linea.split(delimitador, 2)
        if len(partes) < 3:
            continue

        movimientos.append(
            {
                "fecha": parsear_fecha(partes[0]),
                "descripcion": partes[1].strip()[:200] or "Movimiento",
                "importe": parsear_importe(partes[2]),
            }
        )

    if not movimientos:
        raise ApiError(
            "El CSV no tiene movimientos válidos (fecha;descripción;importe).",
            codigo="csv_invalido",
            status=422,
        )

    return movimientos


class ConciliacionService:
    @staticmethod
    def listar_extractos(cliente_id: int, actor: Usuario) -> list[Extracto]:
        ClienteService.obtener(cliente_id, actor)
        return list(
            db.session.scalars(
                select(Extracto)
                .where(Extracto.cliente_id == cliente_id)
                .order_by(Extracto.id.desc())
            )
        )

    @staticmethod
    def obtener_extracto(extracto_id: int, actor: Usuario) -> Extracto:
        extracto = db.session.get(Extracto, extracto_id)
        if extracto is None:
            raise ApiError("El extracto no existe.", codigo="no_encontrado", status=404)
        ClienteService.obtener(extracto.cliente_id, actor)
        return extracto

    @staticmethod
    def importar(cliente_id: int, datos: dict, actor: Usuario) -> Extracto:
        ClienteService.obtener(cliente_id, actor)
        movimientos = parsear_csv(datos["csv"])

        extracto = Extracto(
            cliente_id=cliente_id,
            banco=datos["banco"].strip(),
            periodo=datos["periodo"].strip(),
            saldo_inicial=Decimal(datos.get("saldo_inicial") or 0).quantize(CENTAVO),
            saldo_final=Decimal(datos.get("saldo_final") or 0).quantize(CENTAVO),
            creado_por_id=actor.id,
        )

        for movimiento in movimientos:
            extracto.movimientos.append(
                MovimientoBancario(
                    fecha=movimiento["fecha"],
                    descripcion=movimiento["descripcion"],
                    importe=movimiento["importe"],
                    estado=EstadoMovimiento.PENDIENTE,
                )
            )

        db.session.add(extracto)
        db.session.commit()
        return extracto

    @staticmethod
    def eliminar_extracto(extracto_id: int, actor: Usuario) -> None:
        extracto = ConciliacionService.obtener_extracto(extracto_id, actor)
        db.session.delete(extracto)
        db.session.commit()

    @staticmethod
    def vincular(
        movimiento_id: int,
        actor: Usuario,
        *,
        asiento_id: int | None = None,
        comprobante_id: int | None = None,
    ) -> MovimientoBancario:
        movimiento = ConciliacionService._movimiento(movimiento_id, actor)
        cliente_id = movimiento.extracto.cliente_id

        if comprobante_id is not None:
            from app.models.comprobante import Comprobante, EstadoComprobante

            comprobante = db.session.get(Comprobante, comprobante_id)
            if (
                comprobante is None
                or comprobante.cliente_id != cliente_id
                or comprobante.estado == EstadoComprobante.ANULADO.value
            ):
                raise ApiError(
                    "El comprobante no es válido para este cliente.",
                    codigo="comprobante_invalido",
                    status=422,
                )

            ya_vinculado = db.session.scalar(
                select(MovimientoBancario.id).where(
                    MovimientoBancario.comprobante_id == comprobante.id,
                    MovimientoBancario.id != movimiento.id,
                )
            )
            if ya_vinculado is not None:
                raise ApiError(
                    "Ese comprobante ya está conciliado con otro movimiento.",
                    codigo="comprobante_ya_vinculado",
                    status=409,
                )

            movimiento.comprobante_id = comprobante.id
            movimiento.asiento_id = comprobante.asiento_id
            movimiento.estado = EstadoMovimiento.CONCILIADO
            db.session.commit()
            return movimiento

        asiento = db.session.get(Asiento, asiento_id) if asiento_id else None
        if (
            asiento is None
            or asiento.cliente_id != cliente_id
            or asiento.estado != EstadoAsiento.CONFIRMADO.value
        ):
            raise ApiError(
                "El asiento no es válido para este cliente.",
                codigo="asiento_invalido",
                status=422,
            )

        ya_vinculado = db.session.scalar(
            select(MovimientoBancario.id).where(
                MovimientoBancario.asiento_id == asiento.id,
                MovimientoBancario.id != movimiento.id,
            )
        )
        if ya_vinculado is not None:
            raise ApiError(
                "Ese asiento ya está conciliado con otro movimiento.",
                codigo="asiento_ya_vinculado",
                status=409,
            )

        movimiento.asiento_id = asiento.id
        movimiento.comprobante_id = None
        movimiento.estado = EstadoMovimiento.CONCILIADO
        db.session.commit()
        return movimiento

    @staticmethod
    def generar_asiento(
        movimiento_id: int, cuenta_id: int, actor: Usuario, concepto: str | None = None
    ) -> tuple[MovimientoBancario, Asiento]:
        movimiento = ConciliacionService._movimiento(movimiento_id, actor)

        if movimiento.estado != EstadoMovimiento.PENDIENTE:
            raise ApiError(
                "Solo se puede generar un asiento para movimientos pendientes.",
                codigo="movimiento_no_pendiente",
                status=409,
            )

        cliente_id = movimiento.extracto.cliente_id
        cuenta = db.session.get(Cuenta, cuenta_id)
        if (
            cuenta is None
            or cuenta.cliente_id != cliente_id
            or not cuenta.imputable
            or not cuenta.activa
        ):
            raise ApiError(
                "La cuenta elegida no es imputable o no pertenece al cliente.",
                codigo="cuenta_invalida",
                status=422,
            )

        banco = db.session.scalar(
            select(Cuenta).where(
                Cuenta.cliente_id == cliente_id, Cuenta.codigo == "1.1.02"
            )
        )
        if banco is None:
            raise ApiError(
                "El plan de cuentas no tiene la cuenta Banco (1.1.02).",
                codigo="plan_incompleto",
                status=409,
            )

        importe = abs(Decimal(str(movimiento.importe)))
        if importe == 0:
            raise ApiError(
                "El movimiento no tiene importe.", codigo="importe_invalido", status=422
            )

        # Importe positivo: entra plata al banco (debe banco / haber contrapartida).
        if Decimal(str(movimiento.importe)) >= 0:
            renglones = [
                {"cuenta_id": banco.id, "debe": str(importe), "haber": "0.00"},
                {"cuenta_id": cuenta.id, "debe": "0.00", "haber": str(importe)},
            ]
        else:
            renglones = [
                {"cuenta_id": cuenta.id, "debe": str(importe), "haber": "0.00"},
                {"cuenta_id": banco.id, "debe": "0.00", "haber": str(importe)},
            ]

        asiento = AsientoService.crear_confirmado(
            cliente_id,
            fecha=movimiento.fecha,
            concepto=(concepto or f"Movimiento bancario: {movimiento.descripcion}"),
            renglones=renglones,
            actor=actor,
        )

        movimiento.asiento_id = asiento.id
        movimiento.comprobante_id = None
        movimiento.estado = EstadoMovimiento.CONCILIADO
        db.session.commit()

        return movimiento, asiento

    @staticmethod
    def desvincular(movimiento_id: int, actor: Usuario) -> MovimientoBancario:
        movimiento = ConciliacionService._movimiento(movimiento_id, actor)
        movimiento.asiento_id = None
        movimiento.comprobante_id = None
        movimiento.estado = EstadoMovimiento.PENDIENTE
        db.session.commit()
        return movimiento

    @staticmethod
    def descartar(movimiento_id: int, actor: Usuario) -> MovimientoBancario:
        movimiento = ConciliacionService._movimiento(movimiento_id, actor)
        movimiento.estado = EstadoMovimiento.DESCARTADO
        movimiento.asiento_id = None
        db.session.commit()
        return movimiento

    @staticmethod
    def resumen(extracto: Extracto) -> dict:
        total = sum((Decimal(str(m.importe)) for m in extracto.movimientos), Decimal("0.00"))
        conciliados = sum(
            1 for m in extracto.movimientos if m.estado == EstadoMovimiento.CONCILIADO
        )
        pendientes = sum(
            1 for m in extracto.movimientos if m.estado == EstadoMovimiento.PENDIENTE
        )
        conciliado_total = sum(
            (
                Decimal(str(m.importe))
                for m in extracto.movimientos
                if m.estado == EstadoMovimiento.CONCILIADO
            ),
            Decimal("0.00"),
        )

        return {
            "movimientos": len(extracto.movimientos),
            "conciliados": conciliados,
            "pendientes": pendientes,
            "suma_movimientos": str(total.quantize(CENTAVO)),
            "saldo_contable": str(
                (Decimal(str(extracto.saldo_inicial)) + conciliado_total).quantize(CENTAVO)
            ),
            "diferencia": str(
                (Decimal(str(extracto.saldo_inicial)) + total - Decimal(str(extracto.saldo_final))).quantize(CENTAVO)
            ),
        }

    @staticmethod
    def sugerencias(movimiento: MovimientoBancario, extracto: Extracto) -> list[dict]:
        """Asientos confirmados con total igual al importe y fecha cercana."""
        importe = abs(Decimal(str(movimiento.importe)))
        desde = movimiento.fecha - timedelta(days=3)
        hasta = movimiento.fecha + timedelta(days=3)

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
            .join(totales, totales.c.asiento_id == Asiento.id)
            .where(
                Asiento.cliente_id == extracto.cliente_id,
                Asiento.estado == EstadoAsiento.CONFIRMADO.value,
                Asiento.fecha >= desde,
                Asiento.fecha <= hasta,
            )
            .order_by(Asiento.fecha)
        ).all()

        sugerencias = []
        for asiento, total in filas:
            if Decimal(str(total)).quantize(CENTAVO) != importe:
                continue

            dias = abs((asiento.fecha - movimiento.fecha).days)
            confianza = {0: 100, 1: 90, 2: 75, 3: 60}.get(dias, 40)

            sugerencias.append(
                {
                    "asiento_id": asiento.id,
                    "numero": asiento.numero,
                    "fecha": asiento.fecha.isoformat(),
                    "concepto": asiento.concepto,
                    "total": str(total),
                    "confianza": confianza,
                }
            )

        return sorted(sugerencias, key=lambda s: -s["confianza"])

    @staticmethod
    def _movimiento(movimiento_id: int, actor: Usuario) -> MovimientoBancario:
        movimiento = db.session.get(MovimientoBancario, movimiento_id)
        if movimiento is None:
            raise ApiError(
                "El movimiento no existe.", codigo="no_encontrado", status=404
            )
        ClienteService.obtener(movimiento.extracto.cliente_id, actor)
        return movimiento

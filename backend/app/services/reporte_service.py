"""Reportes contables sobre asientos confirmados."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.extensions import db
from app.models.asiento import Asiento, EstadoAsiento, RenglonAsiento
from app.models.comprobante import Comprobante, EstadoComprobante
from app.models.cuenta import Cuenta
from app.models.usuario import Usuario
from app.services.cliente_service import ClienteService

CERO = Decimal("0.00")


def _decimal(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(CERO)


class ReporteService:
    @staticmethod
    def diario(cliente_id: int, actor: Usuario, desde: date, hasta: date) -> list[dict]:
        ClienteService.obtener(cliente_id, actor)

        asientos = db.session.scalars(
            select(Asiento)
            .where(
                Asiento.cliente_id == cliente_id,
                Asiento.estado == EstadoAsiento.CONFIRMADO.value,
                Asiento.fecha >= desde,
                Asiento.fecha <= hasta,
            )
            .order_by(Asiento.fecha, Asiento.numero)
        ).all()

        return [
            {
                "numero": asiento.numero,
                "fecha": asiento.fecha.isoformat(),
                "concepto": asiento.concepto,
                "renglones": [
                    {
                        "cuenta_codigo": renglon.cuenta.codigo,
                        "cuenta_nombre": renglon.cuenta.nombre,
                        "debe": str(renglon.debe),
                        "haber": str(renglon.haber),
                    }
                    for renglon in asiento.renglones
                ],
            }
            for asiento in asientos
        ]

    @staticmethod
    def mayor(
        cliente_id: int, actor: Usuario, cuenta_id: int, desde: date, hasta: date
    ) -> dict:
        ClienteService.obtener(cliente_id, actor)

        cuenta = db.session.get(Cuenta, cuenta_id)
        if cuenta is None or cuenta.cliente_id != cliente_id:
            from app.utils.errors import ApiError

            raise ApiError("La cuenta no existe.", codigo="no_encontrado", status=404)

        anterior = db.session.execute(
            select(
                func.coalesce(func.sum(RenglonAsiento.debe), 0),
                func.coalesce(func.sum(RenglonAsiento.haber), 0),
            )
            .join(Asiento, Asiento.id == RenglonAsiento.asiento_id)
            .where(
                RenglonAsiento.cuenta_id == cuenta_id,
                Asiento.estado == EstadoAsiento.CONFIRMADO.value,
                Asiento.fecha < desde,
            )
        ).one()

        saldo_inicial = _decimal(anterior[0]) - _decimal(anterior[1])

        filas = db.session.execute(
            select(Asiento.fecha, Asiento.numero, Asiento.concepto, RenglonAsiento.debe, RenglonAsiento.haber)
            .join(RenglonAsiento, RenglonAsiento.asiento_id == Asiento.id)
            .where(
                RenglonAsiento.cuenta_id == cuenta_id,
                Asiento.estado == EstadoAsiento.CONFIRMADO.value,
                Asiento.fecha >= desde,
                Asiento.fecha <= hasta,
            )
            .order_by(Asiento.fecha, Asiento.numero)
        ).all()

        movimientos = []
        saldo = saldo_inicial
        for fecha, numero, concepto, debe, haber in filas:
            saldo += _decimal(debe) - _decimal(haber)
            movimientos.append(
                {
                    "fecha": fecha.isoformat(),
                    "numero": numero,
                    "concepto": concepto,
                    "debe": str(_decimal(debe)),
                    "haber": str(_decimal(haber)),
                    "saldo": str(saldo),
                }
            )

        return {
            "cuenta": {
                "codigo": cuenta.codigo,
                "nombre": cuenta.nombre,
                "tipo": cuenta.tipo,
            },
            "saldo_inicial": str(saldo_inicial),
            "movimientos": movimientos,
            "saldo_final": str(saldo),
        }

    @staticmethod
    def balance(cliente_id: int, actor: Usuario, desde: date, hasta: date) -> dict:
        ClienteService.obtener(cliente_id, actor)

        filas = db.session.execute(
            select(
                Cuenta.codigo,
                Cuenta.nombre,
                Cuenta.tipo,
                func.coalesce(func.sum(RenglonAsiento.debe), 0),
                func.coalesce(func.sum(RenglonAsiento.haber), 0),
            )
            .join(RenglonAsiento, RenglonAsiento.cuenta_id == Cuenta.id)
            .join(Asiento, Asiento.id == RenglonAsiento.asiento_id)
            .where(
                Cuenta.cliente_id == cliente_id,
                Asiento.estado == EstadoAsiento.CONFIRMADO.value,
                Asiento.fecha >= desde,
                Asiento.fecha <= hasta,
            )
            .group_by(Cuenta.id, Cuenta.codigo, Cuenta.nombre, Cuenta.tipo)
            .order_by(Cuenta.codigo)
        ).all()

        cuentas = []
        total_debe = CERO
        total_haber = CERO

        for codigo, nombre, tipo, debe, haber in filas:
            debe_d = _decimal(debe)
            haber_d = _decimal(haber)
            total_debe += debe_d
            total_haber += haber_d
            cuentas.append(
                {
                    "codigo": codigo,
                    "nombre": nombre,
                    "tipo": tipo,
                    "debe": str(debe_d),
                    "haber": str(haber_d),
                    "saldo": str(debe_d - haber_d),
                }
            )

        return {
            "cuentas": cuentas,
            "total_debe": str(total_debe),
            "total_haber": str(total_haber),
            "diferencia": str(total_debe - total_haber),
        }

    @staticmethod
    def libro_iva(cliente_id: int, actor: Usuario, desde: date, hasta: date) -> dict:
        ClienteService.obtener(cliente_id, actor)

        comprobantes = db.session.scalars(
            select(Comprobante)
            .where(
                Comprobante.cliente_id == cliente_id,
                Comprobante.estado == EstadoComprobante.CONTABILIZADO.value,
                Comprobante.fecha >= desde,
                Comprobante.fecha <= hasta,
            )
            .order_by(Comprobante.fecha, Comprobante.id)
        ).all()

        def bloque(tipo: str) -> dict:
            items = [c for c in comprobantes if c.tipo == tipo]
            return {
                "items": [
                    {
                        "numero": c.numero,
                        "fecha": c.fecha.isoformat(),
                        "tercero": c.tercero,
                        "neto": str(c.neto),
                        "iva": str(c.iva),
                        "total": str(c.total),
                    }
                    for c in items
                ],
                "neto": str(sum((_decimal(c.neto) for c in items), CERO)),
                "iva": str(sum((_decimal(c.iva) for c in items), CERO)),
                "total": str(sum((_decimal(c.total) for c in items), CERO)),
            }

        return {"ventas": bloque("venta"), "compras": bloque("compra")}

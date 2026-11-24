"""Reglas de negocio de comprobantes y contabilización."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.asiento import Asiento, EstadoAsiento, RenglonAsiento
from app.models.comprobante import Comprobante, EstadoComprobante, TipoComprobante
from app.models.cuenta import Cuenta
from app.models.usuario import Rol, Usuario
from app.services.asiento_service import AsientoService
from app.services.auditoria_service import AuditoriaService
from app.services.cliente_service import ClienteService
from app.utils.errors import ApiError

CENTAVO = Decimal("0.01")
CIEN = Decimal("100")
ALICUOTAS = {
    Decimal("0.00"),
    Decimal("10.50"),
    Decimal("21.00"),
    Decimal("27.00"),
}

# Códigos del plan base que usa la contabilización.
CUENTAS_POR_TIPO = {
    "venta": {
        "deudores": "1.2.01",
        "ingreso": "4.1.01",
        "iva": "2.2.01",
    },
    "compra": {
        "gasto": "5.1.01",
        "iva": "1.3.01",
        "proveedores": "2.1.01",
    },
}
ETIQUETAS_CUENTA = {
    "1.2.01": "Deudores por ventas",
    "4.1.01": "Ventas",
    "2.2.01": "IVA débito fiscal",
    "5.1.01": "Compras",
    "1.3.01": "IVA crédito fiscal",
    "2.1.01": "Proveedores",
}


def calcular_iva(neto: Decimal, alicuota: Decimal) -> tuple[Decimal, Decimal]:
    iva = (neto * alicuota / CIEN).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    return iva, neto + iva


class ComprobanteService:
    @staticmethod
    def listar(
        cliente_id: int,
        actor: Usuario,
        *,
        tipo: str | None = None,
        estado: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        q: str | None = None,
    ) -> list[Comprobante]:
        ClienteService.obtener(cliente_id, actor)

        consulta = select(Comprobante).where(Comprobante.cliente_id == cliente_id)

        if tipo:
            consulta = consulta.where(Comprobante.tipo == tipo)
        if estado:
            consulta = consulta.where(Comprobante.estado == estado)
        if desde:
            consulta = consulta.where(Comprobante.fecha >= desde)
        if hasta:
            consulta = consulta.where(Comprobante.fecha <= hasta)
        if q:
            consulta = consulta.where(Comprobante.tercero.ilike(f"%{q.strip()}%"))

        consulta = consulta.order_by(Comprobante.fecha.desc(), Comprobante.id.desc())
        return list(db.session.scalars(consulta))

    @staticmethod
    def listar_global(
        actor: Usuario,
        *,
        cliente_id: int | None = None,
        tipo: str | None = None,
        estado: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        q: str | None = None,
    ) -> tuple[list[Comprobante], dict[int, str]]:
        """Comprobantes de todos los clientes visibles para el actor."""
        clientes = ClienteService.listar(actor)
        ids = [cliente.id for cliente in clientes]
        nombres = {cliente.id: cliente.razon_social for cliente in clientes}

        if not ids:
            return [], nombres
        if cliente_id is not None and cliente_id not in ids:
            raise ApiError(
                "El cliente no existe.", codigo="no_encontrado", status=404
            )

        consulta = select(Comprobante).where(Comprobante.cliente_id.in_(ids))
        if cliente_id is not None:
            consulta = consulta.where(Comprobante.cliente_id == cliente_id)
        if tipo:
            consulta = consulta.where(Comprobante.tipo == tipo)
        if estado:
            consulta = consulta.where(Comprobante.estado == estado)
        if desde:
            consulta = consulta.where(Comprobante.fecha >= desde)
        if hasta:
            consulta = consulta.where(Comprobante.fecha <= hasta)
        if q:
            patron = f"%{q.strip()}%"
            consulta = consulta.where(
                (Comprobante.tercero.ilike(patron))
                | (Comprobante.numero.ilike(patron))
            )

        consulta = consulta.order_by(Comprobante.fecha.desc(), Comprobante.id.desc())
        return list(db.session.scalars(consulta)), nombres

    @staticmethod
    def obtener(comprobante_id: int, actor: Usuario) -> Comprobante:
        comprobante = db.session.get(Comprobante, comprobante_id)
        if comprobante is None:
            raise ApiError(
                "El comprobante no existe.", codigo="no_encontrado", status=404
            )

        ClienteService.obtener(comprobante.cliente_id, actor)
        return comprobante

    @staticmethod
    def crear(cliente_id: int, datos: dict, actor: Usuario) -> Comprobante:
        cliente, _ = ClienteService.obtener(cliente_id, actor)

        if not cliente.activo:
            raise ApiError(
                "El cliente está inactivo: no admite comprobantes.",
                codigo="cliente_inactivo",
                status=409,
            )

        # El rol cliente sólo puede subir sus propias facturas de compra.
        if actor.rol == Rol.CLIENTE.value and datos["tipo"] != "compra":
            raise ApiError(
                "Como cliente sólo podés subir comprobantes de compra.",
                codigo="tipo_no_permitido",
                status=403,
            )

        ComprobanteService._validar_fecha(datos["fecha"])
        ComprobanteService._validar_alicuota(datos["alicuota_iva"])

        neto = Decimal(datos["neto"]).quantize(CENTAVO)
        iva, total = calcular_iva(neto, Decimal(datos["alicuota_iva"]))

        comprobante = Comprobante(
            cliente_id=cliente_id,
            tipo=datos["tipo"],
            numero=datos["numero"].strip(),
            fecha=datos["fecha"],
            tercero=datos["tercero"].strip(),
            neto=neto,
            alicuota_iva=Decimal(datos["alicuota_iva"]).quantize(CENTAVO),
            iva=iva,
            total=total,
            estado=EstadoComprobante.PENDIENTE.value,
            creado_por_id=actor.id,
        )

        db.session.add(comprobante)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ApiError(
                "Ya existe un comprobante con ese número para ese tipo y cliente.",
                codigo="numero_duplicado",
                status=409,
                detalles={"numero": ["Número ya registrado."]},
            )

        return comprobante

    @staticmethod
    def actualizar(comprobante_id: int, datos: dict, actor: Usuario) -> Comprobante:
        comprobante = ComprobanteService.obtener(comprobante_id, actor)

        if comprobante.estado != EstadoComprobante.PENDIENTE.value:
            raise ApiError(
                "Solo los comprobantes pendientes se pueden editar.",
                codigo="comprobante_no_editable",
                status=409,
            )

        ComprobanteService._validar_fecha(datos["fecha"])
        ComprobanteService._validar_alicuota(datos["alicuota_iva"])

        neto = Decimal(datos["neto"]).quantize(CENTAVO)
        iva, total = calcular_iva(neto, Decimal(datos["alicuota_iva"]))

        comprobante.tipo = datos["tipo"]
        comprobante.numero = datos["numero"].strip()
        comprobante.fecha = datos["fecha"]
        comprobante.tercero = datos["tercero"].strip()
        comprobante.neto = neto
        comprobante.alicuota_iva = Decimal(datos["alicuota_iva"]).quantize(CENTAVO)
        comprobante.iva = iva
        comprobante.total = total

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ApiError(
                "Ya existe un comprobante con ese número para ese tipo y cliente.",
                codigo="numero_duplicado",
                status=409,
            )

        return comprobante

    @staticmethod
    def contabilizar(comprobante_id: int, actor: Usuario) -> Comprobante:
        # Bloqueo de fila: dos clics simultáneos no generan dos asientos.
        comprobante = db.session.get(
            Comprobante, comprobante_id, with_for_update=True
        )
        if comprobante is None:
            raise ApiError(
                "El comprobante no existe.", codigo="no_encontrado", status=404
            )

        ClienteService.obtener(comprobante.cliente_id, actor)

        if comprobante.estado == EstadoComprobante.CONTABILIZADO.value:
            raise ApiError(
                "El comprobante ya está contabilizado.",
                codigo="ya_contabilizado",
                status=409,
            )
        if comprobante.estado == EstadoComprobante.ANULADO.value:
            raise ApiError(
                "El comprobante está anulado.",
                codigo="comprobante_anulado",
                status=409,
            )

        cuentas = ComprobanteService._cuentas_para(comprobante)
        renglones = ComprobanteService._renglones_contables(comprobante, cuentas)

        asiento = AsientoService.crear_confirmado(
            comprobante.cliente_id,
            fecha=comprobante.fecha,
            concepto=ComprobanteService._concepto(comprobante),
            renglones=renglones,
            actor=actor,
        )

        comprobante.asiento = asiento
        comprobante.estado = EstadoComprobante.CONTABILIZADO.value

        try:
            db.session.flush()
            AuditoriaService.registrar(
                actor,
                "contabilizar",
                "comprobante",
                comprobante.id,
                despues={
                    "numero": comprobante.numero,
                    "asiento_id": asiento.id,
                    "total": str(comprobante.total),
                },
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ApiError(
                "El comprobante ya fue contabilizado.",
                codigo="ya_contabilizado",
                status=409,
            )

        return comprobante

    @staticmethod
    def anular(comprobante_id: int, actor: Usuario) -> Comprobante:
        comprobante = ComprobanteService.obtener(comprobante_id, actor)

        if comprobante.estado == EstadoComprobante.ANULADO.value:
            raise ApiError(
                "El comprobante ya está anulado.",
                codigo="ya_anulado",
                status=409,
            )

        motivo = f"Anulación del comprobante {comprobante.tipo} {comprobante.numero}"

        if comprobante.asiento is not None and comprobante.asiento.estado != EstadoAsiento.ANULADO.value:
            comprobante.asiento.estado = EstadoAsiento.ANULADO.value
            comprobante.asiento.motivo_anulacion = motivo
            comprobante.asiento.anulado_por_id = actor.id
            comprobante.asiento.anulado_en = datetime.now().astimezone()

        comprobante.estado = EstadoComprobante.ANULADO.value
        comprobante.motivo_anulacion = motivo
        comprobante.anulado_en = datetime.now().astimezone()
        AuditoriaService.registrar(
            actor,
            "anular",
            "comprobante",
            comprobante.id,
            antes={"estado": EstadoComprobante.CONTABILIZADO.value if comprobante.asiento else EstadoComprobante.PENDIENTE.value},
            despues={"numero": comprobante.numero, "motivo": motivo},
        )
        db.session.commit()

        return comprobante

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _cuentas_para(comprobante: Comprobante) -> dict[str, Cuenta]:
        codigos = CUENTAS_POR_TIPO[comprobante.tipo]
        cuentas = {
            cuenta.codigo: cuenta
            for cuenta in db.session.scalars(
                select(Cuenta).where(
                    Cuenta.cliente_id == comprobante.cliente_id,
                    Cuenta.codigo.in_(list(codigos.values())),
                )
            )
        }

        faltantes = [codigo for codigo in codigos.values() if codigo not in cuentas]
        if faltantes:
            nombres = ", ".join(
                f"{codigo} ({ETIQUETAS_CUENTA.get(codigo, 'cuenta')})"
                for codigo in faltantes
            )
            raise ApiError(
                f"El plan de cuentas no tiene las cuentas necesarias: {nombres}.",
                codigo="plan_incompleto",
                status=409,
                detalles={"codigos": faltantes},
            )

        return cuentas

    @staticmethod
    def _renglones_contables(
        comprobante: Comprobante, cuentas: dict[str, Cuenta]
    ) -> list[dict]:
        neto = Decimal(comprobante.neto)
        iva = Decimal(comprobante.iva)
        total = Decimal(comprobante.total)

        if comprobante.tipo == TipoComprobante.VENTA.value:
            renglones = [
                {"cuenta_id": cuentas["1.2.01"].id, "debe": str(total), "haber": "0.00"},
                {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": str(neto)},
            ]
            if iva > 0:
                renglones.append(
                    {
                        "cuenta_id": cuentas["2.2.01"].id,
                        "debe": "0.00",
                        "haber": str(iva),
                    }
                )
            return renglones

        renglones = [
            {"cuenta_id": cuentas["5.1.01"].id, "debe": str(neto), "haber": "0.00"},
        ]
        if iva > 0:
            renglones.append(
                {"cuenta_id": cuentas["1.3.01"].id, "debe": str(iva), "haber": "0.00"}
            )
        renglones.append(
            {"cuenta_id": cuentas["2.1.01"].id, "debe": "0.00", "haber": str(total)}
        )
        return renglones

    @staticmethod
    def _concepto(comprobante: Comprobante) -> str:
        return (
            f"Comprobante {comprobante.tipo} {comprobante.numero} — {comprobante.tercero}"
        )[:200]

    @staticmethod
    def _validar_fecha(fecha: date) -> None:
        if fecha > date.today():
            raise ApiError(
                "La fecha del comprobante no puede ser futura.",
                codigo="fecha_invalida",
                status=422,
                detalles={"fecha": ["La fecha no puede ser futura."]},
            )

    @staticmethod
    def _validar_alicuota(alicuota) -> None:
        if Decimal(alicuota) not in ALICUOTAS:
            raise ApiError(
                "La alícuota de IVA debe ser 0, 10.5, 21 o 27.",
                codigo="alicuota_invalida",
                status=422,
                detalles={"alicuota_iva": ["Alícuota no permitida."]},
            )

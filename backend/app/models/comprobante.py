"""Comprobantes (facturas de compra y venta) y su asiento asociado."""

import enum

from app.extensions import db


class TipoComprobante(str, enum.Enum):
    COMPRA = "compra"
    VENTA = "venta"

    @property
    def etiqueta(self) -> str:
        return {"compra": "Compra", "venta": "Venta"}[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [tipo.value for tipo in cls]


class EstadoComprobante(str, enum.Enum):
    PENDIENTE = "pendiente"
    CONTABILIZADO = "contabilizado"
    ANULADO = "anulado"

    @property
    def etiqueta(self) -> str:
        return {
            "pendiente": "Pendiente",
            "contabilizado": "Contabilizado",
            "anulado": "Anulado",
        }[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [estado.value for estado in cls]


class Comprobante(db.Model):
    __tablename__ = "comprobantes"
    __table_args__ = (
        db.UniqueConstraint(
            "cliente_id", "tipo", "numero", name="uq_comprobantes_cliente_tipo_numero"
        ),
        db.CheckConstraint(
            "tipo IN ('compra', 'venta')", name="ck_comprobantes_tipo"
        ),
        db.CheckConstraint(
            "estado IN ('pendiente', 'contabilizado', 'anulado')",
            name="ck_comprobantes_estado",
        ),
        db.CheckConstraint(
            "neto >= 0 AND iva >= 0 AND total >= 0",
            name="ck_comprobantes_importes",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tipo = db.Column(db.String(10), nullable=False)
    numero = db.Column(db.String(40), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    tercero = db.Column(db.String(160), nullable=False)

    neto = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    alicuota_iva = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    iva = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    estado = db.Column(
        db.String(20), nullable=False, default=EstadoComprobante.PENDIENTE.value
    )

    # Un comprobante genera como máximo un asiento (1:1).
    asiento_id = db.Column(
        db.Integer,
        db.ForeignKey("asientos.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    motivo_anulacion = db.Column(db.String(300), nullable=True)
    anulado_en = db.Column(db.DateTime(timezone=True), nullable=True)

    creado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    asiento = db.relationship("Asiento", lazy="selectin")
    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_id], lazy="selectin")

    @property
    def tipo_etiqueta(self) -> str:
        return TipoComprobante(self.tipo).etiqueta

    @property
    def estado_etiqueta(self) -> str:
        return EstadoComprobante(self.estado).etiqueta

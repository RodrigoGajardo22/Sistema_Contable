"""Asientos contables y sus renglones (partida doble)."""

import enum

from app.extensions import db


class EstadoAsiento(str, enum.Enum):
    BORRADOR = "borrador"
    CONFIRMADO = "confirmado"
    ANULADO = "anulado"

    @property
    def etiqueta(self) -> str:
        return {
            "borrador": "Borrador",
            "confirmado": "Confirmado",
            "anulado": "Anulado",
        }[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [estado.value for estado in cls]


class Asiento(db.Model):
    __tablename__ = "asientos"
    __table_args__ = (
        db.UniqueConstraint("cliente_id", "numero", name="uq_asientos_cliente_numero"),
        db.CheckConstraint(
            "estado IN ('borrador', 'confirmado', 'anulado')",
            name="ck_asientos_estado",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    numero = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    concepto = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default=EstadoAsiento.BORRADOR.value)

    creado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    anulado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    motivo_anulacion = db.Column(db.String(300), nullable=True)
    anulado_en = db.Column(db.DateTime(timezone=True), nullable=True)

    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    renglones = db.relationship(
        "RenglonAsiento",
        back_populates="asiento",
        cascade="all, delete-orphan",
        order_by="RenglonAsiento.id",
        lazy="selectin",
    )
    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_id], lazy="joined")
    anulado_por = db.relationship("Usuario", foreign_keys=[anulado_por_id], lazy="joined")

    @property
    def estado_etiqueta(self) -> str:
        return EstadoAsiento(self.estado).etiqueta


class RenglonAsiento(db.Model):
    __tablename__ = "renglones_asiento"
    __table_args__ = (
        db.CheckConstraint(
            "debe >= 0 AND haber >= 0 AND NOT (debe > 0 AND haber > 0)",
            name="ck_renglones_un_solo_lado",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    asiento_id = db.Column(
        db.Integer,
        db.ForeignKey("asientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cuenta_id = db.Column(
        db.Integer,
        db.ForeignKey("cuentas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    debe = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    haber = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    asiento = db.relationship("Asiento", back_populates="renglones")
    cuenta = db.relationship("Cuenta", lazy="joined")

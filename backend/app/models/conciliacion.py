"""Conciliación bancaria: extractos y movimientos."""

from app.extensions import db


class Extracto(db.Model):
    __tablename__ = "extractos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    banco = db.Column(db.String(80), nullable=False)
    periodo = db.Column(db.String(10), nullable=False)
    saldo_inicial = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    saldo_final = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    creado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    movimientos = db.relationship(
        "MovimientoBancario",
        back_populates="extracto",
        cascade="all, delete-orphan",
        order_by="MovimientoBancario.fecha",
        lazy="selectin",
    )


class EstadoMovimiento:
    PENDIENTE = "pendiente"
    CONCILIADO = "conciliado"
    DESCARTADO = "descartado"


class MovimientoBancario(db.Model):
    __tablename__ = "movimientos_bancarios"

    id = db.Column(db.Integer, primary_key=True)
    extracto_id = db.Column(
        db.Integer,
        db.ForeignKey("extractos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha = db.Column(db.Date, nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    importe = db.Column(db.Numeric(14, 2), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default=EstadoMovimiento.PENDIENTE)

    asiento_id = db.Column(
        db.Integer, db.ForeignKey("asientos.id", ondelete="SET NULL"), nullable=True
    )
    comprobante_id = db.Column(
        db.Integer, db.ForeignKey("comprobantes.id", ondelete="SET NULL"), nullable=True
    )

    extracto = db.relationship("Extracto", back_populates="movimientos")
    asiento = db.relationship("Asiento", lazy="selectin")
    comprobante = db.relationship("Comprobante", lazy="selectin")

    @property
    def estado_etiqueta(self) -> str:
        return {
            "pendiente": "Pendiente",
            "conciliado": "Conciliado",
            "descartado": "Descartado",
        }[self.estado]

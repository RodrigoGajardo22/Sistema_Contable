"""Plan de cuentas contable de cada cliente."""

import enum

from app.extensions import db


class TipoCuenta(str, enum.Enum):
    ACTIVO = "activo"
    PASIVO = "pasivo"
    PATRIMONIO = "patrimonio"
    INGRESO = "ingreso"
    EGRESO = "egreso"

    @property
    def etiqueta(self) -> str:
        return {
            "activo": "Activo",
            "pasivo": "Pasivo",
            "patrimonio": "Patrimonio neto",
            "ingreso": "Ingreso",
            "egreso": "Egreso",
        }[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [tipo.value for tipo in cls]


class Cuenta(db.Model):
    __tablename__ = "cuentas"
    __table_args__ = (
        db.UniqueConstraint("cliente_id", "codigo", name="uq_cuentas_cliente_codigo"),
        db.CheckConstraint(
            "tipo IN ('activo', 'pasivo', 'patrimonio', 'ingreso', 'egreso')",
            name="ck_cuentas_tipo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    codigo = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    padre_id = db.Column(
        db.Integer,
        db.ForeignKey("cuentas.id", ondelete="RESTRICT"),
        nullable=True,
    )
    imputable = db.Column(db.Boolean, nullable=False, default=False)
    activa = db.Column(db.Boolean, nullable=False, default=True)

    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    padre = db.relationship("Cuenta", remote_side=[id], back_populates="hijos")
    hijos = db.relationship(
        "Cuenta",
        back_populates="padre",
        cascade="save-update, merge",
        lazy="selectin",
    )

    @property
    def tipo_etiqueta(self) -> str:
        return TipoCuenta(self.tipo).etiqueta

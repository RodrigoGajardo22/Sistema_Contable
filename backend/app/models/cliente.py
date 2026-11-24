"""Clientes del estudio, con historial de versiones.

El cliente es una identidad estable (CUIT) y sus datos viven en versiones
inmutables: cada actualización inserta una fila nueva en ``cliente_versiones``
y las pantallas muestran la última. Así el historial no se puede perder ni
sobrescribir.
"""

import enum

from app.extensions import db


class CondicionIva(str, enum.Enum):
    RESPONSABLE_INSCRIPTO = "responsable_inscripto"
    MONOTRIBUTO = "monotributo"
    EXENTO = "exento"
    CONSUMIDOR_FINAL = "consumidor_final"

    @property
    def etiqueta(self) -> str:
        return {
            "responsable_inscripto": "Responsable Inscripto",
            "monotributo": "Monotributo",
            "exento": "Exento",
            "consumidor_final": "Consumidor Final",
        }[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [condicion.value for condicion in cls]


class Cliente(db.Model):
    """Identidad del cliente. Los datos editables viven en las versiones."""

    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    cuit = db.Column(db.String(11), nullable=False, unique=True, index=True)
    # Usuario con rol "cliente" vinculado (opcional, se usa más adelante).
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    versiones = db.relationship(
        "ClienteVersion",
        back_populates="cliente",
        cascade="all, delete-orphan",
        order_by="ClienteVersion.id",
    )
    usuario = db.relationship("Usuario", foreign_keys=[usuario_id], lazy="selectin")


class ClienteVersion(db.Model):
    """Foto inmutable de los datos del cliente en un momento dado."""

    __tablename__ = "cliente_versiones"
    __table_args__ = (
        db.CheckConstraint(
            "condicion_iva IN ('responsable_inscripto', 'monotributo', 'exento', 'consumidor_final')",
            name="ck_cliente_versiones_condicion_iva",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    razon_social = db.Column(db.String(160), nullable=False)
    condicion_iva = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(180), nullable=True)
    telefono = db.Column(db.String(40), nullable=True)
    direccion = db.Column(db.String(200), nullable=True)

    contador_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    creado_por_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )

    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    cliente = db.relationship("Cliente", back_populates="versiones")
    contador = db.relationship("Usuario", foreign_keys=[contador_id], lazy="joined")
    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_id], lazy="joined")

    @property
    def condicion_iva_etiqueta(self) -> str:
        return CondicionIva(self.condicion_iva).etiqueta

    @property
    def contador_nombre(self) -> str | None:
        return self.contador.nombre if self.contador else None

    @property
    def creado_por_nombre(self) -> str | None:
        return self.creado_por.nombre if self.creado_por else None

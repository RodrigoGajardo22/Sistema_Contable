"""Vencimientos impositivos por cliente."""

import enum

from app.extensions import db


class Obligacion(str, enum.Enum):
    IVA = "iva"
    INGRESOS_BRUTOS = "ingresos_brutos"
    GANANCIAS = "ganancias"
    AUTONOMOS = "autonomos"
    MUNICIPAL = "municipal"
    OTRO = "otro"

    @property
    def etiqueta(self) -> str:
        return {
            "iva": "IVA",
            "ingresos_brutos": "Ingresos Brutos",
            "ganancias": "Ganancias",
            "autonomos": "Autónomos",
            "municipal": "Municipal",
            "otro": "Otro",
        }[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [obligacion.value for obligacion in cls]


class EstadoVencimiento(str, enum.Enum):
    PENDIENTE = "pendiente"
    PRESENTADO = "presentado"
    PAGADO = "pagado"

    @property
    def etiqueta(self) -> str:
        return {
            "pendiente": "Pendiente",
            "presentado": "Presentado",
            "pagado": "Pagado",
        }[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [estado.value for estado in cls]


class Vencimiento(db.Model):
    __tablename__ = "vencimientos"
    __table_args__ = (
        db.CheckConstraint(
            "obligacion IN ('iva', 'ingresos_brutos', 'ganancias', 'autonomos', 'municipal', 'otro')",
            name="ck_vencimientos_obligacion",
        ),
        db.CheckConstraint(
            "estado IN ('pendiente', 'presentado', 'pagado')",
            name="ck_vencimientos_estado",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    obligacion = db.Column(db.String(30), nullable=False)
    periodo = db.Column(db.String(10), nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="pendiente")
    observaciones = db.Column(db.String(300), nullable=True)

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

    @property
    def obligacion_etiqueta(self) -> str:
        return Obligacion(self.obligacion).etiqueta

    @property
    def estado_etiqueta(self) -> str:
        return EstadoVencimiento(self.estado).etiqueta

    @property
    def vencido(self) -> bool:
        from datetime import date

        return self.estado != "pagado" and self.fecha_vencimiento < date.today()

"""Bitácora de auditoría (sólo lectura para el admin)."""

from app.extensions import db


class Auditoria(db.Model):
    __tablename__ = "auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    accion = db.Column(db.String(30), nullable=False)
    entidad = db.Column(db.String(40), nullable=False)
    entidad_id = db.Column(db.Integer, nullable=True)
    antes = db.Column(db.JSON, nullable=True)
    despues = db.Column(db.JSON, nullable=True)
    fecha = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    usuario = db.relationship("Usuario", lazy="joined")

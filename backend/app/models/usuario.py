"""Modelo de usuarios y roles."""

import enum

from app.extensions import db


class Rol(str, enum.Enum):
    ADMIN = "admin"
    CONTADOR = "contador"
    CLIENTE = "cliente"

    @property
    def etiqueta(self) -> str:
        return {
            "admin": "Administrador",
            "contador": "Contador",
            "cliente": "Cliente",
        }[self.value]

    @classmethod
    def valores(cls) -> list[str]:
        return [rol.value for rol in cls]


class Usuario(db.Model):
    __tablename__ = "usuarios"
    __table_args__ = (
        db.CheckConstraint(
            "rol IN ('admin', 'contador', 'cliente')",
            name="ck_usuarios_rol",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default=Rol.CONTADOR.value)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    # El propietario es un admin intocable: sólo él gestiona administradores.
    es_propietario = db.Column(
        db.Boolean, nullable=False, default=False, server_default="0"
    )
    # Se activa cuando la clave la generó el sistema (clientes y resets).
    debe_cambiar_password = db.Column(
        db.Boolean, nullable=False, default=False, server_default="0"
    )
    password_temporal_expira_en = db.Column(
        db.DateTime(timezone=True), nullable=True
    )
    # Se incrementa al cambiar la clave o revocar sesiones. Los JWT viejos
    # quedan inválidos al comparar este valor con el claim ``tv``.
    token_version = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )

    creado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    @property
    def rol_enum(self) -> Rol:
        return Rol(self.rol)

    @property
    def es_owner(self) -> bool:
        """True sólo para el admin marcado como propietario."""
        return self.rol == Rol.ADMIN.value and bool(self.es_propietario)

    def tiene_rol(self, *roles: str | Rol) -> bool:
        permitidos = {rol.value if isinstance(rol, Rol) else str(rol) for rol in roles}
        return self.rol in permitidos

    def __repr__(self) -> str:  # pragma: no cover - ayuda para debugging
        return f"<Usuario {self.email} ({self.rol})>"

"""Schemas de validación y serialización (Marshmallow)."""

from marshmallow import Schema, fields, validate
from sqlalchemy import select

from app.extensions import db
from app.models.cliente import Cliente
from app.models.usuario import Rol

ROLES = Rol.valores()
LARGO_MINIMO_PASSWORD = 8
LARGO_MAXIMO_PASSWORD = 128


class UsuarioSchema(Schema):
    """Salida: nunca expone password_hash."""

    id = fields.Int(dump_only=True)
    nombre = fields.Str()
    email = fields.Email()
    rol = fields.Str()
    activo = fields.Bool()
    es_propietario = fields.Bool()
    debe_cambiar_password = fields.Bool()
    cliente_id = fields.Method("get_cliente_id", dump_only=True)
    creado_en = fields.DateTime(format="iso")
    actualizado_en = fields.DateTime(format="iso")

    def get_cliente_id(self, usuario) -> int | None:
        """Id de la ficha propia cuando el usuario tiene rol cliente."""
        if usuario.rol != Rol.CLIENTE.value:
            return None
        return db.session.scalar(
            select(Cliente.id).where(Cliente.usuario_id == usuario.id)
        )


class UsuarioCreateSchema(Schema):
    nombre = fields.Str(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True, validate=validate.Length(max=180))
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(
            min=LARGO_MINIMO_PASSWORD,
            max=LARGO_MAXIMO_PASSWORD,
            error=f"La contraseña debe tener entre {LARGO_MINIMO_PASSWORD} y {LARGO_MAXIMO_PASSWORD} caracteres.",
        ),
    )
    # El rol "cliente" no se crea desde acá: se genera desde la ficha del
    # cliente para que quede vinculado a su usuario (POST /clientes/<id>/acceso).
    rol = fields.Str(required=True, validate=validate.OneOf(["admin", "contador"]))


class UsuarioUpdateSchema(Schema):
    nombre = fields.Str(validate=validate.Length(min=2, max=120))
    email = fields.Email(validate=validate.Length(max=180))
    rol = fields.Str(validate=validate.OneOf(["admin", "contador"]))


class CambioPasswordSchema(Schema):
    """Un admin cambia la de cualquiera; un usuario, la propia."""

    password_actual = fields.Str(load_only=True)
    password_nueva = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(
            min=LARGO_MINIMO_PASSWORD,
            max=LARGO_MAXIMO_PASSWORD,
            error=f"La contraseña debe tener entre {LARGO_MINIMO_PASSWORD} y {LARGO_MAXIMO_PASSWORD} caracteres.",
        ),
    )


class LoginSchema(Schema):
    # El formato se valida siempre; la existencia, nunca (login genérico).
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=1, max=LARGO_MAXIMO_PASSWORD))

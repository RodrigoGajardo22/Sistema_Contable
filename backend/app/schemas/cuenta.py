"""Schemas del plan de cuentas."""

from marshmallow import Schema, fields, validate

from app.models.cuenta import TipoCuenta

TIPOS_CUENTA = TipoCuenta.valores()


class CuentaCreateSchema(Schema):
    codigo = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    nombre = fields.Str(required=True, validate=validate.Length(min=2, max=120))
    tipo = fields.Str(required=True, validate=validate.OneOf(TIPOS_CUENTA))
    padre_id = fields.Int(allow_none=True, load_default=None)
    imputable = fields.Bool(load_default=False)


class CuentaUpdateSchema(Schema):
    nombre = fields.Str(validate=validate.Length(min=2, max=120))
    padre_id = fields.Int(allow_none=True)
    imputable = fields.Bool()
    activa = fields.Bool()


class CuentaSchema(Schema):
    id = fields.Int()
    cliente_id = fields.Int()
    codigo = fields.Str()
    nombre = fields.Str()
    tipo = fields.Str()
    tipo_etiqueta = fields.Str()
    padre_id = fields.Int(allow_none=True)
    imputable = fields.Bool()
    activa = fields.Bool()
    creado_en = fields.DateTime(format="iso")

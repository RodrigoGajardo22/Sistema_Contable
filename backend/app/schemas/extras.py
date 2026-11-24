"""Schemas de vencimientos y conciliación."""

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.models.vencimiento import EstadoVencimiento, Obligacion
from app.schemas.asiento import Monto

OBLIGACIONES = Obligacion.valores()
ESTADOS = EstadoVencimiento.valores()


class VencimientoCreateSchema(Schema):
    obligacion = fields.Str(required=True, validate=validate.OneOf(OBLIGACIONES))
    periodo = fields.Str(required=True, validate=validate.Length(min=3, max=10))
    fecha_vencimiento = fields.Date(required=True)
    observaciones = fields.Str(allow_none=True, validate=validate.Length(max=300))


class VencimientoUpdateSchema(Schema):
    obligacion = fields.Str(validate=validate.OneOf(OBLIGACIONES))
    periodo = fields.Str(validate=validate.Length(min=3, max=10))
    fecha_vencimiento = fields.Date()
    observaciones = fields.Str(allow_none=True, validate=validate.Length(max=300))


class EstadoVencimientoSchema(Schema):
    estado = fields.Str(required=True, validate=validate.OneOf(ESTADOS))


class ExtractoSchema(Schema):
    banco = fields.Str(required=True, validate=validate.Length(min=2, max=80))
    periodo = fields.Str(required=True, validate=validate.Length(min=3, max=10))
    saldo_inicial = Monto(as_string=True, load_default=None, allow_none=True)
    saldo_final = Monto(as_string=True, load_default=None, allow_none=True)
    csv = fields.Str(required=True)


class VincularSchema(Schema):
    asiento_id = fields.Int(allow_none=True, load_default=None)
    comprobante_id = fields.Int(allow_none=True, load_default=None)

    @validates_schema
    def uno_solo(self, datos, **kwargs):
        if bool(datos.get("asiento_id")) == bool(datos.get("comprobante_id")):
            raise ValidationError(
                "Indicá un asiento o un comprobante (exactamente uno).",
                field_name="asiento_id",
            )


class AsientoDesdeMovimientoSchema(Schema):
    cuenta_id = fields.Int(required=True)
    concepto = fields.Str(allow_none=True, validate=validate.Length(max=190))


class AccesoClienteSchema(Schema):
    nombre = fields.Str(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True, validate=validate.Length(max=180))
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))

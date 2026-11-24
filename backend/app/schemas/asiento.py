"""Schemas de importes y asientos.

Los importes se serializan como string ("1250.00") para que el frontend no
los trate como float. En la entrada se rechazan negativos y más de dos
decimales: no se redondea plata en silencio.
"""

from decimal import Decimal

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)

from app.models.asiento import EstadoAsiento

LIMITE_IMPORTE = Decimal("999999999999.99")
CENTAVO = Decimal("0.01")


class Monto(fields.Decimal):
    """Decimal con dos decimales exactos, rechazando negativos y excesos."""

    def _deserialize(self, value, attr, data, **kwargs):
        monto = super()._deserialize(value, attr, data, **kwargs)

        if monto < 0:
            raise ValidationError("El importe no puede ser negativo.")
        if monto != monto.quantize(CENTAVO):
            raise ValidationError("El importe admite como máximo dos decimales.")
        if monto > LIMITE_IMPORTE:
            raise ValidationError("El importe supera el máximo permitido (14 dígitos).")

        return monto.quantize(CENTAVO)


class RenglonSchema(Schema):
    cuenta_id = fields.Int(required=True)
    debe = Monto(as_string=True, load_default=Decimal("0.00"))
    haber = Monto(as_string=True, load_default=Decimal("0.00"))

    @validates_schema
    def un_solo_lado(self, datos, **kwargs):
        debe = datos.get("debe") or Decimal("0.00")
        haber = datos.get("haber") or Decimal("0.00")

        if debe == 0 and haber == 0:
            raise ValidationError(
                "Cada renglón necesita un importe en el debe o en el haber.",
                field_name="debe",
            )
        if debe > 0 and haber > 0:
            raise ValidationError(
                "Un renglón no puede tener debe y haber a la vez.",
                field_name="debe",
            )


class AsientoCreateSchema(Schema):
    fecha = fields.Date(required=True)
    concepto = fields.Str(required=True, validate=validate.Length(min=3, max=200))
    renglones = fields.List(
        fields.Nested(RenglonSchema),
        required=True,
        validate=validate.Length(min=2, error="Un asiento necesita al menos dos renglones."),
    )

    @pre_load
    def normalizar(self, datos, **kwargs):
        if isinstance(datos, dict) and isinstance(datos.get("concepto"), str):
            datos["concepto"] = datos["concepto"].strip()
        return datos


class AsientoUpdateSchema(AsientoCreateSchema):
    pass


class AnulacionSchema(Schema):
    motivo = fields.Str(required=True, validate=validate.Length(min=5, max=300))


class RenglonOutSchema(Schema):
    id = fields.Int()
    cuenta_id = fields.Int()
    cuenta_codigo = fields.Str(attribute="cuenta.codigo")
    cuenta_nombre = fields.Str(attribute="cuenta.nombre")
    debe = Monto(as_string=True)
    haber = Monto(as_string=True)


class AsientoSchema(Schema):
    id = fields.Int()
    cliente_id = fields.Int()
    numero = fields.Int()
    fecha = fields.Date(format="iso")
    concepto = fields.Str()
    estado = fields.Str()
    estado_etiqueta = fields.Str()
    renglones = fields.List(fields.Nested(RenglonOutSchema))
    creado_por = fields.Str(attribute="creado_por.nombre", allow_none=True)
    creado_en = fields.DateTime(format="iso")
    anulado_por = fields.Str(attribute="anulado_por.nombre", allow_none=True)
    motivo_anulacion = fields.Str(allow_none=True)
    anulado_en = fields.DateTime(format="iso", allow_none=True)


class AsientoListadoSchema(Schema):
    """Versión liviana para la tabla del libro diario (sin renglones)."""

    id = fields.Int()
    cliente_id = fields.Int()
    numero = fields.Int()
    fecha = fields.Date(format="iso")
    concepto = fields.Str()
    estado = fields.Str()
    estado_etiqueta = fields.Str()
    debe = Monto(as_string=True)
    haber = Monto(as_string=True)
    creado_en = fields.DateTime(format="iso")


ESTADOS_ASIENTO = EstadoAsiento.valores()

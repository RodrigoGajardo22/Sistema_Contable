"""Schemas de comprobantes.

No se aceptan `iva` ni `total` en la entrada: los calcula el backend a partir
del neto y la alícuota. Tampoco `estado` ni `asiento_id`.
"""

from marshmallow import Schema, fields, validate

from app.models.comprobante import TipoComprobante
from app.schemas.asiento import Monto

TIPOS_COMPROBANTE = TipoComprobante.valores()


class ComprobanteCreateSchema(Schema):
    tipo = fields.Str(required=True, validate=validate.OneOf(TIPOS_COMPROBANTE))
    numero = fields.Str(required=True, validate=validate.Length(min=1, max=40))
    fecha = fields.Date(required=True)
    tercero = fields.Str(required=True, validate=validate.Length(min=2, max=160))
    neto = Monto(required=True, as_string=True)
    alicuota_iva = Monto(required=True, as_string=True)


class ComprobanteSchema(Schema):
    id = fields.Int()
    cliente_id = fields.Int()
    tipo = fields.Str()
    tipo_etiqueta = fields.Str()
    numero = fields.Str()
    fecha = fields.Date(format="iso")
    tercero = fields.Str()
    neto = Monto(as_string=True)
    alicuota_iva = Monto(as_string=True)
    iva = Monto(as_string=True)
    total = Monto(as_string=True)
    estado = fields.Str()
    estado_etiqueta = fields.Str()
    asiento_id = fields.Int(allow_none=True)
    asiento_numero = fields.Int(attribute="asiento.numero", allow_none=True)
    motivo_anulacion = fields.Str(allow_none=True)
    creado_por = fields.Str(attribute="creado_por.nombre", allow_none=True)
    creado_en = fields.DateTime(format="iso")

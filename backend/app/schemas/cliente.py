"""Schemas de clientes."""

from marshmallow import Schema, fields, pre_load, validate

from app.models.cliente import CondicionIva

CONDICIONES_IVA = CondicionIva.valores()


class _LimpiarVacios(Schema):
    """Un string vacío del formulario equivale a "sin dato"."""

    @pre_load
    def limpiar_vacios(self, datos, **kwargs):
        if not isinstance(datos, dict):
            return datos
        return {clave: (None if valor == "" else valor) for clave, valor in datos.items()}


class ClienteCreateSchema(_LimpiarVacios):
    razon_social = fields.Str(required=True, validate=validate.Length(min=2, max=160))
    cuit = fields.Str(required=True, validate=validate.Length(min=11, max=14))
    condicion_iva = fields.Str(required=True, validate=validate.OneOf(CONDICIONES_IVA))
    # El email es la credencial del portal: sin email no hay usuario cliente.
    email = fields.Email(
        required=True,
        allow_none=False,
        validate=validate.Length(max=180),
    )
    telefono = fields.Str(allow_none=True, load_default=None, validate=validate.Length(max=40))
    direccion = fields.Str(allow_none=True, load_default=None, validate=validate.Length(max=200))
    contador_id = fields.Int(allow_none=True, load_default=None)


class ClienteUpdateSchema(_LimpiarVacios):
    razon_social = fields.Str(validate=validate.Length(min=2, max=160))
    condicion_iva = fields.Str(validate=validate.OneOf(CONDICIONES_IVA))
    email = fields.Email(allow_none=True, validate=validate.Length(max=180))
    telefono = fields.Str(allow_none=True, validate=validate.Length(max=40))
    direccion = fields.Str(allow_none=True, validate=validate.Length(max=200))
    contador_id = fields.Int(allow_none=True)


class ClienteSchema(Schema):
    """Cliente con los datos de su versión vigente."""

    id = fields.Int()
    cuit = fields.Str()
    activo = fields.Bool()
    razon_social = fields.Str()
    condicion_iva = fields.Str()
    condicion_iva_etiqueta = fields.Str()
    email = fields.Str(allow_none=True)
    telefono = fields.Str(allow_none=True)
    direccion = fields.Str(allow_none=True)
    contador_id = fields.Int(allow_none=True)
    contador_nombre = fields.Str(allow_none=True)
    contador_email = fields.Str(allow_none=True)
    usuario_id = fields.Int(allow_none=True)
    usuario_nombre = fields.Str(allow_none=True)
    usuario_email = fields.Str(allow_none=True)
    usuario_activo = fields.Bool(allow_none=True)
    # Sólo viene completo en el alta (o cuando se crea el acceso): se muestra
    # una vez y no se vuelve a serializar.
    acceso_temporal = fields.Str(allow_none=True)
    version_id = fields.Int()
    actualizado_en = fields.DateTime(format="iso")
    actualizado_por = fields.Str(allow_none=True)


class ClienteVersionSchema(Schema):
    id = fields.Int()
    razon_social = fields.Str()
    condicion_iva = fields.Str()
    condicion_iva_etiqueta = fields.Str()
    email = fields.Str(allow_none=True)
    telefono = fields.Str(allow_none=True)
    direccion = fields.Str(allow_none=True)
    contador_id = fields.Int(allow_none=True)
    contador_nombre = fields.Str(allow_none=True)
    creado_en = fields.DateTime(format="iso")
    creado_por = fields.Str(attribute="creado_por_nombre", allow_none=True)

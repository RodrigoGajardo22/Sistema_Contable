"""Tests de comprobantes: cálculo de IVA, contabilización y anulación."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.asiento import Asiento
from app.models.comprobante import Comprobante
from tests.helpers import autorizacion

HOY = date.today().isoformat()
MANANA = (date.today() + timedelta(days=1)).isoformat()
CUIT = "20123456786"


def _cliente(client, **extra):
    datos = {
        "razon_social": "Panadería La Espiga SRL",
        "cuit": CUIT,
        "condicion_iva": "responsable_inscripto",
    }
    datos.update(extra)
    datos.setdefault("email", f"contacto-{datos['cuit'].replace('-', '')}@test.com")
    return client.post(
        "/api/clientes", json=datos, headers=autorizacion(client)
    ).get_json()["datos"]


def _comprobante(client, cliente_id, **extra):
    datos = {
        "tipo": "venta",
        "numero": "A-0001-00000001",
        "fecha": HOY,
        "tercero": "Cliente Final SA",
        "neto": "100000.00",
        "alicuota_iva": "21.00",
    }
    datos.update(extra)
    return client.post(
        f"/api/clientes/{cliente_id}/comprobantes",
        json=datos,
        headers=autorizacion(client),
    )


# --------------------------------------------------------------------------
# Alta y cálculo
# --------------------------------------------------------------------------
def test_crear_comprobante_calcula_iva_y_total(client, admin):
    cliente = _cliente(client)

    respuesta = _comprobante(client, cliente["id"])

    assert respuesta.status_code == 201
    datos = respuesta.get_json()["datos"]
    assert Decimal(datos["neto"]) == Decimal("100000.00")
    assert Decimal(datos["iva"]) == Decimal("21000.00")
    assert Decimal(datos["total"]) == Decimal("121000.00")
    assert datos["estado"] == "pendiente"


def test_no_se_puede_inyectar_el_total(client, admin):
    cliente = _cliente(client)

    respuesta = _comprobante(client, cliente["id"], total="1.00", iva="0.00")

    # Marshmallow rechaza campos desconocidos: no hay mass assignment.
    assert respuesta.status_code == 422


def test_alicuota_invalida(client, admin):
    cliente = _cliente(client)

    respuesta = _comprobante(client, cliente["id"], alicuota_iva="15.00")

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "alicuota_invalida"


def test_alicuota_cero_genera_dos_renglones(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"], alicuota_iva="0.00").get_json()[
        "datos"
    ]

    respuesta = client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )
    assert respuesta.status_code == 200

    asiento = db.session.get(Asiento, comprobante and respuesta.get_json()["datos"]["asiento_id"])
    assert len(asiento.renglones) == 2


def test_numero_duplicado_por_tipo(client, admin):
    cliente = _cliente(client)
    _comprobante(client, cliente["id"])

    duplicado = _comprobante(client, cliente["id"])

    assert duplicado.status_code == 409
    assert duplicado.get_json()["error"]["codigo"] == "numero_duplicado"


def test_mismo_numero_en_otro_tipo_es_valido(client, admin):
    cliente = _cliente(client)
    _comprobante(client, cliente["id"])

    compra = _comprobante(client, cliente["id"], tipo="compra", tercero="Proveedor SA")

    assert compra.status_code == 201


def test_fecha_futura(client, admin):
    cliente = _cliente(client)

    respuesta = _comprobante(client, cliente["id"], fecha=MANANA)

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "fecha_invalida"


# --------------------------------------------------------------------------
# Contabilización
# --------------------------------------------------------------------------
def test_contabilizar_venta_genera_asiento_balanceado(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]

    respuesta = client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()["datos"]
    assert datos["estado"] == "contabilizado"
    assert datos["asiento_id"]

    asiento = db.session.get(Asiento, datos["asiento_id"])
    assert asiento.estado == "confirmado"
    assert asiento.concepto.startswith("Comprobante venta")
    debe = sum(Decimal(r.debe) for r in asiento.renglones)
    haber = sum(Decimal(r.haber) for r in asiento.renglones)
    assert debe == haber == Decimal("121000.00")
    assert len(asiento.renglones) == 3


def test_contabilizar_compra_usa_iva_credito(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(
        client, cliente["id"], tipo="compra", tercero="Proveedor SA"
    ).get_json()["datos"]

    respuesta = client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )
    asiento = db.session.get(Asiento, respuesta.get_json()["datos"]["asiento_id"])

    codigos = {renglon.cuenta.codigo for renglon in asiento.renglones}
    assert codigos == {"5.1.01", "1.3.01", "2.1.01"}


def test_contabilizar_dos_veces(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]

    client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )
    respuesta = client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "ya_contabilizado"


def test_contabilizado_no_se_edita(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]
    client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )

    respuesta = client.put(
        f"/api/comprobantes/{comprobante['id']}",
        json={
            "tipo": "venta",
            "numero": comprobante["numero"],
            "fecha": HOY,
            "tercero": "Otro",
            "neto": "50.00",
            "alicuota_iva": "21.00",
        },
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "comprobante_no_editable"


# --------------------------------------------------------------------------
# Anulación
# --------------------------------------------------------------------------
def test_anular_contabilizado_anula_el_asiento(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]
    contabilizado = client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    ).get_json()["datos"]

    respuesta = client.delete(
        f"/api/comprobantes/{comprobante['id']}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["estado"] == "anulado"

    asiento = db.session.get(Asiento, contabilizado["asiento_id"])
    assert asiento.estado == "anulado"
    assert asiento.motivo_anulacion


def test_no_se_anula_dos_veces(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]
    client.delete(f"/api/comprobantes/{comprobante['id']}", headers=autorizacion(client))

    respuesta = client.delete(
        f"/api/comprobantes/{comprobante['id']}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 409


# --------------------------------------------------------------------------
# Aislamiento y edición
# --------------------------------------------------------------------------
def test_editar_pendiente_recalcula(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]

    respuesta = client.put(
        f"/api/comprobantes/{comprobante['id']}",
        json={
            "tipo": "venta",
            "numero": comprobante["numero"],
            "fecha": HOY,
            "tercero": "Cliente Final SA",
            "neto": "200.00",
            "alicuota_iva": "10.50",
        },
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()["datos"]
    assert Decimal(datos["iva"]) == Decimal("21.00")
    assert Decimal(datos["total"]) == Decimal("221.00")


def test_contador_ajeno_no_ve_el_comprobante(client, admin, contador):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]

    cabecera = autorizacion(client, "contador@test.com")

    assert (
        client.get(f"/api/comprobantes/{comprobante['id']}", headers=cabecera).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/clientes/{cliente['id']}/comprobantes", headers=cabecera
        ).status_code
        == 404
    )


def test_anular_pendiente_no_genera_asiento(client, admin):
    cliente = _cliente(client)
    comprobante = _comprobante(client, cliente["id"]).get_json()["datos"]

    client.delete(f"/api/comprobantes/{comprobante['id']}", headers=autorizacion(client))

    assert db.session.scalar(select(Comprobante).where(Comprobante.id == comprobante["id"])).asiento_id is None

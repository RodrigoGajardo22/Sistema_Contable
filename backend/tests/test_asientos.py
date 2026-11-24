"""Tests de asientos: partida doble, estados y aislamiento."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.asiento import Asiento
from app.models.cuenta import Cuenta
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


def _cuentas(cliente_id: int) -> dict[str, Cuenta]:
    return {
        cuenta.codigo: cuenta
        for cuenta in db.session.scalars(
            select(Cuenta).where(Cuenta.cliente_id == cliente_id)
        )
    }


def _renglones(cliente_id: int, debe: str = "1000.00", haber: str = "1000.00"):
    cuentas = _cuentas(cliente_id)
    return [
        {"cuenta_id": cuentas["1.1.01"].id, "debe": debe, "haber": "0.00"},
        {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": haber},
    ]


def _crear(client, cliente_id, renglones=None, **extra):
    datos = {
        "fecha": HOY,
        "concepto": "Venta de mercadería",
        "renglones": renglones if renglones is not None else _renglones(cliente_id),
    }
    datos.update(extra)
    return client.post(
        f"/api/clientes/{cliente_id}/asientos",
        json=datos,
        headers=autorizacion(client),
    )


# --------------------------------------------------------------------------
# Partida doble
# --------------------------------------------------------------------------
def test_crear_asiento_balanceado(client, admin):
    cliente = _cliente(client)

    respuesta = _crear(client, cliente["id"])

    assert respuesta.status_code == 201
    datos = respuesta.get_json()["datos"]
    assert datos["estado"] == "borrador"
    assert datos["numero"] == 1
    assert len(datos["renglones"]) == 2
    assert datos["renglones"][0]["debe"] == "1000.00"
    assert datos["renglones"][1]["haber"] == "1000.00"


def test_asiento_desbalanceado(client, admin):
    cliente = _cliente(client)
    renglones = _renglones(cliente["id"], debe="1000.00", haber="900.00")

    respuesta = _crear(client, cliente["id"], renglones)

    assert respuesta.status_code == 422
    error = respuesta.get_json()["error"]
    assert error["codigo"] == "asiento_desbalanceado"
    assert error["detalles"]["diferencia"] == "100.00"


def test_minimo_dos_renglones(client, admin):
    cliente = _cliente(client)
    cuentas = _cuentas(cliente["id"])

    respuesta = _crear(
        client,
        cliente["id"],
        [{"cuenta_id": cuentas["1.1.01"].id, "debe": "100.00", "haber": "0.00"}],
    )

    assert respuesta.status_code == 422


def test_renglon_con_debe_y_haber(client, admin):
    cliente = _cliente(client)
    cuentas = _cuentas(cliente["id"])

    respuesta = _crear(
        client,
        cliente["id"],
        [
            {"cuenta_id": cuentas["1.1.01"].id, "debe": "100.00", "haber": "100.00"},
            {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": "0.00"},
        ],
    )

    assert respuesta.status_code == 422


def test_importe_con_tres_decimales(client, admin):
    cliente = _cliente(client)
    renglones = _renglones(cliente["id"], debe="1000.123", haber="1000.12")

    respuesta = _crear(client, cliente["id"], renglones)

    assert respuesta.status_code == 422


def test_cuenta_agrupadora_no_recibe_movimientos(client, admin):
    cliente = _cliente(client)
    cuentas = _cuentas(cliente["id"])

    renglones = [
        {"cuenta_id": cuentas["1"].id, "debe": "100.00", "haber": "0.00"},
        {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": "100.00"},
    ]

    respuesta = _crear(client, cliente["id"], renglones)

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "cuenta_no_imputable"


def test_cuenta_de_otro_cliente_es_rechazada(client, admin):
    cliente = _cliente(client)
    otro = _cliente(client, cuit="30712345671", razon_social="Otra SA")
    cuentas_otro = _cuentas(otro["id"])

    renglones = [
        {"cuenta_id": cuentas_otro["1.1.01"].id, "debe": "100.00", "haber": "0.00"},
        {"cuenta_id": cuentas_otro["4.1.01"].id, "debe": "0.00", "haber": "100.00"},
    ]

    respuesta = _crear(client, cliente["id"], renglones)

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "cuenta_invalida"


def test_fecha_futura_rechazada(client, admin):
    cliente = _cliente(client)

    respuesta = _crear(client, cliente["id"], fecha=MANANA)

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "fecha_invalida"


# --------------------------------------------------------------------------
# Estados
# --------------------------------------------------------------------------
def test_confirmar_congela_el_asiento(client, admin):
    cliente = _cliente(client)
    asiento = _crear(client, cliente["id"]).get_json()["datos"]

    confirmado = client.post(
        f"/api/asientos/{asiento['id']}/confirmar", headers=autorizacion(client)
    )
    assert confirmado.status_code == 200
    assert confirmado.get_json()["datos"]["estado"] == "confirmado"

    editar = client.put(
        f"/api/asientos/{asiento['id']}",
        json={
            "fecha": HOY,
            "concepto": "Otro concepto",
            "renglones": _renglones(cliente["id"]),
        },
        headers=autorizacion(client),
    )
    assert editar.status_code == 409
    assert editar.get_json()["error"]["codigo"] == "asiento_no_editable"

    descartar = client.delete(
        f"/api/asientos/{asiento['id']}", headers=autorizacion(client)
    )
    assert descartar.status_code == 409


def test_anular_confirmado_con_motivo(client, admin):
    cliente = _cliente(client)
    asiento = _crear(client, cliente["id"]).get_json()["datos"]
    client.post(f"/api/asientos/{asiento['id']}/confirmar", headers=autorizacion(client))

    respuesta = client.post(
        f"/api/asientos/{asiento['id']}/anular",
        json={"motivo": "Error de imputación"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()["datos"]
    assert datos["estado"] == "anulado"
    assert datos["motivo_anulacion"] == "Error de imputación"
    assert datos["anulado_por"] == "Admin"

    repetida = client.post(
        f"/api/asientos/{asiento['id']}/anular",
        json={"motivo": "Otra vez"},
        headers=autorizacion(client),
    )
    assert repetida.status_code == 409
    assert repetida.get_json()["error"]["codigo"] == "ya_anulado"


def test_motivo_de_anulacion_corto(client, admin):
    cliente = _cliente(client)
    asiento = _crear(client, cliente["id"]).get_json()["datos"]

    respuesta = client.post(
        f"/api/asientos/{asiento['id']}/anular",
        json={"motivo": "x"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 422


def test_editar_borrador_reemplaza_renglones(client, admin):
    cliente = _cliente(client)
    asiento = _crear(client, cliente["id"]).get_json()["datos"]
    cuentas = _cuentas(cliente["id"])

    nuevos = [
        {"cuenta_id": cuentas["1.1.02"].id, "debe": "2500.50", "haber": "0.00"},
        {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": "2500.50"},
    ]

    respuesta = client.put(
        f"/api/asientos/{asiento['id']}",
        json={"fecha": HOY, "concepto": "Venta por transferencia", "renglones": nuevos},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()["datos"]
    assert len(datos["renglones"]) == 2
    assert datos["renglones"][0]["debe"] == "2500.50"
    assert datos["renglones"][1]["haber"] == "2500.50"


def test_descartar_borrador(client, admin):
    cliente = _cliente(client)
    asiento = _crear(client, cliente["id"]).get_json()["datos"]

    respuesta = client.delete(
        f"/api/asientos/{asiento['id']}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    assert db.session.get(Asiento, asiento["id"]) is None


# --------------------------------------------------------------------------
# Numeración, filtros y aislamiento
# --------------------------------------------------------------------------
def test_numeracion_por_cliente(client, admin):
    cliente_a = _cliente(client)
    cliente_b = _cliente(client, cuit="30712345671", razon_social="Otra SA")

    a1 = _crear(client, cliente_a["id"]).get_json()["datos"]
    a2 = _crear(client, cliente_a["id"]).get_json()["datos"]
    b1 = _crear(client, cliente_b["id"]).get_json()["datos"]

    assert a1["numero"] == 1
    assert a2["numero"] == 2
    assert b1["numero"] == 1


def test_listado_filtra_por_estado_y_cuenta(client, admin):
    cliente = _cliente(client)
    asiento = _crear(client, cliente["id"]).get_json()["datos"]
    client.post(f"/api/asientos/{asiento['id']}/confirmar", headers=autorizacion(client))
    _crear(client, cliente["id"])

    confirmados = client.get(
        f"/api/clientes/{cliente['id']}/asientos?estado=confirmado",
        headers=autorizacion(client),
    ).get_json()
    assert confirmados["meta"]["total"] == 1

    cuenta = _cuentas(cliente["id"])["1.1.01"]
    por_cuenta = client.get(
        f"/api/clientes/{cliente['id']}/asientos?cuenta={cuenta.id}",
        headers=autorizacion(client),
    ).get_json()
    assert por_cuenta["meta"]["total"] == 2


def test_listado_pagina(client, admin):
    cliente = _cliente(client)
    for _ in range(3):
        _crear(client, cliente["id"])

    respuesta = client.get(
        f"/api/clientes/{cliente['id']}/asientos?por_pagina=2",
        headers=autorizacion(client),
    ).get_json()

    assert len(respuesta["datos"]) == 2
    assert respuesta["meta"]["total"] == 3


def test_contador_no_accede_a_asientos_ajenos(client, admin, contador):
    cliente = _cliente(client)
    asiento = _crear(client, cliente["id"]).get_json()["datos"]

    cabecera = autorizacion(client, "contador@test.com")

    assert (
        client.get(f"/api/asientos/{asiento['id']}", headers=cabecera).status_code == 404
    )
    assert (
        client.get(
            f"/api/clientes/{cliente['id']}/asientos", headers=cabecera
        ).status_code
        == 404
    )


def test_cliente_inactivo_no_admite_asientos(client, admin):
    cliente = _cliente(client)
    client.delete(f"/api/clientes/{cliente['id']}", headers=autorizacion(client))

    respuesta = _crear(client, cliente["id"])

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "cliente_inactivo"


def test_importe_negativo(client, admin):
    cliente = _cliente(client)
    renglones = _renglones(cliente["id"], debe="-100.00", haber="-100.00")

    respuesta = _crear(client, cliente["id"], renglones)

    assert respuesta.status_code == 422


def test_totales_coinciden_con_los_renglones(client, admin):
    cliente = _cliente(client)
    renglones = _renglones(cliente["id"], debe="10500.75", haber="10500.75")
    _crear(client, cliente["id"], renglones)

    listado = client.get(
        f"/api/clientes/{cliente['id']}/asientos", headers=autorizacion(client)
    ).get_json()["datos"][0]

    assert Decimal(listado["debe"]) == Decimal("10500.75")
    assert Decimal(listado["haber"]) == Decimal("10500.75")

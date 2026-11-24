"""Tests de las reglas de integridad y funciones de la fase 6."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.cuenta import Cuenta
from tests.helpers import autorizacion

HOY = date.today().isoformat()
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
        c.codigo: c
        for c in db.session.scalars(
            select(Cuenta).where(Cuenta.cliente_id == cliente_id)
        )
    }


def _asiento(client, cliente_id, importe="1000.00"):
    cuentas = _cuentas(cliente_id)
    asiento = client.post(
        f"/api/clientes/{cliente_id}/asientos",
        json={
            "fecha": HOY,
            "concepto": "Venta",
            "renglones": [
                {"cuenta_id": cuentas["1.1.01"].id, "debe": importe, "haber": "0.00"},
                {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": importe},
            ],
        },
        headers=autorizacion(client),
    ).get_json()["datos"]
    client.post(f"/api/asientos/{asiento['id']}/confirmar", headers=autorizacion(client))
    return asiento


# --------------------------------------------------------------------------
# Integridad
# --------------------------------------------------------------------------
def test_no_se_da_de_baja_un_cliente_con_asientos(client, admin):
    cliente = _cliente(client)
    _asiento(client, cliente["id"])

    respuesta = client.delete(
        f"/api/clientes/{cliente['id']}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "cliente_con_movimientos"


def test_no_se_elimina_una_cuenta_con_movimientos(client, admin):
    cliente = _cliente(client)
    _asiento(client, cliente["id"])
    cuenta = _cuentas(cliente["id"])["1.1.01"]

    respuesta = client.delete(
        f"/api/cuentas/{cuenta.id}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "cuenta_con_movimientos"


def test_auditoria_guarda_el_estado_anterior(client, admin):
    cliente = _cliente(client)
    _asiento(client, cliente["id"])

    entradas = client.get("/api/auditoria", headers=autorizacion(client)).get_json()[
        "datos"
    ]
    confirmacion = next(
        e for e in entradas if e["entidad"] == "asiento" and e["accion"] == "confirmar"
    )
    assert confirmacion["antes"]["estado"] == "borrador"


# --------------------------------------------------------------------------
# Conciliación: comprobante y asiento desde movimiento
# --------------------------------------------------------------------------
def _extracto(client, cliente_id, csv, final="1000.00"):
    return client.post(
        f"/api/clientes/{cliente_id}/extractos",
        json={
            "banco": "Galicia",
            "periodo": "2026-11",
            "saldo_inicial": "0.00",
            "saldo_final": final,
            "csv": csv,
        },
        headers=autorizacion(client),
    ).get_json()["datos"]


def test_vincular_movimiento_a_comprobante(client, admin):
    cliente = _cliente(client)
    comprobante = client.post(
        f"/api/clientes/{cliente['id']}/comprobantes",
        json={
            "tipo": "venta",
            "numero": "A-1",
            "fecha": HOY,
            "tercero": "Cliente SA",
            "neto": "100000.00",
            "alicuota_iva": "21.00",
        },
        headers=autorizacion(client),
    ).get_json()["datos"]
    client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )

    extracto = _extracto(
        client,
        cliente["id"],
        f"fecha;desc;importe\n{HOY};Transf;121000,00\n",
        "121000.00",
    )
    movimiento = extracto["movimientos"][0]

    respuesta = client.put(
        f"/api/movimientos/{movimiento['id']}/vincular",
        json={"comprobante_id": comprobante["id"]},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["comprobante_id"] == comprobante["id"]


def test_generar_asiento_desde_un_movimiento(client, admin):
    cliente = _cliente(client)
    extracto = _extracto(
        client,
        cliente["id"],
        f"fecha;desc;importe\n{HOY};Depósito;500,00\n",
        "500.00",
    )
    movimiento = extracto["movimientos"][0]
    cuenta = _cuentas(cliente["id"])["4.1.01"]

    respuesta = client.post(
        f"/api/movimientos/{movimiento['id']}/asiento",
        json={"cuenta_id": cuenta.id, "concepto": "Depósito de cliente"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 201
    datos = respuesta.get_json()["datos"]
    assert datos["estado"] == "conciliado"

    detalle = client.get(
        f"/api/asientos/{datos['asiento_id']}", headers=autorizacion(client)
    ).get_json()["datos"]
    assert detalle["estado"] == "confirmado"
    assert len(detalle["renglones"]) == 2
    assert Decimal(detalle["renglones"][0]["debe"]) == Decimal("500.00")


def test_no_se_genera_asiento_para_movimiento_conciliado(client, admin):
    cliente = _cliente(client)
    extracto = _extracto(
        client, cliente["id"], f"fecha;desc;importe\n{HOY};Dep;500,00\n", "500.00"
    )
    movimiento = extracto["movimientos"][0]
    cuenta = _cuentas(cliente["id"])["4.1.01"]

    client.post(
        f"/api/movimientos/{movimiento['id']}/asiento",
        json={"cuenta_id": cuenta.id},
        headers=autorizacion(client),
    )
    repetido = client.post(
        f"/api/movimientos/{movimiento['id']}/asiento",
        json={"cuenta_id": cuenta.id},
        headers=autorizacion(client),
    )

    assert repetido.status_code == 409


# --------------------------------------------------------------------------
# Dashboard y proximidad
# --------------------------------------------------------------------------
def test_dashboard_trae_listas(client, admin):
    cliente = _cliente(client)
    _asiento(client, cliente["id"])
    client.post(
        f"/api/clientes/{cliente['id']}/vencimientos",
        json={
            "obligacion": "iva",
            "periodo": "2026-11",
            "fecha_vencimiento": (date.today() + timedelta(days=5)).isoformat(),
        },
        headers=autorizacion(client),
    )

    datos = client.get("/api/dashboard", headers=autorizacion(client)).get_json()["datos"]

    assert len(datos["proximos_vencimientos"]) == 1
    assert datos["proximos_vencimientos"][0]["dias"] == 5
    assert len(datos["ultimos_asientos"]) == 1


def test_vencimientos_filtro_proximidad(client, admin):
    cliente = _cliente(client)
    ayer = (date.today() - timedelta(days=1)).isoformat()
    futuro = (date.today() + timedelta(days=10)).isoformat()

    for fecha in (ayer, futuro):
        client.post(
            f"/api/clientes/{cliente['id']}/vencimientos",
            json={"obligacion": "iva", "periodo": "2026-11", "fecha_vencimiento": fecha},
            headers=autorizacion(client),
        )

    vencidos = client.get(
        f"/api/clientes/{cliente['id']}/vencimientos?proximidad=vencidos",
        headers=autorizacion(client),
    ).get_json()
    proximos = client.get(
        f"/api/clientes/{cliente['id']}/vencimientos?proximidad=proximos",
        headers=autorizacion(client),
    ).get_json()

    assert vencidos["meta"]["total"] == 1
    assert proximos["meta"]["total"] == 1
